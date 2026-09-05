from __future__ import annotations

"""Walk-forward robustness audit for the dynamic lean Player DNA market candidate.

Three expanding chronological folds retrain both the profile-only reference and
the dynamic lean stateful candidate. Evaluation windows are disjoint and never
split equal scheduled timestamps. This module is SHADOW-only and cannot promote
or modify runtime, Symfonia 2.0, or Superbet PLAYABLE behavior.
"""

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from backend.player_dna_market_backtest import (
        BINARY_MARKETS,
        MIN_PRIOR_MATCHES,
        POINTS,
        PROFILES,
        _dynamic_lean_comparison,
        _iter_jsonl_gz,
        _labels_by_match,
        _predict_dynamic_lean_simulations,
        _predict_match_simulations,
        _rank_context_by_match,
        _snapshot_pairs,
    )
    from backend.player_dna_point_scorer import (
        LEAN_STATE_NUMERIC,
        PROFILE_NUMERIC,
        RANK_NUMERIC,
        _cohort,
        _fit_logistic_newton,
        build_feature_rows,
    )
except ModuleNotFoundError:  # direct execution
    from player_dna_market_backtest import (
        BINARY_MARKETS,
        MIN_PRIOR_MATCHES,
        POINTS,
        PROFILES,
        _dynamic_lean_comparison,
        _iter_jsonl_gz,
        _labels_by_match,
        _predict_dynamic_lean_simulations,
        _predict_match_simulations,
        _rank_context_by_match,
        _snapshot_pairs,
    )
    from player_dna_point_scorer import (
        LEAN_STATE_NUMERIC,
        PROFILE_NUMERIC,
        RANK_NUMERIC,
        _cohort,
        _fit_logistic_newton,
        build_feature_rows,
    )

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data" / "player_dna_dynamic_market_walk_forward.json"

VERSION = "player-dna-dynamic-market-walk-forward-v1"
MODE = "SHADOW_DYNAMIC_LEAN_MARKET_WALK_FORWARD_ONLY"
TRAIN_FRACTIONS = (0.55, 0.70, 0.85)
REQUIRED_FOLDS = 3
FOLD_MIN_MATCHED = 120
FOLD_MIN_MARKET_N = 80
FOLD_MIN_EVALUATED_MARKETS = 6
AGGREGATE_MIN_MATCHED = 500


def _match_times(feature_rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in feature_rows:
        match_id = str(row.get("match_id") or "").strip()
        scheduled = row.get("scheduled_time")
        if not match_id or scheduled is None:
            continue
        previous = out.get(match_id)
        if previous is not None and previous != scheduled:
            raise ValueError(f"conflicting scheduled_time for match {match_id}")
        out[match_id] = scheduled
    return out


def walk_forward_fold_specs(feature_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    match_times = _match_times(feature_rows)
    ordered = sorted(match_times.items(), key=lambda item: (item[1], item[0]))
    n = len(ordered)
    if n < 4:
        return []

    cutoffs = []
    for fraction in TRAIN_FRACTIONS:
        index = max(1, min(n - 1, int(n * fraction)))
        cutoffs.append(ordered[index][1])

    if not (cutoffs[0] < cutoffs[1] < cutoffs[2]):
        return []

    specs = []
    for index, start in enumerate(cutoffs):
        end = cutoffs[index + 1] if index + 1 < len(cutoffs) else None
        train_ids = {
            match_id
            for match_id, scheduled in match_times.items()
            if scheduled < start
        }
        eval_ids = {
            match_id
            for match_id, scheduled in match_times.items()
            if scheduled >= start and (end is None or scheduled < end)
        }
        train_times = {match_times[mid] for mid in train_ids}
        eval_times = {match_times[mid] for mid in eval_ids}
        specs.append({
            "fold": index + 1,
            "train_fraction_target": TRAIN_FRACTIONS[index],
            "train_before": start,
            "eval_from": start,
            "eval_before": end,
            "train_ids": train_ids,
            "eval_ids": eval_ids,
            "same_timestamp_split": bool(train_times & eval_times),
        })
    return specs


def fold_verdict(comparison: dict[str, Any]) -> dict[str, Any]:
    binary = comparison.get("binary_markets_vs_profile_only") or {}
    evaluated = [
        metrics
        for metrics in binary.values()
        if int(metrics.get("n") or 0) >= FOLD_MIN_MARKET_N
    ]
    positive_both = sum(
        1
        for metrics in evaluated
        if metrics.get("dynamic_better_on_brier_and_log_loss") is True
    )
    primary_names = ("match_p1_win", "first_set_p1_win")
    primary_ready = all(
        int((binary.get(name) or {}).get("n") or 0) >= FOLD_MIN_MARKET_N
        for name in primary_names
    )
    primary_positive = primary_ready and all(
        (binary.get(name) or {}).get("dynamic_better_on_brier_and_log_loss") is True
        for name in primary_names
    )
    matched = int(comparison.get("matched_settled_matches") or 0)
    support_sufficient = (
        matched >= FOLD_MIN_MATCHED
        and len(evaluated) >= FOLD_MIN_EVALUATED_MARKETS
        and primary_ready
    )
    repeatable_gain = bool(
        support_sufficient
        and primary_positive
        and positive_both >= math.ceil(0.60 * len(evaluated))
    )
    return {
        "matched_settled_matches": matched,
        "binary_markets_evaluated_ge_fold_min": len(evaluated),
        "binary_markets_better_on_brier_and_log_loss": positive_both,
        "primary_match_and_first_set_better_on_both": primary_positive,
        "support_sufficient": support_sufficient,
        "repeatable_gain": repeatable_gain,
    }


def summarize_walk_forward(
    folds: list[dict[str, Any]],
    aggregate_comparison: dict[str, Any],
) -> dict[str, Any]:
    completed = [fold for fold in folds if fold.get("status") == "FOLD_COMPLETE"]
    supported = [
        fold for fold in completed
        if (fold.get("verdict") or {}).get("support_sufficient") is True
    ]
    repeatable = [
        fold for fold in supported
        if (fold.get("verdict") or {}).get("repeatable_gain") is True
    ]

    primary_repeatability = {}
    for market in ("match_p1_win", "first_set_p1_win"):
        positive_folds = 0
        eligible_folds = 0
        for fold in supported:
            metrics = (
                ((fold.get("comparison") or {}).get("binary_markets_vs_profile_only") or {})
                .get(market)
                or {}
            )
            if int(metrics.get("n") or 0) < FOLD_MIN_MARKET_N:
                continue
            eligible_folds += 1
            positive_folds += int(
                metrics.get("dynamic_better_on_brier_and_log_loss") is True
            )
        primary_repeatability[market] = {
            "eligible_folds": eligible_folds,
            "positive_both_folds": positive_folds,
        }

    aggregate_matched = int(aggregate_comparison.get("matched_settled_matches") or 0)
    aggregate_promising = (
        aggregate_comparison.get("signal")
        == "DYNAMIC_LEAN_STATEFUL_E2E_PROMISING_SHADOW"
    )
    enough = (
        len(completed) == REQUIRED_FOLDS
        and len(supported) == REQUIRED_FOLDS
        and aggregate_matched >= AGGREGATE_MIN_MATCHED
    )
    robust = (
        enough
        and len(repeatable) >= 2
        and aggregate_promising
        and all(
            int(row.get("positive_both_folds") or 0) >= 2
            for row in primary_repeatability.values()
        )
    )

    if not enough:
        signal = "INSUFFICIENT_DYNAMIC_LEAN_MARKET_WALK_FORWARD_SAMPLE"
    elif robust:
        signal = "DYNAMIC_LEAN_MARKET_WALK_FORWARD_ROBUST_SHADOW"
    else:
        signal = "DYNAMIC_LEAN_MARKET_WALK_FORWARD_MIXED_OR_NO_GAIN"

    return {
        "signal": signal,
        "required_folds": REQUIRED_FOLDS,
        "completed_folds": len(completed),
        "supported_folds": len(supported),
        "repeatable_gain_folds": len(repeatable),
        "aggregate_matched_settled_matches": aggregate_matched,
        "aggregate_promising": aggregate_promising,
        "primary_repeatability": primary_repeatability,
    }


def evaluate_walk_forward(
    point_rows: list[dict[str, Any]],
    profile_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    feature_rows, join_counts = build_feature_rows(point_rows, profile_rows)
    specs = walk_forward_fold_specs(feature_rows)
    labels, label_counts = _labels_by_match(point_rows)
    pairs = _snapshot_pairs(profile_rows)
    rank_context, rank_counts = _rank_context_by_match(point_rows)

    base_report = {
        "version": VERSION,
        "mode": MODE,
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "promotion_gate": False,
        "feature_groups": ["profile", "rank", "point_pressure", "set_match_state"],
        "dropped_state_groups": ["tiebreak_context", "prior_momentum"],
        "tiebreak_policy": "PROFILE_ONLY_NEUTRAL_FIXED_PER_MATCH",
        "fold_policy": {
            "train_fractions": list(TRAIN_FRACTIONS),
            "evaluation_fraction_windows": [[0.55, 0.70], [0.70, 0.85], [0.85, 1.0]],
            "expanding_train_windows": True,
            "evaluation_windows_disjoint": True,
            "same_timestamp_groups_not_split": True,
            "fold_min_matched": FOLD_MIN_MATCHED,
            "fold_min_market_n": FOLD_MIN_MARKET_N,
            "aggregate_min_matched": AGGREGATE_MIN_MATCHED,
        },
        "chronology_contract": {
            "models_refit_per_fold_on_prior_matches_only": True,
            "evaluation_windows_are_future_only": True,
            "evaluation_windows_are_disjoint": True,
            "same_timestamp_groups_are_never_split": True,
            "profiles_are_as_of_each_target_match": True,
            "rank_metadata_is_pre_match_context": True,
            "hypothetical_point_features_are_pre_point_only": True,
            "outcome_labels_used_only_for_evaluation": True,
        },
        "counts": {
            "point_join": join_counts,
            "label_counts": label_counts,
            "rank_context_counts": rank_counts,
            "feature_rows": len(feature_rows),
            "fold_specs": len(specs),
        },
    }

    if len(specs) != REQUIRED_FOLDS:
        return {
            **base_report,
            "status": "WALK_FORWARD_INCOMPLETE_NO_PROMOTION",
            "signal": "INSUFFICIENT_DYNAMIC_LEAN_MARKET_WALK_FORWARD_SAMPLE",
            "folds": [],
            "aggregate": {},
            "summary": {
                "required_folds": REQUIRED_FOLDS,
                "completed_folds": 0,
                "supported_folds": 0,
                "repeatable_gain_folds": 0,
            },
        }

    folds: list[dict[str, Any]] = []
    aggregate_profile: dict[str, dict[str, Any]] = {}
    aggregate_dynamic: dict[str, dict[str, Any]] = {}
    aggregate_labels: dict[str, dict[str, Any]] = {}

    for spec in specs:
        start = spec["eval_from"]
        end = spec["eval_before"]
        train_rows = _cohort(
            [row for row in feature_rows if row.get("scheduled_time") < start],
            MIN_PRIOR_MATCHES,
        )
        eval_rows = _cohort(
            [
                row
                for row in feature_rows
                if row.get("scheduled_time") >= start
                and (end is None or row.get("scheduled_time") < end)
            ],
            MIN_PRIOR_MATCHES,
        )
        train_ids = {str(row["match_id"]) for row in train_rows}
        eval_ids = {str(row["match_id"]) for row in eval_rows}

        fold_meta = {
            "fold": spec["fold"],
            "train_fraction_target": spec["train_fraction_target"],
            "train_before": start.isoformat(),
            "eval_from": start.isoformat(),
            "eval_before": end.isoformat() if end is not None else None,
            "same_timestamp_split": spec["same_timestamp_split"],
            "train_match_ids": len(train_ids),
            "eval_match_ids": len(eval_ids),
            "train_point_rows": len(train_rows),
            "eval_point_rows": len(eval_rows),
        }

        if not train_rows or not eval_rows or spec["same_timestamp_split"]:
            folds.append({
                **fold_meta,
                "status": "FOLD_INCOMPLETE",
                "reason": "EMPTY_WINDOW_OR_TIMESTAMP_SPLIT",
                "verdict": {"support_sufficient": False, "repeatable_gain": False},
            })
            continue

        train_frame = pd.DataFrame(train_rows)
        profile_model = _fit_logistic_newton(train_frame, list(PROFILE_NUMERIC))
        lean_model = _fit_logistic_newton(
            train_frame,
            list(PROFILE_NUMERIC) + list(RANK_NUMERIC) + list(LEAN_STATE_NUMERIC),
        )
        if profile_model.get("converged") is not True or lean_model.get("converged") is not True:
            folds.append({
                **fold_meta,
                "status": "FOLD_INCOMPLETE",
                "reason": "MODEL_NOT_CONVERGED",
                "profile_model_converged": bool(profile_model.get("converged")),
                "dynamic_lean_model_converged": bool(lean_model.get("converged")),
                "verdict": {"support_sufficient": False, "repeatable_gain": False},
            })
            continue

        profile_predictions, profile_counts = _predict_match_simulations(
            eval_ids,
            pairs,
            profile_model,
        )
        dynamic_predictions, dynamic_counts = _predict_dynamic_lean_simulations(
            eval_ids,
            pairs,
            profile_predictions,
            rank_context,
            lean_model,
        )
        comparison = _dynamic_lean_comparison(
            profile_predictions,
            dynamic_predictions,
            labels,
            prediction_counts=dynamic_counts,
            rank_counts=rank_counts,
            lean_model=lean_model,
        )
        verdict = fold_verdict(comparison)
        folds.append({
            **fold_meta,
            "status": "FOLD_COMPLETE",
            "profile_model_converged": True,
            "dynamic_lean_model_converged": True,
            "profile_prediction_counts": profile_counts,
            "dynamic_prediction_counts": dynamic_counts,
            "comparison": comparison,
            "verdict": verdict,
        })

        matched_ids = (
            set(profile_predictions)
            & set(dynamic_predictions)
            & set(labels)
        )
        for match_id in matched_ids:
            aggregate_profile[match_id] = profile_predictions[match_id]
            aggregate_dynamic[match_id] = dynamic_predictions[match_id]
            aggregate_labels[match_id] = labels[match_id]

    aggregate_comparison = _dynamic_lean_comparison(
        aggregate_profile,
        aggregate_dynamic,
        aggregate_labels,
        prediction_counts={"simulated": len(aggregate_dynamic)},
        rank_counts=rank_counts,
        lean_model={"converged": True},
    )
    summary = summarize_walk_forward(folds, aggregate_comparison)

    return {
        **base_report,
        "status": (
            "WALK_FORWARD_COMPLETE_NO_PROMOTION"
            if summary["completed_folds"] == REQUIRED_FOLDS
            else "WALK_FORWARD_INCOMPLETE_NO_PROMOTION"
        ),
        "signal": summary["signal"],
        "folds": folds,
        "aggregate": aggregate_comparison,
        "summary": summary,
    }


def build() -> dict[str, Any]:
    point_rows = list(_iter_jsonl_gz(POINTS) or ())
    profile_rows = list(_iter_jsonl_gz(PROFILES) or ())
    report = evaluate_walk_forward(point_rows, profile_rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": report.get("version"),
        "mode": report.get("mode"),
        "status": report.get("status"),
        "signal": report.get("signal"),
        "summary": report.get("summary"),
        "production_influence": report.get("production_influence"),
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
