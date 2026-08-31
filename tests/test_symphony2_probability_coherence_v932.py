from backend.symphony2_engine import _cohere_exclusive_probabilities


def test_match_winner_pair_is_projected_to_exactly_100_percent():
    rows = [
        {"market": "match_winner", "pick": "A", "operator_model_probability": 46.24, "probability_kind": "SUPERVISED_OPERATOR_LINE_P_HIT"},
        {"market": "match_winner", "pick": "B", "operator_model_probability": 42.10, "probability_kind": "SUPERVISED_OPERATOR_LINE_P_HIT"},
    ]
    out = _cohere_exclusive_probabilities(rows)
    assert round(sum(r["operator_model_probability"] for r in out), 2) == 100.0
    assert max(r["operator_model_probability"] for r in out) >= 50.0
    assert all(r["probability_coherence"] == "NORMALIZED_EXCLUSIVE_GROUP" for r in out)


def test_over_under_same_line_is_projected_but_different_lines_are_independent():
    rows = [
        {"market": "match_total", "pick": "over", "line": 22.5, "operator_model_probability": 71.0},
        {"market": "match_total", "pick": "under", "line": 22.5, "operator_model_probability": 49.0},
        {"market": "match_total", "pick": "over", "line": 23.5, "operator_model_probability": 60.0},
        {"market": "match_total", "pick": "under", "line": 23.5, "operator_model_probability": 30.0},
    ]
    out = _cohere_exclusive_probabilities(rows)
    for line in (22.5, 23.5):
        pair = [r for r in out if r["line"] == line]
        assert round(sum(r["operator_model_probability"] for r in pair), 2) == 100.0


def test_unsupported_or_singleton_rows_are_not_invented_or_changed():
    rows = [
        {"market": "match_winner", "pick": "A", "operator_model_probability": None},
        {"market": "player_total_games", "pick": "over", "line": 12.5, "operator_model_probability": 61.0},
    ]
    out = _cohere_exclusive_probabilities(rows)
    assert out[0]["operator_model_probability"] is None
    assert out[1]["operator_model_probability"] == 61.0
    assert "probability_coherence" not in out[1]
