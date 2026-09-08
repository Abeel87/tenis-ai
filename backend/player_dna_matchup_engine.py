from __future__ import annotations

"""Canonical Phase-3 pre-match matchup packet for Player DNA.

This module separates the proven pre-match main-effect matchup inputs already
used by the Player DNA point scorer from optional nonlinear/context profile
families that have been audited but have not earned activation.

It is a composition boundary, not a new model. Current SHADOW scoring may consume
only scorer_feature_row. Diagnostic candidate interactions never alter the
prediction feature vector.

Phase-3 closure is evidence based: a proven profile/rank baseline is required,
and every non-robust optional interaction must remain excluded. The next phase
may then build the point-probability engine on this stable matchup contract.
"""

import json
import math
from pathlib import Path
from typing import Any

try:
    from backend.player_dna_point_scorer import PROFILE_NUMERIC
except ModuleNotFoundError:
    from player_dna_point_scorer import PROFILE_NUMERIC

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data" / "player_dna_phase3_matchup_engine.json"

VERSION = "player-dna-phase3-matchup-engine-v1"
MODE = "SHADOW_PHASE3_CANONICAL_MATCHUP"

REPORT_PATHS = {
    "point_scorer": ROOT / "frontend" / "data" / "player_dna_point_scorer.json",
    "serve_return_matchup": ROOT / "frontend" / "data" / "player_dna_matchup_challenger.json",
    "opponent_context": ROOT / "frontend" / "data" / "player_dna_opponent_adjustment_audit.json",
    "pressure": ROOT / "frontend" / "data" / "player_dna_pressure_challenger.json",
    "tiebreak": ROOT / "frontend" / "data" / "player_dna_tiebreak_challenger.json",
    "recent_form": ROOT / "frontend" / "data" / "player_dna_recent_form_challenger.json",
    "small_sample": ROOT / "frontend" / "data" / "player_dna_small_sample_challenger.json",
    "match_state": ROOT / "frontend" / "data" / "player_dna_match_state_challenger.json",
}

EXPECTED_PROFILE_NUMERIC = (
    "server_overall_serve_rate",
    "receiver_overall_return_rate",
    "server_surface_serve_rate",
    "receiver_surface_return_rate",
    "server_overall_matches",
    "receiver_overall_matches",
    "server_surface_matches",
    "receiver_surface_matches",
)


def _finite_rate(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        return None
    return number


def _prior(profile: dict[str, Any], key: str) -> dict[str, Any]:
    value = profile.get(key)
    return value if isinstance(value, dict) else {}


def _count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def scorer_feature_row(
    target: dict[str, Any],
    server_profile: dict[str, Any],
    receiver_profile: dict[str, Any],
) -> dict[str, Any]:
    """Return the exact proven pre-match profile feature row."""
    so = _prior(server_profile, "overall_prior")
    ro = _prior(receiver_profile, "overall_prior")
    ss = _prior(server_profile, "same_surface_prior")
    rs = _prior(receiver_profile, "same_surface_prior")
    best_of = target.get("best_of")
    return {
        "match_id": str(target.get("id")),
        "surface": str(target.get("surface") or "unknown").strip().lower(),
        "tour": str(target.get("tour") or "unknown").strip().upper(),
        "match_format": (
            f"BO{int(best_of)}"
            if isinstance(best_of, int) and not isinstance(best_of, bool)
            else "unknown"
        ),
        "server_overall_serve_rate": so.get("serve_win_rate"),
        "receiver_overall_return_rate": ro.get("return_win_rate"),
        "server_surface_serve_rate": ss.get("serve_win_rate"),
        "receiver_surface_return_rate": rs.get("return_win_rate"),
        "server_overall_matches": _count(so.get("matches")),
        "receiver_overall_matches": _count(ro.get("matches")),
        "server_surface_matches": _count(ss.get("matches")),
        "receiver_surface_matches": _count(rs.get("matches")),
    }


def _directional_diagnostics(feature_row: dict[str, Any]) -> dict[str, Any]:
    serve = _finite_rate(feature_row.get("server_overall_serve_rate"))
    return_rate = _finite_rate(feature_row.get("receiver_overall_return_rate"))
    surface_serve = _finite_rate(feature_row.get("server_surface_serve_rate"))
    surface_return = _finite_rate(feature_row.get("receiver_surface_return_rate"))

    overall_interaction = (
        serve * (1.0 - return_rate)
        if serve is not None and return_rate is not None
        else None
    )
    surface_interaction = (
        surface_serve * (1.0 - surface_return)
        if surface_serve is not None and surface_return is not None
        else None
    )
    supports = {
        "server_overall_matches": _count(feature_row.get("server_overall_matches")),
        "receiver_overall_matches": _count(feature_row.get("receiver_overall_matches")),
        "server_surface_matches": _count(feature_row.get("server_surface_matches")),
        "receiver_surface_matches": _count(feature_row.get("receiver_surface_matches")),
    }
    minimum_overall = min(
        supports["server_overall_matches"],
        supports["receiver_overall_matches"],
    )
    minimum_surface = min(
        supports["server_surface_matches"],
        supports["receiver_surface_matches"],
    )

    return {
        "main_effects": {
            "server_overall_serve_rate": serve,
            "receiver_overall_return_rate": return_rate,
            "server_surface_serve_rate": surface_serve,
            "receiver_surface_return_rate": surface_return,
        },
        "support": {
            **supports,
            "minimum_overall_prior_matches": minimum_overall,
            "minimum_same_surface_prior_matches": minimum_surface,
            "threshold_flags": {
                str(threshold): {
                    "overall": minimum_overall >= threshold,
                    "same_surface": minimum_surface >= threshold,
                }
                for threshold in (1, 3, 5, 10)
            },
        },
        "candidate_interactions_diagnostic_only": {
            "overall_serve_return_dominance": (
                round(overall_interaction, 8)
                if overall_interaction is not None
                else None
            ),
            "same_surface_serve_return_dominance": (
                round(surface_interaction, 8)
                if surface_interaction is not None
                else None
            ),
            "prediction_feature_activation_enabled": False,
        },
    }


def build_matchup_packet(
    target: dict[str, Any],
    p1_profile: dict[str, Any],
    p2_profile: dict[str, Any],
) -> dict[str, Any]:
    """Build one reciprocal pre-match matchup packet for a target match."""
    p1_serving = scorer_feature_row(target, p1_profile, p2_profile)
    p2_serving = scorer_feature_row(target, p2_profile, p1_profile)
    return {
        "version": VERSION,
        "mode": MODE,
        "match_id": str(target.get("id")),
        "strict_as_of_required": True,
        "same_time_matches_count_as_prior": False,
        "stable_provider_player_ids_only": True,
        "production_influence": False,
        "runtime_prediction_change": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "p1_serving": {
            "scorer_feature_row": p1_serving,
            "diagnostics": _directional_diagnostics(p1_serving),
        },
        "p2_serving": {
            "scorer_feature_row": p2_serving,
            "diagnostics": _directional_diagnostics(p2_serving),
        },
        "feature_contract": {
            "active_pre_match_profile_numeric": list(EXPECTED_PROFILE_NUMERIC),
            "nonlinear_serve_return_interaction_active": False,
            "opponent_strength_adjustment_active": False,
            "pressure_profile_interaction_active": False,
            "tiebreak_profile_interaction_active": False,
            "recent_form_interaction_active": False,
            "match_state_profile_interaction_active": False,
            "small_sample_shrinkage_active": False,
            "small_sample_shrinkage_waits_for_fresh_confirmation": True,
        },
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _signal_status(report: dict[str, Any]) -> str | None:
    signal = report.get("signal")
    if isinstance(signal, dict):
        status = signal.get("status")
        return str(status) if status is not None else None
    return None


def evaluate_phase3_reports(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    scorer = reports.get("point_scorer") or {}
    scorer_signal = scorer.get("signal") if isinstance(scorer.get("signal"), dict) else {}
    stateful_walk = (
        scorer.get("stateful_walk_forward")
        if isinstance(scorer.get("stateful_walk_forward"), dict)
        else {}
    )

    pre_match_base_signal = bool(
        scorer_signal.get("legacy_profile_signal_positive") is True
    )
    lean_stateful_robust = bool(
        stateful_walk.get(
            "lean_all_three_folds_positive_on_all_primary_proper_scores"
        )
        is True
    )

    excluded_candidates = {
        "serve_return_nonlinear": {
            "status": _signal_status(reports.get("serve_return_matchup") or {}),
            "active": False,
        },
        "opponent_strength": {
            "status": _signal_status(reports.get("opponent_context") or {}),
            "active": False,
        },
        "pressure_profiles": {
            "status": _signal_status(reports.get("pressure") or {}),
            "active": False,
        },
        "tiebreak_profiles": {
            "status": _signal_status(reports.get("tiebreak") or {}),
            "active": False,
        },
        "recent_form_l5": {
            "status": _signal_status(reports.get("recent_form") or {}),
            "active": False,
        },
    }

    match_state = reports.get("match_state") or {}
    match_tasks = match_state.get("tasks") if isinstance(match_state.get("tasks"), dict) else {}
    excluded_candidates["comeback_bo3"] = {
        "status": _signal_status(match_tasks.get("comeback_bo3") or {}),
        "active": False,
    }
    excluded_candidates["bo5_late_set_stamina_proxy"] = {
        "status": _signal_status(match_tasks.get("bo5_late_set") or {}),
        "active": False,
    }

    small_report = reports.get("small_sample") or {}
    small_status = _signal_status(small_report)
    shrinkage_fresh = (
        small_report.get("fresh_confirmation")
        if isinstance(small_report.get("fresh_confirmation"), dict)
        else {}
    )
    shrinkage_fresh_status = shrinkage_fresh.get("status")
    shrinkage_historical_robust = bool(
        small_status
        == "SMALL_SAMPLE_SHRINKAGE_ROBUST_HISTORICAL_SIGNAL_REQUIRES_FRESH_CONFIRMATION"
    )
    shrinkage_historical_rejected = bool(
        small_status == "SMALL_SAMPLE_SHRINKAGE_NOT_ROBUST_ENOUGH"
    )
    shrinkage_historical_resolved = bool(
        shrinkage_historical_robust or shrinkage_historical_rejected
    )
    shrinkage_fresh_confirmation_positive = bool(
        shrinkage_fresh_status == "FRESH_CONFIRMATION_POSITIVE_SHADOW"
    )
    shrinkage_activation_blocked = bool(
        shrinkage_historical_robust
        and not shrinkage_fresh_confirmation_positive
    )
    shrinkage_evidence_gate_satisfied = bool(
        shrinkage_historical_robust
        and shrinkage_fresh_confirmation_positive
    )
    # Small-sample shrinkage is an optional Phase-3 candidate. A resolved
    # historical rejection keeps it OFF and excluded; it must not invalidate
    # the already-proven baseline matchup core. Unknown/missing evidence still
    # fails closed.
    shrinkage_safe_for_phase3 = shrinkage_historical_resolved

    reports_present = {
        name: bool(report)
        for name, report in reports.items()
    }
    all_required_reports_present = all(
        reports_present.get(name, False)
        for name in REPORT_PATHS
    )

    phase3_complete = bool(
        all_required_reports_present
        and pre_match_base_signal
        and all(not row["active"] for row in excluded_candidates.values())
        and shrinkage_safe_for_phase3
    )

    return {
        "version": VERSION,
        "mode": MODE,
        "phase": "PHASE_3_MATCHUP_ENGINE",
        "status": (
            "PHASE3_COMPLETE_BASELINE_ONLY_OPTIONAL_INTERACTIONS_EXCLUDED"
            if phase3_complete
            else "PHASE3_GATE_NOT_COMPLETE"
        ),
        "phase3_complete": phase3_complete,
        "phase4_ready": phase3_complete,
        "reports_present": reports_present,
        "all_required_reports_present": all_required_reports_present,
        "approved_core": {
            "pre_match_profile_main_effects": pre_match_base_signal,
            "canonical_feature_vector": list(EXPECTED_PROFILE_NUMERIC),
            "lean_point_state_walk_forward_robust_for_phase4": lean_stateful_robust,
        },
        "excluded_optional_candidates": excluded_candidates,
        "small_sample_shrinkage": {
            "historical_status": small_status,
            "fresh_confirmation_status": shrinkage_fresh_status,
            "historically_rejected": shrinkage_historical_rejected,
            "fresh_confirmation_positive": shrinkage_fresh_confirmation_positive,
            "active": False,
            "blocked_pending_fresh_confirmation": shrinkage_activation_blocked,
            "fresh_confirmation_satisfied": shrinkage_evidence_gate_satisfied,
            "explicit_activation_required": shrinkage_evidence_gate_satisfied,
        },
        "production_influence": False,
        "runtime_prediction_change": False,
        "training_join_change": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "contract": {
            "single_canonical_matchup_feature_builder": True,
            "current_shadow_uses_same_pre_match_feature_contract": True,
            "failed_optional_interactions_are_not_composed_together": True,
            "no_post_hoc_interaction_screen": True,
            "historically_robust_shrinkage_still_requires_fresh_confirmation": True,
            "historically_non_robust_shrinkage_is_excluded_without_reopening_phase3": True,
            "historical_shrinkage_status_must_be_explicitly_resolved": True,
            "positive_fresh_confirmation_never_auto_activates_shrinkage": True,
            "positive_fresh_confirmation_does_not_reopen_phase3": True,
            "phase4_may_start_from_proven_main_effects_and_lean_score_state": True,
            "phase3_completion_does_not_promote_runtime_or_prod": True,
        },
        "note": (
            "Phase 3 closes by preserving the proven pre-match serve/return main "
            "effects and explicitly rejecting optional interaction families that "
            "failed robust historical gates. Small-sample shrinkage is optional: "
            "a non-robust historical result leaves it rejected and OFF without "
            "reopening the proven baseline gate. Positive fresh confirmation can "
            "satisfy its evidence gate only after robust historical evidence and "
            "never activates the feature automatically; activation still requires "
            "an explicit PR."
        ),
    }


def build() -> dict[str, Any]:
    if tuple(PROFILE_NUMERIC) != EXPECTED_PROFILE_NUMERIC:
        raise SystemExit(
            "canonical profile numeric drifted from Phase-3 matchup feature contract"
        )

    reports = {
        name: _read_json(path)
        for name, path in REPORT_PATHS.items()
    }
    report = evaluate_phase3_reports(reports)

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
                "phase3_complete": report["phase3_complete"],
                "phase4_ready": report["phase4_ready"],
                "approved_core": report["approved_core"],
                "small_sample_shrinkage": report["small_sample_shrinkage"],
            },
            ensure_ascii=False,
        )
    )
    return report


if __name__ == "__main__":
    build()
