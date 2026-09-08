from datetime import date, datetime, timedelta, timezone

import backend.history_backfill_v83 as backfill
from backend.history_backfill_v83 import (
    DEFAULT_STOP_DATE,
    _candidate_ok,
    _interval_due,
    _parse_date,
)


def test_backfill_has_no_second_quota_policy_owner():
    assert not hasattr(backfill, "compute_backfill_budget")
    assert not hasattr(backfill, "_usage")


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
