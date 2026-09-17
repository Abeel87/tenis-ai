from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

import population_priors_audit as audit


def _history(population: str, n: int, *, surface: str = "hard", start="2026-09-01", hold=0.7):
    dates = pd.date_range(start=start, periods=n, freq="D")
    rows = []
    for i, date in enumerate(dates):
        rows.append({
            "source_tour": population,
            "surface": surface,
            "date": date,
            "player": f"P{i%4}",
            "player_key": f"p{i%4}",
            "hold_rate": hold,
            "break_rate": 1.0 - hold,
            "serve_points_won": 0.60,
            "return_points_won": 0.40,
            "won": 0.5,
            "first_set_won": 0.5,
            "second_set_won": 0.5,
            "second_after_first_win": 0.55,
            "second_after_first_loss": 0.45,
            "third_set_won": 0.5,
            "first_set_over85": 0.7,
            "first_set_over95": 0.5,
            "first_set_over105": 0.3,
            "first_set_over115": 0.2,
            "first_set_over125": 0.1,
        })
    return rows


def test_fixture_population_is_exact_and_fail_closed():
    assert audit._fixture_population("ATP") == "ATP"
    assert audit._fixture_population("wta") == "WTA"
    assert audit._fixture_population("ATP Challenger") == "CH"
    assert audit._fixture_population("CH") == "CH"
    assert audit._fixture_population("ITF") is None
    assert audit._fixture_population("ATP-ish") is None


def test_prior_support_matches_production_threshold_and_excludes_future():
    rows = _history("ATP", 99, surface="hard", start="2026-01-01")
    frame = pd.DataFrame(rows)
    cut = pd.Timestamp("2026-12-31")
    support = audit._prior_support(frame, "hard", cut)
    assert support["surface_rows"] == 99
    assert support["surface_specific_used"] is False
    assert support["fallback"] == "all_surfaces_within_input_population"
    assert support["fallback_reason"] == "surface_support_below_threshold"

    frame2 = pd.concat([frame, pd.DataFrame(_history("ATP", 1, surface="hard", start="2026-06-01"))], ignore_index=True)
    support2 = audit._prior_support(frame2, "hard", cut)
    assert support2["surface_rows"] == 100
    assert support2["surface_specific_used"] is True
    assert support2["fallback"] is None
    assert support2["fallback_reason"] is None

    future = frame2.iloc[[0]].copy()
    future["date"] = pd.Timestamp("2027-01-02")
    frame3 = pd.concat([frame2, future], ignore_index=True)
    support3 = audit._prior_support(frame3, "hard", cut)
    assert support3["pre_cut_rows"] == 100


def test_missing_surface_is_not_misreported_as_low_surface_support():
    frame = pd.DataFrame(_history("ATP", 120, surface="hard", start="2026-01-01"))
    support = audit._prior_support(frame, "", pd.Timestamp("2026-12-31"))
    assert support["surface_known"] is False
    assert support["surface_rows"] == 0
    assert support["surface_specific_used"] is False
    assert support["fallback"] == "all_surfaces_within_input_population"
    assert support["fallback_reason"] == "surface_missing"
    assert support["rows_used_by_prior_mean"] == 120


def test_frozen_surface_priors_restores_original():
    original = audit.model._core._surface_priors
    with audit._frozen_surface_priors({"hold_rate": 0.81}):
        assert audit.model._core._surface_priors(pd.DataFrame(), "hard", None)["hold_rate"] == 0.81
    assert audit.model._core._surface_priors is original


def test_output_view_does_not_count_profile_passthrough():
    left = {"p1_stats": {"hold_rate": 0.7}, "model_ready": True, "first_set_win": {"A": 55.0, "B": 45.0}}
    right = {"p1_stats": {"hold_rate": 0.9}, "model_ready": True, "first_set_win": {"A": 55.0, "B": 45.0}}
    delta = audit._output_delta(left, right)
    assert delta["changed_numeric_fields"] == 0
    assert delta["max_absolute_delta"] == 0.0


def test_build_report_is_shadow_only_and_isolates_population_prior(monkeypatch):
    frame = pd.DataFrame(
        _history("ATP", 120, hold=0.80)
        + _history("WTA", 120, hold=0.60)
        + _history("CH", 120, hold=0.70)
    )
    match = {
        "id": 1,
        "tour": "ATP",
        "surface": "hard",
        "scheduled_time": "2026-12-31T12:00:00Z",
        "p1": "A",
        "p2": "B",
        "model_ready": True,
    }

    def fake_analyse(history, fixture):
        priors = audit.model._core._surface_priors(history, "hard", pd.Timestamp("2026-12-31"))
        hold = float(priors["hold_rate"])
        return {
            **fixture,
            "model_ready": True,
            "p1_stats": {"hold_rate": hold, "break_rate": 1-hold, "serve_points_won": .6, "return_points_won": .4},
            "p2_stats": {"hold_rate": hold, "break_rate": 1-hold, "serve_points_won": .6, "return_points_won": .4},
            "first_set_win": {"A": round(hold * 100, 6), "B": round((1-hold) * 100, 6)},
        }

    monkeypatch.setattr(audit.model, "analyse_match", fake_analyse)
    report = audit.build_report(
        frame,
        [match],
        now=datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc),
    )

    assert report["policy"]["audit_only"] is True
    assert report["policy"]["shadow_only"] is True
    assert report["policy"]["runtime_change"] is False
    assert report["policy"]["model_math_changed"] is False
    assert report["policy"]["production_surface_support_threshold_changed"] is False
    assert report["summary"]["eligible_model_ready_counterfactuals"] == 1
    assert report["summary"]["fixtures_with_output_change"] == 1
    assert report["summary"]["player_profiles_changed"] == 2
    assert report["summary"]["model_ready_fixture_population_mapped_counts"]["ATP"] == 1
    assert report["summary"]["population_counterfactual_effect"]["ATP"]["eligible_model_ready_fixtures"] == 1
    assert report["summary"]["population_counterfactual_effect"]["ATP"]["fixtures_with_output_change"] == 1
    assert report["decision"]["production_change_authorized"] is False
    assert report["candidate_hierarchy"]["threshold_100_change_authorized"] is False
