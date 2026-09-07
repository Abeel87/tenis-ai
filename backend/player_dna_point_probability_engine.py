from __future__ import annotations

"""Canonical Phase-4 point probability engine for Player DNA.

The canonical SHADOW point model is the already-validated interpretable logistic
baseline built from:
- Phase-3 pre-match serve/return main effects,
- provider ranking context,
- the validated lean pre-point score-state family.

This module is a composition and API boundary, not a new post-hoc model family.
It intentionally excludes feature families that did not pass robust historical
gates: nonlinear matchup interactions, opponent adjustment, pressure-profile
families, tiebreak-profile families, recent form and match-state profile effects.

Output contract:
    P(server wins next point | pre-match matchup, provider rank, legal pre-point
    standard-game score state)

Tiebreak point probability remains outside this engine because the validated lean
state adapter explicitly excludes tiebreak state. Current simulator behavior keeps
its separate neutral/profile-based tiebreak policy until a tiebreak family earns
its own gate.
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from backend.player_dna_matchup_engine import (
        EXPECTED_PROFILE_NUMERIC,
        scorer_feature_row,
    )
    from backend.player_dna_point_scorer import (
        LEAN_STATE_NUMERIC,
        PROFILE_NUMERIC,
        RANK_NUMERIC,
        _fit_logistic_newton,
        _model_meta,
        lean_state_features_from_simulation_state,
        predict_logistic_row,
    )
except ModuleNotFoundError:  # direct execution compatibility
    from player_dna_matchup_engine import (
        EXPECTED_PROFILE_NUMERIC,
        scorer_feature_row,
    )
    from player_dna_point_scorer import (
        LEAN_STATE_NUMERIC,
        PROFILE_NUMERIC,
        RANK_NUMERIC,
        _fit_logistic_newton,
        _model_meta,
        lean_state_features_from_simulation_state,
        predict_logistic_row,
    )

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data" / "player_dna_phase4_point_probability_engine.json"
PHASE3_REPORT = ROOT / "frontend" / "data" / "player_dna_phase3_matchup_engine.json"
POINT_SCORER_REPORT = ROOT / "frontend" / "data" / "player_dna_point_scorer.json"

VERSION = "player-dna-phase4-point-probability-engine-v1"
MODE = "SHADOW_PHASE4_POINT_PROBABILITY_ENGINE"

POINT_PROBABILITY_NUMERIC = tuple(
    list(PROFILE_NUMERIC) + list(RANK_NUMERIC) + list(LEAN_STATE_NUMERIC)
)

EXPECTED_POINT_PROBABILITY_NUMERIC = tuple(
    list(EXPECTED_PROFILE_NUMERIC)
    + ["server_rank", "receiver_rank"]
    + list(LEAN_STATE_NUMERIC)
)


def _target_from_profile(profile: dict[str, Any]) -> dict[str, Any]:
    fmt = str(profile.get("target_format") or "").strip().upper()
    if fmt == "BO5":
        best_of = 5
    elif fmt == "BO3":
        best_of = 3
    else:
        best_of = None

    return {
        "id": profile.get("target_match_id"),
        "surface": profile.get("target_surface"),
        "tour": profile.get("target_tour"),
        "best_of": best_of,
    }


def prematch_feature_with_rank(
    server_profile: dict[str, Any],
    receiver_profile: dict[str, Any],
    *,
    server_rank: float | None,
    receiver_rank: float | None,
) -> dict[str, Any]:
    """Build canonical Phase-3 pre-match main effects plus provider rank."""
    row = scorer_feature_row(
        _target_from_profile(server_profile),
        server_profile,
        receiver_profile,
    )
    row.pop("match_id", None)
    row["server_rank"] = server_rank
    row["receiver_rank"] = receiver_rank
    return row


def point_probability_feature_row_from_prematch(
    prematch_row: dict[str, Any],
    simulation_state: dict[str, Any],
) -> dict[str, Any]:
    """Add the validated lean pre-point score state to a canonical pre-match row."""
    return {
        **prematch_row,
        **lean_state_features_from_simulation_state(simulation_state),
    }


def point_probability_feature_row(
    server_profile: dict[str, Any],
    receiver_profile: dict[str, Any],
    *,
    server_rank: float | None,
    receiver_rank: float | None,
    simulation_state: dict[str, Any],
) -> dict[str, Any]:
    """Build one legal pre-point Phase-4 feature row.

    The state adapter accepts standard-game states only and raises on tiebreak or
    malformed tennis state, preserving the scorer's validated lean-state contract.
    """
    return point_probability_feature_row_from_prematch(
        prematch_feature_with_rank(
            server_profile,
            receiver_profile,
            server_rank=server_rank,
            receiver_rank=receiver_rank,
        ),
        simulation_state,
    )


def fit_point_probability_model(training: pd.DataFrame) -> dict[str, Any]:
    """Fit the exact canonical Phase-4 logistic baseline."""
    if tuple(PROFILE_NUMERIC) != EXPECTED_PROFILE_NUMERIC:
        raise ValueError("Phase-3 profile feature vector drifted")
    if POINT_PROBABILITY_NUMERIC != EXPECTED_POINT_PROBABILITY_NUMERIC:
        raise ValueError("Phase-4 point probability feature vector drifted")
    if training.empty:
        raise ValueError("Phase-4 training frame is empty")
    if "server_won" not in training:
        raise ValueError("Phase-4 training frame is missing server_won label")

    model = _fit_logistic_newton(
        training,
        list(POINT_PROBABILITY_NUMERIC),
    )
    return model


def predict_server_point_probability(
    model: dict[str, Any],
    feature_row: dict[str, Any],
) -> float:
    """Predict P(server wins next standard-game point)."""
    if model.get("converged") is not True:
        raise ValueError("Phase-4 point probability model did not converge")
    value = float(predict_logistic_row(model, feature_row))
    if not 0.0 <= value <= 1.0:
        raise ValueError("Phase-4 point probability escaped [0,1]")
    return value


def model_summary(model: dict[str, Any]) -> dict[str, Any]:
    meta = _model_meta(model)
    return {
        "version": VERSION,
        "mode": MODE,
        "feature_numeric": list(POINT_PROBABILITY_NUMERIC),
        "fit": meta,
        "standard_game_only": True,
        "tiebreak_probability_policy_external": True,
        "production_influence": False,
        "runtime_switch_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
    }


def support_diagnostics(
    server_profile: dict[str, Any],
    receiver_profile: dict[str, Any],
) -> dict[str, Any]:
    so = (
        server_profile.get("overall_prior")
        if isinstance(server_profile.get("overall_prior"), dict)
        else {}
    )
    ro = (
        receiver_profile.get("overall_prior")
        if isinstance(receiver_profile.get("overall_prior"), dict)
        else {}
    )
    ss = (
        server_profile.get("same_surface_prior")
        if isinstance(server_profile.get("same_surface_prior"), dict)
        else {}
    )
    rs = (
        receiver_profile.get("same_surface_prior")
        if isinstance(receiver_profile.get("same_surface_prior"), dict)
        else {}
    )

    def count(value: Any) -> int:
        if isinstance(value, bool):
            return 0
        try:
            number = int(value)
        except (TypeError, ValueError):
            return 0
        return max(0, number)

    overall = min(count(so.get("matches")), count(ro.get("matches")))
    same_surface = min(count(ss.get("matches")), count(rs.get("matches")))
    return {
        "server_overall_prior_matches": count(so.get("matches")),
        "receiver_overall_prior_matches": count(ro.get("matches")),
        "server_same_surface_prior_matches": count(ss.get("matches")),
        "receiver_same_surface_prior_matches": count(rs.get("matches")),
        "minimum_overall_prior_matches": overall,
        "minimum_same_surface_prior_matches": same_surface,
        "support_flags": {
            str(threshold): {
                "overall": overall >= threshold,
                "same_surface": same_surface >= threshold,
            }
            for threshold in (1, 3, 5, 10)
        },
        "uncertainty_classification_enabled": False,
        "raw_support_exposed_instead_of_arbitrary_confidence_bucket": True,
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def evaluate_phase4_reports(
    phase3: dict[str, Any],
    point_scorer: dict[str, Any],
) -> dict[str, Any]:
    signal = (
        point_scorer.get("signal")
        if isinstance(point_scorer.get("signal"), dict)
        else {}
    )
    walk = (
        point_scorer.get("stateful_walk_forward")
        if isinstance(point_scorer.get("stateful_walk_forward"), dict)
        else {}
    )
    lean_comparison = (
        point_scorer.get("lean_stateful_comparison")
        if isinstance(point_scorer.get("lean_stateful_comparison"), dict)
        else {}
    )
    state_contract = (
        point_scorer.get("stateful_context_contract")
        if isinstance(point_scorer.get("stateful_context_contract"), dict)
        else {}
    )

    phase3_ready = bool(
        phase3.get("phase3_complete") is True
        and phase3.get("phase4_ready") is True
    )
    holdout_positive = bool(
        signal.get(
            "lean_stateful_improves_profile_plus_rank_on_all_primary_proper_scores"
        )
        is True
    )
    robust_walk_forward = bool(
        walk.get(
            "lean_all_three_folds_positive_on_all_primary_proper_scores"
        )
        is True
    )
    lean_superior_to_full = bool(
        walk.get("lean_superior_to_full_on_all_three_folds") is True
    )
    score_before_only = bool(
        state_contract.get("features_use_score_before_only") is True
        and state_contract.get("score_after_used_as_feature") is False
        and state_contract.get("current_point_winner_used_as_feature") is False
    )

    dropped_groups = list(state_contract.get("lean_dropped_state_groups") or [])
    expected_dropped = ["tiebreak_context", "prior_momentum"]
    dropped_contract_ok = dropped_groups == expected_dropped
    feature_contract_ok = bool(
        list(state_contract.get("lean_state_numeric_features") or [])
        == list(LEAN_STATE_NUMERIC)
        and int(lean_comparison.get("lean_feature_count") or 0)
        == len(LEAN_STATE_NUMERIC)
    )

    phase4_complete = bool(
        phase3_ready
        and holdout_positive
        and robust_walk_forward
        and lean_superior_to_full
        and score_before_only
        and dropped_contract_ok
        and feature_contract_ok
        and tuple(PROFILE_NUMERIC) == EXPECTED_PROFILE_NUMERIC
        and POINT_PROBABILITY_NUMERIC == EXPECTED_POINT_PROBABILITY_NUMERIC
    )

    return {
        "version": VERSION,
        "mode": MODE,
        "phase": "PHASE_4_POINT_PROBABILITY_ENGINE",
        "status": (
            "PHASE4_COMPLETE_CANONICAL_LEAN_LOGISTIC_BASELINE"
            if phase4_complete
            else "PHASE4_GATE_NOT_COMPLETE"
        ),
        "phase4_complete": phase4_complete,
        "phase5_ready": phase4_complete,
        "phase3_ready": phase3_ready,
        "point_probability_target": (
            "P(server_wins_next_standard_game_point | "
            "serve_return_main_effects, provider_rank, pre_point_lean_score_state)"
        ),
        "canonical_numeric_features": list(POINT_PROBABILITY_NUMERIC),
        "evidence": {
            "holdout_positive_all_primary_proper_scores": holdout_positive,
            "robust_three_fold_walk_forward": robust_walk_forward,
            "lean_superior_to_full_stateful_three_of_three": lean_superior_to_full,
            "score_before_only": score_before_only,
            "feature_contract_exact": feature_contract_ok,
            "dropped_state_groups_exact": dropped_contract_ok,
        },
        "excluded_until_separate_gate": {
            "tiebreak_state": True,
            "prior_momentum": True,
            "recent_form_l5": True,
            "opponent_adjustment": True,
            "nonlinear_serve_return_interaction": True,
            "pressure_profile_interactions": True,
            "tiebreak_profile_interactions": True,
            "comeback_match_state_profiles": True,
            "bo5_stamina_match_state_profiles": True,
            "first_second_serve_return_split_scoring": True,
            "neural_network": True,
        },
        "uncertainty_policy": {
            "raw_support_counts_required": True,
            "arbitrary_confidence_bucket_forbidden": True,
            "small_sample_shrinkage_active": False,
            "small_sample_shrinkage_waits_for_fresh_confirmation": True,
        },
        "production_influence": False,
        "runtime_switch_enabled": False,
        "training_pipeline_replaced": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "contract": {
            "single_canonical_point_probability_api": True,
            "interpretable_logistic_baseline_first": True,
            "phase3_matchup_contract_is_input": True,
            "provider_rank_context_is_input": True,
            "pre_point_lean_score_state_only": True,
            "no_score_after_feature": True,
            "no_current_point_outcome_feature": True,
            "tiebreak_policy_remains_external_until_validated": True,
            "unproven_optional_families_are_not_composed": True,
            "phase4_completion_does_not_promote_runtime_or_prod": True,
        },
        "note": (
            "Phase 4 closes the canonical SHADOW point-probability API around "
            "the already robust lean logistic baseline. It does not add a new "
            "model family or activate unvalidated feature groups."
        ),
    }


def build() -> dict[str, Any]:
    if tuple(PROFILE_NUMERIC) != EXPECTED_PROFILE_NUMERIC:
        raise SystemExit("Phase-3 profile feature vector drifted")
    if POINT_PROBABILITY_NUMERIC != EXPECTED_POINT_PROBABILITY_NUMERIC:
        raise SystemExit("Phase-4 point probability feature vector drifted")

    report = evaluate_phase4_reports(
        _read_json(PHASE3_REPORT),
        _read_json(POINT_SCORER_REPORT),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "version": report["version"],
                "status": report["status"],
                "phase4_complete": report["phase4_complete"],
                "phase5_ready": report["phase5_ready"],
                "evidence": report["evidence"],
            },
            ensure_ascii=False,
        )
    )
    return report


if __name__ == "__main__":
    build()
