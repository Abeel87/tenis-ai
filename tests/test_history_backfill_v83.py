from datetime import date, datetime, timedelta, timezone

import backend.history_backfill_v83 as backfill
from backend.api_quota import DEFAULT_POLICIES
from backend.history_backfill_v83 import (
    DEFAULT_RUN_CAP,
    DEFAULT_STOP_DATE,
    _candidate_ok,
    _interval_due,
    _parse_date,
)


def test_backfill_has_no_second_quota_policy_owner():
    assert not hasattr(backfill, "compute_backfill_budget")
    assert not hasattr(backfill, "_usage")


def test_backfill_requester_matches_canonical_background_run_cap():
    assert DEFAULT_RUN_CAP == 120
    assert DEFAULT_RUN_CAP == DEFAULT_POLICIES["history_backfill"]["run_cap"]


def test_candidate_requires_complete_from_start_singles():
    ok = {
        "id": 123,
        "is_doubles": False,
        "tape": {
            "coverage": "from_start",
            "starts_at_love": True,
            "completeness": 0.99,
            "rows": 80,
        },
    }
    assert _candidate_ok(ok)
    assert not _candidate_ok({**ok, "is_doubles": True})
    assert not _candidate_ok({**ok, "tape": {**ok["tape"], "coverage": "partial"}})
    assert not _candidate_ok({**ok, "tape": {**ok["tape"], "completeness": 0.90}})
    assert not _candidate_ok({**ok, "tape": {**ok["tape"], "rows": 10}})


def test_backfill_interval_is_respected():
    now = datetime(2026, 8, 23, 18, tzinfo=timezone.utc)
    state = {"last_run_at": (now - timedelta(hours=1)).isoformat()}
    assert not _interval_due(state, now, 3)
    assert _interval_due(state, now, 0.5)


def test_stop_date_never_before_pbp_era():
    assert DEFAULT_STOP_DATE == date(2023, 1, 1)
    assert _parse_date("bad", DEFAULT_STOP_DATE) == DEFAULT_STOP_DATE


def test_completed_full_sweep_transitions_to_incremental_day_only():
    now = datetime(2026, 9, 23, 5, tzinfo=timezone.utc)
    state = {"cursor_date": "2023-08-12"}
    cursor, floor, ceiling, complete_through, idle = backfill._prepare_sweep(
        state, now, DEFAULT_STOP_DATE
    )
    assert cursor == date(2023, 8, 12)
    assert floor == DEFAULT_STOP_DATE
    assert ceiling == date(2026, 9, 22)
    assert complete_through is None
    assert idle is False

    completed = backfill._mark_sweep_complete(state, ceiling, now)
    assert completed == date(2026, 9, 22)
    cursor, floor, ceiling, complete_through, idle = backfill._prepare_sweep(
        state, now, DEFAULT_STOP_DATE
    )
    assert idle is True
    assert complete_through == date(2026, 9, 22)

    next_day = datetime(2026, 9, 24, 5, tzinfo=timezone.utc)
    cursor, floor, ceiling, complete_through, idle = backfill._prepare_sweep(
        state, next_day, DEFAULT_STOP_DATE
    )
    assert idle is False
    assert cursor == date(2026, 9, 23)
    assert floor == date(2026, 9, 23)
    assert ceiling == date(2026, 9, 23)


def test_force_full_sweep_restarts_from_newest_without_losing_high_water():
    now = datetime(2026, 9, 24, 5, tzinfo=timezone.utc)
    state = {"complete_through_date": "2026-09-22", "cursor_date": "2026-09-22"}
    cursor, floor, ceiling, complete_through, idle = backfill._prepare_sweep(
        state, now, DEFAULT_STOP_DATE, force_full=True
    )
    assert idle is False
    assert cursor == date(2026, 9, 23)
    assert floor == DEFAULT_STOP_DATE
    assert ceiling == date(2026, 9, 23)
    assert complete_through == date(2026, 9, 22)
