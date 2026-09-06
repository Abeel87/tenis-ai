from __future__ import annotations

"""First Phase-3 Matchup Engine challenger for Player DNA.

This SHADOW evaluator tests one predeclared nonlinear matchup interaction:
server overall serve strength multiplied by opponent return resistance.

The feature is derived only from canonical strict-as-of Player DNA rates already
used by the current scorer. It does not introduce a new data source, tune a
threshold, screen multiple interaction families, or change runtime behavior.
"""

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from backend.player_dna_point_scorer import (
        EVAL_MIN_PRIOR_MATCHES,
        LEAN_STATE_NUMERIC,
        POINTS,
        PROFILE_NUMERIC,
        PROFILES,
        RANK_NUMERIC,
        _cohort,
        _fit_candidate,
        _frame,
        _iter_jsonl_gz,
        _proper_score_gains,
        _walk_forward_slices,
        build_feature_rows,
        split_chronological_by_match,
    )
except ModuleNotFoundError:  # direct execution compatibility
    from player_dna_point_scorer import (
        EVAL_MIN_PRIOR_MATCHES,
        LEAN_STATE_NUMERIC,
        POINTS,
        PROFILE_NUMERIC,
        PROFILES,
        RANK_NUMERIC,
        _cohort,
        _fit_candidate,
        _frame,
        _iter_jsonl_gz,
        _proper_score_gains,
        _walk_forward_slices,
        build_feature_rows,
        split_chronological_by_match,
    )

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data" / "player_dna_matchup_challenger.json"

VERSION = "player-dna-matchup-challenger-v1"
MODE = "SHADOW_MATCHUP_CHALLENGER_EVAL_ONLY"
FEATURE_NAME = "server_overall_serve_return_dominance"
MATCHUP_NUMERIC = [FEATURE_NAME]


def _finite_rate(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        return None
    return number


def _matchup_feature(row: dict[str, Any]) -> float | None:
    serve = _finite_rate(row.get("server_overall_serve_rate"))
    opponent_return = _finite_rate(row.get("receiver_overall_return_rate"))
    if serve is None or opponent_return is None:
        return None
    # Nonlinear interaction. The base reference already sees serve and return
    # independently, so this term specifically asks whether their matchup adds
    # information beyond those main effects.
    return serve * (1.0 - opponent_return)


def enrich_feature_rows(
    point_rows: list[dict[str, Any]],
    profile_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, base_counts = build_feature_rows(point_rows, profile_rows)
    counts = Counter()
    enriched = []

    for row in rows:
        value = _matchup_feature(row)
        out = {**row, FEATURE_NAME: value}
        enriched.append(out)
        counts["rows"] += 1
        counts["rows_with_matchup_feature"] += int(value is not None)
        counts["rows_in_canonical_min3_cohort"] += int(
            int(row.get("server_overall_matches") or 0) >= EVAL_MIN_PRIOR_MATCHES
            and int(row.get("receiver_overall_matches") or 0) >= EVAL_MIN_PRIOR_MATCHES
        )
        counts["rows_in_min3_cohort_with_matchup_feature"] += int(
            value is not None
            and int(row.get("server_overall_matches") or 0) >= EVAL_MIN_PRIOR_MATCHES
            and int(row.get("receiver_overall_matches") or 0) >= EVAL_MIN_PRIOR_MATCHES
        )

    return enriched, {
        "base_join_counts": base_counts,
        "enrichment_counts": dict(counts),
    }


def _eligible(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in _cohort(rows, EVAL_MIN_PRIOR_MATCHES)
        if _finite_rate(row.get(FEATURE_NAME)) is not None
    ]


def _positive(gains: dict[str, float]) -> bool:
    return bool(
        gains["brier_gain"] > 0
        and gains["match_equal_brier_gain"] > 0
        and gains["log_loss_gain"] > 0
    )


def _evaluate_frames(train, test) -> dict[str, Any]:
    reference_numeric = (
        list(PROFILE_NUMERIC) + list(RANK_NUMERIC) + list(LEAN_STATE_NUMERIC)
    )
    candidate_numeric = reference_numeric + list(MATCHUP_NUMERIC)

    reference, _ = _fit_candidate(train, test, reference_numeric)
    candidate, _ = _fit_candidate(train, test, candidate_numeric)
    gains = _proper_score_gains(reference["metrics"], candidate["metrics"])
    return {
        "lean_stateful_reference": reference,
        "lean_stateful_plus_serve_return_matchup": candidate,
        "matchup_gains_vs_lean_stateful": gains,
        "positive_all_proper_scores": _positive(gains),
    }


def _walk_forward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    folds = []
    for train_rows, test_rows, meta in _walk_forward_slices(rows):
        train = _frame(_eligible(train_rows))
        test = _frame(_eligible(test_rows))
        enough = bool(
            not train.empty
            and not test.empty
            and len(train) >= 1000
            and len(test) >= 500
            and train["match_id"].nunique() >= 30
            and test["match_id"].nunique() >= 20
            and train["server_won"].nunique() == 2
            and test["server_won"].nunique() == 2
        )
        if not enough:
            folds.append({
                **meta,
                "status": "INSUFFICIENT_MATCHUP_FOLD_SAMPLE",
                "train_points": int(len(train)),
                "test_points": int(len(test)),
            })
            continue

        result = _evaluate_frames(train, test)
        folds.append({
            **meta,
            "status": (
                "POSITIVE_MATCHUP_FOLD"
                if result["positive_all_proper_scores"]
                else "MIXED_OR_NEGATIVE_MATCHUP_FOLD"
            ),
            "train_points": int(len(train)),
            "test_points": int(len(test)),
            **result,
        })

    completed = [f for f in folds if "matchup_gains_vs_lean_stateful" in f]
    positive = [f for f in completed if f.get("positive_all_proper_scores") is True]

    def mean_gain(name: str) -> float | None:
        values = [float(f["matchup_gains_vs_lean_stateful"][name]) for f in completed]
        return round(sum(values) / len(values), 6) if values else None

    return {
        "mode": "CANONICAL_EXPANDING_TRAIN_DISJOINT_WINDOWS",
        "folds": folds,
        "completed_folds": len(completed),
        "positive_folds": len(positive),
        "robust_positive_all_three_folds": bool(
            len(completed) == 3 and len(positive) == 3
        ),
        "mean_gains_vs_lean_stateful": {
            "brier_gain": mean_gain("brier_gain"),
            "match_equal_brier_gain": mean_gain("match_equal_brier_gain"),
            "log_loss_gain": mean_gain("log_loss_gain"),
        },
        "same_timestamp_groups_not_split": True,
        "test_windows_disjoint": True,
    }


def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    train_all, holdout_all, split = split_chronological_by_match(rows)
    train = _frame(_eligible(train_all))
    holdout = _frame(_eligible(holdout_all))

    enough = bool(
        not train.empty
        and not holdout.empty
        and len(train) >= 1000
        and len(holdout) >= 1000
        and train["match_id"].nunique() >= 30
        and holdout["match_id"].nunique() >= 20
        and train["server_won"].nunique() == 2
        and holdout["server_won"].nunique() == 2
    )

    report: dict[str, Any] = {
        "version": VERSION,
        "mode": MODE,
        "phase": "PHASE_3_MATCHUP_ENGINE",
        "label": "server_won",
        "split": split,
        "all_enriched_points": len(rows),
        "evaluation_min_prior_matches": EVAL_MIN_PRIOR_MATCHES,
        "train_points_after_matchup_gate": int(len(train)),
        "holdout_points_after_matchup_gate": int(len(holdout)),
        "matchup_numeric_features": list(MATCHUP_NUMERIC),
        "feature_formula": {
            FEATURE_NAME: (
                "server_overall_serve_rate * "
                "(1 - receiver_overall_return_rate)"
            )
        },
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "training_join_enabled": False,
        "canonical_profile_write_enabled": False,
        "simulator_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "promotion_gate": False,
        "candidate_may_replace_reference": False,
        "contract": {
            "single_predeclared_matchup_family_only": True,
            "primary_family": "overall_serve_vs_return_nonlinear_interaction",
            "uses_existing_canonical_profile_rates_only": True,
            "reference_already_contains_individual_serve_and_return_main_effects": True,
            "feature_is_nonlinear_interaction_not_linear_relabel": True,
            "same_surface_interaction_excluded_from_this_challenger": True,
            "hold_break_bp_early_game_tiebreak_interactions_excluded": True,
            "no_interaction_family_screen": True,
            "no_support_threshold_tuning": True,
            "uses_existing_scorer_min_prior_matches": True,
            "historical_success_requires_holdout_and_three_walk_forward_folds": True,
            "all_three_proper_scores_must_improve": True,
            "fresh_confirmation_required_before_any_activation": True,
        },
        "leakage_contract": {
            "canonical_strict_as_of_profiles_only": True,
            "same_timestamp_matches_never_count_as_prior": True,
            "stable_provider_player_ids_only": True,
            "target_point_outcome_not_used_in_matchup_feature": True,
            "matchup_feature_is_pre_match_only": True,
            "current_target_match_never_contributes_to_its_own_profile": True,
        },
        "signal": {
            "status": "NOT_EVALUATED",
            "positive_holdout": False,
            "robust_walk_forward": False,
            "fresh_confirmation_required": True,
            "candidate_may_replace_reference": False,
        },
    }

    if not enough:
        report["signal"]["status"] = "INSUFFICIENT_MATCHUP_SHADOW_SAMPLE"
        return report

    holdout_result = _evaluate_frames(train, holdout)
    walk_forward = _walk_forward(rows)
    holdout_positive = bool(holdout_result["positive_all_proper_scores"])
    robust = bool(walk_forward["robust_positive_all_three_folds"])

    report["holdout"] = holdout_result
    report["walk_forward"] = walk_forward
    report["signal"] = {
        "status": (
            "SERVE_RETURN_MATCHUP_ROBUST_HISTORICAL_SIGNAL_REQUIRES_FRESH_CONFIRMATION"
            if holdout_positive and robust
            else "SERVE_RETURN_MATCHUP_NOT_ROBUST_ENOUGH"
        ),
        "positive_holdout": holdout_positive,
        "robust_walk_forward": robust,
        "fresh_confirmation_required": True,
        "candidate_may_replace_reference": False,
        "promotion_gate": False,
    }
    return report


def build() -> dict[str, Any]:
    point_rows = list(_iter_jsonl_gz(POINTS) or ())
    profile_rows = list(_iter_jsonl_gz(PROFILES) or ())
    rows, build_counts = enrich_feature_rows(point_rows, profile_rows)
    report = evaluate(rows)
    report["build_counts"] = build_counts

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
