import math

from backend.symphony2_engine import (
    _best_compositions,
    _composition_dependency_diagnostics,
    _composition_utility,
    _selection_id,
)
from backend.symphony2_state import build_outcomes, joint_probability


def _match():
    return {
        "p1": "Alpha",
        "p2": "Beta",
        "best_of": 3,
        "service_model": {"p1_hold": 0.79, "p2_hold": 0.73},
        "first_set_win": {"Alpha": 0.59, "Beta": 0.41},
        "second_set_win": {"Alpha": 0.57, "Beta": 0.43},
        "third_set_win": {"Alpha": 0.55, "Beta": 0.45},
    }


def _row(market, pick, probability, **extra):
    return {
        "selection_id": f"{market}|{pick}",
        "market": market,
        "pick": pick,
        "operator_model_probability": probability,
        "learning_support_rows": 500,
        "state_supported": True,
        **extra,
    }


def test_exact_state_diagnostics_expose_implication_without_classifying_it():
    match = _match()
    outcomes = build_outcomes(match)
    winner = _row("match_winner", "Alpha", 68.0)
    exact = _row("exact_match_score", "2:0", 58.0)
    combo = (winner, exact)

    joint, supported = joint_probability(match, list(combo), outcomes)
    assert joint is not None and supported == 2

    diagnostics = _composition_dependency_diagnostics(
        match,
        combo,
        joint,
        outcomes,
    )

    assert diagnostics["status"] == "EXACT_SHARED_STATE_DIAGNOSTIC_ONLY"
    assert diagnostics["ranking_influence"] is False
    assert diagnostics["threshold_classification_enabled"] is False
    assert len(diagnostics["per_leg"]) == 2
    assert len(diagnostics["pairs"]) == 1

    winner_diag = next(
        row
        for row in diagnostics["per_leg"]
        if row["selection_id"] == _selection_id(winner)
    )
    # Exact 2:0 already implies Alpha wins. The winner leg therefore removes
    # zero additional state mass when the exact-score leg is already present.
    assert winner_diag["conditional_probability_given_other_legs"] == 100.0
    assert winner_diag["joint_mass_removed_by_leg_pp"] == 0.0
    assert math.isclose(
        winner_diag["conditional_information_nats"],
        0.0,
        abs_tol=1e-12,
    )

    pair = diagnostics["pairs"][0]
    assert pair["overlap_of_smaller_leg"] == 1.0
    assert pair["redundancy_score"] == 1.0
    assert pair["conflict_score"] == 0.0
    assert pair["score_semantics"] == "NORMALIZED_EXACT_PAIR_OVERLAP_AXIS"
    assert pair["exact_pair_joint_probability"] > 0.0
    assert winner_diag["marginal_information_gain_nats"] == winner_diag["conditional_information_nats"]


def test_dependency_diagnostics_do_not_change_composition_utility_or_selection():
    match = _match()
    outcomes = build_outcomes(match)
    scored = [
        _row("match_winner", "Alpha", 68.0),
        _row("exact_match_score", "2:0", 58.0),
    ]

    joint, supported = joint_probability(match, scored, outcomes)
    assert joint is not None and supported == 2
    expected_score = round(_composition_utility(tuple(scored), joint), 2)

    compositions = _best_compositions(match, scored, outcomes)

    assert set(compositions) == {"2"}
    selected = compositions["2"]
    assert selected["score"] == expected_score
    assert selected["joint_status"] == "EXACT_SHARED_STATE"
    assert selected["dependency_diagnostics"]["ranking_influence"] is False
    assert {
        row["selection_id"]
        for row in selected["dependency_diagnostics"]["per_leg"]
    } == {_selection_id(row) for row in scored}



def test_mutually_exclusive_pair_has_full_conflict_score():
    match = _match()
    outcomes = build_outcomes(match)
    over = _row("set1_total", "over", 60.0, line=9.5)
    under = _row("set1_total", "under", 60.0, line=9.5)
    combo = (over, under)

    joint, supported = joint_probability(match, list(combo), outcomes)
    assert joint is not None and supported == 2
    assert abs(joint) < 1e-15

    diagnostics = _composition_dependency_diagnostics(
        match,
        combo,
        joint,
        outcomes,
    )

    pair = diagnostics["pairs"][0]
    assert pair["redundancy_score"] == 0.0
    assert pair["conflict_score"] == 1.0
    assert pair["exact_pair_joint_probability"] == 0.0
    assert diagnostics["threshold_classification_enabled"] is False


def test_weakest_leg_impact_is_exposed_without_affecting_ranking():
    match = _match()
    outcomes = build_outcomes(match)
    winner = _row("match_winner", "Alpha", 68.0)
    total = _row("match_total", "over", 57.0, line=20.5)
    combo = (winner, total)

    joint, supported = joint_probability(match, list(combo), outcomes)
    assert joint is not None and supported == 2

    diagnostics = _composition_dependency_diagnostics(
        match,
        combo,
        joint,
        outcomes,
    )

    assert diagnostics["weakest_supervised_leg_selection_id"] == _selection_id(total)
    assert diagnostics["weakest_supervised_leg_joint_mass_removed_pp"] is not None
    assert diagnostics["dependency_score_semantics"]["thresholds_enabled"] is False
    assert diagnostics["ranking_influence"] is False

def test_best_compositions_rejects_exact_zero_cross_market_conflict():
    match = _match()
    outcomes = build_outcomes(match)
    scored = [
        _row("match_winner", "Alpha", 68.0),
        _row("p1_wins_a_set", "no", 60.0, player="Alpha"),
    ]

    joint, supported = joint_probability(match, scored, outcomes)
    assert joint is not None and supported == 2
    assert joint == 0.0

    compositions = _best_compositions(match, scored, outcomes)

    assert compositions == {}
