from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

import context_engine_shadow as context


def _all_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key).casefold()
            yield from _all_keys(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _all_keys(item)


def _long_rows():
    return pd.DataFrame([
        {"date": pd.Timestamp("2024-05-01"), "surface": "clay", "source_tour": "atp",
         "player": "Alpha One", "player_key": "alpha one",
         "opponent": "Old Rival", "opponent_key": "old rival",
         "rank": 80, "opponent_rank": 40},
        {"date": pd.Timestamp("2025-08-01"), "surface": "hard", "source_tour": "atp",
         "player": "Alpha One", "player_key": "alpha one",
         "opponent": "Beta Two", "opponent_key": "beta two",
         "rank": 50, "opponent_rank": 25},
        {"date": pd.Timestamp("2026-08-01"), "surface": "hard", "source_tour": "atp",
         "player": "Alpha One", "player_key": "alpha one",
         "opponent": "Gamma Three", "opponent_key": "gamma three",
         "rank": 30, "opponent_rank": 60},
        {"date": pd.Timestamp("2026-09-17"), "surface": "hard", "source_tour": "atp",
         "player": "Alpha One", "player_key": "alpha one",
         "opponent": "Same Day", "opponent_key": "same day",
         "rank": 29, "opponent_rank": 70},
        {"date": pd.Timestamp("2026-09-18"), "surface": "hard", "source_tour": "atp",
         "player": "Alpha One", "player_key": "alpha one",
         "opponent": "Future Row", "opponent_key": "future row",
         "rank": 28, "opponent_rank": 90},
    ])


def test_freshness_boundaries_are_descriptive_only():
    expected = {
        0: "0-30", 30: "0-30", 31: "31-60", 60: "31-60",
        61: "61-90", 90: "61-90", 91: "91-120", 120: "91-120",
        121: "121-180", 180: "121-180", 181: "181-365",
        365: "181-365", 366: ">365",
    }
    for days, bucket in expected.items():
        assert context._freshness_bucket(days) == bucket
    assert context._freshness_bucket(-1) is None


def test_strict_pre_history_excludes_same_day_and_future():
    pre, same_day = context._strict_pre_history(_long_rows(), pd.Timestamp("2026-09-17"))
    assert set(pre["date"].dt.strftime("%Y-%m-%d")) == {
        "2024-05-01", "2025-08-01", "2026-08-01",
    }
    assert same_day["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-09-17"]
    assert "2026-09-18" not in pre["date"].dt.strftime("%Y-%m-%d").tolist()


def test_identity_resolution_fails_closed_when_pre_fixture_candidates_are_ambiguous():
    frame = pd.DataFrame([
        {"date": pd.Timestamp("2026-08-01"), "player": "John Smith", "player_key": "john smith"},
        {"date": pd.Timestamp("2026-08-02"), "player": "Jane Smith", "player_key": "jane smith"},
    ])
    result = context._player_context(
        frame,
        player="J Smith",
        cut=pd.Timestamp("2026-09-17"),
        fixture_surface="hard",
        event_index={},
    )
    assert result["identity"]["mode"] == "ambiguous"
    assert result["identity"]["resolved_key"] is None
    assert result["records"] == []


def test_season_partition_is_relative_to_fixture_year():
    assert context._season_bucket(pd.Timestamp("2026-01-01"), 2026) == "current_season"
    assert context._season_bucket(pd.Timestamp("2025-12-31"), 2026) == "previous_season"
    assert context._season_bucket(pd.Timestamp("2024-12-31"), 2026) == "career_prior"
    assert context._season_bucket(pd.Timestamp("2027-01-01"), 2026) is None


def test_event_level_is_direct_only_and_missing_stays_unavailable():
    raw = pd.DataFrame([{
        "tourney_date": 20260801,
        "tourney_name": "Example Open",
        "winner_name": "Alpha One",
        "loser_name": "Gamma Three",
        "score": "6-4 6-4",
        "source_tour": "ATP",
    }])
    index = context._raw_event_index(raw)
    item = context._event_metadata(
        index,
        date=pd.Timestamp("2026-08-01"),
        player_key="alpha one",
        opponent_key="gamma three",
    )
    assert item["event_name"] == "Example Open"
    assert item["event_level"] is None
    assert item["resolution"] == "direct"
    assert item["reason"] == "event_level_missing_in_source"


def test_rank_gap_band_and_inactivity_are_factual_not_strength_or_medical_labels():
    player = context._player_context(
        _long_rows(),
        player="Alpha One",
        cut=pd.Timestamp("2026-09-17"),
        fixture_surface="hard",
        event_index={},
    )
    assert player["history"]["season_counts"] == {
        "fixture_year": 2026,
        "current_season": 1,
        "previous_season": 1,
        "career_prior": 1,
    }
    assert player["history"]["days_since_last_pre_fixture_match"] == 47
    latest = player["records"][0]
    assert latest["player_rank"] == 30
    assert latest["opponent_rank"] == 60
    assert latest["rank_gap_player_minus_opponent"] == -30
    assert latest["opponent_rank_band"] == "51-100"
    assert latest["same_surface"] is True
    assert latest["freshness_bucket"] == "31-60"
    assert "injury" not in latest and "comeback" not in latest


def test_gap_windows_do_not_choose_a_single_comeback_definition():
    dates = [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-04-15"), pd.Timestamp("2026-05-01")]
    windows = context._gap_windows(dates, pd.Timestamp("2026-05-20"))
    assert set(windows) == {"30", "60", "90", "180"}
    assert windows["30"]["last_observed_gap_days"] == 104
    assert windows["30"]["matches_played_since_last_observed_gap"] == 2
    assert windows["90"]["last_observed_gap_days"] == 104
    assert windows["180"]["last_observed_gap_days"] is None


def test_report_contract_is_shadow_only_and_emits_no_predictive_fields():
    raw = pd.DataFrame([{
        "tourney_date": 20260801,
        "tourney_name": "Example Open",
        "tourney_level": "A",
        "winner_name": "Alpha One",
        "loser_name": "Gamma Three",
        "score": "6-4 6-4",
        "surface": "Hard",
        "source_tour": "ATP",
    }])
    result = [{
        "id": 1,
        "scheduled_time": "2026-09-17T12:00:00Z",
        "surface": "Hard",
        "tour": "ATP",
        "p1": "Alpha One",
        "p2": "Missing Player",
        "model_ready": False,
    }]
    report = context.build_report(
        raw,
        _long_rows(),
        result,
        now=datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc),
    )
    p = report["policy"]
    assert p["audit_only"] is True and p["shadow_only"] is True
    assert p["runtime_wiring"] is False and p["predictive_output_generated"] is False
    assert p["injury_inference"] is False and p["event_level_inference"] is False
    assert p["live_tennis_api_calls"] == 0
    assert report["decision"]["runtime_promotion_authorized"] is False
    assert report["summary"]["player_contexts"] == 2

    fixture_keys = list(_all_keys(report["fixtures"]))
    for forbidden in ("probability", "prediction", "injury", "comeback"):
        assert not any(forbidden in key for key in fixture_keys)
