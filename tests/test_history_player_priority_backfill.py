from datetime import datetime, timedelta, timezone

import backend.history_player_priority_backfill as priority


def _entry(player_id, matches):
    return {
        "player": f"P{player_id}",
        "player_id": player_id,
        "matches": [{"id": mid} for mid in matches],
    }


def test_priority_prefers_current_players_then_small_samples(tmp_path):
    for mid in (1, 2, 3, 4):
        (tmp_path / f"{mid}.json.gz").write_bytes(b"x")

    index = {
        "players": {
            "current-rich": _entry(1, [1, 2, 3, 4]),
            "current-thin": _entry(2, [10]),
            "other-thin": _entry(3, [20]),
        }
    }
    now = datetime(2026, 9, 11, 18, tzinfo=timezone.utc)
    rows = priority._priority_players(
        index,
        {"current-rich", "current-thin"},
        {"players": {}},
        now,
        cache_dir=tmp_path,
    )

    assert [row["key"] for row in rows] == [
        "current-thin",
        "current-rich",
        "other-thin",
    ]


def test_priority_respects_cooldown(tmp_path):
    now = datetime(2026, 9, 11, 18, tzinfo=timezone.utc)
    index = {"players": {"p1": _entry(1, []), "p2": _entry(2, [])}}
    state = {
        "players": {
            "p1": {"last_attempt_at": (now - timedelta(hours=2)).isoformat()},
            "p2": {"last_attempt_at": (now - timedelta(hours=13)).isoformat()},
        }
    }

    rows = priority._priority_players(
        index,
        {"p1", "p2"},
        state,
        now,
        cooldown_hours=12,
        cache_dir=tmp_path,
    )

    assert [row["key"] for row in rows] == ["p2"]


def test_current_player_keys_are_normalized_and_deduplicated():
    rows = [
        {"p1": "Ilia Simakin", "p2": "Max Purcell"},
        {"p1": "Ilia  Simakin", "p2": None},
    ]
    assert priority._current_player_keys(rows) == {"ilia simakin", "max purcell"}


def test_detail_quality_requires_point_tape_and_from_start():
    ok = {"tape": [{}] * 20, "meta": {"coverage": "from_start"}}
    assert priority._detail_quality_ok(ok)
    assert not priority._detail_quality_ok({"tape": [{}] * 19})
    assert not priority._detail_quality_ok(
        {"tape": [{}] * 20, "meta": {"coverage": "partial"}}
    )


def test_upcoming_players_precede_started_feed_without_new_identity_join(tmp_path):
    now = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)
    results = [
        {"p1": "Started", "scheduled_time": (now-timedelta(hours=1)).isoformat()},
        {"p1": "Upcoming", "scheduled_time": (now+timedelta(hours=1)).isoformat()},
        {"p1": "Unknown", "scheduled_time": (now+timedelta(hours=2)).isoformat()},
    ]
    times = priority._upcoming_player_times(results, now)
    rows = priority._priority_players(
        {"players": {"started": _entry(1, []), "upcoming": _entry(2, [])}},
        priority._current_player_keys(results), {"players": {}}, now,
        upcoming_times=times, cache_dir=tmp_path,
    )
    assert [r["key"] for r in rows] == ["upcoming", "started"]
    assert "unknown" in times and all(r["key"] != "unknown" for r in rows)
    assert [r["player_id"] for r in rows] == [2, 1]
