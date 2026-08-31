from backend.neuro_capability_map_v934 import (
    CAPABILITY_MAP,
    DIRECT_STATE_NOW,
    MODEL_ADAPTER_REQUIRED,
    PBP_REQUIRED,
    STATE_EXTENSION_REQUIRED,
    WEAK_BASE_NEURO_LATER,
    capability,
    recovery_priority,
)
from backend.neuro_market_registry_v934 import MARKET_REGISTRY


def test_every_registered_market_has_a_capability_classification():
    missing = sorted(set(MARKET_REGISTRY) - set(CAPABILITY_MAP))
    assert missing == []


def test_biggest_uncovered_families_do_not_default_to_neuro():
    assert capability("player_total_games")["capability"] == STATE_EXTENSION_REQUIRED
    assert capability("match_game_handicap")["capability"] == STATE_EXTENSION_REQUIRED
    assert capability("set2_exact_score")["capability"] == STATE_EXTENSION_REQUIRED
    assert capability("set2_total")["capability"] == STATE_EXTENSION_REQUIRED
    assert capability("set1_game_handicap")["capability"] == DIRECT_STATE_NOW


def test_serve_markets_have_existing_model_owner():
    assert capability("match_total_aces")["capability"] == MODEL_ADAPTER_REQUIRED
    assert "serve_props" in capability("match_total_aces")["model_sources"]
    assert capability("most_aces")["capability"] == MODEL_ADAPTER_REQUIRED


def test_pbp_and_weak_base_are_explicitly_separate():
    assert capability("set2_game_state")["capability"] == PBP_REQUIRED
    assert capability("match_games_parity")["capability"] == WEAK_BASE_NEURO_LATER
    assert recovery_priority("set1_game_handicap") < recovery_priority("match_games_parity")


def test_unknown_market_is_not_silently_neuro_eligible():
    assert capability("future_unknown_market") == {
        "capability": "UNASSIGNED",
        "owner": "UNASSIGNED",
    }
