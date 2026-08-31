from backend.neuro_shadow_market_adapter_v935 import (
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    adapt_canonical_selection,
    adapt_market_context,
)


def _match():
    return {
        "p1": "Alpha",
        "p2": "Beta",
        "best_of": 3,
        "service_model": {"p1_hold": 0.78, "p2_hold": 0.72},
        "first_set_win": {"Alpha": 0.58, "Beta": 0.42},
        "second_set_win": {"Alpha": 0.55, "Beta": 0.45},
        "third_set_win": {"Alpha": 0.53, "Beta": 0.47},
    }


def _selection(market, pick, *, line=None, player=None, verified=True):
    return {
        "market": market,
        "pick": pick,
        "line": line,
        "player": player,
        "market_id": "m1",
        "outcome_id": "o1",
        "operator_available": True,
        "operator_line_verified": verified,
    }


def test_adapter_is_hard_shadow_only():
    assert PRODUCTION_INFLUENCE is False
    assert PLAYABLE_INFLUENCE is False
    assert SYMPHONY_PROD_INFLUENCE is False


def test_winner_and_line_markets_adapt_from_canonical_schema():
    cases = [
        _selection("set2_winner", "Alpha"),
        _selection("set3_winner", "Beta"),
        _selection("set2_total", "over", line=9.5),
        _selection("set3_total", "under", line=9.5),
        _selection("player_total_games", "over", line=12.5, player="Alpha"),
        _selection("match_game_handicap", "Alpha", line=-1.5),
    ]
    for selection in cases:
        row = adapt_canonical_selection(_match(), selection)
        assert row is not None
        assert 0.0 <= row["probability"] <= 1.0
        assert row["mode"] == "SHADOW"
        assert row["operator_playable"] is False
        assert row["production_influence"] is False
        assert row["playable_influence"] is False


def test_adapter_refuses_unverified_or_invented_line():
    assert adapt_canonical_selection(
        _match(), _selection("set3_total", "over", line=9.5, verified=False)
    ) is None
    assert adapt_canonical_selection(
        _match(), _selection("set3_total", "over", line=None)
    ) is None


def test_adapter_refuses_unknown_player_and_unsupported_market():
    assert adapt_canonical_selection(
        _match(), _selection("player_total_games", "over", line=12.5, player="Ghost")
    ) is None
    assert adapt_canonical_selection(
        _match(), _selection("future_unknown", "Alpha")
    ) is None


def test_adapter_requires_current_operator_availability():
    selection = _selection("set2_winner", "Alpha")
    selection["operator_available"] = False
    assert adapt_canonical_selection(_match(), selection) is None


def test_market_context_only_emits_safe_shadow_rows():
    context = {
        "canonical_selections": [
            _selection("set2_winner", "Alpha"),
            _selection("set3_total", "over", line=9.5),
            _selection("future_unknown", "Alpha"),
        ]
    }
    rows = adapt_market_context(_match(), context)
    assert len(rows) == 2
    assert {row["market"] for row in rows} == {"set2_winner", "set3_total"}
    assert all(row["operator_playable"] is False for row in rows)
