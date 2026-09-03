from backend import symphony2_engine as engine


def _pair(line, over_p, under_p, state_over):
    return [
        {
            "market": "match_total",
            "pick": "over",
            "line": line,
            "operator_model_probability": over_p,
            "state_probability": state_over,
        },
        {
            "market": "match_total",
            "pick": "under",
            "line": line,
            "operator_model_probability": under_p,
            "state_probability": 100.0 - state_over,
        },
    ]


def _by(rows, pick, line):
    return next(r for r in rows if r["pick"] == pick and r["line"] == line)


def test_flat_verified_total_ladder_gets_shared_state_shape_and_exact_complements():
    rows = []
    rows += _pair(20.5, 60.0, 40.0, 76.0)
    rows += _pair(21.5, 60.0, 40.0, 63.0)
    rows += _pair(22.5, 60.0, 40.0, 49.0)

    out = engine._cohere_ou_line_ladders(rows)
    overs = [_by(out, "over", line)["operator_model_probability"] for line in (20.5, 21.5, 22.5)]
    unders = [_by(out, "under", line)["operator_model_probability"] for line in (20.5, 21.5, 22.5)]

    assert overs[0] > overs[1] > overs[2]
    assert unders[0] < unders[1] < unders[2]
    for over, under in zip(overs, unders):
        assert round(over + under, 2) == 100.0
    assert all(_by(out, "over", line).get("probability_coherence") == "MONOTONIC_OU_LADDER" for line in (20.5, 21.5, 22.5))


def test_non_monotonic_model_ladder_is_projected_without_breaking_pair_complements():
    rows = []
    rows += _pair(20.5, 55.0, 45.0, 70.0)
    rows += _pair(21.5, 66.0, 34.0, 60.0)
    rows += _pair(22.5, 48.0, 52.0, 50.0)

    out = engine._cohere_ou_line_ladders(rows)
    overs = [_by(out, "over", line)["operator_model_probability"] for line in (20.5, 21.5, 22.5)]
    unders = [_by(out, "under", line)["operator_model_probability"] for line in (20.5, 21.5, 22.5)]

    assert overs[0] >= overs[1] >= overs[2]
    assert unders[0] <= unders[1] <= unders[2]
    for over, under in zip(overs, unders):
        assert round(over + under, 2) == 100.0


def test_unpaired_total_line_is_left_untouched():
    row = {
        "market": "match_total",
        "pick": "over",
        "line": 23.5,
        "operator_model_probability": 61.25,
        "state_probability": 45.0,
    }
    out = engine._cohere_ou_line_ladders([row])
    assert out[0]["operator_model_probability"] == 61.25
    assert "operator_model_probability_pre_line_coherence" not in out[0]
