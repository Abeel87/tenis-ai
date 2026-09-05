from __future__ import annotations

"""Real SHADOW learning gate for Player DNA point prediction.

The scorer learns whether leakage-safe, as-of Player DNA profiles predict the
next strict point outcome (server_won) on a chronological untouched holdout.
It compares profile-only, ranking-only and combined logistic models. Nothing is
published to PROD and no runtime scoring path consumes the fitted candidates.
"""

import gzip
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "data" / "derived" / "player_dna" / "point_events.jsonl.gz"
PROFILES = ROOT / "data" / "derived" / "player_dna" / "profile_snapshots.jsonl.gz"
READINESS = ROOT / "frontend" / "data" / "player_dna_profile_readiness.json"
OUT = ROOT / "frontend" / "data" / "player_dna_point_scorer.json"

VERSION = "player-dna-point-scorer-v1"
MODE = "SHADOW_EVAL_ONLY"
EVAL_MIN_PRIOR_MATCHES = 3
TRAIN_FRACTION = 0.80

PROFILE_NUMERIC = [
    "server_overall_serve_rate",
    "receiver_overall_return_rate",
    "server_surface_serve_rate",
    "receiver_surface_return_rate",
    "server_overall_matches",
    "receiver_overall_matches",
    "server_surface_matches",
    "receiver_surface_matches",
]
RANK_NUMERIC = ["server_rank", "receiver_rank"]
CATEGORICAL = ["surface", "tour", "match_format"]

STATE_NUMERIC = [
    "is_tiebreak",
    "sets_completed_before",
    "set_diff_server_before",
    "current_set_games_total_before",
    "current_set_game_diff_server_before",
    "server_point_stage_before",
    "receiver_point_stage_before",
    "deuce_before",
    "server_advantage_before",
    "receiver_advantage_before",
    "server_game_point_before",
    "break_point_against_server_before",
    "late_set_before",
    "deciding_set_before",
    "previous_point_won_by_server",
    "server_point_streak_before",
    "receiver_point_streak_before",
    "previous_game_won_by_server",
    "previous_game_was_break",
    "previous_game_break_winner_is_server",
]


def _int_pair(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, list) or len(value) < 2:
        return None
    try:
        a, b = int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None
    return a, b


def _current_set_games(score: dict[str, Any], completed_sets: int) -> tuple[int, int] | None:
    games = score.get("games")
    if not isinstance(games, list) or len(games) < 2:
        return None
    p1, p2 = games[0], games[1]
    if not isinstance(p1, list) or not isinstance(p2, list):
        return None
    if completed_sets < 0 or completed_sets >= len(p1) or completed_sets >= len(p2):
        return None
    try:
        return int(p1[completed_sets]), int(p2[completed_sets])
    except (TypeError, ValueError):
        return None


def _point_token(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    token = str(value).strip().upper()
    if token == "AD":
        token = "A"
    return token or None


def _standard_point_stage(token: str | None) -> int | None:
    return {"0": 0, "15": 1, "30": 2, "40": 3, "A": 4}.get(token or "")


def _game_point_flags(
    server_token: str | None,
    receiver_token: str | None,
    is_tiebreak: bool,
) -> tuple[int | None, int | None, int | None, int | None, int | None]:
    if is_tiebreak:
        try:
            s = int(server_token) if server_token is not None else None
            r = int(receiver_token) if receiver_token is not None else None
        except ValueError:
            s = r = None
        if s is None or r is None:
            return None, None, None, None, None
        server_gp = int(s >= 6 and s - r >= 1)
        receiver_gp = int(r >= 6 and r - s >= 1)
        return server_gp, receiver_gp, 0, 0, 0

    if server_token is None or receiver_token is None:
        return None, None, None, None, None
    server_gp = int(
        (server_token == "40" and receiver_token in {"0", "15", "30"})
        or (server_token == "A" and receiver_token == "40")
    )
    receiver_gp = int(
        (receiver_token == "40" and server_token in {"0", "15", "30"})
        or (receiver_token == "A" and server_token == "40")
    )
    deuce = int(server_token == "40" and receiver_token == "40")
    server_adv = int(server_token == "A" and receiver_token == "40")
    receiver_adv = int(receiver_token == "A" and server_token == "40")
    return server_gp, receiver_gp, deuce, server_adv, receiver_adv


def _score_state_features(point: dict[str, Any], history: dict[str, Any]) -> dict[str, Any]:
    server_side = point.get("server")
    receiver_side = point.get("receiver")
    score = point.get("score_before")
    is_tiebreak = bool(point.get("is_tiebreak_before"))
    out = {name: None for name in STATE_NUMERIC}
    out["is_tiebreak"] = int(is_tiebreak)
    out["state_score_valid"] = False

    if server_side not in (1, 2) or receiver_side not in (1, 2) or not isinstance(score, dict):
        return out

    sets = _int_pair(score.get("sets"))
    points = score.get("points")
    if sets is None or not isinstance(points, list) or len(points) < 2:
        return out

    completed_sets = sets[0] + sets[1]
    games = _current_set_games(score, completed_sets)
    if games is None:
        return out

    server_idx = server_side - 1
    receiver_idx = receiver_side - 1
    set_pair = (sets[server_idx], sets[receiver_idx])
    game_pair = (games[server_idx], games[receiver_idx])
    server_token = _point_token(points[server_idx])
    receiver_token = _point_token(points[receiver_idx])
    if server_token is None or receiver_token is None:
        return out

    if is_tiebreak:
        try:
            server_stage = int(server_token)
            receiver_stage = int(receiver_token)
        except ValueError:
            return out
    else:
        server_stage = _standard_point_stage(server_token)
        receiver_stage = _standard_point_stage(receiver_token)
        if server_stage is None or receiver_stage is None:
            return out

    server_gp, receiver_gp, deuce, server_adv, receiver_adv = _game_point_flags(
        server_token,
        receiver_token,
        is_tiebreak,
    )
    if server_gp is None or receiver_gp is None:
        return out

    match_format = str(point.get("match_format") or "").upper()
    needed = 3 if match_format == "BO5" else 2
    deciding_set = int(set_pair[0] == needed - 1 and set_pair[1] == needed - 1)

    last_winner = history.get("last_winner")
    streak_winner = history.get("streak_winner")
    streak_length = int(history.get("streak_length") or 0)
    last_game_winner = history.get("last_game_winner")
    last_game_server = history.get("last_game_server")
    previous_game_was_break = (
        int(last_game_winner != last_game_server)
        if last_game_winner in (1, 2) and last_game_server in (1, 2)
        else None
    )

    out.update({
        "sets_completed_before": completed_sets,
        "set_diff_server_before": set_pair[0] - set_pair[1],
        "current_set_games_total_before": game_pair[0] + game_pair[1],
        "current_set_game_diff_server_before": game_pair[0] - game_pair[1],
        "server_point_stage_before": server_stage,
        "receiver_point_stage_before": receiver_stage,
        "deuce_before": deuce,
        "server_advantage_before": server_adv,
        "receiver_advantage_before": receiver_adv,
        "server_game_point_before": server_gp,
        "break_point_against_server_before": receiver_gp if not is_tiebreak else 0,
        "late_set_before": int(game_pair[0] + game_pair[1] >= 8),
        "deciding_set_before": deciding_set,
        "previous_point_won_by_server": (
            int(last_winner == server_side) if last_winner in (1, 2) else None
        ),
        "server_point_streak_before": streak_length if streak_winner == server_side else 0,
        "receiver_point_streak_before": streak_length if streak_winner == receiver_side else 0,
        "previous_game_won_by_server": (
            int(last_game_winner == server_side) if last_game_winner in (1, 2) else None
        ),
        "previous_game_was_break": previous_game_was_break,
        "previous_game_break_winner_is_server": (
            int(previous_game_was_break == 1 and last_game_winner == server_side)
            if previous_game_was_break is not None
            else None
        ),
        "state_score_valid": True,
    })
    return out


def _state_feature_lookup(point_rows: list[dict[str, Any]]) -> tuple[dict[tuple[str, int], dict[str, Any]], dict[str, int]]:
    ordered = sorted(
        [row for row in point_rows if isinstance(row, dict)],
        key=lambda row: (
            str(row.get("match_id") or ""),
            int(row.get("event_index") if isinstance(row.get("event_index"), int) else -1),
        ),
    )
    lookup: dict[tuple[str, int], dict[str, Any]] = {}
    histories: dict[str, dict[str, Any]] = {}
    counts = Counter()

    for point in ordered:
        match_id = str(point.get("match_id") or "").strip()
        event_index = point.get("event_index")
        if not match_id or isinstance(event_index, bool) or not isinstance(event_index, int):
            counts["missing_event_identity"] += 1
            continue

        history = histories.setdefault(match_id, {})
        last_index = history.get("last_event_index")
        last_trainable = history.get("last_event_trainable") is True
        contiguous = isinstance(last_index, int) and event_index == last_index + 1 and last_trainable
        if not contiguous:
            for name in (
                "last_winner",
                "streak_winner",
                "streak_length",
                "last_game_winner",
                "last_game_server",
            ):
                history.pop(name, None)

        features = _score_state_features(point, history)
        lookup[(match_id, event_index)] = features
        counts["state_rows"] += 1
        counts["state_score_valid"] += int(features.get("state_score_valid") is True)

        trainable = point.get("trainable_point") is True
        winner = point.get("point_winner")
        server = point.get("server")
        if trainable and winner in (1, 2) and server in (1, 2):
            if history.get("streak_winner") == winner:
                history["streak_length"] = int(history.get("streak_length") or 0) + 1
            else:
                history["streak_winner"] = winner
                history["streak_length"] = 1
            history["last_winner"] = winner
            if point.get("transition_kind") == "game_score_changed":
                history["last_game_winner"] = winner
                history["last_game_server"] = server
        else:
            for name in (
                "last_winner",
                "streak_winner",
                "streak_length",
                "last_game_winner",
                "last_game_server",
            ):
                history.pop(name, None)

        history["last_event_index"] = event_index
        history["last_event_trainable"] = trainable

    return lookup, dict(counts)


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _iter_jsonl_gz(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def _profile_index(rows: Iterable[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        match_id = str(row.get("target_match_id") or "").strip()
        player_id = row.get("player_id")
        if not match_id or isinstance(player_id, bool) or not isinstance(player_id, int):
            continue
        if row.get("strict_as_of") is not True:
            continue
        if row.get("same_time_matches_count_as_prior") is not False:
            continue
        out[(match_id, player_id)] = row
    return out


def build_feature_rows(
    point_rows: Iterable[dict[str, Any]],
    profile_rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    profiles = _profile_index(profile_rows)
    point_rows = [point for point in point_rows if isinstance(point, dict)]
    state_lookup, state_counts = _state_feature_lookup(point_rows)
    rows: list[dict[str, Any]] = []
    counts = Counter()

    for point in point_rows:
        counts["point_rows_seen"] += 1
        if point.get("context_ready_player_point") is not True:
            counts["non_strict_rows_skipped"] += 1
            continue
        if not isinstance(point.get("server_won"), bool):
            counts["missing_label"] += 1
            continue

        match_id = str(point.get("match_id") or "").strip()
        server_id = point.get("server_player_id")
        receiver_id = point.get("receiver_player_id")
        scheduled = _parse_utc(point.get("match_scheduled_time"))
        if (
            not match_id or scheduled is None
            or isinstance(server_id, bool) or not isinstance(server_id, int)
            or isinstance(receiver_id, bool) or not isinstance(receiver_id, int)
            or server_id == receiver_id
        ):
            counts["invalid_identity_or_time"] += 1
            continue

        server = profiles.get((match_id, server_id))
        receiver = profiles.get((match_id, receiver_id))
        if server is None or receiver is None:
            counts["missing_profile_snapshot"] += 1
            continue

        server_time = _parse_utc(server.get("target_scheduled_time"))
        receiver_time = _parse_utc(receiver.get("target_scheduled_time"))
        if server_time != scheduled or receiver_time != scheduled:
            counts["profile_time_mismatch"] += 1
            continue

        so = server.get("overall_prior") if isinstance(server.get("overall_prior"), dict) else {}
        ro = receiver.get("overall_prior") if isinstance(receiver.get("overall_prior"), dict) else {}
        ss = server.get("same_surface_prior") if isinstance(server.get("same_surface_prior"), dict) else {}
        rs = receiver.get("same_surface_prior") if isinstance(receiver.get("same_surface_prior"), dict) else {}

        event_index = point.get("event_index")
        state = (
            state_lookup.get((match_id, event_index), {})
            if isinstance(event_index, int) and not isinstance(event_index, bool)
            else {}
        )
        rows.append({
            "match_id": match_id,
            "scheduled_time": scheduled,
            "event_index": event_index,
            "surface": str(point.get("surface") or "unknown"),
            "tour": str(point.get("tour") or "unknown"),
            "match_format": str(point.get("match_format") or "unknown"),
            "is_tiebreak": bool(point.get("is_tiebreak_before")),
            "server_won": int(point["server_won"]),
            "server_rank": point.get("server_ranking"),
            "receiver_rank": point.get("receiver_ranking"),
            "server_overall_serve_rate": so.get("serve_win_rate"),
            "receiver_overall_return_rate": ro.get("return_win_rate"),
            "server_surface_serve_rate": ss.get("serve_win_rate"),
            "receiver_surface_return_rate": rs.get("return_win_rate"),
            "server_overall_matches": int(so.get("matches") or 0),
            "receiver_overall_matches": int(ro.get("matches") or 0),
            "server_surface_matches": int(ss.get("matches") or 0),
            "receiver_surface_matches": int(rs.get("matches") or 0),
            **{name: state.get(name) for name in STATE_NUMERIC},
            "state_score_valid": state.get("state_score_valid") is True,
        })
        counts["joined_rows"] += 1
        counts["joined_rows_with_valid_score_state"] += int(state.get("state_score_valid") is True)

    counts["profile_snapshots"] = len(profiles)
    for key, value in state_counts.items():
        counts[f"state_{key}"] = int(value)
    return rows, dict(counts)


def split_chronological_by_match(
    rows: list[dict[str, Any]],
    train_fraction: float = TRAIN_FRACTION,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not rows:
        return [], [], {"cutoff_time": None, "train_matches": 0, "holdout_matches": 0}

    match_times: dict[str, datetime] = {}
    for row in rows:
        match_id = str(row["match_id"])
        scheduled = row["scheduled_time"]
        previous = match_times.get(match_id)
        if previous is not None and previous != scheduled:
            raise ValueError(f"conflicting scheduled_time for match {match_id}")
        match_times[match_id] = scheduled

    ordered = sorted(match_times.items(), key=lambda item: (item[1], item[0]))
    if len(ordered) < 2:
        return rows, [], {
            "cutoff_time": None,
            "train_matches": len(ordered),
            "holdout_matches": 0,
            "same_timestamp_split": False,
        }

    desired = max(1, min(len(ordered) - 1, int(len(ordered) * train_fraction)))
    cutoff_time = ordered[desired][1]

    train_ids = {match_id for match_id, ts in ordered if ts < cutoff_time}
    holdout_ids = {match_id for match_id, ts in ordered if ts >= cutoff_time}

    train = [row for row in rows if row["match_id"] in train_ids]
    holdout = [row for row in rows if row["match_id"] in holdout_ids]

    train_times = {match_times[mid] for mid in train_ids}
    holdout_times = {match_times[mid] for mid in holdout_ids}
    same_timestamp_split = bool(train_times & holdout_times)

    return train, holdout, {
        "cutoff_time": cutoff_time.isoformat(),
        "train_matches": len(train_ids),
        "holdout_matches": len(holdout_ids),
        "same_timestamp_split": same_timestamp_split,
        "policy": "all matches before cutoff train; cutoff timestamp and later holdout",
    }


def _cohort(rows: list[dict[str, Any]], min_prior_matches: int) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if int(row.get("server_overall_matches") or 0) >= min_prior_matches
        and int(row.get("receiver_overall_matches") or 0) >= min_prior_matches
    ]


def _frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _fit_schema(train: pd.DataFrame, numeric: list[str]) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "numeric": list(numeric),
        "medians": {},
        "means": {},
        "stds": {},
        "categorical_levels": {},
    }
    for name in numeric:
        series = pd.to_numeric(train[name], errors="coerce")
        median = float(series.median()) if bool(series.notna().any()) else 0.0
        values = series.fillna(median).to_numpy(dtype=float)
        mean = float(values.mean()) if len(values) else 0.0
        std = float(values.std()) if len(values) else 1.0
        if not math.isfinite(std) or std < 1e-12:
            std = 1.0
        schema["medians"][name] = median
        schema["means"][name] = mean
        schema["stds"][name] = std

    for name in CATEGORICAL:
        values = train[name].fillna("__MISSING__").astype(str)
        schema["categorical_levels"][name] = sorted(set(values.tolist()))
    return schema


def _design(frame: pd.DataFrame, schema: dict[str, Any]) -> tuple[np.ndarray, list[str]]:
    columns: list[np.ndarray] = [np.ones(len(frame), dtype=float)]
    names = ["intercept"]

    for name in schema["numeric"]:
        series = pd.to_numeric(frame[name], errors="coerce")
        values = series.fillna(float(schema["medians"][name])).to_numpy(dtype=float)
        values = (values - float(schema["means"][name])) / float(schema["stds"][name])
        columns.append(values)
        names.append(name)

    for name in CATEGORICAL:
        values = frame[name].fillna("__MISSING__").astype(str).to_numpy()
        for level in schema["categorical_levels"][name]:
            columns.append((values == level).astype(float))
            names.append(f"{name}={level}")

    return np.column_stack(columns), names


def _sigmoid(values: np.ndarray) -> np.ndarray:
    z = np.clip(np.asarray(values, dtype=float), -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-z))


def _fit_logistic_newton(
    train: pd.DataFrame,
    numeric: list[str],
    *,
    l2: float = 0.01,
    max_iter: int = 40,
    tolerance: float = 1e-8,
) -> dict[str, Any]:
    schema = _fit_schema(train, numeric)
    x, feature_names = _design(train, schema)
    y = train["server_won"].astype(int).to_numpy(dtype=float)
    beta = np.zeros(x.shape[1], dtype=float)
    converged = False

    for iteration in range(1, max_iter + 1):
        p = _sigmoid(x @ beta)
        gradient = (x.T @ (p - y)) / len(y)
        gradient[1:] += l2 * beta[1:]

        weights = p * (1.0 - p)
        hessian = ((x.T * weights) @ x) / len(y)
        regularizer = np.diag(np.concatenate(([1e-9], np.full(x.shape[1] - 1, l2))))
        hessian = hessian + regularizer

        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.pinv(hessian) @ gradient

        beta -= step
        if float(np.max(np.abs(step))) < tolerance:
            converged = True
            break

    return {
        "schema": schema,
        "beta": beta,
        "feature_names": feature_names,
        "iterations": iteration,
        "converged": converged,
        "l2": l2,
    }


def _predict_logistic(model: dict[str, Any], frame: pd.DataFrame) -> np.ndarray:
    x, _ = _design(frame, model["schema"])
    return _sigmoid(x @ model["beta"])


def _match_equal_brier(match_ids: pd.Series, y: np.ndarray, p: np.ndarray) -> float:
    frame = pd.DataFrame({
        "match_id": match_ids.astype(str).to_numpy(),
        "sq_error": np.square(y - p),
    })
    return float(frame.groupby("match_id", sort=False)["sq_error"].mean().mean())


def _metrics(frame: pd.DataFrame, probs: np.ndarray) -> dict[str, Any]:
    y = frame["server_won"].astype(int).to_numpy(dtype=float)
    p = np.clip(np.asarray(probs, dtype=float), 1e-6, 1 - 1e-6)
    brier = float(np.mean(np.square(y - p))) if len(y) else None
    loss = float(np.mean(-(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))) if len(y) else None
    accuracy = float(np.mean((p >= 0.5) == (y >= 0.5))) if len(y) else None
    return {
        "points": int(len(frame)),
        "matches": int(frame["match_id"].astype(str).nunique()),
        "server_win_rate": round(float(y.mean()), 6) if len(y) else None,
        "brier": round(brier, 6) if brier is not None else None,
        "match_equal_brier": round(_match_equal_brier(frame["match_id"], y, p), 6) if len(y) else None,
        "log_loss": round(loss, 6) if loss is not None else None,
        "accuracy": round(accuracy, 6) if accuracy is not None else None,
    }


def _model_meta(model: dict[str, Any]) -> dict[str, Any]:
    beta = np.asarray(model["beta"], dtype=float)
    feature_names = [str(v) for v in model["feature_names"]]
    pairs = sorted(
        zip(feature_names[1:], beta[1:]),
        key=lambda item: abs(item[1]),
        reverse=True,
    )
    payload = {
        "features": feature_names,
        "coef": [round(float(v), 10) for v in beta],
        "l2": float(model["l2"]),
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "fitted": True,
        "engine": "NUMPY_NEWTON_LOGISTIC_L2",
        "converged": bool(model["converged"]),
        "iterations": int(model["iterations"]),
        "l2": float(model["l2"]),
        "feature_count": len(feature_names) - 1,
        "coefficient_l2": round(float(math.sqrt(float(np.square(beta[1:]).sum()))), 6),
        "intercept": round(float(beta[0]), 6),
        "model_fingerprint_sha256": fingerprint,
        "top_coefficients": [
            {"feature": feature, "coefficient": round(float(coef), 6)}
            for feature, coef in pairs[:12]
        ],
    }


def _fit_candidate(
    train: pd.DataFrame,
    holdout: pd.DataFrame,
    numeric: list[str],
) -> tuple[dict[str, Any], np.ndarray]:
    model = _fit_logistic_newton(train, numeric)
    probs = _predict_logistic(model, holdout)
    return {
        "metrics": _metrics(holdout, probs),
        "model": _model_meta(model),
    }, probs


def evaluate(rows: list[dict[str, Any]], readiness: dict[str, Any] | None = None) -> dict[str, Any]:
    train_all, holdout_all, split = split_chronological_by_match(rows)
    train = _frame(_cohort(train_all, EVAL_MIN_PRIOR_MATCHES))
    holdout = _frame(_cohort(holdout_all, EVAL_MIN_PRIOR_MATCHES))

    enough = (
        len(train) >= 1000
        and len(holdout) >= 1000
        and train["match_id"].nunique() >= 30
        and holdout["match_id"].nunique() >= 20
        and train["server_won"].nunique() == 2
        and holdout["server_won"].nunique() == 2
    ) if not train.empty and not holdout.empty else False

    report: dict[str, Any] = {
        "version": VERSION,
        "mode": MODE,
        "label": "server_won",
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "prod_model_write_enabled": False,
        "model_artifact_persisted": False,
        "real_shadow_training": bool(enough),
        "evaluation_min_prior_matches": EVAL_MIN_PRIOR_MATCHES,
        "evaluation_threshold_is_production_gate": False,
        "split": split,
        "all_joined_points": len(rows),
        "train_points_after_support_gate": int(len(train)),
        "holdout_points_after_support_gate": int(len(holdout)),
        "readiness_evidence": {
            "threshold_3": ((readiness or {}).get("readiness_any_surface") or {}).get("3"),
            "threshold_5": ((readiness or {}).get("readiness_any_surface") or {}).get("5"),
            "note": "3 is a SHADOW evaluation cohort, not a production readiness threshold.",
        },
        "models": {},
        "signal": {
            "status": "NOT_EVALUATED",
            "profile_only_brier_gain_vs_rank": None,
            "combined_brier_gain_vs_rank": None,
            "combined_match_equal_brier_gain_vs_rank": None,
            "stateful_brier_gain_vs_profile_plus_rank": None,
            "stateful_match_equal_brier_gain_vs_profile_plus_rank": None,
            "stateful_log_loss_gain_vs_profile_plus_rank": None,
        },
    }

    if not enough:
        report["signal"]["status"] = "INSUFFICIENT_SHADOW_SAMPLE"
        return report

    profile_numeric = list(PROFILE_NUMERIC)
    rank_numeric = list(RANK_NUMERIC)
    state_numeric = list(STATE_NUMERIC)
    combined_numeric = profile_numeric + rank_numeric
    stateful_numeric = combined_numeric + state_numeric

    profile_result, profile_probs = _fit_candidate(train, holdout, profile_numeric)
    rank_result, rank_probs = _fit_candidate(train, holdout, rank_numeric)
    combined_result, combined_probs = _fit_candidate(train, holdout, combined_numeric)
    state_only_result, state_only_probs = _fit_candidate(train, holdout, state_numeric)
    stateful_result, stateful_probs = _fit_candidate(train, holdout, stateful_numeric)

    base_probability = float(train["server_won"].mean())
    baseline_probs = np.full(len(holdout), base_probability, dtype=float)
    baseline = {
        "probability": round(base_probability, 6),
        "metrics": _metrics(holdout, baseline_probs),
    }

    report["models"] = {
        "constant_baseline": baseline,
        "profile_only_logistic": profile_result,
        "rank_only_logistic": rank_result,
        "profile_plus_rank_logistic": combined_result,
        "score_state_only_logistic": state_only_result,
        "profile_rank_plus_score_state_logistic": stateful_result,
    }

    pm = profile_result["metrics"]
    rm = rank_result["metrics"]
    cm = combined_result["metrics"]
    sm = stateful_result["metrics"]

    profile_gain = float(rm["brier"] - pm["brier"])
    combined_gain = float(rm["brier"] - cm["brier"])
    match_equal_gain = float(rm["match_equal_brier"] - cm["match_equal_brier"])
    stateful_gain = float(cm["brier"] - sm["brier"])
    stateful_match_equal_gain = float(cm["match_equal_brier"] - sm["match_equal_brier"])
    stateful_log_loss_gain = float(cm["log_loss"] - sm["log_loss"])

    profile_signal_positive = profile_gain > 0 and combined_gain > 0 and match_equal_gain > 0
    stateful_signal_positive = (
        stateful_gain > 0
        and stateful_match_equal_gain > 0
        and stateful_log_loss_gain > 0
    )
    signal_status = (
        "STATEFUL_CONTEXT_POSITIVE_HOLDOUT_SIGNAL"
        if stateful_signal_positive
        else "STATEFUL_CONTEXT_MIXED_OR_NO_INCREMENTAL_SIGNAL"
    )

    same_surface_mask = (
        (holdout["server_surface_matches"].fillna(0).astype(int) >= EVAL_MIN_PRIOR_MATCHES)
        & (holdout["receiver_surface_matches"].fillna(0).astype(int) >= EVAL_MIN_PRIOR_MATCHES)
    )
    same_surface_holdout = holdout.loc[same_surface_mask].copy()
    same_surface_probs = combined_probs[np.asarray(same_surface_mask, dtype=bool)]

    report["signal"] = {
        "status": signal_status,
        "profile_only_brier_gain_vs_rank": round(profile_gain, 6),
        "combined_brier_gain_vs_rank": round(combined_gain, 6),
        "combined_match_equal_brier_gain_vs_rank": round(match_equal_gain, 6),
        "combined_log_loss_gain_vs_rank": round(float(rm["log_loss"] - cm["log_loss"]), 6),
        "profile_has_incremental_information_beyond_rank": bool(profile_gain > 0),
        "combined_improves_rank_on_point_and_match_equal_brier": bool(
            combined_gain > 0 and match_equal_gain > 0
        ),
        "legacy_profile_signal_positive": bool(profile_signal_positive),
        "stateful_brier_gain_vs_profile_plus_rank": round(stateful_gain, 6),
        "stateful_match_equal_brier_gain_vs_profile_plus_rank": round(stateful_match_equal_gain, 6),
        "stateful_log_loss_gain_vs_profile_plus_rank": round(stateful_log_loss_gain, 6),
        "stateful_improves_all_primary_proper_scores": bool(stateful_signal_positive),
        "promotion_gate": False,
    }
    report["segments"] = {
        "holdout_with_both_same_surface_history_ge_3": (
            _metrics(same_surface_holdout, same_surface_probs)
            if len(same_surface_holdout) else None
        ),
        "holdout_tiebreak": (
            {
                "profile_plus_rank": _metrics(
                    holdout.loc[holdout["is_tiebreak"] == True].copy(),
                    combined_probs[np.asarray(holdout["is_tiebreak"] == True, dtype=bool)],
                ),
                "stateful": _metrics(
                    holdout.loc[holdout["is_tiebreak"] == True].copy(),
                    stateful_probs[np.asarray(holdout["is_tiebreak"] == True, dtype=bool)],
                ),
            }
            if bool((holdout["is_tiebreak"] == True).any()) else None
        ),
        "holdout_break_point_against_server": (
            {
                "profile_plus_rank": _metrics(
                    holdout.loc[holdout["break_point_against_server_before"].fillna(0).astype(int) == 1].copy(),
                    combined_probs[np.asarray(holdout["break_point_against_server_before"].fillna(0).astype(int) == 1, dtype=bool)],
                ),
                "stateful": _metrics(
                    holdout.loc[holdout["break_point_against_server_before"].fillna(0).astype(int) == 1].copy(),
                    stateful_probs[np.asarray(holdout["break_point_against_server_before"].fillna(0).astype(int) == 1, dtype=bool)],
                ),
            }
            if bool((holdout["break_point_against_server_before"].fillna(0).astype(int) == 1).any()) else None
        ),
        "holdout_late_set": (
            {
                "profile_plus_rank": _metrics(
                    holdout.loc[holdout["late_set_before"].fillna(0).astype(int) == 1].copy(),
                    combined_probs[np.asarray(holdout["late_set_before"].fillna(0).astype(int) == 1, dtype=bool)],
                ),
                "stateful": _metrics(
                    holdout.loc[holdout["late_set_before"].fillna(0).astype(int) == 1].copy(),
                    stateful_probs[np.asarray(holdout["late_set_before"].fillna(0).astype(int) == 1, dtype=bool)],
                ),
            }
            if bool((holdout["late_set_before"].fillna(0).astype(int) == 1).any()) else None
        ),
        "holdout_after_break": (
            {
                "profile_plus_rank": _metrics(
                    holdout.loc[holdout["previous_game_was_break"].fillna(0).astype(int) == 1].copy(),
                    combined_probs[np.asarray(holdout["previous_game_was_break"].fillna(0).astype(int) == 1, dtype=bool)],
                ),
                "stateful": _metrics(
                    holdout.loc[holdout["previous_game_was_break"].fillna(0).astype(int) == 1].copy(),
                    stateful_probs[np.asarray(holdout["previous_game_was_break"].fillna(0).astype(int) == 1, dtype=bool)],
                ),
            }
            if bool((holdout["previous_game_was_break"].fillna(0).astype(int) == 1).any()) else None
        ),
    }
    report["stateful_context_contract"] = {
        "features_use_score_before_only": True,
        "score_after_used_as_feature": False,
        "current_point_winner_used_as_feature": False,
        "momentum_uses_only_proven_contiguous_prior_atomic_points": True,
        "state_numeric_features": state_numeric,
        "runtime_scoring_enabled": False,
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
    }
    return report


def build() -> dict[str, Any]:
    point_rows = list(_iter_jsonl_gz(POINTS) or ())
    profile_rows = list(_iter_jsonl_gz(PROFILES) or ())
    feature_rows, join_counts = build_feature_rows(point_rows, profile_rows)

    try:
        readiness = json.loads(READINESS.read_text(encoding="utf-8")) if READINESS.exists() else {}
    except json.JSONDecodeError:
        readiness = {}

    report = evaluate(feature_rows, readiness)
    report["join_counts"] = join_counts
    report["join_coverage"] = round(
        int(join_counts.get("joined_rows") or 0)
        / max(1, int(join_counts.get("point_rows_seen") or 0) - int(join_counts.get("non_strict_rows_skipped") or 0)),
        6,
    )
    report["leakage_contract"] = {
        "profiles_are_as_of_match_start": True,
        "point_timestamp_used_as_feature": False,
        "same_timestamp_matches_split_across_train_holdout": bool(report.get("split", {}).get("same_timestamp_split")),
        "chronological_match_split": "80/20 by time boundary",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
