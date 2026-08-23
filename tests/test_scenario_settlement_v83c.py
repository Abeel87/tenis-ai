from datetime import datetime, timezone

from backend.scenario_settlement_v83c import build_feed


def test_feed_merges_base_result_and_pbp_checkpoints():
    history = [{
        "match_id": 123,
        "match_key": "id:123",
        "scheduled_time": "2026-08-23T18:00:00Z",
        "p1": "A",
        "p2": "B",
        "status": "settled",
        "settled_at": "2026-08-23T20:00:00Z",
        "result": {
            "status": "completed",
            "winner": "A",
            "sets": [[6, 4], [6, 3]],
            "match_score": "2:0",
            "number_of_sets": 2,
            "total_games": 19,
            "first_set_score": "6:4",
        },
    }]
    pbp = [{
        "match_id": 123,
        "scheduled_time": "2026-08-23T18:00:00Z",
        "p1": "A",
        "p2": "B",
        "status": "settled",
        "settled_at": "2026-08-23T20:01:00Z",
        "actual": {
            "first_set_score": "6:4",
            "first_set_winner": "A",
            "first_set_games": 10,
            "over85": True,
            "states": {"2": "1:1", "4": "2:2", "6": "4:2"},
            "source": "BASIC PBP",
        },
    }]
    feed = build_feed(history, pbp, now=datetime(2026, 8, 23, 21, 0, tzinfo=timezone.utc))
    assert feed["count"] == 1
    row = feed["matches"][0]
    assert row["winner"] == "A"
    assert row["total_games"] == 19
    assert row["pbp"]["states"]["6"] == "4:2"


def test_void_match_is_exported_for_neutral_settlement():
    history = [{
        "match_id": 999,
        "match_key": "id:999",
        "scheduled_time": "2026-08-23T18:00:00Z",
        "p1": "A",
        "p2": "B",
        "status": "void",
        "result": {"status": "void", "reason": "retirement"},
    }]
    feed = build_feed(history, [], now=datetime(2026, 8, 23, 21, 0, tzinfo=timezone.utc))
    assert feed["matches"][0]["status"] == "void"
    assert feed["matches"][0]["reason"] == "retirement"
