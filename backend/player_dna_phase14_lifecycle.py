from __future__ import annotations

"""Canonical Phase-14 promotion lifecycle policy for Player DNA / simulator / Neuro.

This module closes the master-plan lifecycle without activating any candidate.
It composes evidence already produced by canonical SHADOW gates and reports
whether a bounded CANARY review may be requested manually. It never changes
runtime routing, PROD, Symphony 2.0, Superbet PLAYABLE, weights, or thresholds.
"""

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"
OUT = DATA / "player_dna_phase14_lifecycle.json"

PHASE7 = DATA / "player_dna_phase7_calibration_walk_forward.json"
PHASE8 = DATA / "neuro_shadow_phase8_challenger_walk_forward.json"
PHASE9 = DATA / "symphony2_phase9_player_dna_shared_state.json"
PHASE10 = DATA / "symphony2_phase10_bet_builder_dependency.json"
PHASE12 = DATA / "player_dna_phase12_master_regression.json"
PHASE13 = DATA / "player_dna_phase13_performance.json"
HOLD_WF = DATA / "player_dna_hold_walk_forward.json"
PROSPECTIVE = DATA / "player_dna_prospective_validation.json"

VERSION = "player-dna-phase14-promotion-lifecycle"
MODE = "PHASE14_PROMOTION_LIFECYCLE_POLICY_ONLY"
LIFECYCLE = ("OFFLINE", "SHADOW", "AUDYT", "CANARY", "PROD")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _all_false(source: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return all(source.get(key) is False for key in keys)


def _blockers(checks: dict[str, bool]) -> list[str]:
    return [name for name, ok in checks.items() if ok is not True]


def _lane(
    name: str,
    checks: dict[str, bool],
    *,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    blockers = _blockers(checks)
    ready = not blockers
    return {
        "name": name,
        "current_deployment_stage": "SHADOW",
        "audit_evidence_complete": ready,
        "manual_canary_review_eligible": ready,
        "canary_active": False,
        "prod_active": False,
        "auto_promote": False,
        "checks": checks,
        "blockers": blockers,
        "evidence": evidence,
        "status": (
            "AUDIT_READY_FOR_MANUAL_BOUNDED_CANARY_REVIEW"
            if ready
            else "KEEP_SHADOW_AND_COLLECT_EVIDENCE"
        ),
    }


def evaluate_lifecycle(
    *,
    phase7: dict[str, Any],
    phase8: dict[str, Any],
    phase9: dict[str, Any],
    phase10: dict[str, Any],
    phase12: dict[str, Any],
    phase13: dict[str, Any],
    hold_walk_forward: dict[str, Any],
    prospective: dict[str, Any],
) -> dict[str, Any]:
    phase_chain = {
        "phase7_complete": phase7.get("phase7_complete") is True,
        "phase8_complete": phase8.get("phase8_complete") is True,
        "phase9_complete": phase9.get("phase9_complete") is True,
        "phase10_complete": phase10.get("phase10_complete") is True,
        "phase12_complete": phase12.get("phase12_complete") is True,
        "phase13_complete": phase13.get("phase13_complete") is True,
        "phase14_ready": phase13.get("phase14_ready") is True,
    }

    isolation = {
        "phase7_isolated": _all_false(
            phase7,
            (
                "production_influence",
                "runtime_scoring_enabled",
                "symphony2_influence",
                "superbet_playable_influence",
                "auto_promote",
            ),
        ),
        "phase8_isolated": _all_false(
            phase8,
            (
                "production_influence",
                "runtime_switch_enabled",
                "playable_influence",
                "symphony_prod_influence",
                "superbet_playable_influence",
                "auto_promote",
            ),
        ),
        "phase9_isolated": _all_false(
            phase9,
            (
                "production_influence",
                "runtime_ranking_influence",
                "operator_model_probability_influence",
                "superbet_playable_influence",
                "auto_promote",
            ),
        ),
        "phase10_isolated": _all_false(
            phase10,
            (
                "production_influence",
                "runtime_ranking_influence",
                "operator_model_probability_influence",
                "recommended_leg_count_influence",
                "superbet_playable_influence",
                "auto_promote",
            ),
        ),
        "phase12_isolated": _all_false(
            phase12,
            (
                "production_influence",
                "runtime_scoring_influence",
                "symphony2_ranking_influence",
                "superbet_playable_influence",
                "auto_promote",
            ),
        ),
        "phase13_isolated": _all_false(
            phase13,
            (
                "production_influence",
                "runtime_prediction_change",
                "symphony2_influence",
                "superbet_playable_influence",
                "auto_promote",
            ),
        ),
        "hold_walk_forward_isolated": _all_false(
            hold_walk_forward,
            (
                "production_influence",
                "symphony2_influence",
                "superbet_playable_influence",
                "auto_integrate",
            ),
        ),
        "prospective_isolated": _all_false(
            prospective,
            (
                "production_influence",
                "symphony2_influence",
                "superbet_playable_influence",
                "auto_integrate",
            ),
        ),
    }

    prospective_integrity = (
        (prospective.get("ledger_integrity") or {}).get("status")
        == "LEDGER_INTEGRITY_OK"
    )
    deterministic = (
        ((phase13.get("simulation") or {}).get("deterministic_seed_replay"))
        is True
    )
    observability = bool(
        isinstance(
            ((phase13.get("ci_runtime_cost") or {}).get("phase13_step_wall_seconds")),
            (int, float),
        )
        and float(
            (phase13.get("ci_runtime_cost") or {}).get("phase13_step_wall_seconds")
            or 0.0
        )
        > 0.0
        and prospective.get("status") == "PROSPECTIVE_COLLECTION_ACTIVE"
        and prospective_integrity
    )

    common_ready = all(phase_chain.values()) and all(isolation.values())

    hold_aggregate = hold_walk_forward.get("aggregate") or {}
    hold_readiness = prospective.get("evidence_readiness") or {}
    hold_checks = {
        "technical_chain_complete": common_ready,
        "hold_walk_forward_complete": (
            hold_walk_forward.get("status")
            == "WALK_FORWARD_COMPLETE_NO_INTEGRATION"
        ),
        "hold_walk_forward_robust": hold_aggregate.get("robust") is True,
        "prospective_ledger_integrity": prospective_integrity,
        "prospective_sample_ready": (
            hold_readiness.get("ready_for_performance_verdict") is True
        ),
        "prospective_robust": (
            prospective.get("signal") == "PROSPECTIVE_DURATION_ROBUST_SHADOW"
        ),
        "deterministic_reproducibility": deterministic,
        "observability_available": observability,
    }
    hold_lane = _lane(
        "PLAYER_DNA_HOLD_CALIBRATED_SIMULATOR",
        hold_checks,
        evidence={
            "walk_forward_signal": hold_walk_forward.get("signal"),
            "walk_forward_robust": hold_aggregate.get("robust"),
            "prospective_signal": prospective.get("signal"),
            "prospective_counts": prospective.get("counts"),
        },
    )

    dynamic = prospective.get("dynamic_lean_evidence") or {}
    dynamic_readiness = dynamic.get("evidence_readiness") or {}
    dynamic_verdict = dynamic.get("performance_verdict") or {}
    dynamic_checks = {
        "technical_chain_complete": common_ready,
        "phase7_existing_promotion_evidence_sufficient": (
            phase7.get("promotion_evidence_sufficient") is True
        ),
        "dynamic_source_contract_valid": dynamic.get("source_contract_valid") is True,
        "dynamic_ledger_integrity": (
            (dynamic.get("ledger_integrity") or {}).get("status")
            == "LEDGER_INTEGRITY_OK"
        ),
        "dynamic_prospective_sample_ready": (
            dynamic_readiness.get("ready_for_performance_verdict") is True
        ),
        "dynamic_direct_segment_sample_ready": (
            (dynamic.get("direct_segment_readiness") or {}).get(
                "ready_for_performance_verdict"
            )
            is True
        ),
        "dynamic_prospective_verdict_emitted": (
            dynamic.get("performance_verdict_emitted") is True
        ),
        "dynamic_prospective_robust": (
            dynamic_verdict.get("signal")
            == "DYNAMIC_LEAN_PROSPECTIVE_ROBUST_SHADOW"
        ),
        "deterministic_reproducibility": deterministic,
        "observability_available": observability,
    }
    dynamic_lane = _lane(
        "PLAYER_DNA_DYNAMIC_LEAN",
        dynamic_checks,
        evidence={
            "phase7_promotion_verdict": phase7.get("promotion_verdict"),
            "prospective_signal": dynamic.get("signal"),
            "performance_verdict": dynamic_verdict,
            "counts": dynamic.get("counts"),
        },
    )

    phase8_summary = phase8.get("summary") or {}
    neural_review = list(phase8_summary.get("neural_review_candidates") or [])
    ensemble_review = list(phase8_summary.get("ensemble_review_candidates") or [])
    neuro_checks = {
        "technical_chain_complete": common_ready,
        "phase8_identical_fold_evaluation_complete": (
            phase8.get("status") == "PHASE8_VALIDATION_COMPLETE_NO_PROMOTION"
        ),
        "per_market_review_candidate_exists": bool(neural_review or ensemble_review),
        # Phase 8 explicitly authorizes audit review only. There is no separate
        # prospective bounded-canary evidence ledger for Neuro yet, therefore
        # Phase 14 must fail closed instead of interpreting one good fold/market
        # as a runtime promotion signal.
        "separate_neuro_prospective_canary_gate_complete": False,
    }
    neuro_lane = _lane(
        "NEURO_MODEL_CLASS_CHALLENGER",
        neuro_checks,
        evidence={
            "phase8_promotion_verdict": phase8_summary.get("promotion_verdict"),
            "neural_review_candidates": neural_review,
            "ensemble_review_candidates": ensemble_review,
            "global_neural_promotion_authorized": phase8_summary.get(
                "neural_global_promotion_authorized"
            ),
        },
    )

    price_experiment = phase10.get("operator_price_reaction_experiment") or {}
    shared_checks = {
        "technical_chain_complete": common_ready,
        "phase9_shared_state_complete": phase9.get("phase9_complete") is True,
        "phase10_dependency_diagnostics_complete": (
            phase10.get("phase10_complete") is True
        ),
        # Phase 9/10 are integration/diagnostic gates only. A separate
        # out-of-sample ranking-impact/canary gate is required before this
        # shared state may affect P_final, ranking, leg count or PLAYABLE.
        "separate_shared_state_ranking_canary_gate_complete": False,
    }
    shared_lane = _lane(
        "SYMPHONY2_PLAYER_DNA_SHARED_STATE",
        shared_checks,
        evidence={
            "phase9_status": phase9.get("status"),
            "phase10_status": phase10.get("status"),
            "operator_price_experiment_status": price_experiment.get("status"),
            "operator_price_used_as_truth": price_experiment.get(
                "used_as_truth_label"
            ),
        },
    )

    lanes = {
        "player_dna_hold_calibrated_simulator": hold_lane,
        "player_dna_dynamic_lean": dynamic_lane,
        "neuro_model_class_challenger": neuro_lane,
        "symphony2_player_dna_shared_state": shared_lane,
    }
    manual_canary_review_candidates = sorted(
        name
        for name, lane in lanes.items()
        if lane.get("manual_canary_review_eligible") is True
    )

    rollback = {
        "required": True,
        "immutable_last_known_good_prod_reference_required": True,
        "candidate_artifact_fingerprint_required": True,
        "canary_to_shadow": [
            "set_candidate_canary_traffic_to_zero",
            "disable_candidate_runtime_influence",
            "restore_shadow_only_collection",
            "leave_current_prod_reference_untouched",
            "preserve_evidence_for_postmortem",
        ],
        "prod_to_last_known_good": [
            "disable_candidate_runtime_influence",
            "restore_immutable_last_known_good_prod_artifact_and_routing",
            "verify_prod_health_and_exact_operator_line_guards",
            "return_candidate_to_shadow",
            "reopen_audit_before_any_new_canary",
        ],
        "rollback_triggers": [
            "any_existing_mandatory_gate_regresses",
            "walk_forward_or_calibration_gate_regresses",
            "provenance_or_semantic_contract_drift",
            "deterministic_replay_regresses",
            "observability_or_settlement_integrity_is_lost",
            "exact_current_superbet_line_or_playable_guard_regresses",
            "bounded_canary_evidence_regresses_against_its_frozen_baseline",
        ],
        "new_numeric_rollback_thresholds_introduced": False,
    }

    promotion_policy = {
        "lifecycle": list(LIFECYCLE),
        "offline_to_shadow": {
            "requires_unit_and_integration_tests": True,
            "requires_leakage_safe_chronology": True,
            "automatic_activation": False,
        },
        "shadow_to_audyt": {
            "requires_existing_validation_gates_complete": True,
            "requires_observability_and_reproducibility": True,
            "automatic_activation": False,
        },
        "audyt_to_canary": {
            "requires_lane_evidence_complete": True,
            "requires_manual_approval": True,
            "requires_bounded_canary_plan": True,
            "requires_frozen_baseline_and_candidate_fingerprint": True,
            "phase14_itself_can_activate_canary": False,
        },
        "canary_to_prod": {
            "requires_separate_canary_evidence": True,
            "requires_manual_approval": True,
            "requires_rollback_drill_confirmed": True,
            "requires_no_regression_in_existing_gates": True,
            "requires_old_active_pipeline_cleanup_plan": True,
            "phase14_itself_can_activate_prod": False,
        },
        "single_good_coupon_or_single_good_run_can_promote": False,
        "existing_thresholds_are_authoritative": True,
        "new_thresholds_added_for_phase14": False,
    }

    lifecycle_safety_complete = bool(
        common_ready
        and list(LIFECYCLE) == ["OFFLINE", "SHADOW", "AUDYT", "CANARY", "PROD"]
        and rollback.get("required") is True
        and promotion_policy["audyt_to_canary"]["requires_manual_approval"] is True
        and promotion_policy["canary_to_prod"]["requires_manual_approval"] is True
        and promotion_policy["single_good_coupon_or_single_good_run_can_promote"]
        is False
        and promotion_policy["new_thresholds_added_for_phase14"] is False
    )

    return {
        "version": VERSION,
        "mode": MODE,
        "status": (
            "PHASE14_LIFECYCLE_COMPLETE_KEEP_SHADOW"
            if lifecycle_safety_complete and not manual_canary_review_candidates
            else "PHASE14_LIFECYCLE_COMPLETE_MANUAL_CANARY_REVIEW_AVAILABLE"
            if lifecycle_safety_complete
            else "PHASE14_LIFECYCLE_INCOMPLETE"
        ),
        "phase": 14,
        "phase13_prerequisite_satisfied": (
            phase13.get("phase13_complete") is True
            and phase13.get("phase14_ready") is True
        ),
        "phase_chain": phase_chain,
        "isolation": isolation,
        "current_deployment_stage": "SHADOW",
        "lanes": lanes,
        "manual_canary_review_candidates": manual_canary_review_candidates,
        "manual_canary_review_available": bool(manual_canary_review_candidates),
        "canary_active": False,
        "prod_activation_performed": False,
        "production_influence": False,
        "runtime_switch_enabled": False,
        "symphony2_ranking_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "legacy_shadow_promotion_v942_authoritative": False,
        "canonical_promotion_authority":
            "backend/player_dna_phase14_lifecycle.py",
        "rollback": rollback,
        "promotion_policy": promotion_policy,
        "phase14_complete": lifecycle_safety_complete,
        "master_plan_complete": lifecycle_safety_complete,
        "contract": {
            "phase14_completion_means_safe_lifecycle_defined_not_model_promoted": True,
            "failed_or_incomplete_evidence_keeps_candidate_in_shadow": True,
            "manual_canary_review_is_not_canary_activation": True,
            "canary_activation_requires_separate_explicit_change": True,
            "prod_activation_requires_separate_explicit_change": True,
            "bookmaker_availability_never_deletes_model_math": True,
            "playable_exact_current_superbet_line_contract_unchanged": True,
            "nearest_line_substitution_forbidden": True,
            "player_dna_simulator_neuro_remain_shadow_without_separate_gate": True,
            "no_parallel_vxxx_promotion_authority_created": True,
        },
    }


def build() -> dict[str, Any]:
    report = evaluate_lifecycle(
        phase7=_read_json(PHASE7),
        phase8=_read_json(PHASE8),
        phase9=_read_json(PHASE9),
        phase10=_read_json(PHASE10),
        phase12=_read_json(PHASE12),
        phase13=_read_json(PHASE13),
        hold_walk_forward=_read_json(HOLD_WF),
        prospective=_read_json(PROSPECTIVE),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": report.get("status"),
        "phase14_complete": report.get("phase14_complete"),
        "master_plan_complete": report.get("master_plan_complete"),
        "current_deployment_stage": report.get("current_deployment_stage"),
        "manual_canary_review_candidates": report.get(
            "manual_canary_review_candidates"
        ),
        "canary_active": report.get("canary_active"),
        "prod_activation_performed": report.get("prod_activation_performed"),
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
