from backend.symphony2_engine import _compatible


def _row(market, pick, line=None):
    return {"market": market, "pick": pick, "line": line}


def test_exact_20_and_under_25_sets_are_semantically_redundant():
    assert _compatible((_row("exact_match_score", "2:0"), _row("total_sets", "under", 2.5))) is False


def test_exact_02_and_under_25_sets_are_semantically_redundant():
    assert _compatible((_row("exact_match_score", "0:2"), _row("total_sets", "under", 2.5))) is False


def test_exact_score_can_still_combine_with_match_games_total():
    assert _compatible((_row("exact_match_score", "2:0"), _row("match_total", "under", 22.5))) is True


def test_set_games_total_is_not_confused_with_match_set_count():
    assert _compatible((_row("exact_match_score", "2:0"), _row("set1_total", "under", 12.5))) is True
