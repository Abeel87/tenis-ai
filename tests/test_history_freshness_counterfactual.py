from __future__ import annotations

import pandas as pd

import history_freshness_counterfactual as audit


def _history_row(player: str, date: str) -> dict:
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


def test_fresh_history_has_lower_and_upper_time_boundaries():
    frame = pd.DataFrame([
        _history_row("Alice", "2026-09-18"),  # future: must never leak
        _history_row("Alice", "2026-09-17"),
        _history_row("Alice", "2026-08-18"),  # exactly 30 days
        _history_row("Alice", "2026-08-17"),  # 31 days: excluded
    ])
    fresh = audit._fresh_history(frame, "2026-09-17T12:00:00Z", 30)
    dates = {pd.Timestamp(value).date().isoformat() for value in fresh["date"]}
    assert dates == {"2026-09-17", "2026-08-18"}


def test_frozen_surface_priors_restores_production_function():
    original = audit.model._core._surface_priors
    expected = {"hold_rate": 0.71, "serve_points_won": 0.62}
    with audit._frozen_surface_priors(expected):
        assert audit.model._core._surface_priors(None, "hard", None) == expected
        assert audit.model._core._surface_priors is not original
    assert audit.model._core._surface_priors is original


def test_output_delta_excludes_profile_input_statistics():
    baseline = {
        "p1_stats": {"matches": 20, "hold_rate": 80.0},
        "p2_stats": {"matches": 20},
        "model_ready": True,
        "first_set_win": {"p1": 60.0, "p2": 40.0},
    }
    scenario = {
        "p1_stats": {"matches": 5, "hold_rate": 10.0},
        "p2_stats": {"matches": 5},
        "model_ready": True,
        "first_set_win": {"p1": 55.0, "p2": 45.0},
    }
    delta = audit._output_delta(baseline, scenario)
    assert delta["changed_numeric_outputs"] == 2
    assert delta["max_abs_delta"] == 5.0
    assert all(not row["path"].startswith("p1_stats") for row in delta["top_changed_outputs"])


def test_pbp_and_early_hold_freshness_use_existing_selected_samples_only():
    results = [{
        "id": 10,
        "scheduled_time": "2026-09-17T12:00:00Z",
        "p1": "Alice",
        "p2": "Bob",
        "early_hold_v7": {
            "p1": {"ready": True, "sample_ids": [1, 2, 3, 4, 5, 6]},
            "p2": {"ready": False, "sample_ids": []},
        },
    }]
    pbp_index = {
        "players": {
            "alice": {
                "matches": [
                    {"id": 1, "scheduled_time": "2026-09-16T12:00:00Z"},
                    {"id": 2, "scheduled_time": "2026-09-15T12:00:00Z"},
                    {"id": 3, "scheduled_time": "2026-09-14T12:00:00Z"},
                    {"id": 4, "scheduled_time": "2026-09-13T12:00:00Z"},
                    {"id": 5, "scheduled_time": "2026-09-12T12:00:00Z"},
                    {"id": 6, "scheduled_time": "2026-07-01T12:00:00Z"},
                    {"id": 99, "scheduled_time": "2026-09-18T12:00:00Z"},
                ]
            },
            "bob": {"matches": []},
        }
    }
    report = audit.build_pbp_freshness(results, pbp_index, scenarios=(30, 90))
    assert report["early_hold_sample_dates_resolved"] == 6
    assert report["scenarios"]["30"]["pbp_profiles_with_at_least_5_cached_candidates"] == 1
    assert report["scenarios"]["30"]["early_hold_profiles_with_at_least_5_selected_samples"] == 1
    assert report["scenarios"]["30"]["currently_ready_early_hold_profiles_retaining_at_least_5_samples"] == 1
    assert report["scenarios"]["90"]["early_hold_profiles_with_at_least_5_selected_samples"] == 1


def test_counterfactual_summary_tracks_readiness_loss(monkeypatch):
    results = [{"id": 1, "p1": "A", "p2": "B", "scheduled_time": "2026-09-17", "surface": "hard", "model_ready": True}]
    baseline = {
        "model_ready": True,
        "p1_stats": {"matches": 10},
        "p2_stats": {"matches": 10},
        "first_set_win": {"p1": 60.0, "p2": 40.0},
    }
    scenario = {
        "model_ready": False,
        "p1_stats": {"matches": 4},
        "p2_stats": {"matches": 6},
        "first_set_win": None,
    }
    monkeypatch.setattr(audit, "_safe_model_run", lambda *_args, **_kwargs: (baseline, None))
    monkeypatch.setattr(audit, "_baseline_priors", lambda *_args, **_kwargs: {"hold_rate": 0.72})
    monkeypatch.setattr(audit, "_safe_scenario_run", lambda *_args, **_kwargs: (scenario, None))

    report = audit.build_current_history_counterfactual(pd.DataFrame(), results, scenarios=(30,))
    row = report["scenarios"]["30"]
    assert row["baseline_model_ready_matches"] == 1
    assert row["model_ready_matches"] == 0
    assert row["baseline_model_ready_lost"] == 1
    assert row["profiles_with_minimum_5_retained"] == 1


def test_report_is_shadow_only(monkeypatch):
    monkeypatch.setattr(audit, "build_current_history_counterfactual", lambda *_args, **_kwargs: {"baseline": {}, "scenarios": {}})
    monkeypatch.setattr(audit, "build_pbp_freshness", lambda *_args, **_kwargs: {"available": True})
    report = audit.build_report(pd.DataFrame(), [], {})
    policy = report["policy"]
    assert policy["audit_only"] is True
    assert policy["shadow_counterfactual_only"] is True
    assert policy["runtime_change"] is False
    assert policy["model_math_changed"] is False
    assert policy["global_surface_priors_recomputed_per_scenario"] is False
    assert report["decision"]["production_cutoff_selected"] is False
    assert report["decision"]["production_change_authorized"] is False
