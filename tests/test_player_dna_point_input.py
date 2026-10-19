"""File ingestion must change allocation, never feature or label semantics."""

import gzip
import importlib
import json
import tracemalloc
from collections import ChainMap
from datetime import datetime, timezone

import pandas as pd
import pytest

from backend.player_dna_point_scorer import PointDataset, build_feature_rows
from backend.player_dna_market_backtest import _labels_by_match


BUILDERS = [
    ("point_scorer", "build_feature_rows"),
    ("pressure_challenger", "enrich_feature_rows"),
    ("tiebreak_challenger", "enrich_feature_rows"),
    ("small_sample_challenger", "enrich_feature_rows"),
    ("matchup_challenger", "enrich_feature_rows"),
]


def _write(path, rows):
    with gzip.open(path, "wt") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _inputs():
    points, profiles = [], []
    # File order is not chronological; state within a match is not input-sorted.
    for match, day in (("later", 4), ("earlier", 2), ("last", 8)):
        when = f"2026-09-{day:02d}T10:00:00Z"
        for player in (1, 2):
            prior = {
                "matches": 5, "serve_win_rate": 0.6 + player / 100,
                "return_win_rate": 0.4 - player / 100,
                "serve_points": 40, "serve_wins": 24,
                "return_points": 40, "return_wins": 16,
                "tiebreak_win_rate": 0.55, "hold_rate": 0.8,
            }
            profiles.append({
                "target_match_id": match, "target_scheduled_time": when,
                "player_id": player, "opponent_id": 3 - player,
                "strict_as_of": True, "same_time_matches_count_as_prior": False,
                "overall_prior": prior, "same_surface_prior": dict(prior),
            })
        for index in (2, 0, 1):
            side = 1 + index % 2
            points.append({
                "match_id": match, "match_scheduled_time": when, "event_index": index,
                "p1_player_id": 1, "p2_player_id": 2,
                "server_player_id": side, "receiver_player_id": 3 - side,
                "server": side, "receiver": 3 - side,
                "server_won": index % 2 == 0, "point_winner": 1,
                "context_ready_player_point": True, "is_tiebreak_before": index == 2,
                "surface": "hard", "tour": "ATP", "match_format": "BO3",
                "score_before": {"sets": [0, 0], "games": [[0], [0]], "points": ["0", "0"]},
                "score_after": {"sets": [2, 0], "games": [[6, 6], [3, 2]], "points": ["0", "0"]},
            })
    # Preserve global profile diagnostics, last-profile-wins and missing input behavior.
    profiles.append({**profiles[0], "target_match_id": "unused"})
    profiles.append({**profiles[0], "overall_prior": {"matches": 0}})
    points.append({"match_id": "invalid", "context_ready_player_point": False})
    return points, profiles


@pytest.mark.parametrize("module_name,builder_name", BUILDERS)
def test_file_and_eager_features_counters_and_frames_are_identical(tmp_path, module_name, builder_name):
    module = importlib.import_module(f"backend.player_dna_{module_name}")
    builder = getattr(module, builder_name)
    points, profiles = _inputs()
    path = tmp_path / "points.gz"
    _write(path, points)
    expected_rows, expected_counts = builder(points, profiles)
    source = PointDataset(path)
    actual_rows, actual_counts = builder(source, iter(profiles))
    assert actual_rows == expected_rows
    assert actual_counts == expected_counts
    pd.testing.assert_frame_equal(
        pd.DataFrame(actual_rows).sort_index(axis=1),
        pd.DataFrame(expected_rows).sort_index(axis=1),
    )
    assert list(source) == points  # Joining must not exhaust the next consumer.
    assert builder(PointDataset(tmp_path / "absent.gz"), profiles) == builder([], profiles)


@pytest.mark.parametrize("module_name,builder_name", BUILDERS + [("market_backtest", "_labels_by_match")])
def test_raw_allocation_is_bounded_for_every_file_consumer(tmp_path, module_name, builder_name):
    module = importlib.import_module(f"backend.player_dna_{module_name}")
    builder = getattr(module, builder_name)
    path = tmp_path / "points.gz"
    _write(path, ({"match_id": str(i), "unused_raw_payload": "x" * 100_000} for i in range(200)))
    tracemalloc.start()
    try:
        if builder_name == "_labels_by_match":
            _, counts = builder(PointDataset(path))
            assert counts["matches_seen"] == 200
        else:
            rows, counts = builder(PointDataset(path), [])
            assert rows == []
            assert counts.get("base_join_counts", counts)["point_rows_seen"] == 200
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 5_000_000


def test_labels_preserve_outcomes_counts_and_order_across_repeated_passes(tmp_path):
    points, profiles = _inputs()
    path = tmp_path / "points.gz"
    _write(path, points)
    source = PointDataset(path)
    expected = _labels_by_match(points)
    assert expected[1] == {"matches_seen": 4, "settled_labels": 3, "incomplete_or_unsettled": 1}
    assert _labels_by_match(source) == expected
    assert build_feature_rows(source, profiles) == build_feature_rows(points, profiles)
    assert _labels_by_match(source) == expected
    assert list(_labels_by_match(source)[0]) == list(expected[0])


def test_split_file_match_fails_while_existing_list_api_keeps_its_semantics(tmp_path):
    points, profiles = _inputs()
    points = points[1:] + points[:1]
    assert build_feature_rows(points, profiles)[0]
    path = tmp_path / "points.gz"
    _write(path, points)
    for builder in (lambda rows: build_feature_rows(rows, profiles), _labels_by_match):
        with pytest.raises(ValueError, match="non-contiguous"):
            builder(PointDataset(path))


def test_current_card_fit_artifact_and_asof_profiles_match_the_eager_input(tmp_path, monkeypatch):
    from backend import player_dna_current_shadow as current

    seed_points, seed_profiles = _inputs()
    points, profiles = [], []
    for index in range(40):
        mid = f"history-{index}"
        when = f"2026-08-{1 + index // 2:02d}T{10 + index % 2:02d}:00:00Z"
        points.extend({**row, "match_id": mid, "match_scheduled_time": when} for row in seed_points[:3])
        profiles.extend({**row, "target_match_id": mid, "target_scheduled_time": when} for row in seed_profiles[:2])
    path = tmp_path / "points.gz"
    _write(path, points)
    # Isolate ingestion through the active scoring path. The existing regression
    # suite separately covers the untouched historical validation gate.
    monkeypatch.setattr(current, "evaluate", lambda *args, **kwargs: {
        "real_shadow_training": True,
        "signal": {"status": "POSITIVE_HOLDOUT_SIGNAL", "legacy_profile_signal_positive": True},
    })
    targets = [{"id": 1000, "p1_id": 1, "p2_id": 2, "scheduled_time": "2026-10-01T10:00:00Z", "surface": "hard", "tour": "ATP", "best_of": 3}]
    clock = datetime(2026, 9, 30, tzinfo=timezone.utc)
    expected = current.build_current_scores(points, profiles, targets, generated_at=clock)
    actual = current.build_current_scores(PointDataset(path), profiles, targets, generated_at=clock)
    assert expected[1] is not None
    assert expected[0]["scored_matches"] == 1
    assert actual == expected  # includes fitted parameters, fingerprint and second-pass profiles


def test_shared_feature_frame_does_not_flatten_every_point_into_a_large_dict():
    from backend.player_dna_point_scorer import _frame

    shared = {f"feature_{i}": i / 100 for i in range(100)}
    rows = [ChainMap({"event_index": i}, shared) for i in range(10_000)]
    expected = pd.DataFrame(rows)
    tracemalloc.start()
    try:
        actual = _frame(rows)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    pd.testing.assert_frame_equal(actual, expected)
    assert peak < 20_000_000  # ~8 MB of values; a flattened dict population exceeds 40 MB.


def test_shared_feature_frame_preserves_missing_values_dtypes_and_column_order():
    from backend.player_dna_point_scorer import _frame

    shared = {"overridden": 0.5, "all_none": None, "both_int": 2}
    rows = [
        ChainMap({"scheduled": datetime(2026, 9, 1, tzinfo=timezone.utc), "only_first": 1, "flag": True, "overridden": None}, shared),
        ChainMap({"scheduled": datetime(2026, 9, 2, tzinfo=timezone.utc), "name": "ATP", "flag": False}, shared),
    ]
    pd.testing.assert_frame_equal(_frame(rows), pd.DataFrame(rows))
    # Existing dictionary and mixed-mapping callers retain pandas' column semantics.
    for variants in ([], [dict(row) for row in rows], [dict(rows[0]), rows[1]], [ChainMap({}), ChainMap({})]):
        pd.testing.assert_frame_equal(_frame(variants), pd.DataFrame(variants))


@pytest.mark.parametrize("module_name,extra_features", [
    ("pressure_challenger", "PRESSURE_PRIMARY_NUMERIC"),
    ("opponent_adjustment_audit", "OPPONENT_STRENGTH_NUMERIC"),
])
def test_column_frame_keeps_fitted_parameters_and_predictions_exact(module_name, extra_features):
    import numpy as np
    from backend.player_dna_point_scorer import PROFILE_NUMERIC, _fit_logistic_newton, _frame, _predict_logistic

    module = importlib.import_module(f"backend.player_dna_{module_name}")
    points, profiles = _inputs()
    rows, _ = module.enrich_feature_rows(points, profiles)
    before, after = pd.DataFrame(rows), _frame(rows)
    pd.testing.assert_frame_equal(after, before)
    features = list(PROFILE_NUMERIC) + list(getattr(module, extra_features))
    expected = _fit_logistic_newton(before, features)
    actual = _fit_logistic_newton(after, features)
    np.testing.assert_array_equal(actual["beta"], expected["beta"])
    assert {k: v for k, v in actual.items() if k != "beta"} == {k: v for k, v in expected.items() if k != "beta"}
    np.testing.assert_array_equal(_predict_logistic(actual, after), _predict_logistic(expected, before))
