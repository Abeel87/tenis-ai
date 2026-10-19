from __future__ import annotations

import pytest

from scripts.verify_superbet_market_semantics import validate_availability


def _report(selections, *, p1="Alpha", p2="Beta"):
    return {
        "contains_prices": False,
        "prices_used": False,
        "fixtures": [
            {
                "p1": p1,
                "p2": p2,
                "canonical_selections": selections,
            }
        ],
    }


def test_semantic_guard_accepts_signed_handicap_shared_total_and_named_winner():
    summary = validate_availability(_report([
        {"market": "match_winner", "market_id": "121", "pick": "Alpha"},
        {"market": "match_winner", "market_id": "121", "pick": "Beta"},
        {"market": "match_total", "market_id": "1237", "pick": "over", "line": 22.5},
        {"market": "match_total", "market_id": "1237", "pick": "under", "line": 22.5},
        {"market": "match_game_handicap", "market_id": "12175", "pick": "Alpha", "line": -3.5},
        {"market": "match_game_handicap", "market_id": "12175", "pick": "Beta", "line": 3.5},
    ]))
    assert summary["handicap_pairs_checked"] == 1
    assert summary["total_pairs_checked"] == 1
    assert summary["winner_fixtures_checked"] == 1


def test_semantic_guard_accepts_unambiguous_operator_middle_name_expansion():
    summary = validate_availability(_report([
        {"market": "match_winner", "market_id": "121", "pick": "Maks Kasnikowski"},
        {"market": "match_winner", "market_id": "121", "pick": "Jay Dylan Hara Friend"},
    ], p1="Maks Kasnikowski", p2="Jay Friend"))
    assert summary["winner_fixtures_checked"] == 1


def test_semantic_guard_rejects_ambiguous_operator_name_expansion():
    with pytest.raises(AssertionError, match="match winner mapping incomplete"):
        validate_availability(_report([
            {"market": "match_winner", "market_id": "121", "pick": "Jay Dylan Hara Friend"},
            {"market": "match_winner", "market_id": "121", "pick": "Other Player"},
        ], p1="Jay Friend", p2="Jay Hara"))


def test_semantic_guard_rejects_same_signed_handicap_for_both_players():
    with pytest.raises(AssertionError, match="handicap perspective mismatch"):
        validate_availability(_report([
            {"market": "match_game_handicap", "market_id": "12175", "pick": "Alpha", "line": -3.5},
            {"market": "match_game_handicap", "market_id": "12175", "pick": "Beta", "line": -3.5},
        ]))


def test_semantic_guard_rejects_literal_winner_outcomes():
    with pytest.raises(AssertionError, match="literal bookmaker outcome"):
        validate_availability(_report([
            {"market": "match_winner", "market_id": "121", "pick": "1"},
            {"market": "match_winner", "market_id": "121", "pick": "2"},
        ]))


def test_split_over_under_thresholds_are_not_reported_as_a_pair():
    result = validate_availability(_report([
        {"market": "match_total", "market_id": "1237", "pick": "over", "line": 22.5},
        {"market": "match_total", "market_id": "1237", "pick": "under", "line": 23.5},
    ]))
    assert result["total_pairs_checked"] == 0
    assert result["unpaired_total_lines"] == 2


def test_semantic_guard_accepts_exact_reordered_operator_full_name():
    summary = validate_availability(_report([
        {'market': 'match_winner', 'market_id': '121', 'pick': 'Yujia Huang'},
        {'market': 'match_winner', 'market_id': '121', 'pick': 'Sijia Wei'},
    ], p1='Huang Yujia', p2='Sijia Wei'))
    assert summary['winner_fixtures_checked'] == 1


def test_semantic_guard_rejects_ambiguous_reordered_name():
    with pytest.raises(AssertionError, match='match winner mapping incomplete'):
        validate_availability(_report([
            {'market': 'match_winner', 'market_id': '121', 'pick': 'Yujia Huang'},
            {'market': 'match_winner', 'market_id': '121', 'pick': 'Other Player'},
        ], p1='Huang Yujia', p2='Yujia Huang'))


def test_alternate_totals_are_paired_by_exact_line_independent_of_row_order():
    rows = [
        {"market": "set2_total", "market_id": "524", "pick": "over", "line": 9.5},
        {"market": "set2_total", "market_id": "524", "pick": "under", "line": 12.5},
        {"market": "set2_total", "market_id": "524", "pick": "over", "line": 12.5},
        {"market": "set2_total", "market_id": "524", "pick": "under", "line": 9.5},
    ]
    from itertools import permutations
    for ordering in permutations(rows):
        assert validate_availability(_report(list(ordering)))["total_pairs_checked"] == 2


def test_totals_cannot_borrow_an_opposite_side_from_another_player():
    rows = [
        {"market": "player_total_games", "market_id": "same-family", "player": "Alpha", "pick": "over", "line": 10.5},
        {"market": "player_total_games", "market_id": "same-family", "player": "Alpha", "pick": "under", "line": 12.5},
        {"market": "player_total_games", "market_id": "same-family", "player": "Beta", "pick": "over", "line": 12.5},
        {"market": "player_total_games", "market_id": "same-family", "player": "Beta", "pick": "under", "line": 10.5},
    ]
    result = validate_availability(_report(rows))
    assert result["total_pairs_checked"] == 0
    assert result["unpaired_total_lines"] == 4


def test_earlier_unpaired_lines_are_reported_alongside_a_valid_pair():
    rows = [
        {"market": "match_total", "market_id": "1002", "pick": "over", "line": 20.5},
        {"market": "match_total", "market_id": "1002", "pick": "under", "line": 21.5},
        {"market": "match_total", "market_id": "1002", "pick": "over", "line": 22.5},
        {"market": "match_total", "market_id": "1002", "pick": "under", "line": 22.5},
    ]
    result = validate_availability(_report(rows))
    assert result["total_pairs_checked"] == 1
    assert result["unpaired_total_lines"] == 2


@pytest.mark.parametrize("line", [None, "not-a-line", float("nan"), float("inf")])
def test_invalid_total_line_still_fails_closed(line):
    with pytest.raises(AssertionError, match="missing total line"):
        validate_availability(_report([
            {"market": "match_total", "market_id": "1002", "pick": "over", "line": line},
        ]))
