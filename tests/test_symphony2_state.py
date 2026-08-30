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


def test_unsupported_market_never_gets_fake_joint():
    match = _match()
    outcomes = build_outcomes(match)
    joint, supported = joint_probability(match, [
        {"market": "match_total", "pick": "over", "line": 20.5},
        {"market": "player_aces", "pick": "over", "line": 5.5, "player": "A"},
    ], outcomes)
    assert joint is None
    assert supported == 1
