from backend.neuro_shadow_capability_v937 import (
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    READY,
    SYMPHONY_PROD_INFLUENCE,
    UNSUPPORTED,
    ready_markets,
    shadow_capability,
)


def test_shadow_capability_never_implies_production_influence():
    assert PRODUCTION_INFLUENCE is False
    assert PLAYABLE_INFLUENCE is False
    assert SYMPHONY_PROD_INFLUENCE is False


def test_state_extensions_completed_in_108_are_reported_shadow_ready():
    for market in (
        "set2_winner",
        "set3_winner",
        "set2_exact_score",
        "set2_total",
        "set3_total",
        "player_total_games",
        "match_game_handicap",
        "set2_game_handicap",
        "set_handicap",
        "exact_sets",
    ):
        assert shadow_capability(market)["status"] == READY


def test_any_set_to_nil_is_truthfully_scoped_to_bo3():
    assert shadow_capability("any_set_to_nil")["scope"] == "BO3_ONLY"
    assert shadow_capability("any_set_to_nil", best_of=3)["status"] == READY
    assert shadow_capability("any_set_to_nil", best_of=5)["status"] == UNSUPPORTED
    assert "any_set_to_nil" in ready_markets(best_of=3)
    assert "any_set_to_nil" not in ready_markets(best_of=5)


def test_unknown_market_is_never_reported_ready():
    row = shadow_capability("future_unknown_market")
    assert row["status"] == UNSUPPORTED
    assert row["production_influence"] is False
    assert row["playable_influence"] is False
