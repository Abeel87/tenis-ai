from backend.symphony_engine_v90 import (
    Candidate,
    _build_outcomes,
    _compatible,
    _joint,
    _predicate,
    build_match_symphony,
)


def _c(key, market, pick, score=80.0, line=None, checkpoint=None):
    return Candidate(
        key=key,
        label=key,
        market=market,
        pick=pick,
        line=line,
        checkpoint=checkpoint,
        prod_score=score,
        shadow_scores={},
        path_probability=None,
        evidence_score=score,
        agreement=0.8,
        conflict=0.0,
    )


def test_exact_states_same_checkpoint_conflict():
    a = _c("a", "game_state", "3:1", checkpoint=4)
    b = _c("b", "game_state", "2:2", checkpoint=4)
    assert _compatible(a, b) is False


def test_three_three_after_six_blocks_under_8_5():
    a = _c("a", "game_state", "3:3", checkpoint=6)
    b = _c("b", "set1_total", "under", line=8.5)
    assert _compatible(a, b) is False


def test_three_three_after_six_allows_over_8_5():
    a = _c("a", "game_state", "3:3", checkpoint=6)
    b = _c("b", "set1_total", "over", line=8.5)
    assert _compatible(a, b) is True


def _match_with_service():
    return {
        "id": 1,
        "p1": "A",
        "p2": "B",
        "best_of": 3,
        "service_model": {"p1_hold": 82, "p2_hold": 78},
        "first_set_win": {"A": 64, "B": 36},
        "autolearn_v84": {
            "signals": [
                {"key": "state|2|1:1", "market": "game_state", "checkpoint": 2, "pick": "1:1", "ensemble": 79},
                {"key": "state|4|2:2", "market": "game_state", "checkpoint": 4, "pick": "2:2", "ensemble": 75},
                {"key": "state|6|3:3", "market": "game_state", "checkpoint": 6, "pick": "3:3", "ensemble": 72},
                {"key": "set1_total|8.5|over", "market": "set1_total", "pick": "over", "line": 8.5, "ensemble": 81},
                {"key": "set1|A", "market": "set1_winner", "pick": "A", "ensemble": 78},
                {"key": "winner|A", "market": "match_winner", "pick": "A", "ensemble": 82},
            ]
        },
    }


def test_exact_outcomes_sum_to_one_and_include_full_match_state():
    outcomes = _build_outcomes(_match_with_service())
    assert outcomes
    assert abs(sum(x["prob"] for x in outcomes) - 1.0) < 1e-9
    assert all("cp2" in x and "cp4" in x and "cp6" in x for x in outcomes)
    assert all(x["sets"] in {(2, 0), (2, 1), (0, 2), (1, 2)} for x in outcomes)


def test_joint_probability_uses_same_exact_paths():
    match = _match_with_service()
    outcomes = _build_outcomes(match)
    legs = [
        _c("state|6|3:3", "game_state", "3:3", checkpoint=6),
        _c("set1_total|8.5|over", "set1_total", "over", line=8.5),
    ]
    joint, supported = _joint(outcomes, [_predicate(match, x) for x in legs])
    assert supported == 2
    assert joint is not None and joint > 0
    # 3:3 after six logically implies over 8.5, so adding over cannot lower this joint.
    state_only, _ = _joint(outcomes, [_predicate(match, legs[0])])
    assert abs(joint - state_only) < 1e-12


def test_shadow_support_does_not_replace_prod_contract():
    match = _match_with_service()
    shadow = {
        "winner|A": {"catboost_player": 90, "ensemble_player": 88},
        "set1|A": {"catboost_player": 84},
    }
    out = build_match_symphony(match, shadow, legs=3)
    assert out is not None
    assert out["analysis_only"] is True
    assert out["legs_selected"] == 3
    assert out["path_engine"] == "EXACT"
    assert 0 <= out["symphony_score"] <= 100
    assert "2" in out["compositions"] and "6" in out["compositions"]
