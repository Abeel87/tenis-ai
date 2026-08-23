from backend.api_quota_v83b import compute_budget


def test_pbp_current_start_of_day_gets_run_cap_not_whole_day():
    q = compute_budget(
        per_day=1000,
        remaining=999,
        role_spent=0,
        requested=560,
        daily_fraction=0.42,
        run_cap=90,
        reserve_fraction=0.20,
    )
    assert q["budget"] == 90
    assert q["daily_cap"] == 420
    assert q["reserve"] == 200


def test_pbp_current_daily_cap_preserves_later_matches():
    q = compute_budget(
        per_day=1000,
        remaining=500,
        role_spent=390,
        requested=90,
        daily_fraction=0.42,
        run_cap=90,
        reserve_fraction=0.20,
    )
    assert q["budget"] == 30
    assert q["reason"] == "ok"


def test_backfill_stops_above_hard_reserve():
    q = compute_budget(
        per_day=1000,
        remaining=430,
        role_spent=0,
        requested=18,
        daily_fraction=0.08,
        run_cap=18,
        reserve_fraction=0.45,
    )
    assert q["budget"] == 0
    assert q["reason"] == "protected_reserve"


def test_backfill_never_exceeds_its_daily_cap():
    q = compute_budget(
        per_day=1000,
        remaining=900,
        role_spent=75,
        requested=18,
        daily_fraction=0.08,
        run_cap=18,
        reserve_fraction=0.45,
    )
    assert q["budget"] == 5


def test_unknown_usage_fails_closed_in_pure_policy():
    q = compute_budget(
        per_day=None,
        remaining=None,
        role_spent=0,
        requested=18,
        daily_fraction=0.08,
        run_cap=18,
        reserve_fraction=0.45,
    )
    assert q["budget"] == 0
    assert q["reason"] == "usage_unknown"
