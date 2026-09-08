from backend import symphony2_engine as engine
from backend.symphony2_state import build_player_dna_shared_outcomes


def _match():
    return {
        "p1": "A",
        "p2": "B",
        "best_of": 3,
        "service_model": {"p1_hold": 0.78, "p2_hold": 0.74},
        "first_set_win": {"A": 0.56, "B": 0.44},
        "second_set_win": {"A": 0.55, "B": 0.45},
        "third_set_win": {"A": 0.54, "B": 0.46},
    }


def test_phase10_three_leg_dependency_metrics_come_from_one_shared_state():
    match = _match()
    states = build_player_dna_shared_outcomes(match)
    legs = [
        {"market": "set1_winner", "pick": "A"},
        {"market": "set2_total", "pick": "over", "line": 8.5},
        {"market": "match_winner", "pick": "A"},
    ]

    report = engine._phase10_dependency_diagnostics(match, legs, states)

    assert report["status"] == "EXACT_PLAYER_DNA_DEPENDENCY_DIAGNOSTIC"
    assert report["legs"] == 3
    assert report["joint_source"] == "PLAYER_DNA_SINGLE_WHOLE_MATCH_SHARED_STATE"
    assert report["joint_probability"] is not None
    assert len(report["per_leg"]) == 3
    assert len(report["pairs"]) == 3
    assert all(
        row["conditional_probability_given_other_legs"] is not None
        for row in report["per_leg"]
    )
    assert any(
        row["marginal_information_gain_nats"] is not None
        for row in report["per_leg"]
    )
    assert report["weakest_state_leg_selection_id"]
    assert report["weakest_state_leg_joint_mass_removed_pp"] is not None
    assert report["independence_product_forbidden_as_joint"] is True
    assert report["threshold_classification_enabled"] is False


def test_phase10_exact_redundancy_and_conflict_are_mathematical_not_thresholded():
    match = _match()
    states = build_player_dna_shared_outcomes(match)

    redundant = engine._phase10_dependency_diagnostics(
        match,
        [
            {"market": "exact_match_score", "pick": "2:0"},
            {"market": "total_sets", "pick": "under", "line": 2.5},
        ],
        states,
    )
    conflict = engine._phase10_dependency_diagnostics(
        match,
        [
            {"market": "exact_match_score", "pick": "2:0"},
            {"market": "total_sets", "pick": "over", "line": 2.5},
        ],
        states,
    )

    redundant_pair = redundant["pairs"][0]
    conflict_pair = conflict["pairs"][0]

    assert redundant_pair["exact_containment"] is True
    assert abs(redundant_pair["redundancy_score"] - 1.0) < 1e-12
    assert redundant_pair["runtime_semantic_redundancy"] is True

    assert conflict_pair["exact_conflict"] is True
    assert abs(conflict_pair["conflict_score"] - 1.0) < 1e-12

    assert redundant["threshold_classification_enabled"] is False
    assert conflict["threshold_classification_enabled"] is False


def test_phase10_price_reaction_experiment_fails_closed_without_observations():
    report = engine._phase10_operator_price_reaction_experiment()

    assert report["status"] == "NOT_AVAILABLE_NO_OBSERVED_BUILDER_PRICE_DELTAS"
    assert report["observed_builder_price_delta_rows"] == 0
    assert report["used_as_truth_label"] is False
    assert report["used_for_model_training"] is False
    assert report["used_for_ranking"] is False
    assert report["gate_required"] is False


def test_phase10_gate_closes_without_runtime_or_playable_promotion():
    gate = engine.evaluate_phase10_gate({
        "phase9_complete": True,
        "phase10_ready": True,
    })

    assert gate["status"] == "PHASE10_DEPENDENCY_DIAGNOSTICS_COMPLETE_NO_PROMOTION"
    assert gate["phase10_complete"] is True
    assert gate["phase11_ready"] is True
    assert gate["evidence"]["exact_metrics_complete"] is True
    assert gate["evidence"]["redundancy_identified"] is True
    assert gate["evidence"]["conflict_identified"] is True
    assert gate["evidence"]["independence_product_not_used_as_joint"] is True

    assert gate["promotion_allowed_by_this_gate"] is False
    assert gate["production_influence"] is False
    assert gate["runtime_ranking_influence"] is False
    assert gate["operator_model_probability_influence"] is False
    assert gate["recommended_leg_count_influence"] is False
    assert gate["superbet_playable_influence"] is False
    assert gate["auto_promote"] is False


def test_phase10_current_offer_summary_is_shadow_only():
    match = _match()
    states = build_player_dna_shared_outcomes(match)
    scored = [
        {
            "market": "set1_winner",
            "pick": "A",
            "operator_model_probability": 64.0,
            "player_dna_shared_state_supported_shadow": True,
        },
        {
            "market": "set2_total",
            "pick": "over",
            "line": 8.5,
            "operator_model_probability": 62.0,
            "player_dna_shared_state_supported_shadow": True,
        },
        {
            "market": "match_winner",
            "pick": "A",
            "operator_model_probability": 66.0,
            "player_dna_shared_state_supported_shadow": True,
        },
    ]

    report = engine._phase10_shadow_dependency_summary(match, scored, states)

    assert report["status"] == "SHADOW_DEPENDENCY_DIAGNOSTICS_AVAILABLE"
    assert report["representative_pair"] is not None
    assert report["representative_triple"] is not None
    assert report["ranking_influence"] is False
    assert report["operator_model_probability_influence"] is False
    assert report["recommended_leg_count_influence"] is False
    assert report["production_influence"] is False
    assert report["playable_influence"] is False
    assert report["auto_promote"] is False
