from backend.player_dna_phase14_lifecycle import evaluate_lifecycle


def _base_reports(*, hold_robust=False, prospective_robust=False, dynamic_robust=False):
    phase7 = {
        "phase7_complete": True,
        "promotion_evidence_sufficient": dynamic_robust,
        "promotion_verdict": (
            "PROMOTION_EVIDENCE_SUFFICIENT_FOR_AUDIT_REVIEW"
            if dynamic_robust
            else "EVIDENCE_INSUFFICIENT_NO_PROMOTION"
        ),
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
    }
    phase8 = {
        "phase8_complete": True,
        "status": "PHASE8_VALIDATION_COMPLETE_NO_PROMOTION",
        "production_influence": False,
        "runtime_switch_enabled": False,
        "playable_influence": False,
        "symphony_prod_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "summary": {
            "neural_review_candidates": [],
            "ensemble_review_candidates": [],
            "neural_global_promotion_authorized": False,
            "promotion_verdict": "NO_MODEL_CLASS_PROMOTION_EVIDENCE_REMAINS_SHADOW",
        },
    }
    phase9 = {
        "phase9_complete": True,
        "status": "PHASE9_SHARED_STATE_INTEGRATION_COMPLETE_NO_PROMOTION",
        "production_influence": False,
        "runtime_ranking_influence": False,
        "operator_model_probability_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
    }
    phase10 = {
        "phase10_complete": True,
        "status": "PHASE10_DEPENDENCY_DIAGNOSTICS_COMPLETE_NO_PROMOTION",
        "production_influence": False,
        "runtime_ranking_influence": False,
        "operator_model_probability_influence": False,
        "recommended_leg_count_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "operator_price_reaction_experiment": {
            "status": "NOT_AVAILABLE",
            "used_as_truth_label": False,
        },
    }
    phase12 = {
        "phase12_complete": True,
        "production_influence": False,
        "runtime_scoring_influence": False,
        "symphony2_ranking_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
    }
    phase13 = {
        "phase13_complete": True,
        "phase14_ready": True,
        "production_influence": False,
        "runtime_prediction_change": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "simulation": {"deterministic_seed_replay": True},
        "ci_runtime_cost": {"phase13_step_wall_seconds": 1.0},
    }
    hold_walk_forward = {
        "status": "WALK_FORWARD_COMPLETE_NO_INTEGRATION",
        "signal": (
            "HOLD_CALIBRATION_WALK_FORWARD_ROBUST_SHADOW"
            if hold_robust
            else "HOLD_CALIBRATION_WALK_FORWARD_NOT_YET_ROBUST"
        ),
        "aggregate": {"robust": hold_robust},
    }
    prospective = {
        "status": "PROSPECTIVE_COLLECTION_ACTIVE",
        "signal": (
            "PROSPECTIVE_DURATION_ROBUST_SHADOW"
            if prospective_robust
            else "COLLECTING_PROSPECTIVE_EVIDENCE"
        ),
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_integrate": False,
        "ledger_integrity": {"status": "LEDGER_INTEGRITY_OK"},
        "evidence_readiness": {
            "ready_for_performance_verdict": prospective_robust,
        },
        "counts": {"verdict_settled_snapshots": 200 if prospective_robust else 0},
        "dynamic_lean_evidence": {
            "source_contract_valid": True,
            "ledger_integrity": {"status": "LEDGER_INTEGRITY_OK"},
            "evidence_readiness": {
                "ready_for_performance_verdict": dynamic_robust,
            },
            "direct_segment_readiness": {
                "ready_for_performance_verdict": dynamic_robust,
            },
            "performance_verdict_emitted": dynamic_robust,
            "performance_verdict": {
                "signal": (
                    "DYNAMIC_LEAN_PROSPECTIVE_ROBUST_SHADOW"
                    if dynamic_robust
                    else "DYNAMIC_LEAN_PROSPECTIVE_VERDICT_NOT_READY"
                )
            },
            "signal": (
                "DYNAMIC_LEAN_PROSPECTIVE_EVIDENCE_READY_SHADOW"
                if dynamic_robust
                else "COLLECTING_DYNAMIC_LEAN_PROSPECTIVE_EVIDENCE"
            ),
            "counts": {},
        },
    }
    return {
        "phase7": phase7,
        "phase8": phase8,
        "phase9": phase9,
        "phase10": phase10,
        "phase12": phase12,
        "phase13": phase13,
        "hold_walk_forward": hold_walk_forward,
        "prospective": prospective,
    }


def test_phase14_closes_safely_even_when_current_evidence_keeps_shadow():
    report = evaluate_lifecycle(**_base_reports())

    assert report["phase14_complete"] is True
    assert report["master_plan_complete"] is True
    assert report["current_deployment_stage"] == "SHADOW"
    assert report["status"] == "PHASE14_LIFECYCLE_COMPLETE_KEEP_SHADOW"
    assert report["manual_canary_review_candidates"] == []
    assert report["canary_active"] is False
    assert report["prod_activation_performed"] is False
    assert report["auto_promote"] is False


def test_one_good_prospective_result_cannot_bypass_non_robust_walk_forward():
    reports = _base_reports(
        hold_robust=False,
        prospective_robust=True,
        dynamic_robust=False,
    )
    report = evaluate_lifecycle(**reports)

    lane = report["lanes"]["player_dna_hold_calibrated_simulator"]
    assert lane["manual_canary_review_eligible"] is False
    assert "hold_walk_forward_robust" in lane["blockers"]
    assert report["canary_active"] is False
    assert report["prod_activation_performed"] is False


def test_complete_existing_evidence_only_allows_manual_canary_review_not_activation():
    report = evaluate_lifecycle(
        **_base_reports(
            hold_robust=True,
            prospective_robust=True,
            dynamic_robust=True,
        )
    )

    assert "player_dna_hold_calibrated_simulator" in report[
        "manual_canary_review_candidates"
    ]
    assert "player_dna_dynamic_lean" in report[
        "manual_canary_review_candidates"
    ]
    assert report["manual_canary_review_available"] is True
    assert report["canary_active"] is False
    assert report["prod_activation_performed"] is False
    assert report["promotion_policy"]["audyt_to_canary"][
        "requires_manual_approval"
    ] is True
    assert report["promotion_policy"]["audyt_to_canary"][
        "phase14_itself_can_activate_canary"
    ] is False
    assert report["promotion_policy"]["canary_to_prod"][
        "phase14_itself_can_activate_prod"
    ] is False


def test_neuro_and_shared_state_fail_closed_without_separate_canary_gates():
    reports = _base_reports(
        hold_robust=True,
        prospective_robust=True,
        dynamic_robust=True,
    )
    reports["phase8"]["summary"]["neural_review_candidates"] = ["match_winner"]

    report = evaluate_lifecycle(**reports)

    neuro = report["lanes"]["neuro_model_class_challenger"]
    shared = report["lanes"]["symphony2_player_dna_shared_state"]
    assert neuro["manual_canary_review_eligible"] is False
    assert "separate_neuro_prospective_canary_gate_complete" in neuro["blockers"]
    assert shared["manual_canary_review_eligible"] is False
    assert (
        "separate_shared_state_ranking_canary_gate_complete"
        in shared["blockers"]
    )


def test_phase14_defines_explicit_rollback_without_new_numeric_thresholds():
    report = evaluate_lifecycle(**_base_reports())

    rollback = report["rollback"]
    assert rollback["required"] is True
    assert rollback["immutable_last_known_good_prod_reference_required"] is True
    assert "set_candidate_canary_traffic_to_zero" in rollback["canary_to_shadow"]
    assert (
        "restore_immutable_last_known_good_prod_artifact_and_routing"
        in rollback["prod_to_last_known_good"]
    )
    assert rollback["new_numeric_rollback_thresholds_introduced"] is False
    assert report["promotion_policy"]["new_thresholds_added_for_phase14"] is False
    assert report["promotion_policy"][
        "single_good_coupon_or_single_good_run_can_promote"
    ] is False
