from __future__ import annotations

import pandas as pd

from history_freshness_audit import _days_old, _quantiles, build_audit


def _row(player, date):
    return {
        "player": player,
        "player_key": player.lower(),
        "date": pd.Timestamp(date),
        "surface": "hard",
        "won": 1.0,
        "hold_rate": 0.8,
        "break_rate": 0.2,
        "serve_points_won": 0.62,
        "return_points_won": 0.38,
        "first_set_won": 1.0,
    }


def test_days_old():
    cut = pd.Timestamp("2026-09-17")
    assert _days_old(cut, "2026-09-16") == 1
    assert _days_old(cut, "2025-09-17") == 365


def test_quantiles_empty():
    assert _quantiles([]) == {"n": 0, "median": None, "p90": None, "max": None}


def test_audit_reports_old_fifth_match():
    df = pd.DataFrame([
        _row("Alice", "2026-09-16"),
        _row("Alice", "2026-09-10"),
        _row("Alice", "2026-08-20"),
        _row("Alice", "2026-07-01"),
        _row("Alice", "2025-09-01"),
        _row("Bob", "2026-09-15"),
        _row("Bob", "2026-09-14"),
        _row("Bob", "2026-09-13"),
        _row("Bob", "2026-09-12"),
        _row("Bob", "2026-09-11"),
    ])
    results = [{
        "id": 1,
        "scheduled_time": "2026-09-17T12:00:00Z",
        "p1": "Alice",
        "p2": "Bob",
        "model_ready": True,
        "p1_stats": {"matches": 5, "quality": "MEDIUM"},
        "p2_stats": {"matches": 5, "quality": "MEDIUM"},
    }]
    report = build_audit(df, results)
    assert report["summary"]["profiles_position_older_than_days"]["5"]["365"] == 1
    assert report["summary"]["model_has_explicit_max_history_age_days"] is False


def test_audit_does_not_change_runtime_policy():
    report = build_audit(pd.DataFrame(), [])
    assert report["policy"]["audit_only"] is True
    assert report["policy"]["runtime_change"] is False
    assert report["policy"]["model_math_changed"] is False
