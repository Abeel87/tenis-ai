from __future__ import annotations

"""Historical match-market validation for the Player DNA tennis simulator.

This is an evaluation-only layer. It trains the same profile-only point model
used by current-card SHADOW scoring on the chronological training partition,
converts untouched holdout match profiles into serve-point probabilities, runs
the tennis simulator, and compares those probabilities with provider score-tape
outcomes.

No result from this module may influence PROD, Symfonia 2.0 or Superbet
PLAYABLE. Earlier holdout matches may contribute to later holdout profile
history because those outcomes would be known in real chronological operation;
model parameters remain frozen from the training partition.
"""

import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

try:
    from backend.player_dna_point_scorer import (
        PROFILE_NUMERIC,
        _cohort,
        _fit_logistic_newton,
        _predict_logistic,
        build_feature_rows,
        split_chronological_by_match,
    )
    from backend.player_dna_tennis_simulator import simulate_match
except ModuleNotFoundError:  # direct execution
    from player_dna_point_scorer import (
        PROFILE_NUMERIC,
        _cohort,
        _fit_logistic_newton,
        _predict_logistic,
        build_feature_rows,
        split_chronological_by_match,
    )
    from player_dna_tennis_simulator import simulate_match

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "data" / "derived" / "player_dna" / "point_events.jsonl.gz"
PROFILES = ROOT / "data" / "derived" / "player_dna" / "profile_snapshots.jsonl.gz"
OUT = ROOT / "frontend" / "data" / "player_dna_market_backtest.json"

VERSION = "player-dna-market-backtest-v1"
MODE = "SHADOW_BACKTEST_ONLY"
MIN_PRIOR_MATCHES = 3
BINARY_MARKETS = (
    "match_p1_win",
    "first_set_p1_win",
    "first_set_tiebreak",
    "first_set_over_8.5",
    "first_set_over_9.5",
    "first_set_over_10.5",
    "first_set_over_11.5",
    "first_set_over_12.5",
    "early_1:1",
    "early_2:2",
    "early_3:3",
)


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


def _two_ints(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, list) or len(value) < 2:
        return None
    try:
        a, b = int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None
    return a, b


def _game_lists(score: Any) -> tuple[list[int], list[int]] | None:
    if not isinstance(score, dict):
        return None
    games = score.get("games")
    if not isinstance(games, list) or len(games) < 2:
        return None
    if not isinstance(games[0], list) or not isinstance(games[1], list):
        return None
    try:
        p1 = [int(v) for v in games[0]]
        p2 = [int(v) for v in games[1]]
    except (TypeError, ValueError):
        return None
    return p1, p2


def _reconstruct_game_paths(
    ordered: list[dict[str, Any]],
    total_sets: int,
    final_games: tuple[list[int], list[int]],
) -> dict[str, Any]:
    paths: list[list[str]] = [[] for _ in range(total_sets)]
    last: list[tuple[int, int] | None] = [None for _ in range(total_sets)]
    first_server = None

    for row in ordered:
        if first_server is None and row.get("server") in (1, 2):
            first_server = int(row["server"])

        score = row.get("score_after")
        gl = _game_lists(score)
        if gl is None:
            continue
        p1_games, p2_games = gl
        for set_index in range(min(total_sets, len(p1_games), len(p2_games))):
            a, b = int(p1_games[set_index]), int(p2_games[set_index])
            if a < 0 or b < 0 or a + b <= 0:
                continue
            pair = (a, b)
            previous = last[set_index]
            if previous == pair:
                continue
            if previous is not None and a + b <= previous[0] + previous[1]:
                continue
            paths[set_index].append(f"{a}:{b}")
            last[set_index] = pair

    final_p1, final_p2 = final_games
    complete = []
    for set_index in range(total_sets):
        expected = int(final_p1[set_index]) + int(final_p2[set_index])
        progression = paths[set_index]
        totals = [sum(int(x) for x in score.split(":")) for score in progression]
        complete.append(
            expected > 0
            and len(progression) == expected
            and totals == list(range(1, expected + 1))
            and progression[-1] == f"{final_p1[set_index]}:{final_p2[set_index]}"
        )

    first_path = paths[0] if paths else []
    checkpoints = {}
    for games in (2, 4, 6):
        checkpoints[str(games)] = first_path[games - 1] if complete and complete[0] and len(first_path) >= games else None

    return {
        "first_server": first_server,
        "set_progressions": paths,
        "set_progression_complete": complete,
        "first_set_progression": first_path if complete and complete[0] else None,
        "checkpoint_scores": checkpoints,
        "full_match_progression_complete": bool(complete) and all(complete),
    }


def reconstruct_match_label(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Reconstruct settled match/first-set/early-game labels from score tape."""
    if not rows:
        return None
    ordered = sorted(rows, key=lambda r: int(r.get("event_index") or 0))
    fmt = str(ordered[0].get("match_format") or "")
    best_of = 5 if fmt == "BO5" else 3
    needed = best_of // 2 + 1

    final_score = None
    for row in reversed(ordered):
        score = row.get("score_after")
        if isinstance(score, dict) and _two_ints(score.get("sets")) is not None:
            final_score = score
            break
    if final_score is None:
        return None

    sets = _two_ints(final_score.get("sets"))
    games = _game_lists(final_score)
    if sets is None or games is None:
        return None
    s1, s2 = sets
    if max(s1, s2) != needed:
        return None

    total_sets = s1 + s2
    g1, g2 = games
    if total_sets <= 0 or len(g1) < total_sets or len(g2) < total_sets:
        return None

    first_g1, first_g2 = g1[0], g2[0]
    if max(first_g1, first_g2) < 6:
        return None

    early: dict[int, bool | None] = {2: None, 4: None, 6: None}
    for row in ordered:
        score = row.get("score_after")
        if not isinstance(score, dict):
            continue
        set_pair = _two_ints(score.get("sets"))
        if set_pair is None:
            continue
        if sum(set_pair) > 0:
            break
        gl = _game_lists(score)
        if gl is None or not gl[0] or not gl[1]:
            continue
        a, b = gl[0][0], gl[1][0]
        total = a + b
        if total in early and early[total] is None:
            early[total] = bool(a == b)

    first_total = first_g1 + first_g2
    trajectory_actual = _reconstruct_game_paths(ordered, total_sets, games)
    return {
        "best_of": best_of,
        "match_p1_win": bool(s1 == needed),
        "match_exact_score": f"{s1}:{s2}",
        "total_sets": str(total_sets),
        "first_set_p1_win": bool(first_g1 > first_g2),
        "first_set_exact_score": f"{first_g1}:{first_g2}",
        "first_set_games": first_total,
        "first_set_tiebreak": bool((first_g1, first_g2) in ((7, 6), (6, 7))),
        "first_set_over_8.5": bool(first_total > 8.5),
        "first_set_over_9.5": bool(first_total > 9.5),
        "first_set_over_10.5": bool(first_total > 10.5),
        "first_set_over_11.5": bool(first_total > 11.5),
        "first_set_over_12.5": bool(first_total > 12.5),
        "early_1:1": early[2],
        "early_2:2": early[4],
        "early_3:3": early[6],
        "trajectory_actual": {
            **trajectory_actual,
            "set_score_sequence": [
                f"{g1[idx]}:{g2[idx]}" for idx in range(total_sets)
            ],
        },
    }


def _labels_by_match(point_rows: Iterable[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in point_rows:
        match_id = str(row.get("match_id") or "").strip()
        if match_id:
            grouped[match_id].append(row)

    labels: dict[str, dict[str, Any]] = {}
    counts = Counter()
    for match_id, rows in grouped.items():
        counts["matches_seen"] += 1
        label = reconstruct_match_label(rows)
        if label is None:
            counts["incomplete_or_unsettled"] += 1
            continue
        labels[match_id] = label
        counts["settled_labels"] += 1
    return labels, dict(counts)


def _snapshot_pairs(profile_rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    pairs: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in profile_rows:
        if not isinstance(row, dict):
            continue
        match_id = str(row.get("target_match_id") or "").strip()
        side = str(row.get("player_side") or "")
        if match_id and side in ("p1", "p2"):
            pairs[match_id][side] = row
    return dict(pairs)


def _serve_feature(server: dict[str, Any], receiver: dict[str, Any]) -> dict[str, Any]:
    so = server.get("overall_prior") if isinstance(server.get("overall_prior"), dict) else {}
    ro = receiver.get("overall_prior") if isinstance(receiver.get("overall_prior"), dict) else {}
    ss = server.get("same_surface_prior") if isinstance(server.get("same_surface_prior"), dict) else {}
    rs = receiver.get("same_surface_prior") if isinstance(receiver.get("same_surface_prior"), dict) else {}
    return {
        "surface": str(server.get("target_surface") or "unknown"),
        "tour": str(server.get("target_tour") or "unknown"),
        "match_format": str(server.get("target_format") or "unknown"),
        "server_overall_serve_rate": so.get("serve_win_rate"),
        "receiver_overall_return_rate": ro.get("return_win_rate"),
        "server_surface_serve_rate": ss.get("serve_win_rate"),
        "receiver_surface_return_rate": rs.get("return_win_rate"),
        "server_overall_matches": int(so.get("matches") or 0),
        "receiver_overall_matches": int(ro.get("matches") or 0),
        "server_surface_matches": int(ss.get("matches") or 0),
        "receiver_surface_matches": int(rs.get("matches") or 0),
    }


def _predict_match_simulations(
    holdout_ids: set[str],
    pairs: dict[str, dict[str, dict[str, Any]]],
    model: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    predictions: dict[str, dict[str, Any]] = {}
    counts = Counter()

    for match_id in sorted(holdout_ids):
        pair = pairs.get(match_id) or {}
        p1 = pair.get("p1")
        p2 = pair.get("p2")
        if not isinstance(p1, dict) or not isinstance(p2, dict):
            counts["missing_profile_pair"] += 1
            continue

        p1_overall = p1.get("overall_prior") if isinstance(p1.get("overall_prior"), dict) else {}
        p2_overall = p2.get("overall_prior") if isinstance(p2.get("overall_prior"), dict) else {}
        if int(p1_overall.get("matches") or 0) < MIN_PRIOR_MATCHES or int(p2_overall.get("matches") or 0) < MIN_PRIOR_MATCHES:
            counts["below_support_gate"] += 1
            continue

        feature_frame = pd.DataFrame([
            _serve_feature(p1, p2),
            _serve_feature(p2, p1),
        ])
        probs = _predict_logistic(model, feature_frame)
        if len(probs) != 2:
            counts["prediction_failure"] += 1
            continue

        fmt = str(p1.get("target_format") or "")
        best_of = 5 if fmt == "BO5" else 3
        simulation = simulate_match(float(probs[0]), float(probs[1]), best_of=best_of)
        predictions[match_id] = {
            "p1_serve_point": float(probs[0]),
            "p2_serve_point": float(probs[1]),
            "simulation": simulation,
        }
        counts["simulated"] += 1

    return predictions, dict(counts)


def _clip(p: float) -> float:
    return min(1.0 - 1e-6, max(1e-6, float(p)))


def _calibration_bins(records: list[tuple[float, int]], bins: int = 10) -> list[dict[str, Any]]:
    out = []
    for idx in range(bins):
        lo = idx / bins
        hi = (idx + 1) / bins
        selected = [(p, y) for p, y in records if (lo <= p < hi) or (idx == bins - 1 and p == 1.0)]
        if not selected:
            continue
        mean_p = sum(p for p, _ in selected) / len(selected)
        rate = sum(y for _, y in selected) / len(selected)
        out.append({
            "from": round(lo, 2),
            "to": round(hi, 2),
            "n": len(selected),
            "mean_probability": round(mean_p, 6),
            "observed_rate": round(rate, 6),
            "gap": round(abs(mean_p - rate), 6),
        })
    return out


def binary_metrics(
    records: list[tuple[float, int]],
    train_labels: list[int],
) -> dict[str, Any]:
    if not records or not train_labels:
        return {"n": 0, "status": "NO_DATA"}
    probs = np.asarray([_clip(p) for p, _ in records], dtype=float)
    y = np.asarray([int(v) for _, v in records], dtype=float)
    base = _clip(sum(int(v) for v in train_labels) / len(train_labels))
    base_probs = np.full(len(y), base, dtype=float)

    brier = float(np.mean(np.square(probs - y)))
    base_brier = float(np.mean(np.square(base_probs - y)))
    loss = float(np.mean(-(y * np.log(probs) + (1.0 - y) * np.log(1.0 - probs))))
    base_loss = float(np.mean(-(y * np.log(base_probs) + (1.0 - y) * np.log(1.0 - base_probs))))
    calibration = _calibration_bins(list(zip(probs.tolist(), y.astype(int).tolist())))
    ece = sum((row["n"] / len(y)) * row["gap"] for row in calibration)

    return {
        "n": int(len(y)),
        "positive_rate": round(float(y.mean()), 6),
        "mean_probability": round(float(probs.mean()), 6),
        "brier": round(brier, 6),
        "baseline_probability": round(base, 6),
        "baseline_brier": round(base_brier, 6),
        "brier_gain_vs_train_rate": round(base_brier - brier, 6),
        "brier_skill_vs_train_rate": round(1.0 - brier / base_brier, 6) if base_brier > 0 else None,
        "log_loss": round(loss, 6),
        "baseline_log_loss": round(base_loss, 6),
        "log_loss_gain_vs_train_rate": round(base_loss - loss, 6),
        "accuracy_0.5": round(float(np.mean((probs >= 0.5) == (y >= 0.5))), 6),
        "ece_10_bin": round(float(ece), 6),
        "calibration_bins": calibration,
        "status": "EVALUATED",
    }


def categorical_metrics(
    records: list[tuple[dict[str, float], str]],
    train_labels: list[str],
) -> dict[str, Any]:
    if not records or not train_labels:
        return {"n": 0, "status": "NO_DATA"}

    train_counts = Counter(train_labels)
    total_train = sum(train_counts.values())
    keys = sorted(set(train_counts) | {actual for _, actual in records} | {k for probs, _ in records for k in probs})
    baseline = {k: train_counts.get(k, 0) / total_train for k in keys}

    model_brier = []
    base_brier = []
    model_nll = []
    base_nll = []
    top1 = 0
    actual_prob = []

    for probs, actual in records:
        normalized = {k: max(0.0, float(probs.get(k, 0.0))) for k in keys}
        mass = sum(normalized.values())
        if mass <= 0:
            continue
        normalized = {k: v / mass for k, v in normalized.items()}
        model_brier.append(sum((normalized[k] - (1.0 if k == actual else 0.0)) ** 2 for k in keys))
        base_brier.append(sum((baseline[k] - (1.0 if k == actual else 0.0)) ** 2 for k in keys))
        pa = _clip(normalized.get(actual, 0.0))
        ba = _clip(baseline.get(actual, 0.0))
        actual_prob.append(pa)
        model_nll.append(-math.log(pa))
        base_nll.append(-math.log(ba))
        top1 += int(max(normalized, key=normalized.get) == actual)

    n = len(model_brier)
    if n == 0:
        return {"n": 0, "status": "NO_VALID_PROBABILITY_MASS"}
    mb = sum(model_brier) / n
    bb = sum(base_brier) / n
    return {
        "n": n,
        "classes": keys,
        "multiclass_brier": round(mb, 6),
        "baseline_multiclass_brier": round(bb, 6),
        "brier_gain_vs_train_distribution": round(bb - mb, 6),
        "negative_log_likelihood": round(sum(model_nll) / n, 6),
        "baseline_negative_log_likelihood": round(sum(base_nll) / n, 6),
        "nll_gain_vs_train_distribution": round((sum(base_nll) - sum(model_nll)) / n, 6),
        "top1_accuracy": round(top1 / n, 6),
        "mean_probability_assigned_to_actual": round(sum(actual_prob) / n, 6),
        "status": "EVALUATED",
    }


def _normalized_progression(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    out = []
    for item in value:
        score = str(item or "").strip()
        if not score:
            continue
        if out and out[-1] == score:
            continue
        out.append(score)
    return tuple(out)


def _rank_hit(rows: list[dict[str, Any]], actual: tuple[str, ...], field: str, limits: tuple[int, ...]) -> dict[str, Any]:
    ranked = []
    for row in rows:
        value = row.get(field)
        candidate = _normalized_progression(value) if field == "progression" else tuple(str(x) for x in (value or []))
        ranked.append(candidate)
    hit_rank = None
    for idx, candidate in enumerate(ranked, start=1):
        if candidate == actual:
            hit_rank = idx
            break
    return {
        "rank": hit_rank,
        **{f"hit_at_{limit}": bool(hit_rank is not None and hit_rank <= limit) for limit in limits},
    }


def _trajectory_validation(
    predictions: dict[str, dict[str, Any]],
    labels: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    checkpoint_records = {2: [], 4: [], 6: []}
    first_set_records = []
    match_set_records = []

    for match_id, label in labels.items():
        pred = predictions.get(match_id)
        if not isinstance(pred, dict):
            continue
        sim = pred.get("simulation") or {}
        trajectory = sim.get("trajectory") or {}
        actual = label.get("trajectory_actual") or {}

        checkpoints = trajectory.get("checkpoints_neutral_start_server") or {}
        for games in (2, 4, 6):
            actual_score = (actual.get("checkpoint_scores") or {}).get(str(games))
            rows = checkpoints.get(f"after_{games}_games") or []
            if not actual_score or not rows:
                continue
            ranked_scores = [str(row.get("score") or "") for row in rows]
            checkpoint_records[games].append({
                "top1": ranked_scores[0] == actual_score,
                "top3": actual_score in ranked_scores[:3],
            })

        first_server = actual.get("first_server")
        branch_key = "p1_serves_first" if first_server == 1 else "p2_serves_first" if first_server == 2 else None
        branch = (trajectory.get("serve_order_conditioned") or {}).get(branch_key) if branch_key else None
        if not isinstance(branch, dict):
            continue

        first_path = _normalized_progression(actual.get("first_set_progression"))
        if first_path:
            ranked = branch.get("first_set_top_game_paths") or []
            hit = _rank_hit(ranked, first_path, "progression", (1, 3, 8))
            top1 = _normalized_progression((ranked[0] if ranked else {}).get("progression"))
            prefix = 0
            for expected, predicted in zip(first_path, top1):
                if expected != predicted:
                    break
                prefix += 1
            first_set_records.append({
                **hit,
                "prefix_fraction_top1": prefix / len(first_path),
            })

        set_sequence = tuple(str(x) for x in (actual.get("set_score_sequence") or []))
        if set_sequence:
            ranked_sets = branch.get("match_top_set_paths") or []
            match_set_records.append(_rank_hit(ranked_sets, set_sequence, "set_scores", (1, 3, 12)))

    def summarize_checkpoint(rows: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(rows)
        return {
            "n": n,
            "top1_accuracy": round(sum(int(row["top1"]) for row in rows) / n, 6) if n else None,
            "top3_accuracy": round(sum(int(row["top3"]) for row in rows) / n, 6) if n else None,
        }

    def summarize_rank(rows: list[dict[str, Any]], limits: tuple[int, ...], include_prefix: bool = False) -> dict[str, Any]:
        n = len(rows)
        out = {"n": n}
        for limit in limits:
            out[f"hit_at_{limit}"] = round(sum(int(row[f"hit_at_{limit}"]) for row in rows) / n, 6) if n else None
        ranks = [int(row["rank"]) for row in rows if row.get("rank") is not None]
        out["mean_rank_when_hit"] = round(sum(ranks) / len(ranks), 6) if ranks else None
        if include_prefix:
            out["mean_top1_prefix_fraction"] = round(
                sum(float(row.get("prefix_fraction_top1") or 0.0) for row in rows) / n, 6
            ) if n else None
        return out

    return {
        "status": "TRAJECTORY_HISTORICAL_DIAGNOSTIC",
        "promotion_gate": False,
        "claim": "ranked path diagnostics only; no match-level robustness claim",
        "checkpoint_neutral_start_server": {
            f"after_{games}_games": summarize_checkpoint(checkpoint_records[games])
            for games in (2, 4, 6)
        },
        "first_set_conditioned_on_observed_first_server": summarize_rank(first_set_records, (1, 3, 8), include_prefix=True),
        "match_set_sequence_conditioned_on_observed_first_server": summarize_rank(match_set_records, (1, 3, 12)),
        "coverage": {
            "settled_predictions": len(labels),
            "first_set_complete_paths": len(first_set_records),
            "match_set_sequences": len(match_set_records),
        },
    }


def _binary_probability(sim: dict[str, Any], market: str) -> float | None:
    if market == "match_p1_win":
        return float((sim.get("match") or {}).get("p1_win"))
    if market == "first_set_p1_win":
        return float((sim.get("first_set") or {}).get("p1_win"))
    if market == "first_set_tiebreak":
        return float((sim.get("first_set") or {}).get("tiebreak"))
    if market.startswith("first_set_over_"):
        line = market.removeprefix("first_set_over_")
        value = ((sim.get("first_set") or {}).get("over") or {}).get(line)
        return float(value) if value is not None else None
    if market.startswith("early_"):
        label = market.removeprefix("early_")
        value = (sim.get("early_equal_score") or {}).get(label)
        return float(value) if value is not None else None
    return None


def evaluate_backtest(
    point_rows: list[dict[str, Any]],
    profile_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    feature_rows, join_counts = build_feature_rows(point_rows, profile_rows)
    train_all, holdout_all, split = split_chronological_by_match(feature_rows)
    train = _cohort(train_all, MIN_PRIOR_MATCHES)
    holdout = _cohort(holdout_all, MIN_PRIOR_MATCHES)

    train_ids = {str(row["match_id"]) for row in train}
    holdout_ids = {str(row["match_id"]) for row in holdout}
    if not train or not holdout:
        return {
            "version": VERSION,
            "mode": MODE,
            "status": "INSUFFICIENT_SHADOW_SAMPLE",
            "production_influence": False,
            "symphony2_influence": False,
            "superbet_playable_influence": False,
            "auto_promote": False,
            "split": split,
        }

    train_frame = pd.DataFrame(train)
    model = _fit_logistic_newton(train_frame, list(PROFILE_NUMERIC))
    pairs = _snapshot_pairs(profile_rows)
    predictions, prediction_counts = _predict_match_simulations(holdout_ids, pairs, model)
    labels, label_counts = _labels_by_match(point_rows)

    train_settled = {mid: labels[mid] for mid in train_ids if mid in labels}
    holdout_settled = {mid: labels[mid] for mid in predictions if mid in labels}

    binary: dict[str, Any] = {}
    for market in BINARY_MARKETS:
        records: list[tuple[float, int]] = []
        for match_id, label in holdout_settled.items():
            actual = label.get(market)
            if not isinstance(actual, bool):
                continue
            prob = _binary_probability(predictions[match_id]["simulation"], market)
            if prob is not None and math.isfinite(prob):
                records.append((float(prob), int(actual)))
        train_labels = [
            int(label[market])
            for label in train_settled.values()
            if isinstance(label.get(market), bool)
        ]
        binary[market] = binary_metrics(records, train_labels)

    exact_first_records = [
        ((predictions[mid]["simulation"].get("first_set") or {}).get("exact_score") or {}, label["first_set_exact_score"])
        for mid, label in holdout_settled.items()
    ]
    exact_match_records = [
        ((predictions[mid]["simulation"].get("match") or {}).get("exact_score") or {}, label["match_exact_score"])
        for mid, label in holdout_settled.items()
    ]
    total_sets_records = [
        ((predictions[mid]["simulation"].get("match") or {}).get("total_sets") or {}, label["total_sets"])
        for mid, label in holdout_settled.items()
    ]

    trajectory_validation = _trajectory_validation(predictions, holdout_settled)

    categorical = {
        "first_set_exact_score": categorical_metrics(
            exact_first_records,
            [label["first_set_exact_score"] for label in train_settled.values()],
        ),
        "match_exact_score": categorical_metrics(
            exact_match_records,
            [label["match_exact_score"] for label in train_settled.values()],
        ),
        "total_sets": categorical_metrics(
            total_sets_records,
            [label["total_sets"] for label in train_settled.values()],
        ),
    }

    evaluated = [m for m in binary.values() if int(m.get("n") or 0) >= 100 and m.get("brier_gain_vs_train_rate") is not None]
    positive = sum(1 for m in evaluated if float(m["brier_gain_vs_train_rate"]) > 0)
    primary_positive = all(
        float((binary[name].get("brier_gain_vs_train_rate") or 0.0)) > 0
        for name in ("match_p1_win", "first_set_p1_win")
        if int(binary[name].get("n") or 0) >= 100
    )
    enough = len(holdout_settled) >= 200 and len(evaluated) >= 6
    if not enough:
        signal = "INSUFFICIENT_MATCH_LEVEL_SAMPLE"
    elif primary_positive and positive >= math.ceil(0.6 * len(evaluated)):
        signal = "POSITIVE_MATCH_LEVEL_HOLDOUT_SIGNAL"
    else:
        signal = "MIXED_OR_NO_MATCH_LEVEL_SIGNAL"

    return {
        "version": VERSION,
        "mode": MODE,
        "status": "BACKTEST_COMPLETE_NO_PROMOTION",
        "signal": signal,
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "current_simulation_status_unchanged": "UNVALIDATED_MATCH_LEVEL",
        "evaluation_min_prior_matches": MIN_PRIOR_MATCHES,
        "evaluation_threshold_is_production_gate": False,
        "model_features": "PROFILE_ONLY_CURRENT_COMPATIBLE",
        "model_converged": bool(model.get("converged")),
        "model_iterations": int(model.get("iterations") or 0),
        "split": split,
        "chronology_policy": {
            "model_parameters_fit_train_only": True,
            "holdout_predictions_chronological": True,
            "earlier_holdout_matches_may_update_later_profiles": True,
            "same_timestamp_matches_isolated_by_profile_builder": True,
            "outcome_labels_used_only_for_evaluation": True,
        },
        "counts": {
            "point_join": join_counts,
            "train_point_rows": len(train),
            "holdout_point_rows": len(holdout),
            "train_match_ids": len(train_ids),
            "holdout_match_ids": len(holdout_ids),
            "simulated_holdout_matches": len(predictions),
            "settled_train_matches": len(train_settled),
            "settled_simulated_holdout_matches": len(holdout_settled),
            "label_counts": label_counts,
            "prediction_counts": prediction_counts,
        },
        "binary_markets": binary,
        "categorical_markets": categorical,
        "trajectory_validation": trajectory_validation,
        "summary": {
            "binary_markets_evaluated_ge_100": len(evaluated),
            "binary_markets_with_positive_brier_gain": positive,
            "primary_match_and_first_set_positive": primary_positive,
        },
    }


def build() -> dict[str, Any]:
    point_rows = list(_iter_jsonl_gz(POINTS) or ())
    profile_rows = list(_iter_jsonl_gz(PROFILES) or ())
    report = evaluate_backtest(point_rows, profile_rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": report.get("version"),
        "mode": report.get("mode"),
        "status": report.get("status"),
        "signal": report.get("signal"),
        "counts": report.get("counts"),
        "summary": report.get("summary"),
        "trajectory_validation": report.get("trajectory_validation"),
        "production_influence": report.get("production_influence"),
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
