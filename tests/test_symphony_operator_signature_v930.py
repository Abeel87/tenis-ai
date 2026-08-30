from backend import symphony_operator_guard_v91 as guard


def _sig(**kwargs):
    row = {
        "market": kwargs.get("market", "player_total_games"),
        "pick": kwargs.get("pick", "over"),
        "line": kwargs.get("line", 7.5),
        "checkpoint": kwargs.get("checkpoint", 0),
        "player": kwargs.get("player"),
    }
    return guard._signature(row)


def test_player_scoped_markets_include_player_identity_in_signature():
    a = _sig(player="Emiliana Arango")
    b = _sig(player="Xinyu Wang")
    assert a != b


def test_player_name_order_normalizes_for_signature():
    a = _sig(player="Arango, Emiliana")
    b = _sig(player="Emiliana Arango")
    assert a == b


def test_non_player_market_signature_ignores_player_field():
    a = _sig(market="match_total", line=21.5, player="Emiliana Arango")
    b = _sig(market="match_total", line=21.5, player="Xinyu Wang")
    assert a == b


def test_wrong_player_line_is_not_accepted_by_operator_guard():
    original = {
        "superbet_market_v91": {
            "operator_verified": True,
            "status": "VERIFIED",
            "canonical_selections": [
                {
                    "market": "player_total_games",
                    "pick": "over",
                    "line": 7.5,
                    "player": "Emiliana Arango",
                    "operator_available": True,
                }
            ],
            "model_signals": [],
        }
    }
    augmented = {
        "autolearn_v84": {
            "signals": [
                {
                    "market": "player_total_games",
                    "pick": "over",
                    "line": 7.5,
                    "player": "Xinyu Wang",
                    "key": "player_total_games|7.5|over",
                }
            ]
        }
    }
    guarded, meta = guard.apply_superbet_market_guard(augmented, {}, original)
    assert guarded["autolearn_v84"]["signals"] == []
    assert meta["operator_suppressed_unavailable"] == 1
