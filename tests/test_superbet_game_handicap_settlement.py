from datetime import datetime, timezone

from backend.signal_settlement import settle_signal, settle_signal_live
from backend.superbet_candidate_settlement import capture_candidates


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
            "model_signals": [{
                "key": "mh",
                "label": "Alpha -2.5",
                "market": "match_game_handicap",
                "pick": "Alpha Player",
                "line": -2.5,
                "score": 72.0,
                "operator_line_verified": True,
            }],
        },
    }]
    out, report = capture_candidates(history, results, now=datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc))
    rows = out[0]["superbet_candidate_signals_v925"]
    assert report["captured"] == 1
    assert rows[0]["market"] == "match_game_handicap"
    assert rows[0]["line"] == -2.5
    assert rows[0]["operator_playable"] is False
    assert rows[0]["candidate_for_playable"] is True
