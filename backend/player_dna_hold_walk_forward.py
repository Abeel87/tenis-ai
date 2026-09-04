from __future__ import annotations

"""Walk-forward robustness audit for Player DNA hold calibration.

This is a SHADOW-only evidence gate. It reuses the canonical Player DNA point
model, hold calibrator and tennis simulator, but evaluates them over multiple
chronological windows with disjoint test periods. It never alters current
runtime scoring, Symfonia 2.0, Superbet PLAYABLE or PROD.
"""

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from backend.player_dna_point_scorer import PROFILE_NUMERIC, _cohort, _fit_logistic_newton, build_feature_rows
    from backend.player_dna_market_backtest import _labels_by_match, _predict_match_simulations, _snapshot_pairs
    from backend.player_dna_hold_calibration import (
        MIN_PRIOR_MATCHES,
        UNIQUE_DURATION_MARKETS,
        _binary_eval,
        _calibrated_match_simulations,
        _game_observations,
        _iter_jsonl_gz,
        _market_comparison,
        calibrated_hold_probability,
        fit_hold_platt,
    )
except ModuleNotFoundError:  # direct execution
    from player_dna_point_scorer import PROFILE_NUMERIC, _cohort, _fit_logistic_newton, build_feature_rows
    from player_dna_market_backtest import _labels_by_match, _predict_match_simulations, _snapshot_pairs
    from player_dna_hold_calibration import (
        MIN_PRIOR_MATCHES,
        UNIQUE_DURATION_MARKETS,
        _binary_eval,
        _calibrated_match_simulations,
        _game_observations,
        _iter_jsonl_gz,
        _market_comparison,
        calibrated_hold_probability,
        fit_hold_platt,
    )

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "data" / "derived" / "player_dna" / "point_events.jsonl.gz"
PROFILES = ROOT / "data" / "derived" / "player_dna" / "profile_snapshots.jsonl.gz"
OUT = ROOT / "frontend" / "data" / "player_dna_hold_walk_forward.json"

VERSION = "player-dna-hold-walk-forward-v1"
MODE = "SHADOW_WALK_FORWARD_AUDIT_ONLY"
FOLDS = (
    ("wf1", 0.60, 0.70, 0.80),
    ("wf2", 0.70, 0.80, 0.90),
    ("wf3", 0.80, 0.90, 1.00),
)
MIN_CALIBRATION_GAMES = 300
MIN_TEST_GAMES = 300
MIN_SETTLED_TEST_MATCHES = 50
MIN_SEGMENT_SETTLED_MATCHES = 20
WALK_FORWARD_POLICY = "mature-history expanding fit; adjacent calibration; disjoint 10% test windows"


def _match_times(rows: list[dict[str, Any]]) -> dict[str, datetime]:
    out: dict[str, datetime] = {}
    for row in rows:
        match_id = str(row.get("match_id") or "")
        scheduled = row.get("scheduled_time")
        if not match_id or not isinstance(scheduled, datetime):
            continue
        previous = out.get(match_id)
        if previous is not None and previous != scheduled:
            raise ValueError(f"conflicting scheduled_time for match {match_id}")
        out[match_id] = scheduled
    return out


def _fraction_cutoff(ordered: list[tuple[str, datetime]], fraction: float) -> datetime | None:
    if fraction >= 1.0:
        return None
    if not ordered:
        return None
    idx = max(1, min(len(ordered) - 1, int(len(ordered) * fraction)))
    return ordered[idx][1]


def partition_feature_rows(
    rows: list[dict[str, Any]],
    fit_end: float,
    calibration_end: float,
    test_end: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    times = _match_times(rows)
    ordered = sorted(times.items(), key=lambda item: (item[1], item[0]))
    fit_cutoff = _fraction_cutoff(ordered, fit_end)
    calibration_cutoff = _fraction_cutoff(ordered, calibration_end)
    test_cutoff = _fraction_cutoff(ordered, test_end)
    if fit_cutoff is None or calibration_cutoff is None:
        return [], [], [], {
            "fit_cutoff": None,
            "calibration_cutoff": None,
            "test_cutoff": None,
            "same_timestamp_split": False,
        }

    fit_ids = {mid for mid, ts in ordered if ts < fit_cutoff}
    calibration_ids = {
        mid for mid, ts in ordered
        if ts >= fit_cutoff and ts < calibration_cutoff
    }
    test_ids = {
        mid for mid, ts in ordered
        if ts >= calibration_cutoff and (test_cutoff is None or ts < test_cutoff)
    }

    fit = [row for row in rows if str(row.get("match_id")) in fit_ids]
    calibration = [row for row in rows if str(row.get("match_id")) in calibration_ids]
    test = [row for row in rows if str(row.get("match_id")) in test_ids]

    fit_times = {times[mid] for mid in fit_ids}
    calibration_times = {times[mid] for mid in calibration_ids}
    test_times = {times[mid] for mid in test_ids}
    same_timestamp_split = bool(
        (fit_times & calibration_times) or (fit_times & test_times) or (calibration_times & test_times)
    )
    return fit, calibration, test, {
        "fit_cutoff": fit_cutoff.isoformat(),
        "calibration_cutoff": calibration_cutoff.isoformat(),
        "test_cutoff": test_cutoff.isoformat() if test_cutoff is not None else None,
        "fit_matches": len(fit_ids),
        "calibration_matches": len(calibration_ids),
        "test_matches": len(test_ids),
        "same_timestamp_split": same_timestamp_split,
        "policy": WALK_FORWARD_POLICY,
    }


def _segment_summary(
    raw_predictions: dict[str, dict[str, Any]],
    calibrated_predictions: dict[str, dict[str, Any]],
    labels: dict[str, dict[str, Any]],
    pairs: dict[str, dict[str, dict[str, Any]]],
    key: str,
) -> dict[str, Any]:
    groups: dict[str, set[str]] = defaultdict(set)
    for match_id in raw_predictions:
        p1 = (pairs.get(match_id) or {}).get("p1") or {}
        raw_value = p1.get(key)
        value = str(raw_value or "unknown").strip().lower()
        groups[value].add(match_id)

    out = {}
    for value, ids in sorted(groups.items()):
        settled = {mid for mid in ids if mid in labels}
        if len(settled) < MIN_SEGMENT_SETTLED_MATCHES:
            continue
        raw_subset = {mid: raw_predictions[mid] for mid in settled if mid in raw_predictions}
        calibrated_subset = {mid: calibrated_predictions[mid] for mid in settled if mid in calibrated_predictions}
        comparison = _market_comparison(raw_subset, calibrated_subset, labels)
        duration_improved = sum(
            1 for market in UNIQUE_DURATION_MARKETS
            if (comparison.get(market) or {}).get("improved") is True
        )
        out[value] = {
            "settled_matches": len(settled),
            "duration_markets_improved": duration_improved,
            "duration_markets_total": len(UNIQUE_DURATION_MARKETS),
            "match_winner_brier_gain": (comparison.get("match_p1_win") or {}).get("brier_gain_calibrated_vs_raw"),
            "first_set_winner_brier_gain": (comparison.get("first_set_p1_win") or {}).get("brier_gain_calibrated_vs_raw"),
            "duration_market_gains": {
                market: (comparison.get(market) or {}).get("brier_gain_calibrated_vs_raw")
                for market in UNIQUE_DURATION_MARKETS
            },
        }
    return out


def evaluate_fold(
    name: str,
    feature_rows: list[dict[str, Any]],
    point_rows: list[dict[str, Any]],
    pairs: dict[str, dict[str, dict[str, Any]]],
    labels: dict[str, dict[str, Any]],
    fit_end: float,
    calibration_end: float,
    test_end: float,
) -> dict[str, Any]:
    fit_all, calibration_all, test_all, split = partition_feature_rows(
        feature_rows, fit_end, calibration_end, test_end
    )
    fit_rows = _cohort(fit_all, MIN_PRIOR_MATCHES)
    calibration_rows = _cohort(calibration_all, MIN_PRIOR_MATCHES)
    test_rows = _cohort(test_all, MIN_PRIOR_MATCHES)
    fit_ids = {str(row["match_id"]) for row in fit_rows}
    calibration_ids = {str(row["match_id"]) for row in calibration_rows}
    test_ids = {str(row["match_id"]) for row in test_rows}

    base = {
        "name": name,
        "status": "INSUFFICIENT_FOLD_SAMPLE",
        "split": split,
        "fit_point_rows": len(fit_rows),
        "calibration_point_rows": len(calibration_rows),
        "test_point_rows": len(test_rows),
        "fit_matches": len(fit_ids),
        "calibration_matches": len(calibration_ids),
        "test_matches": len(test_ids),
    }
    if not fit_rows or not calibration_rows or not test_rows or split.get("same_timestamp_split") is True:
        return base

    point_model = _fit_logistic_newton(pd.DataFrame(fit_rows), list(PROFILE_NUMERIC))
    if point_model.get("converged") is not True:
        base["status"] = "POINT_MODEL_NOT_CONVERGED"
        return base

    calibration_predictions, calibration_prediction_counts = _predict_match_simulations(
        calibration_ids, pairs, point_model
    )
    test_predictions, test_prediction_counts = _predict_match_simulations(test_ids, pairs, point_model)
    calibration_games = _game_observations(point_rows, calibration_predictions)
    test_games = _game_observations(point_rows, test_predictions)
    settled_test_matches = sum(1 for mid in test_predictions if mid in labels)

    base["calibration_prediction_counts"] = calibration_prediction_counts
    base["test_prediction_counts"] = test_prediction_counts
    base["calibration_games"] = len(calibration_games)
    base["test_games"] = len(test_games)
    base["settled_test_matches"] = settled_test_matches

    if (
        len(calibration_games) < MIN_CALIBRATION_GAMES
        or len(test_games) < MIN_TEST_GAMES
        or settled_test_matches < MIN_SETTLED_TEST_MATCHES
    ):
        return base

    calibrator = fit_hold_platt(
        [row["iid_hold_probability"] for row in calibration_games],
        [row["held"] for row in calibration_games],
    )
    raw_game = _binary_eval([(row["iid_hold_probability"], row["held"]) for row in test_games])
    calibrated_game = _binary_eval([
        (calibrated_hold_probability(row["iid_hold_probability"], calibrator), row["held"])
        for row in test_games
    ])
    raw_brier = float(raw_game.get("brier") or 1.0)
    calibrated_brier = float(calibrated_game.get("brier") or 1.0)
    game_gain = raw_brier - calibrated_brier

    calibrated_predictions = _calibrated_match_simulations(test_predictions, pairs, calibrator)
    market_comparison = _market_comparison(test_predictions, calibrated_predictions, labels)
    duration_improved = sum(
        1 for market in UNIQUE_DURATION_MARKETS
        if (market_comparison.get(market) or {}).get("improved") is True
    )
    match_gain = float((market_comparison.get("match_p1_win") or {}).get("brier_gain_calibrated_vs_raw") or 0.0)
    first_set_gain = float((market_comparison.get("first_set_p1_win") or {}).get("brier_gain_calibrated_vs_raw") or 0.0)
    no_primary_collapse = match_gain >= -0.01 and first_set_gain >= -0.01
    promising = bool(
        calibrator.get("converged") is True
        and game_gain > 0
        and duration_improved >= 3
        and no_primary_collapse
    )

    return {
        **base,
        "status": "FOLD_COMPLETE",
        "signal": "PROMISING" if promising else "NOT_YET_PROVEN",
        "hold_calibrator": calibrator,
        "game_hold_test": {
            "iid_raw": raw_game,
            "calibrated": calibrated_game,
            "brier_gain_calibrated_vs_raw": round(game_gain, 6),
            "improved": game_gain > 0,
        },
        "market_comparison": market_comparison,
        "summary": {
            "duration_markets_improved": duration_improved,
            "duration_markets_total": len(UNIQUE_DURATION_MARKETS),
            "match_winner_brier_gain_calibrated_vs_raw": round(match_gain, 6),
            "first_set_winner_brier_gain_calibrated_vs_raw": round(first_set_gain, 6),
            "no_primary_collapse": no_primary_collapse,
        },
        "segments": {
            "surface": _segment_summary(
                test_predictions, calibrated_predictions, labels, pairs, "target_surface"
            ),
            "tour": _segment_summary(
                test_predictions, calibrated_predictions, labels, pairs, "target_tour"
            ),
        },
    }


def aggregate_segments(folds: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for dimension in ("surface", "tour"):
        values: dict[str, dict[str, Any]] = {}
        names = sorted({
            name
            for fold in folds
            for name in (((fold.get("segments") or {}).get(dimension) or {}).keys())
        })
        for name in names:
            seen = []
            for fold in folds:
                row = (((fold.get("segments") or {}).get(dimension) or {}).get(name))
                if isinstance(row, dict):
                    seen.append(row)
            if not seen:
                continue
            positive_duration_folds = sum(
                1 for row in seen
                if int(row.get("duration_markets_improved") or 0) >= 3
            )
            primary_safe_folds = sum(
                1 for row in seen
                if float(row.get("match_winner_brier_gain") or 0.0) >= -0.01
                and float(row.get("first_set_winner_brier_gain") or 0.0) >= -0.01
            )
            values[name] = {
                "folds_with_sample": len(seen),
                "settled_matches_total": sum(int(row.get("settled_matches") or 0) for row in seen),
                "duration_positive_folds": positive_duration_folds,
                "primary_safe_folds": primary_safe_folds,
                "repeatable_duration_signal": bool(
                    len(seen) >= 2 and positive_duration_folds >= 2
                ),
            }
        out[dimension] = values
    return out


def aggregate_folds(folds: list[dict[str, Any]]) -> dict[str, Any]:
    complete = [fold for fold in folds if fold.get("status") == "FOLD_COMPLETE"]
    promising = sum(1 for fold in complete if fold.get("signal") == "PROMISING")
    game_improved = sum(
        1 for fold in complete if (fold.get("game_hold_test") or {}).get("improved") is True
    )
    duration_positive = Counter()
    for fold in complete:
        comparison = fold.get("market_comparison") or {}
        for market in UNIQUE_DURATION_MARKETS:
            if (comparison.get(market) or {}).get("improved") is True:
                duration_positive[market] += 1

    no_catastrophic_primary_collapse = all(
        float(((fold.get("summary") or {}).get("match_winner_brier_gain_calibrated_vs_raw") or 0.0)) >= -0.015
        and float(((fold.get("summary") or {}).get("first_set_winner_brier_gain_calibrated_vs_raw") or 0.0)) >= -0.015
        for fold in complete
    ) if complete else False

    robust = bool(
        len(complete) == len(FOLDS)
        and promising >= 2
        and game_improved >= 2
        and all(duration_positive[market] >= 2 for market in UNIQUE_DURATION_MARKETS)
        and no_catastrophic_primary_collapse
    )
    return {
        "completed_folds": len(complete),
        "required_folds": len(FOLDS),
        "promising_folds": promising,
        "game_hold_improved_folds": game_improved,
        "duration_market_positive_folds": {
            market: int(duration_positive[market]) for market in UNIQUE_DURATION_MARKETS
        },
        "no_catastrophic_primary_collapse": no_catastrophic_primary_collapse,
        "robust": robust,
    }


def evaluate(point_rows: list[dict[str, Any]], profile_rows: list[dict[str, Any]]) -> dict[str, Any]:
    feature_rows, join_counts = build_feature_rows(point_rows, profile_rows)
    pairs = _snapshot_pairs(profile_rows)
    labels, label_counts = _labels_by_match(point_rows)
    folds = [
        evaluate_fold(name, feature_rows, point_rows, pairs, labels, fit_end, calibration_end, test_end)
        for name, fit_end, calibration_end, test_end in FOLDS
    ]
    aggregate = aggregate_folds(folds)
    segment_aggregate = aggregate_segments(folds)
    status = (
        "WALK_FORWARD_COMPLETE_NO_INTEGRATION"
        if aggregate["completed_folds"] == aggregate["required_folds"]
        else "WALK_FORWARD_INCOMPLETE_NO_INTEGRATION"
    )
    signal = (
        "HOLD_CALIBRATION_WALK_FORWARD_ROBUST_SHADOW"
        if aggregate["robust"]
        else "HOLD_CALIBRATION_WALK_FORWARD_NOT_YET_ROBUST"
    )
    return {
        "version": VERSION,
        "mode": MODE,
        "status": status,
        "signal": signal,
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "current_simulator_modified": False,
        "candidate_gate_modified": False,
        "auto_integrate": False,
        "chronology_policy": {
            "expanding_fit": True,
            "rolling_calibration": True,
            "test_windows_disjoint": True,
            "mature_history_windows": True,
            "fold_policy": WALK_FORWARD_POLICY,
            "same_timestamp_groups_not_split": all(
                (fold.get("split") or {}).get("same_timestamp_split") is False for fold in folds
            ),
            "profiles_are_strict_as_of": True,
        },
        "counts": {
            "point_join": join_counts,
            "labels": label_counts,
            "folds": len(folds),
        },
        "folds": folds,
        "aggregate": aggregate,
        "segment_aggregate": segment_aggregate,
        "note": (
            "Evidence gate only. A robust result does not promote Player DNA or change the "
            "current hold-calibrated SHADOW candidate."
        ),
    }


def build() -> dict[str, Any]:
    point_rows = list(_iter_jsonl_gz(POINTS) or ())
    profile_rows = list(_iter_jsonl_gz(PROFILES) or ())
    report = evaluate(point_rows, profile_rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": report.get("version"),
        "status": report.get("status"),
        "signal": report.get("signal"),
        "aggregate": report.get("aggregate"),
        "production_influence": report.get("production_influence"),
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
