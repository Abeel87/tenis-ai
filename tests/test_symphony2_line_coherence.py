from backend import symphony2_engine as engine


def _pair(line, over_p, under_p, state_over, player=None, checkpoint=None):
    common = {"market": "match_total", "line": line, "player": player, "checkpoint": checkpoint}
    return [
        {
            **common,
            "pick": "over",
            "operator_model_probability": over_p,
            "state_probability": state_over,
        },
        {
            **common,
            "pick": "under",
            "operator_model_probability": under_p,
            "state_probability": 100.0 - state_over,
        },
    ]


def _by(rows, pick, line, player=None, checkpoint=None):
    return next(
        r
        for r in rows
        if r["pick"] == pick
        and r["line"] == line
        and r.get("player") == player
        and r.get("checkpoint") == checkpoint
    )


def test_flat_verified_total_ladder_stays_flat_and_exactly_complementary():
    rows = []
    rows += _pair(20.5, 60.0, 40.0, 76.0)
    rows += _pair(21.5, 60.0, 40.0, 63.0)
    rows += _pair(22.5, 60.0, 40.0, 49.0)

    out = engine._cohere_ou_line_ladders(rows)
    overs = [_by(out, "over", line)["operator_model_probability"] for line in (20.5, 21.5, 22.5)]
    unders = [_by(out, "under", line)["operator_model_probability"] for line in (20.5, 21.5, 22.5)]

    assert overs == [60.0, 60.0, 60.0]
    assert unders == [40.0, 40.0, 40.0]
    for over, under in zip(overs, unders):
        assert round(over + under, 2) == 100.0
    assert all("operator_model_probability_pre_line_coherence" not in row for row in out)


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
    assert _by(out, "over", 20.5).get("probability_coherence") == "MONOTONIC_OU_LADDER"
    assert _by(out, "over", 21.5).get("probability_coherence") == "MONOTONIC_OU_LADDER"


def test_ladders_do_not_mix_players_or_checkpoints():
    rows = []
    rows += _pair(20.5, 55.0, 45.0, 70.0, player="p1", checkpoint=1)
    rows += _pair(21.5, 65.0, 35.0, 60.0, player="p1", checkpoint=1)
    rows += _pair(20.5, 80.0, 20.0, 80.0, player="p2", checkpoint=2)
    rows += _pair(21.5, 70.0, 30.0, 70.0, player="p2", checkpoint=2)

    out = engine._cohere_ou_line_ladders(rows)

    assert _by(out, "over", 20.5, "p1", 1)["operator_model_probability"] == 60.0
    assert _by(out, "over", 21.5, "p1", 1)["operator_model_probability"] == 60.0
    assert _by(out, "over", 20.5, "p2", 2)["operator_model_probability"] == 80.0
    assert _by(out, "over", 21.5, "p2", 2)["operator_model_probability"] == 70.0


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
