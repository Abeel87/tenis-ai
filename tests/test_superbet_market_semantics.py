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


def test_semantic_guard_rejects_split_over_under_threshold():
    with pytest.raises(AssertionError, match="O/U threshold mismatch"):
        validate_availability(_report([
            {"market": "match_total", "market_id": "1237", "pick": "over", "line": 22.5},
            {"market": "match_total", "market_id": "1237", "pick": "under", "line": 23.5},
        ]))
