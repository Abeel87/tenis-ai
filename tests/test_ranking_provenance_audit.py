from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

import ranking_provenance_audit as audit


def _row(player: str, date: str, rank, opponent_rank, *, opponent: str = "Other") -> dict:
    return {
        "player": player,
        "player_key": player.lower(),
        "opponent": opponent,
        "opponent_key": opponent.lower(),
        "date": pd.Timestamp(date),
        "surface": "hard",
        "rank": rank,
        "opponent_rank": opponent_rank,
        "won": 1.0,
        "hold_rate": 0.8,
        "break_rate": 0.2,
        "serve_points_won": 0.62,
        "return_points_won": 0.38,
        "first_set_won": 1.0,
    }


def test_legal_player_rows_are_strictly_pre_match():
    frame = pd.DataFrame([
        _row("Alice", "2026-09-18", 9, 20),
        _row("Alice", "2026-09-17", 10, 21),
        _row("Alice", "2026-09-10", 11, 22),
    ])
    rows, key, mode = audit._legal_player_rows(frame, "Alice", "2026-09-17T12:00:00Z")
    assert key == "alice"
    assert mode == "exact"
    assert [d.date().isoformat() for d in rows["date"]] == ["2026-09-17", "2026-09-10"]


def test_profile_rank_matches_current_head20_first_non_null_semantics():
    rows = pd.DataFrame([
        _row("Alice", "2026-09-17", None, 30),
        _row("Alice", "2026-09-16", 42, 31),
        _row("Alice", "2026-09-15", 43, 32),
    ])
    observed = audit._profile_rank_observation(rows.head(20))
    assert observed == {
        "rank": 42,
        "observation_date": "2026-09-16",
        "source_row_position": 2,
    }


def test_opponent_rank_provenance_reports_coverage_and_age():
    rows = pd.DataFrame([
        _row("Alice", "2026-09-16", 42, 12),
        _row("Alice", "2026-09-15", 43, None),
        _row("Alice", "2026-09-14", 44, 30),
    ])
    evidence = audit._opponent_rank_evidence(rows, pd.Timestamp("2026-09-17"))
    assert evidence["used_rows"] == 3
    assert evidence["rows_with_opponent_rank"] == 2
    assert evidence["coverage"] == 0.666667
    assert evidence["newest_observation_date"] == "2026-09-16"
    assert evidence["newest_age_days"] == 1


def test_current_output_view_excludes_profile_and_fixture_passthrough():
    left = {
        "p1_rank": 10,
        "p1_stats": {"rank": 11},
        "model_ready": True,
        "first_set_win": {"Alice": 60.0, "Bob": 40.0},
    }
    right = {
        "p1_rank": 9999,
        "p1_stats": {"rank": 9999},
        "model_ready": True,
        "first_set_win": {"Alice": 60.0, "Bob": 40.0},
    }
    assert audit._views_equal(audit._current_output_view(left), audit._current_output_view(right))


def test_fixture_rank_counterfactual_ignores_passthrough_only_changes(monkeypatch):
    def fake_analyse(_history, match):
        return {
            **match,
            "p1_stats": {"rank": match.get("p1_rank")},
            "p2_stats": {"rank": match.get("p2_rank")},
            "model_ready": True,
            "first_set_win": {"Alice": 55.0, "Bob": 45.0},
        }

    monkeypatch.setattr(audit.model, "analyse_match", fake_analyse)
    result = audit._fixture_rank_counterfactual(
        pd.DataFrame(),
        {"p1": "Alice", "p2": "Bob", "p1_rank": 10, "p2_rank": 20},
    )
    assert result == {"ran": True, "current_output_changed": False, "error": None}


def test_report_is_audit_only_and_preserves_rank_provenance(monkeypatch):
    frame = pd.DataFrame([
        _row("Alice", "2026-09-16", 42, 12, opponent="Bob"),
        _row("Bob", "2026-09-16", 18, 42, opponent="Alice"),
    ])
    matches = [{
        "id": 7,
        "scheduled_time": "2026-09-17T12:00:00Z",
        "surface": "hard",
        "p1": "Alice",
        "p2": "Bob",
        "p1_rank": 40,
        "p2_rank": 20,
        "p1_stats": {"rank": 42},
        "p2_stats": {"rank": 18},
        "model_ready": True,
    }]
    monkeypatch.setattr(
        audit,
        "_fixture_rank_counterfactual",
        lambda *_args, **_kwargs: {"ran": True, "current_output_changed": False, "error": None},
    )
    monkeypatch.setattr(
        audit,
        "_history_rank_counterfactual",
        lambda *_args, **_kwargs: {"ran": True, "current_output_changed": False, "error": None},
    )

    report = audit.build_report(
        frame,
        matches,
        {"updated_at": "2026-09-17T10:00:00+00:00"},
        {"mode": "SHADOW_CURRENT_ONLY", "production_influence": False, "rank_features_used": False},
        now=datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc),
    )

    policy = report["policy"]
    assert policy["audit_only"] is True
    assert policy["runtime_change"] is False
    assert policy["model_math_changed"] is False
    assert policy["live_tennis_api_calls"] == 0
    assert policy["production_cache_writes"] == 0
    assert report["sources"]["fixture_ranking"]["ranking_effective_date_available"] is False
    assert report["sources"]["fixture_ranking"]["snapshot_observed_at"] == "2026-09-17T10:00:00+00:00"
    assert report["summary"]["model_ready_matches"] == 1
    assert report["summary"]["model_ready_matches_with_both_fixture_provider_ranks"] == 1
    assert report["summary"]["profiles_with_both_fixture_and_historical_rank"] == 2
    assert report["decision"]["production_change_authorized"] is False
    assert report["decision"]["ranking_feature_activation_authorized"] is False
    assert report["decision"]["opponent_adjustment_authorized"] is False
