from __future__ import annotations

import pandas as pd

import tml_2024_runtime_equivalence_audit as task018


def test_fixture_from_result_keeps_only_runtime_fixture_inputs():
    row = {
        "id": 123,
        "p1": "Alpha",
        "p2": "Beta",
        "surface": "Hard",
        "scheduled_time": "2026-09-17T12:00:00Z",
        "best_of": 3,
        "model_ready": True,
        "match_win": {"Alpha": 60.0, "Beta": 40.0},
    }
    fixture = task018._fixture_from_result(row)
    assert fixture["id"] == 123
    assert fixture["p1"] == "Alpha"
    assert fixture["p2"] == "Beta"
    assert "model_ready" not in fixture
    assert "match_win" not in fixture


def test_diff_paths_reports_nested_changes_deterministically():
    left = {"a": 1, "nested": {"x": 2, "same": 9}}
    right = {"a": 1, "nested": {"x": 3, "same": 9}, "new": True}
    assert task018._diff_paths(left, right) == ["nested.x", "new"]


def test_candidate_pre_match_rows_respects_identity_and_cutoff():
    candidate_long = pd.DataFrame([
        {"player_key": "alpha player", "date": pd.Timestamp("2024-01-01")},
        {"player_key": "alpha player", "date": pd.Timestamp("2024-02-01")},
        {"player_key": "other player", "date": pd.Timestamp("2024-01-15")},
        {"player_key": "alpha player", "date": pd.Timestamp("2026-10-01")},
    ])
    count = task018._candidate_pre_match_rows(
        candidate_long,
        resolved_key="alpha player",
        scheduled_time="2026-09-17T12:00:00Z",
    )
    assert count == 2
    assert task018._candidate_pre_match_rows(
        candidate_long,
        resolved_key="missing player",
        scheduled_time="2026-09-17T12:00:00Z",
    ) == 0


def test_unrelated_output_change_is_fail_closed_signal():
    baseline = {"model_ready": True, "match_win": {"A": 50.0, "B": 50.0}}
    augmented = {"model_ready": True, "match_win": {"A": 50.1, "B": 49.9}}
    result = task018._classify_output_change(
        baseline_projection=baseline,
        augmented_projection=augmented,
        direct_history_touched=False,
        prior_changed=True,
    )
    assert result["output_changed"] is True
    assert result["unrelated_output_change"] is True
    assert result["prior_changed"] is True
    assert result["changed_paths"] == ["match_win.A", "match_win.B"]


def test_direct_history_change_is_not_classified_as_unrelated():
    baseline = {"model_ready": False, "p1_stats": {"matches": 4}}
    augmented = {"model_ready": True, "p1_stats": {"matches": 5}}
    result = task018._classify_output_change(
        baseline_projection=baseline,
        augmented_projection=augmented,
        direct_history_touched=True,
        prior_changed=True,
    )
    assert result["output_changed"] is True
    assert result["unrelated_output_change"] is False
    assert result["direct_history_touched"] is True


def test_generated_projection_removes_fixture_input_but_keeps_model_fields():
    result = {
        "id": 1,
        "p1": "A",
        "p2": "B",
        "surface": "hard",
        "model_ready": True,
        "service_model": {"p1_hold": 75.0, "p2_hold": 74.0},
        "joint_builder_v78b": {"status": "READY"},
    }
    projection = task018._generated_projection(result)
    assert "id" not in projection
    assert "p1" not in projection
    assert "p2" not in projection
    assert projection["model_ready"] is True
    assert projection["joint_builder_v78b"]["status"] == "READY"
