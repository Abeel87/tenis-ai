from backend import superbet_market_core as core


def test_score_maps_are_already_percent_values():
    block = {"0:6": 0.7, "6:0": 1.2, "6:4": 13.9, "6:7": 7.5}

    assert core._lookup_score_map(block, "0:6") == 0.7
    assert core._lookup_score_map(block, "6-0") == 1.2
    assert core._lookup_score_map(block, "6:4") == 13.9
    assert core._lookup_score_map(block, "6:7") == 7.5


def test_exact_first_set_does_not_promote_sub_one_percent_to_fraction():
    match = {"exact_first_set": {"0:6": 0.7, "1:6": 3.0}}

    probability, source = core._model_probability(
        match,
        {"market": "set1_exact_score", "pick": "0:6"},
    )

    assert source == "exact_first_set"
    assert probability == 0.7


def test_game_state_score_map_uses_same_percent_contract():
    match = {"game_states": {"2": {"0:2": 0.4, "1:1": 48.0}}}

    probability, source = core._model_probability(
        match,
        {"market": "game_state", "pick": "0:2", "checkpoint": 2},
    )

    assert source == "game_states"
    assert probability == 0.4
