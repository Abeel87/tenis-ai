from datetime import date, datetime, timedelta, timezone

from backend.history_backfill_v83 import (
    DEFAULT_STOP_DATE,
    _candidate_ok,
    _interval_due,
    _parse_date,
    compute_backfill_budget,
)


def test_budget_keeps_hard_reserve():
    p = compute_backfill_budget(
        per_day=1000,
        remaining_day=700,
        spent_today=0,
        daily_fraction=0.12,
        hard_reserve_fraction=0.45,
        run_cap=18,
    )
    assert p["daily_cap"] == 120
    assert p["hard_reserve"] == 450
    assert p["remote_budget"] == 18


def test_budget_stops_before_current_match_reserve():
    p = compute_backfill_budget(
        per_day=1000,
        remaining_day=449,
        spent_today=0,
        daily_fraction=0.12,
        hard_reserve_fraction=0.45,
        run_cap=18,
    )
    assert p["remote_budget"] == 0
    assert p["reason"] == "hard_reserve"


def test_budget_has_own_daily_cap():
    p = compute_backfill_budget(
        per_day=1000,
        remaining_day=900,
        spent_today=120,
        daily_fraction=0.12,
        hard_reserve_fraction=0.45,
        run_cap=18,
    )
    assert p["remote_budget"] == 0
    assert p["reason"] == "daily_backfill_cap"


def test_budget_fails_closed_when_usage_unknown():
    p = compute_backfill_budget(
        per_day=None,
        remaining_day=None,
        spent_today=0,
    )
    assert p["remote_budget"] == 0
    assert p["reason"] == "usage_unknown"


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
