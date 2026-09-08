from backend.api_quota import (
    DEFAULT_POLICIES,
    _usage_numbers,
    compute_budget,
    request_interval_seconds,
)


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

def test_history_settlement_keeps_budget_after_old_100_call_cap():
    q = compute_budget(
        per_day=1000,
        remaining=211,
        role_spent=100,
        requested=40,
        daily_fraction=0.18,
        run_cap=24,
        reserve_fraction=0.12,
    )
    assert q["budget"] == 24
    assert q["daily_cap"] == 180
    assert q["reserve"] == 120
    assert q["reason"] == "ok"



def test_provider_report_is_authority_for_pro_limits():
    per_day, remaining, calls, per_minute = _usage_numbers({
        "today": {"calls": 843, "remaining_day": 9157},
        "limits": {"per_day": 10000, "per_minute": 300},
    })
    assert (per_day, remaining, calls, per_minute) == (10000, 9157, 843, 300)


def test_pro_capacity_run_caps_keep_global_daily_safety_buffer():
    assert DEFAULT_POLICIES["fixtures"]["run_cap"] == 12
    assert DEFAULT_POLICIES["pbp_current"]["run_cap"] == 180
    assert DEFAULT_POLICIES["pbp_tracker"]["run_cap"] == 36
    assert DEFAULT_POLICIES["history_settle"]["run_cap"] == 48
    assert DEFAULT_POLICIES["history_backfill"]["run_cap"] == 120
    assert sum(p["daily_fraction"] for p in DEFAULT_POLICIES.values()) == 0.87


def test_history_backfill_pro_capacity_remains_hard_capped_daily():
    policy = DEFAULT_POLICIES["history_backfill"]
    assert policy["daily_fraction"] == 0.12
    assert policy["run_cap"] == 120
    assert policy["reserve_fraction"] == 0.45

    start = compute_budget(
        per_day=10000,
        remaining=9000,
        role_spent=0,
        requested=500,
        daily_fraction=policy["daily_fraction"],
        run_cap=policy["run_cap"],
        reserve_fraction=policy["reserve_fraction"],
    )
    assert start["budget"] == 120
    assert start["daily_cap"] == 1200
    assert start["reserve"] == 4500

    almost_spent = compute_budget(
        per_day=10000,
        remaining=7000,
        role_spent=1190,
        requested=500,
        daily_fraction=policy["daily_fraction"],
        run_cap=policy["run_cap"],
        reserve_fraction=policy["reserve_fraction"],
    )
    assert almost_spent["budget"] == 10
    assert almost_spent["cap_left"] == 10


def test_provider_pacing_keeps_headroom_below_documented_rpm():
    interval = request_interval_seconds(300, utilization=0.90)
    assert interval > 60 / 300
    assert 60 / interval <= 270.000001
