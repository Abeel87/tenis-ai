import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import superbet_line_projection_v926 as projection


def match():
    return {
        "p1": "Alpha",
        "p2": "Beta",
        "model_ready": True,
        "service_model": {"p1_hold": 78.0, "p2_hold": 70.0},
        "first_set_win": {"Alpha": 62.0, "Beta": 38.0},
        "second_set_context": {
            "p1_if_p1_wins_set1": 66.0,
            "p1_if_p1_loses_set1": 52.0,
            "p1_unconditional": 60.7,
        },
        "third_set_win": {"Alpha": 59.0, "Beta": 41.0},
        "serve_props_v72": {
            "ready": True,
            "p1": {"aces": {"mean": 8.0}},
            "p2": {"aces": {"mean": 5.0}},
        },
    }


def probability(market, pick, line=None, player=None):
    value, source = projection.projection_probability(
        match(), {"market": market, "pick": pick, "line": line, "player": player}
    )
    assert source
    assert value is not None
    assert 0 <= value <= 100
    return value


def test_half_game_handicaps_are_complements_for_both_players():
    for market in ("match_game_handicap", "set1_game_handicap", "set2_game_handicap"):
        p1 = probability(market, "Alpha", -2.5)
        p2 = probability(market, "Beta", 2.5)
        assert abs(p1 + p2 - 100.0) < 1e-7


def test_projected_totals_are_complements():
    over = probability("set2_total", "over", 9.5)
    under = probability("set2_total", "under", 9.5)
    assert abs(over + under - 100.0) < 1e-7

    p1_over = probability("player_total_games", "over", 11.5, "Alpha")
    p1_under = probability("player_total_games", "under", 11.5, "Alpha")
    assert abs(p1_over + p1_under - 100.0) < 1e-7


def test_most_aces_three_way_sums_to_100():
    p1 = probability("most_aces", "Alpha")
    p2 = probability("most_aces", "Beta")
    draw = probability("most_aces", "draw")
    assert abs(p1 + p2 + draw - 100.0) < 1e-7
    assert p1 > p2


def test_no_projection_without_model_ready_data():
    m = match()
    m["model_ready"] = False
    value, source = projection.projection_probability(
        m, {"market": "match_game_handicap", "pick": "Alpha", "line": -2.5}
    )
    assert value is None
    assert source is not None


def test_augment_match_only_adds_missing_supported_operator_lines():
    m = match()
    selections = [
        {"market": "match_game_handicap", "pick": "Alpha", "line": -2.5, "operator_available": True, "operator_line_verified": True},
        {"market": "match_game_handicap", "pick": "Beta", "line": 2.5, "operator_available": True, "operator_line_verified": True},
        {"market": "set2_total", "pick": "over", "line": 9.5, "operator_available": True, "operator_line_verified": True},
        {"market": "set2_total", "pick": "under", "line": 9.5, "operator_available": True, "operator_line_verified": True},
        {"market": "most_aces", "pick": "Alpha", "line": None, "operator_available": True, "operator_line_verified": True},
    ]
    m["superbet_market_v91"] = {
        "canonical_selections": selections,
        "model_signals": [],
        "prices_used": False,
    }
    out, added = projection.augment_match(m)
    ctx = out["superbet_market_v91"]
    assert added == len(selections)
    assert ctx["model_signals_count"] == len(selections)
    assert ctx["model_coverage"] == 1.0
    assert ctx["projection_adapter_version"] == projection.VERSION
    assert ctx["prices_used"] is False
    assert all(row["model_at_operator_line"] is True for row in ctx["model_signals"])
