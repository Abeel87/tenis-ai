from datetime import datetime, timezone

from backend.signal_settlement import settle_signal, settle_signal_live
from backend.superbet_candidate_settlement_v925 import capture_candidates


def _final():
    return {
        "status": "completed",
        "p1": "Alpha Player",
        "p2": "Beta Player",
        "sets": [(6, 4), (3, 6), (6, 2)],
        "total_games": 27,
    }


def test_match_game_handicap_settles_from_exact_final_game_margin():
    final = _final()
    assert settle_signal({"market": "match_game_handicap", "pick": "Alpha Player", "line": -2.5}, final) == "hit"
    assert settle_signal({"market": "match_game_handicap", "pick": "Beta Player", "line": 2.5}, final) == "miss"
    assert settle_signal({"market": "match_game_handicap", "pick": "Alpha Player", "line": -3.0}, final) == "void"


def test_set_game_handicaps_use_only_their_exact_set():
    final = _final()
    assert settle_signal({"market": "set1_game_handicap", "pick": "Alpha Player", "line": -1.5}, final) == "hit"
    assert settle_signal({"market": "set2_game_handicap", "pick": "Beta Player", "line": -2.5}, final) == "hit"
    assert settle_signal({"market": "set2_game_handicap", "pick": "Alpha Player", "line": 2.5}, final) == "miss"


def test_retirement_only_settles_completed_set_handicap_not_match_handicap():
    final = {
        "status": "retired",
        "p1": "Alpha Player",
        "p2": "Beta Player",
        "sets": [(6, 4), (1, 2)],
        "completed_sets": [True, False],
    }
    assert settle_signal_live({"market": "set1_game_handicap", "pick": "Alpha Player", "line": -1.5}, final) == "hit"
    assert settle_signal_live({"market": "set2_game_handicap", "pick": "Beta Player", "line": -0.5}, final) == "void"
    assert settle_signal_live({"market": "match_game_handicap", "pick": "Alpha Player", "line": -1.5}, final) == "void"


def test_candidate_shadow_captures_verified_operator_game_handicap_without_prod_effect():
    history = [{
        "id": 101,
        "match_id": 101,
        "p1": "Alpha Player",
        "p2": "Beta Player",
        "scheduled_time": "2026-09-01T10:00:00Z",
        "status": "pending",
    }]
    results = [{
        "id": 101,
        "p1": "Alpha Player",
        "p2": "Beta Player",
        "scheduled_time": "2026-09-01T10:00:00Z",
        "superbet_market_v91": {
            "operator_verified": True,
            "status": "VERIFIED",
            "coverage_shadow_signals": [],
            "model_signals": [{
                "market": "match_game_handicap",
                "pick": "Alpha Player",
                "line": -2.5,
                "score": 71.0,
                "operator_line_verified": True,
                "key": "handicap-alpha--2.5",
            }],
        },
    }]
    captured, report = capture_candidates(history, results, datetime(2026, 8, 31, 20, 0, tzinfo=timezone.utc))
    rows = captured[0]["superbet_candidate_signals_v925"]
    assert report["operator_playable_changed"] is False
    assert len(rows) == 1
    assert rows[0]["market"] == "match_game_handicap"
    assert rows[0]["operator_line_verified"] is True
    assert rows[0]["operator_playable"] is False
    assert rows[0]["result"] == "pending"


def test_candidate_shadow_rejects_unverified_operator_line():
    history = [{"id": 102, "match_id": 102, "status": "pending"}]
    results = [{
        "id": 102,
        "superbet_market_v91": {
            "operator_verified": True,
            "status": "VERIFIED",
            "coverage_shadow_signals": [],
            "model_signals": [{
                "market": "match_game_handicap",
                "pick": "Alpha Player",
                "line": -2.5,
                "score": 80.0,
                "operator_line_verified": False,
            }],
        },
    }]
    captured, _ = capture_candidates(history, results)
    assert "superbet_candidate_signals_v925" not in captured[0]
