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
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

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
    rows: list[dict[str, Any]] = []
    counts = Counter()

    for point in point_rows:
        if not isinstance(point, dict):
            continue
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

        rows.append({
            "match_id": match_id,
            "scheduled_time": scheduled,
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
        })
        counts["joined_rows"] += 1

    counts["profile_snapshots"] = len(profiles)
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


def _pipeline(numeric: list[str]) -> Pipeline:
    numeric_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    pre = ColumnTransformer([
        ("numeric", numeric_pipe, numeric),
        ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
    ])
    return Pipeline([
        ("pre", pre),
        ("model", LogisticRegression(max_iter=1000, solver="lbfgs")),
    ])


def _match_equal_brier(match_ids: pd.Series, y: np.ndarray, p: np.ndarray) -> float:
    frame = pd.DataFrame({
        "match_id": match_ids.astype(str).to_numpy(),
        "sq_error": np.square(y - p),
    })
    return float(frame.groupby("match_id", sort=False)["sq_error"].mean().mean())


def _metrics(frame: pd.DataFrame, probs: np.ndarray) -> dict[str, Any]:
    y = frame["server_won"].astype(int).to_numpy()
    p = np.clip(np.asarray(probs, dtype=float), 1e-6, 1 - 1e-6)
    return {
        "points": int(len(frame)),
        "matches": int(frame["match_id"].astype(str).nunique()),
        "server_win_rate": round(float(y.mean()), 6) if len(y) else None,
        "brier": round(float(brier_score_loss(y, p)), 6) if len(y) else None,
        "match_equal_brier": round(_match_equal_brier(frame["match_id"], y, p), 6) if len(y) else None,
        "log_loss": round(float(log_loss(y, p, labels=[0, 1])), 6) if len(y) else None,
        "accuracy": round(float(accuracy_score(y, p >= 0.5)), 6) if len(y) else None,
    }


def _model_meta(pipe: Pipeline) -> dict[str, Any]:
    pre = pipe.named_steps["pre"]
    model = pipe.named_steps["model"]
    feature_names = [str(v) for v in pre.get_feature_names_out()]
    coefs = model.coef_[0].astype(float)
    pairs = sorted(
        zip(feature_names, coefs),
        key=lambda item: abs(item[1]),
        reverse=True,
    )
    payload = {
        "features": feature_names,
        "coef": [round(float(v), 10) for v in coefs],
        "intercept": [round(float(v), 10) for v in model.intercept_],
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "fitted": True,
        "feature_count": len(feature_names),
        "coefficient_l2": round(float(math.sqrt(float(np.square(coefs).sum()))), 6),
        "intercept": round(float(model.intercept_[0]), 6),
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
    pipe = _pipeline(numeric)
    columns = numeric + CATEGORICAL
    pipe.fit(train[columns], train["server_won"].astype(int))
    probs = pipe.predict_proba(holdout[columns])[:, 1]
    return {
        "metrics": _metrics(holdout, probs),
        "model": _model_meta(pipe),
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
        },
    }

    if not enough:
        report["signal"]["status"] = "INSUFFICIENT_SHADOW_SAMPLE"
        return report

    profile_numeric = list(PROFILE_NUMERIC)
    rank_numeric = list(RANK_NUMERIC)
    combined_numeric = profile_numeric + rank_numeric

    profile_result, profile_probs = _fit_candidate(train, holdout, profile_numeric)
    rank_result, rank_probs = _fit_candidate(train, holdout, rank_numeric)
    combined_result, combined_probs = _fit_candidate(train, holdout, combined_numeric)

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
    }

    pm = profile_result["metrics"]
    rm = rank_result["metrics"]
    cm = combined_result["metrics"]

    profile_gain = float(rm["brier"] - pm["brier"])
    combined_gain = float(rm["brier"] - cm["brier"])
    match_equal_gain = float(rm["match_equal_brier"] - cm["match_equal_brier"])

    signal_status = "POSITIVE_HOLDOUT_SIGNAL" if (
        profile_gain > 0 and combined_gain > 0 and match_equal_gain > 0
    ) else "MIXED_OR_NO_INCREMENTAL_SIGNAL"

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
    }
    report["segments"] = {
        "holdout_with_both_same_surface_history_ge_3": (
            _metrics(same_surface_holdout, same_surface_probs)
            if len(same_surface_holdout) else None
        ),
        "holdout_tiebreak": (
            _metrics(
                holdout.loc[holdout["is_tiebreak"] == True].copy(),
                combined_probs[np.asarray(holdout["is_tiebreak"] == True, dtype=bool)],
            )
            if bool((holdout["is_tiebreak"] == True).any()) else None
        ),
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
