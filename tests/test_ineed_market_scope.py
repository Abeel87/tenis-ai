import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import ineed_scope as scope
import ineed_scoped_runner as runner


def playable(signals):
    return {
        "match_id": "1",
        "p1": "A",
        "p2": "B",
        "symphony2_playable": {
            "playable": True,
            "final_playable_authority": True,
            "authority": "SYMPHONY2_FINAL_PLAYABLE",
            "operator": "superbet.pl",
            "playable_count": len(signals),
            "signals": signals,
        },
    }


def test_scope_accepts_only_contract_markets():
    signals = [
        {"market": "set1_winner", "pick": "A"},
        {"market": "set1_total", "pick": "over", "line": 8.5},
        {"market": "game_state", "pick": "A", "checkpoint": 6},
        {"market": "match_winner", "pick": "A"},
        {"market": "match_total", "pick": "over", "line": 21.5},
        {"market": "set1_total", "pick": "under", "line": 8.5},
        {"market": "game_state", "pick": "A", "checkpoint": 2},
        {"market": "game_state", "pick": "A", "checkpoint": 4},
    ]
    original = playable(signals)
    filtered, diag = scope.filter_results([original])

    kept = filtered[0]["symphony2_playable"]["signals"]
    assert [(row.get("market"), row.get("pick"), row.get("checkpoint")) for row in kept] == [
        ("set1_winner", "A", None),
        ("set1_total", "over", None),
        ("game_state", "A", 6),
    ]
    assert filtered[0]["symphony2_playable"]["playable_count"] == 3
    assert diag["signals_seen"] == 8
    assert diag["signals_kept"] == 3
    assert diag["signals_filtered"] == 5
    assert len(original["symphony2_playable"]["signals"]) == 8


def test_scope_is_case_insensitive_but_fail_closed():
    assert scope.signal_allowed({"market": "SET1_WINNER", "pick": "A"}) is True
    assert scope.signal_allowed({"market": "SET1_TOTAL", "pick": "OVER", "line": 9.5}) is True
    assert scope.signal_allowed({"market": "GAME_STATE", "pick": "A", "checkpoint": "6"}) is True
    assert scope.signal_allowed({"market": "set1_total", "pick": "under", "line": 9.5}) is False
    assert scope.signal_allowed({"market": "game_state", "checkpoint": None}) is False
    assert scope.signal_allowed({"market": "match_winner", "pick": "A"}) is False
    assert scope.signal_allowed({"market": "unknown"}) is False
    assert scope.signal_allowed({}) is False


def test_match_with_no_allowed_signal_is_removed():
    filtered, diag = scope.filter_results([
        playable([
            {"market": "match_winner", "pick": "A"},
            {"market": "match_total", "pick": "over", "line": 20.5},
        ])
    ])
    assert filtered == []
    assert diag["matches_seen"] == 1
    assert diag["matches_kept"] == 0
    assert diag["signals_filtered"] == 2


def test_scoped_runner_filters_new_evaluations_but_keeps_open_bets_for_settlement(monkeypatch):
    results = [playable([
        {"market": "set1_winner", "pick": "A", "operator_model_probability": 70},
        {"market": "match_winner", "pick": "A", "operator_model_probability": 90},
    ])]
    open_bets = [{"id": "old-bet", "status": "PENDING", "market": "match_winner"}]
    state = {
        "experiment": {"id": "exp-1", "config": {"version": "test"}},
        "open_bets": open_bets,
    }
    captured = {}

    def fake_read(path, fallback):
        if path == runner.RESULTS:
            return results
        if path == runner.DIRECT:
            return {"status": "OK", "source": "test"}
        if path == runner.HISTORY:
            return [{"match_id": "old"}]
        return fallback

    def fake_refresh(scoped_results, direct_feed):
        captured["refresh_results"] = scoped_results
        return {"status": "OK", "source": "test"}, {"status": "OK"}

    def fake_evaluate(scoped_results, direct_feed, cfg, state_arg):
        captured["evaluate_results"] = scoped_results
        return [{"status": "REJECTED", "market": "set1_winner"}]

    def fake_settlements(bets, history, cfg):
        captured["settlement_bets"] = bets
        return [{"bet_id": "old-bet", "outcome": "WIN"}]

    monkeypatch.setattr(runner, "read", fake_read)
    monkeypatch.setattr(runner, "refresh_direct_for_ineed", fake_refresh)
    monkeypatch.setattr(runner, "evaluate", fake_evaluate)
    monkeypatch.setattr(runner, "build_settlements", fake_settlements)

    payload = runner.build_payload(state)
    scoped_signals = captured["evaluate_results"][0]["symphony2_playable"]["signals"]
    assert [row["market"] for row in scoped_signals] == ["set1_winner"]
    assert captured["settlement_bets"] == open_bets
    assert payload["settlements"][0]["bet_id"] == "old-bet"
    assert payload["health"]["market_scope"]["signals_filtered"] == 1
    assert payload["health"]["automatic_real_betting"] is False
