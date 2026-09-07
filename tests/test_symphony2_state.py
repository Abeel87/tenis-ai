from backend.symphony2_state import build_outcomes, marginal_probability, joint_probability


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


def test_shared_state_distribution_is_normalized():
    outcomes = build_outcomes(_match())
    assert outcomes
    assert abs(sum(x["prob"] for x in outcomes) - 1.0) < 1e-9


def test_real_line_changes_probability():
    match = _match()
    outcomes = build_outcomes(match)
    p20 = marginal_probability(match, {"market": "match_total", "pick": "over", "line": 20.5}, outcomes)
    p24 = marginal_probability(match, {"market": "match_total", "pick": "over", "line": 24.5}, outcomes)
    assert p20 is not None and p24 is not None
    assert p20 >= p24


def test_joint_uses_same_states_not_independence_product():
    match = _match()
    outcomes = build_outcomes(match)
    legs = [
        {"market": "set1_total", "pick": "over", "line": 8.5},
        {"market": "set1_tiebreak", "pick": "no"},
    ]
    joint, supported = joint_probability(match, legs, outcomes)
    p1 = marginal_probability(match, legs[0], outcomes)
    p2 = marginal_probability(match, legs[1], outcomes)
    assert supported == 2
    assert joint is not None
    assert 0.0 <= joint <= min(p1, p2)
    # Correlated tennis events need not equal the independent product.
    assert abs(joint - p1 * p2) > 1e-6


def test_reordered_player_names_keep_winner_semantics():
    match = {
        "p1": "Dalibor Svrcina",
        "p2": "Luciano Darderi",
        "best_of": 3,
        "service_model": {"p1_hold": 0.78, "p2_hold": 0.74},
        "first_set_win": {"Svrcina, Dalibor": 0.56, "Darderi, Luciano": 0.44},
        "second_set_win": {"Svrcina, Dalibor": 0.55, "Darderi, Luciano": 0.45},
        "third_set_win": {"Svrcina, Dalibor": 0.54, "Darderi, Luciano": 0.46},
    }
    outcomes = build_outcomes(match)
    p1 = marginal_probability(match, {"market": "match_winner", "pick": "Svrcina, Dalibor"}, outcomes)
    p2 = marginal_probability(match, {"market": "match_winner", "pick": "Darderi, Luciano"}, outcomes)
    assert p1 is not None and p2 is not None
    assert abs((p1 + p2) - 1.0) < 1e-9


def test_unsupported_market_never_gets_fake_joint():
    match = _match()
    outcomes = build_outcomes(match)
    joint, supported = joint_probability(match, [
        {"market": "match_total", "pick": "over", "line": 20.5},
        {"market": "player_aces", "pick": "over", "line": 5.5, "player": "A"},
    ], outcomes)
    assert joint is None
    assert supported == 1



def test_master_plan_felix_style_builder_joint_comes_from_same_states():
    match = {
        **_match(),
        "p1": "Felix",
        "p2": "Opponent",
        "first_set_win": {"Felix": 0.56, "Opponent": 0.44},
        "second_set_win": {"Felix": 0.55, "Opponent": 0.45},
        "third_set_win": {"Felix": 0.54, "Opponent": 0.46},
    }
    outcomes = build_outcomes(match)
    legs = [
        {"market": "match_winner", "pick": "Felix"},
        {"market": "set1_total", "pick": "over", "line": 8.5},
        {"market": "set1_total", "pick": "under", "line": 12.5},
    ]

    joint, supported = joint_probability(match, legs, outcomes)
    marginals = [
        marginal_probability(match, leg, outcomes)
        for leg in legs
    ]
    expected = sum(
        row["prob"]
        for row in outcomes
        if row["winner"] == 1
        and sum(row["set1"]) > 8.5
        and sum(row["set1"]) < 12.5
    )

    assert supported == 3
    assert joint is not None
    assert abs(joint - expected) < 1e-12
    assert all(value is not None for value in marginals)
    independent_product = marginals[0] * marginals[1] * marginals[2]
    assert abs(joint - independent_product) > 1e-6
    assert joint <= min(marginals) + 1e-12


def test_nested_set1_lines_have_exact_redundant_joint():
    match = _match()
    outcomes = build_outcomes(match)
    loose = {"market": "set1_total", "pick": "over", "line": 8.5}
    strict = {"market": "set1_total", "pick": "over", "line": 9.5}

    joint, supported = joint_probability(match, [loose, strict], outcomes)
    strict_probability = marginal_probability(match, strict, outcomes)
    loose_probability = marginal_probability(match, loose, outcomes)

    assert supported == 2
    assert joint is not None
    assert strict_probability is not None
    assert loose_probability is not None
    # Over 9.5 is a strict subset of over 8.5, so adding the looser leg
    # contributes zero extra state information.
    assert abs(joint - strict_probability) < 1e-12
    assert strict_probability <= loose_probability


def test_conflicting_set1_lines_have_zero_exact_joint():
    match = _match()
    outcomes = build_outcomes(match)
    legs = [
        {"market": "set1_total", "pick": "over", "line": 9.5},
        {"market": "set1_total", "pick": "under", "line": 9.5},
    ]

    joint, supported = joint_probability(match, legs, outcomes)

    assert supported == 2
    assert joint is not None
    assert abs(joint) < 1e-15


def test_joint_probability_is_order_invariant_for_supported_legs():
    match = _match()
    outcomes = build_outcomes(match)
    legs = [
        {"market": "match_winner", "pick": "A"},
        {"market": "set1_total", "pick": "over", "line": 8.5},
        {"market": "set1_tiebreak", "pick": "no"},
    ]

    forward, supported_forward = joint_probability(match, legs, outcomes)
    reverse, supported_reverse = joint_probability(match, list(reversed(legs)), outcomes)

    assert supported_forward == supported_reverse == 3
    assert forward is not None and reverse is not None
    assert abs(forward - reverse) < 1e-12
