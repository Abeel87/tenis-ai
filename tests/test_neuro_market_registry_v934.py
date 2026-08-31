from backend.neuro_market_registry_v934 import MARKET_REGISTRY, market_meta, validate_registry


CURRENT_SUPERBET_CANONICAL_MARKETS = {
    "any_set_to_nil",
    "exact_match_score",
    "exact_sets",
    "game_state",
    "match_game_handicap",
    "match_games_parity",
    "match_total",
    "match_total_aces",
    "match_winner",
    "most_aces",
    "p1_exactly_1_set",
    "p1_exactly_2_sets",
    "p1_wins_a_set",
    "p2_exactly_1_set",
    "p2_exactly_2_sets",
    "p2_wins_a_set",
    "player_total_games",
    "set1_exact_score",
    "set1_game_handicap",
    "set1_games_parity",
    "set1_total",
    "set2_exact_score",
    "set2_game_handicap",
    "set2_game_state",
    "set2_games_parity",
    "set2_total",
    "set_handicap",
    "total_sets",
}


def test_current_superbet_markets_are_all_classified():
    report = validate_registry(CURRENT_SUPERBET_CANONICAL_MARKETS)
    assert report["complete"] is True
    assert report["missing"] == []
    assert report["classified"] == len(CURRENT_SUPERBET_CANONICAL_MARKETS)


def test_registry_has_one_family_and_explicit_neuro_gate_per_market():
    for market in CURRENT_SUPERBET_CANONICAL_MARKETS:
        row = MARKET_REGISTRY[market]
        assert row["family"]
        assert row["coverage_status"]
        assert isinstance(row["sources"], list)
        assert isinstance(row["neuro_eligible"], bool)


def test_unknown_market_is_never_neuro_eligible_by_default():
    row = market_meta("future_unknown_market")
    assert row["family"] == "UNASSIGNED"
    assert row["coverage_status"] == "UNASSIGNED"
    assert row["neuro_eligible"] is False


def test_known_market_meta_is_returned_as_copy():
    row = market_meta("match_winner")
    row["family"] = "BROKEN"
    assert MARKET_REGISTRY["match_winner"]["family"] == "RESULT"
