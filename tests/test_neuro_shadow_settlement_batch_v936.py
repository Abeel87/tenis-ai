from backend.signal_settlement import settle_signal_live


COMPLETED = {
    "status": "completed",
    "p1": "Alpha",
    "p2": "Beta",
    "sets": [[6, 4], [3, 6], [6, 2]],
    "completed_sets": [True, True, True],
    "total_games": 27,
    "number_of_sets": 3,
}


def _settle(market, pick, *, line=None, player=None, final=None):
    signal = {"market": market, "pick": pick, "line": line, "player": player}
    return settle_signal_live(signal, final or COMPLETED)


def test_game_handicap_family_uses_exact_canonical_side_line():
    assert _settle("match_game_handicap", "Alpha", line=-2.5) == "hit"
    assert _settle("match_game_handicap", "Beta", line=2.5) == "miss"
    assert _settle("set1_game_handicap", "Alpha", line=-1.5) == "hit"
    assert _settle("set2_game_handicap", "Beta", line=-2.5) == "hit"
    assert _settle("set_handicap", "Alpha", line=-0.5) == "hit"


def test_integer_handicap_push_is_void():
    assert _settle("set1_game_handicap", "Alpha", line=-2.0) == "void"


def test_parity_markets_settle_from_exact_finished_games():
    assert _settle("match_games_parity", "odd") == "hit"
    assert _settle("match_games_parity", "even") == "miss"
    assert _settle("set1_games_parity", "even") == "hit"
    assert _settle("set2_games_parity", "odd") == "hit"


def test_any_set_to_nil_and_player_set_props_are_exactly_settled():
    assert _settle("any_set_to_nil", "no") == "hit"
    assert _settle("any_set_to_nil", "yes") == "miss"
    assert _settle("p1_exactly_2_sets", "yes") == "hit"
    assert _settle("p2_exactly_1_set", "yes") == "hit"
    assert _settle("p1_wins_a_set", "yes") == "hit"
    assert _settle("p2_wins_a_set", "yes") == "hit"


def test_second_set_absent_is_void_not_miss():
    short = {
        "status": "completed",
        "p1": "Alpha",
        "p2": "Beta",
        "sets": [[6, 0]],
        "completed_sets": [True],
        "total_games": 6,
        "number_of_sets": 1,
    }
    assert _settle("set2_game_handicap", "Alpha", line=-1.5, final=short) == "void"
    assert _settle("set2_games_parity", "even", final=short) == "void"
    assert _settle("set2_winner", "Alpha", final=short) == "void"


def test_retirement_only_settles_completed_set_specific_markets():
    retired = {
        "status": "retired",
        "p1": "Alpha",
        "p2": "Beta",
        "sets": [[6, 4], [2, 1]],
        "completed_sets": [True, False],
    }
    assert _settle("set1_game_handicap", "Alpha", line=-1.5, final=retired) == "hit"
    assert _settle("set1_games_parity", "even", final=retired) == "hit"
    assert _settle("set2_game_handicap", "Alpha", line=-1.5, final=retired) == "void"
    assert _settle("set2_games_parity", "odd", final=retired) == "void"
    assert _settle("match_game_handicap", "Alpha", line=-1.5, final=retired) == "void"
    assert _settle("any_set_to_nil", "no", final=retired) == "void"
