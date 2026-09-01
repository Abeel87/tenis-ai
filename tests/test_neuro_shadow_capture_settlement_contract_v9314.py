from backend.neuro_shadow_state_v935 import CANDIDATE_CAPTURE_READY_MARKETS
from backend.signal_settlement import settle_signal_live


FINAL = {
    "status": "completed",
    "p1": "Alpha",
    "p2": "Beta",
    "winner": "Alpha",
    "sets": [[6, 4], [3, 6], [6, 2]],
    "completed_sets": [True, True, True],
    "total_games": 27,
    "number_of_sets": 3,
    "match_score": "2:1",
    "first_set_score": "6:4",
}


SIGNALS = {
    "set1_tiebreak": {"pick": "no"},
    "set2_winner": {"pick": "Beta"},
    "set3_winner": {"pick": "Alpha"},
    "set2_exact_score": {"pick": "3:6"},
    "set2_total": {"pick": "over", "line": 8.5},
    "set3_total": {"pick": "under", "line": 8.5},
    "player_total_games": {"pick": "over", "line": 14.5, "player": "Alpha"},
    "match_game_handicap": {"pick": "Alpha", "line": -2.5},
    "set1_game_handicap": {"pick": "Alpha", "line": -1.5},
    "set2_game_handicap": {"pick": "Beta", "line": -2.5},
    "set_handicap": {"pick": "Alpha", "line": -0.5},
    "exact_sets": {"pick": "3"},
    "p1_exactly_1_set": {"pick": "no"},
    "p1_exactly_2_sets": {"pick": "yes"},
    "p2_exactly_1_set": {"pick": "yes"},
    "p2_exactly_2_sets": {"pick": "no"},
    "p1_wins_a_set": {"pick": "yes"},
    "p2_wins_a_set": {"pick": "yes"},
    "match_games_parity": {"pick": "odd"},
    "set1_games_parity": {"pick": "even"},
    "set2_games_parity": {"pick": "odd"},
    "any_set_to_nil": {"pick": "no"},
}


def test_every_capture_ready_market_has_a_non_unverifiable_completed_settlement_path():
    assert set(SIGNALS) == set(CANDIDATE_CAPTURE_READY_MARKETS)
    results = {
        market: settle_signal_live({"market": market, **signal}, FINAL)
        for market, signal in SIGNALS.items()
    }
    assert set(results.values()) <= {"hit", "miss", "void"}
    assert "unverifiable" not in results.values()
