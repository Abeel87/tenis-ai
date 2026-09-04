from __future__ import annotations

"""Three-way SHADOW calibration audit for point -> hold -> set propagation.

The market backtest shows that Player DNA point probabilities carry signal but
the IID tennis simulator overpredicts close/long first sets. This experiment
tests one precise hypothesis without touching current runtime simulation:

1. fit the profile-only point model on the earliest chronological partition,
2. fit a hold-probability calibrator on a later calibration partition,
3. evaluate both raw IID and calibrated hold propagation on a final untouched
   partition.

Nothing in this module is allowed to alter PROD, Symfonia 2.0, PLAYABLE or the
current Player DNA simulator. Integration requires a separate gate.
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
        build_feature_rows,
        split_chronological_by_match,
    )
    from backend.player_dna_market_backtest import (
        BINARY_MARKETS,
        _binary_probability,
        _labels_by_match,
        _predict_match_simulations,
        _snapshot_pairs,
    )
    from backend.player_dna_tennis_simulator import (
        calibrated_hold_probability,
        hold_probability,
        inverse_hold_probability,
        simulate_match,
    )
except ModuleNotFoundError:  # direct execution
    from player_dna_point_scorer import (
        PROFILE_NUMERIC,
        _cohort,
        _fit_logistic_newton,
        build_feature_rows,
        split_chronological_by_match,
    )
    from player_dna_market_backtest import (
        BINARY_MARKETS,
        _binary_probability,
        _labels_by_match,
        _predict_match_simulations,
        _snapshot_pairs,
    )
    from player_dna_tennis_simulator import (
        calibrated_hold_probability,
        hold_probability,
        inverse_hold_probability,
        simulate_match,
    )

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "data" / "derived" / "player_dna" / "point_events.jsonl.gz"
PROFILES = ROOT / "data" / "derived" / "player_dna" / "profile_snapshots.jsonl.gz"
OUT = ROOT / "frontend" / "data" / "player_dna_hold_calibration_audit.json"

VERSION = "player-dna-hold-calibration-audit-v1"
MODE = "SHADOW_CALIBRATION_AUDIT_ONLY"
MIN_PRIOR_MATCHES = 3
UNIQUE_DURATION_MARKETS = (
    "first_set_tiebreak",
    "first_set_over_8.5",
    "first_set_over_9.5",
    "first_set_over_10.5",
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


def _logit(value: float) -> float:
    p = min(1.0 - 1e-8, max(1e-8, float(value)))
    return math.log(p / (1.0 - p))


def _sigmoid(value: Any) -> Any:
    z = np.clip(np.asarray(value, dtype=float), -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-z))


def fit_hold_platt(
    iid_hold_probabilities: Iterable[float],
    labels: Iterable[int],
    *,
    l2: float = 0.01,
    max_iter: int = 50,
    tolerance: float = 1e-9,
) -> dict[str, Any]:
    probs = np.asarray([float(v) for v in iid_hold_probabilities], dtype=float)
    y = np.asarray([int(v) for v in labels], dtype=float)
    if len(probs) != len(y) or len(y) < 2 or len(set(y.tolist())) < 2:
        raise ValueError("hold calibrator needs aligned binary observations")

    x = np.asarray([_logit(v) for v in probs], dtype=float)
    design = np.column_stack([np.ones(len(x), dtype=float), x])
    beta = np.asarray([0.0, 1.0], dtype=float)
    converged = False

    for iteration in range(1, max_iter + 1):
        pred = _sigmoid(design @ beta)
        gradient = (design.T @ (pred - y)) / len(y)
        gradient[1] += l2 * beta[1]

        weights = pred * (1.0 - pred)
        hessian = ((design.T * weights) @ design) / len(y)
        hessian += np.diag([1e-9, l2])
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.pinv(hessian) @ gradient

        beta -= step
        if float(np.max(np.abs(step))) < tolerance:
            converged = True
            break

    return {
        "intercept": float(beta[0]),
        "slope": float(beta[1]),
        "l2": float(l2),
        "iterations": int(iteration),
        "converged": bool(converged),
    }


def _game_observations(
    point_rows: Iterable[dict[str, Any]],
    match_predictions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    out = []
    for row in point_rows:
        match_id = str(row.get("match_id") or "").strip()
        pred = match_predictions.get(match_id)
        if pred is None:
            continue
        if row.get("transition_kind") not in ("game_score_changed", "set_score_changed"):
            continue
        server = row.get("server")
        winner = row.get("point_winner")
        if server not in (1, 2) or winner not in (1, 2):
            continue
        raw_point = float(pred["p1_serve_point"] if server == 1 else pred["p2_serve_point"])
        out.append({
            "match_id": match_id,
            "server_side": int(server),
            "raw_point_probability": raw_point,
            "iid_hold_probability": hold_probability(raw_point),
            "held": int(winner == server),
        })
    return out


def _binary_eval(records: list[tuple[float, int]]) -> dict[str, Any]:
    if not records:
        return {"n": 0}
    p = np.asarray([min(1 - 1e-6, max(1e-6, float(v))) for v, _ in records], dtype=float)
    y = np.asarray([int(v) for _, v in records], dtype=float)
    brier = float(np.mean(np.square(p - y)))
    loss = float(np.mean(-(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))))
    return {
        "n": int(len(y)),
        "observed_rate": round(float(y.mean()), 6),
        "mean_probability": round(float(p.mean()), 6),
        "brier": round(brier, 6),
        "log_loss": round(loss, 6),
        "bias": round(float(p.mean() - y.mean()), 6),
    }


def _calibrated_match_simulations(
    raw_predictions: dict[str, dict[str, Any]],
    pairs: dict[str, dict[str, dict[str, Any]]],
    calibrator: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    out = {}
    for match_id, raw in raw_predictions.items():
        pair = pairs.get(match_id) or {}
        p1snap = pair.get("p1") or {}
        fmt = str(p1snap.get("target_format") or "")
        best_of = 5 if fmt == "BO5" else 3

        p1_raw = float(raw["p1_serve_point"])
        p2_raw = float(raw["p2_serve_point"])
        p1_cal_hold = calibrated_hold_probability(hold_probability(p1_raw), calibrator)
        p2_cal_hold = calibrated_hold_probability(hold_probability(p2_raw), calibrator)
        p1_equiv = inverse_hold_probability(p1_cal_hold)
        p2_equiv = inverse_hold_probability(p2_cal_hold)

        out[match_id] = {
            "p1_raw_point": p1_raw,
            "p2_raw_point": p2_raw,
            "p1_iid_hold": hold_probability(p1_raw),
            "p2_iid_hold": hold_probability(p2_raw),
            "p1_calibrated_hold": p1_cal_hold,
            "p2_calibrated_hold": p2_cal_hold,
            "p1_equivalent_point": p1_equiv,
            "p2_equivalent_point": p2_equiv,
            "simulation": simulate_match(p1_equiv, p2_equiv, best_of=best_of),
        }
    return out


def _market_comparison(
    raw_predictions: dict[str, dict[str, Any]],
    calibrated_predictions: dict[str, dict[str, Any]],
    labels: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    out = {}
    for market in BINARY_MARKETS:
        raw_records = []
        calibrated_records = []
        for match_id, raw in raw_predictions.items():
            if match_id not in calibrated_predictions or match_id not in labels:
                continue
            actual = labels[match_id].get(market)
            if not isinstance(actual, bool):
                continue
            raw_p = _binary_probability(raw["simulation"], market)
            cal_p = _binary_probability(calibrated_predictions[match_id]["simulation"], market)
            if raw_p is None or cal_p is None:
                continue
            raw_records.append((float(raw_p), int(actual)))
            calibrated_records.append((float(cal_p), int(actual)))

        raw_m = _binary_eval(raw_records)
        cal_m = _binary_eval(calibrated_records)
        raw_brier = raw_m.get("brier")
        cal_brier = cal_m.get("brier")
        out[market] = {
            "raw": raw_m,
            "calibrated": cal_m,
            "brier_gain_calibrated_vs_raw": (
                round(float(raw_brier) - float(cal_brier), 6)
                if raw_brier is not None and cal_brier is not None else None
            ),
            "improved": bool(
                raw_brier is not None and cal_brier is not None and float(cal_brier) < float(raw_brier)
            ),
        }
    return out


def evaluate(
    point_rows: list[dict[str, Any]],
    profile_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    feature_rows, join_counts = build_feature_rows(point_rows, profile_rows)

    pretest_all, test_all, outer_split = split_chronological_by_match(feature_rows, train_fraction=0.80)
    fit_all, calibration_all, inner_split = split_chronological_by_match(pretest_all, train_fraction=0.75)

    fit_rows = _cohort(fit_all, MIN_PRIOR_MATCHES)
    calibration_rows = _cohort(calibration_all, MIN_PRIOR_MATCHES)
    test_rows = _cohort(test_all, MIN_PRIOR_MATCHES)

    fit_ids = {str(row["match_id"]) for row in fit_rows}
    calibration_ids = {str(row["match_id"]) for row in calibration_rows}
    test_ids = {str(row["match_id"]) for row in test_rows}

    if not fit_rows or not calibration_rows or not test_rows:
        return {
            "version": VERSION,
            "mode": MODE,
            "status": "INSUFFICIENT_THREE_WAY_SAMPLE",
            "production_influence": False,
            "auto_integrate": False,
        }

    point_model = _fit_logistic_newton(pd.DataFrame(fit_rows), list(PROFILE_NUMERIC))
    pairs = _snapshot_pairs(profile_rows)
    calibration_predictions, calibration_pred_counts = _predict_match_simulations(calibration_ids, pairs, point_model)
    test_predictions, test_pred_counts = _predict_match_simulations(test_ids, pairs, point_model)

    calibration_games = _game_observations(point_rows, calibration_predictions)
    test_games = _game_observations(point_rows, test_predictions)
    if len(calibration_games) < 500 or len(test_games) < 500:
        return {
            "version": VERSION,
            "mode": MODE,
            "status": "INSUFFICIENT_GAME_SAMPLE",
            "production_influence": False,
            "auto_integrate": False,
            "counts": {
                "calibration_games": len(calibration_games),
                "test_games": len(test_games),
            },
        }

    calibrator = fit_hold_platt(
        [row["iid_hold_probability"] for row in calibration_games],
        [row["held"] for row in calibration_games],
    )

    raw_game_test = _binary_eval([
        (row["iid_hold_probability"], row["held"]) for row in test_games
    ])
    calibrated_game_test = _binary_eval([
        (calibrated_hold_probability(row["iid_hold_probability"], calibrator), row["held"])
        for row in test_games
    ])

    calibrated_predictions = _calibrated_match_simulations(test_predictions, pairs, calibrator)
    labels, label_counts = _labels_by_match(point_rows)
    market_comparison = _market_comparison(test_predictions, calibrated_predictions, labels)

    duration_results = [market_comparison[name] for name in UNIQUE_DURATION_MARKETS]
    duration_improved = sum(1 for row in duration_results if row.get("improved"))
    raw_game_brier = float(raw_game_test.get("brier") or 1.0)
    calibrated_game_brier = float(calibrated_game_test.get("brier") or 1.0)
    game_improved = calibrated_game_brier < raw_game_brier

    match_delta = float((market_comparison.get("match_p1_win") or {}).get("brier_gain_calibrated_vs_raw") or 0.0)
    first_set_delta = float((market_comparison.get("first_set_p1_win") or {}).get("brier_gain_calibrated_vs_raw") or 0.0)
    no_primary_collapse = match_delta >= -0.01 and first_set_delta >= -0.01

    if (
        calibrator.get("converged") is True
        and game_improved
        and duration_improved >= 3
        and no_primary_collapse
    ):
        signal = "HOLD_CALIBRATION_PROMISING_SHADOW"
    else:
        signal = "HOLD_CALIBRATION_NOT_YET_PROVEN"

    settled_test = sum(1 for mid in test_predictions if mid in labels)
    return {
        "version": VERSION,
        "mode": MODE,
        "status": "CALIBRATION_EXPERIMENT_COMPLETE_NO_INTEGRATION",
        "signal": signal,
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "current_simulator_modified": False,
        "auto_integrate": False,
        "evaluation_min_prior_matches": MIN_PRIOR_MATCHES,
        "point_model_features": "PROFILE_ONLY_CURRENT_COMPATIBLE",
        "split": {
            "fit_point_model": inner_split,
            "final_test": outer_split,
            "partition_policy": "first 60% fit point model; next 20% fit hold calibrator; final 20% untouched test",
            "same_timestamp_groups_not_split": bool(
                inner_split.get("same_timestamp_split") is False
                and outer_split.get("same_timestamp_split") is False
            ),
        },
        "chronology_policy": {
            "point_model_fit_partition_only": True,
            "hold_calibrator_fit_calibration_partition_only": True,
            "final_test_untouched_for_parameters": True,
            "profiles_are_strict_as_of": True,
        },
        "counts": {
            "point_join": join_counts,
            "fit_point_rows": len(fit_rows),
            "calibration_point_rows": len(calibration_rows),
            "test_point_rows": len(test_rows),
            "fit_matches": len(fit_ids),
            "calibration_matches": len(calibration_ids),
            "test_matches": len(test_ids),
            "calibration_simulated_matches": len(calibration_predictions),
            "test_simulated_matches": len(test_predictions),
            "settled_test_matches": settled_test,
            "calibration_games": len(calibration_games),
            "test_games": len(test_games),
            "label_counts": label_counts,
            "calibration_prediction_counts": calibration_pred_counts,
            "test_prediction_counts": test_pred_counts,
        },
        "hold_calibrator": calibrator,
        "game_hold_test": {
            "iid_raw": raw_game_test,
            "calibrated": calibrated_game_test,
            "brier_gain_calibrated_vs_raw": round(raw_game_brier - calibrated_game_brier, 6),
            "improved": game_improved,
        },
        "market_comparison": market_comparison,
        "summary": {
            "unique_duration_markets": list(UNIQUE_DURATION_MARKETS),
            "duration_markets_improved": duration_improved,
            "duration_markets_total": len(UNIQUE_DURATION_MARKETS),
            "match_winner_brier_gain_calibrated_vs_raw": round(match_delta, 6),
            "first_set_winner_brier_gain_calibrated_vs_raw": round(first_set_delta, 6),
            "no_primary_collapse": no_primary_collapse,
        },
    }


def build() -> dict[str, Any]:
    point_rows = list(_iter_jsonl_gz(POINTS) or ())
    profile_rows = list(_iter_jsonl_gz(PROFILES) or ())
    report = evaluate(point_rows, profile_rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": report.get("version"),
        "mode": report.get("mode"),
        "status": report.get("status"),
        "signal": report.get("signal"),
        "counts": report.get("counts"),
        "hold_calibrator": report.get("hold_calibrator"),
        "game_hold_test": report.get("game_hold_test"),
        "summary": report.get("summary"),
        "production_influence": report.get("production_influence"),
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
