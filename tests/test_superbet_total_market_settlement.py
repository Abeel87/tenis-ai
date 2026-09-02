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


def test_set2_total_settles_exact_operator_line():
    final = _final()
    assert settle_signal({"market": "set2_total", "pick": "over", "line": 8.5}, final) == "hit"
    assert settle_signal({"market": "set2_total", "pick": "under", "line": 9.5}, final) == "hit"
    assert settle_signal({"market": "set2_total", "pick": "over", "line": 9.0}, final) == "void"
    assert settle_signal({"market": "set2_total", "pick": "over", "line": 8.5}, {**final, "sets": [(6, 4)]}) == "void"


def test_set3_total_settles_only_when_third_set_exists():
    final = _final()
    assert settle_signal({"market": "set3_total", "pick": "over", "line": 7.5}, final) == "hit"
    assert settle_signal({"market": "set3_total", "pick": "under", "line": 8.5}, final) == "hit"
    assert settle_signal({"market": "set3_total", "pick": "over", "line": 8.0}, final) == "void"
    assert settle_signal({"market": "set3_total", "pick": "over", "line": 7.5}, {**final, "sets": [(6, 4), (3, 6)]}) == "void"


def test_retired_set2_total_requires_completed_second_set():
    finished_second = {
        "status": "retired",
        "p1": "Alpha Player",
        "p2": "Beta Player",
        "sets": [(6, 4), (3, 6), (1, 2)],
        "completed_sets": [True, True, False],
    }
    unfinished_second = {**finished_second, "completed_sets": [True, False, False]}
    signal = {"market": "set2_total", "pick": "over", "line": 8.5}
    assert settle_signal_live(signal, finished_second) == "hit"
    assert settle_signal_live(signal, unfinished_second) == "void"


def test_retired_set3_total_requires_completed_third_set():
    finished_third = {
        "status": "retired",
        "p1": "Alpha Player",
        "p2": "Beta Player",
        "sets": [(6, 4), (3, 6), (6, 2), (1, 1)],
        "completed_sets": [True, True, True, False],
    }
    unfinished_third = {**finished_third, "completed_sets": [True, True, False, False]}
    signal = {"market": "set3_total", "pick": "over", "line": 7.5}
    assert settle_signal_live(signal, finished_third) == "hit"
    assert settle_signal_live(signal, unfinished_third) == "void"


def test_later_set_winners_settle_and_missing_set_is_void():
    final = _final()
    assert settle_signal({"market": "set2_winner", "pick": "Beta Player"}, final) == "hit"
    assert settle_signal({"market": "set3_winner", "pick": "Alpha Player"}, final) == "hit"
    assert settle_signal({"market": "set3_winner", "pick": "Alpha Player"}, {**final, "sets": [(6, 4), (6, 4)]}) == "void"


def test_player_total_games_uses_named_players_exact_game_total():
    final = _final()
    # Alpha: 6+3+6=15; Beta: 4+6+2=12.
    assert settle_signal({"market": "player_total_games", "player": "Alpha Player", "pick": "over", "line": 14.5}, final) == "hit"
    assert settle_signal({"market": "player_total_games", "player": "Beta Player", "pick": "under", "line": 12.5}, final) == "hit"
    assert settle_signal({"market": "player_total_games", "player": "Beta Player", "pick": "over", "line": 12.0}, final) == "void"
    assert settle_signal({"market": "player_total_games", "player": "Unknown", "pick": "over", "line": 10.5}, final) == "unverifiable"


def test_retired_player_total_games_is_void():
    final = {
        "status": "retired",
        "p1": "Alpha Player",
        "p2": "Beta Player",
        "sets": [(6, 4), (2, 1)],
        "completed_sets": [True, False],
    }
    assert settle_signal_live({"market": "player_total_games", "player": "Alpha Player", "pick": "over", "line": 8.5}, final) == "void"


def test_candidate_shadow_captures_verified_later_set_markets_without_playable_effect():
    history = [{
        "id": 201,
        "match_id": 201,
        "p1": "Alpha Player",
        "p2": "Beta Player",
        "scheduled_time": "2026-09-01T10:00:00Z",
        "status": "pending",
    }]
    results = [{
        "id": 201,
        "p1": "Alpha Player",
        "p2": "Beta Player",
        "scheduled_time": "2026-09-01T10:00:00Z",
        "superbet_market_v91": {
            "operator_verified": True,
            "status": "VERIFIED",
            "coverage_shadow_signals": [],
            "model_signals": [
                {"market": "set2_total", "pick": "over", "line": 8.5, "score": 70.0, "operator_line_verified": True},
                {"market": "set3_total", "pick": "over", "line": 7.5, "score": 72.0, "operator_line_verified": True},
                {"market": "set2_winner", "pick": "Beta Player", "score": 73.0, "operator_line_verified": True},
                {"market": "set3_winner", "pick": "Alpha Player", "score": 74.0, "operator_line_verified": True},
                {"market": "player_total_games", "player": "Alpha Player", "pick": "over", "line": 14.5, "score": 69.0, "operator_line_verified": True},
                {"market": "player_total_games", "player": "Beta Player", "pick": "under", "line": 12.5, "score": 80.0, "operator_line_verified": False},
            ],
        },
    }]
    captured, report = capture_candidates(history, results, datetime(2026, 8, 31, 20, 0, tzinfo=timezone.utc))
    rows = captured[0]["superbet_candidate_signals_v925"]
    assert report["operator_playable_changed"] is False
    assert {(row["market"], row.get("player")) for row in rows} == {
        ("set2_total", None),
        ("set3_total", None),
        ("set2_winner", None),
        ("set3_winner", None),
        ("player_total_games", "Alpha Player"),
    }
    assert all(row["operator_line_verified"] is True for row in rows)
    assert all(row["operator_playable"] is False for row in rows)
