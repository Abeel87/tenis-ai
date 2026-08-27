from backend.symphony_engine_v90 import Candidate, _compatible, build_match_symphony


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


def test_shadow_support_does_not_replace_prod_contract():
    match = {
        "id": 1,
        "p1": "A",
        "p2": "B",
        "autolearn_v84": {
            "signals": [
                {"key": "winner|A", "market": "match_winner", "pick": "A", "ensemble": 82},
                {"key": "set1|A", "market": "set1_winner", "pick": "A", "ensemble": 78},
                {"key": "total|8.5|over", "market": "set1_total", "pick": "over", "line": 8.5, "ensemble": 75},
            ]
        },
    }
    shadow = {
        "winner|A": {"catboost_player": 90, "ensemble_player": 88},
        "set1|A": {"catboost_player": 84},
    }
    out = build_match_symphony(match, shadow, legs=3)
    assert out is not None
    assert out["analysis_only"] is True
    assert out["legs_selected"] == 3
    assert 0 <= out["symphony_score"] <= 100
