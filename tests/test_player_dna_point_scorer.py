from datetime import datetime, timezone

import pandas as pd

from backend.player_dna_point_scorer import (
    STATE_NUMERIC,
    _fit_logistic_newton,
    _predict_logistic,
    _state_feature_lookup,
    build_feature_rows,
    split_chronological_by_match,
)


def _profile(match_id, when, player_id, opponent_id, matches=3, surface_matches=2):
    return {
        "target_match_id": match_id,
        "target_scheduled_time": when,
        "player_id": player_id,
        "opponent_id": opponent_id,
        "strict_as_of": True,
        "same_time_matches_count_as_prior": False,
        "overall_prior": {
            "matches": matches,
            "serve_win_rate": 0.64,
            "return_win_rate": 0.38,
        },
        "same_surface_prior": {
            "matches": surface_matches,
            "serve_win_rate": 0.62,
            "return_win_rate": 0.37,
        },
    }


def _point(match_id, when, p1, p2, server, server_won=True):
    receiver = p2 if server == p1 else p1
    return {
        "match_id": match_id,
        "match_scheduled_time": when,
        "surface": "hard",
        "tour": "ATP",
        "match_format": "BO3",
        "context_ready_player_point": True,
        "server_player_id": server,
        "receiver_player_id": receiver,
        "server_won": server_won,
        "server_ranking": 20,
        "receiver_ranking": 40,
        "is_tiebreak_before": False,
    }


def test_feature_join_uses_as_of_server_and_receiver_profiles():
    when = "2026-09-04T10:00:00Z"
    profiles = [
        _profile("m1", when, 1, 2, matches=5, surface_matches=4),
        _profile("m1", when, 2, 1, matches=7, surface_matches=3),
    ]
    points = [_point("m1", when, 1, 2, 1, server_won=True)]
    rows, counts = build_feature_rows(points, profiles)
    assert len(rows) == 1
    row = rows[0]
    assert row["server_overall_matches"] == 5
    assert row["receiver_overall_matches"] == 7
    assert row["server_surface_matches"] == 4
    assert row["receiver_surface_matches"] == 3
    assert row["server_overall_serve_rate"] == 0.64
    assert row["receiver_overall_return_rate"] == 0.38
    assert row["server_won"] == 1
    assert counts["joined_rows"] == 1


def test_profile_timestamp_must_equal_target_match_timestamp():
    profiles = [
        _profile("m1", "2026-09-04T09:00:00Z", 1, 2),
        _profile("m1", "2026-09-04T09:00:00Z", 2, 1),
    ]
    points = [_point("m1", "2026-09-04T10:00:00Z", 1, 2, 1)]
    rows, counts = build_feature_rows(points, profiles)
    assert rows == []
    assert counts["profile_time_mismatch"] == 1


def test_chronological_split_never_splits_same_timestamp_group():
    rows = [
        {"match_id": "a", "scheduled_time": datetime(2026, 9, 1, 10, tzinfo=timezone.utc)},
        {"match_id": "b", "scheduled_time": datetime(2026, 9, 2, 10, tzinfo=timezone.utc)},
        {"match_id": "c", "scheduled_time": datetime(2026, 9, 2, 10, tzinfo=timezone.utc)},
        {"match_id": "d", "scheduled_time": datetime(2026, 9, 3, 10, tzinfo=timezone.utc)},
        {"match_id": "e", "scheduled_time": datetime(2026, 9, 4, 10, tzinfo=timezone.utc)},
    ]
    train, holdout, meta = split_chronological_by_match(rows, train_fraction=0.4)
    train_ids = {row["match_id"] for row in train}
    holdout_ids = {row["match_id"] for row in holdout}
    assert train_ids == {"a"}
    assert {"b", "c"}.issubset(holdout_ids)
    assert meta["same_timestamp_split"] is False


def test_non_strict_point_never_enters_training_join():
    when = "2026-09-04T10:00:00Z"
    profiles = [
        _profile("m1", when, 1, 2),
        _profile("m1", when, 2, 1),
    ]
    point = _point("m1", when, 1, 2, 1)
    point["context_ready_player_point"] = False
    rows, counts = build_feature_rows([point], profiles)
    assert rows == []
    assert counts["non_strict_rows_skipped"] == 1


def test_numpy_logistic_performs_real_converged_fit():
    frame = pd.DataFrame([
        {
            "x": float(i - 40) / 10.0,
            "surface": "hard" if i % 2 else "clay",
            "tour": "ATP",
            "match_format": "BO3",
            "server_won": 1 if i >= 40 else 0,
        }
        for i in range(80)
    ])
    model = _fit_logistic_newton(frame, ["x"], l2=0.05)
    probs = _predict_logistic(model, frame)
    assert model["converged"] is True
    assert model["iterations"] > 0
    assert len(probs) == 80
    assert all(0.0 < float(p) < 1.0 for p in probs)
    assert float(probs[70]) > float(probs[10])


def _state_point(
    event_index,
    score_before,
    *,
    server=1,
    winner=1,
    transition_kind="point_score_changed",
    score_after=None,
):
    return {
        "match_id": "m1",
        "event_index": event_index,
        "match_scheduled_time": "2026-09-04T10:00:00Z",
        "surface": "hard",
        "tour": "ATP",
        "match_format": "BO3",
        "context_ready_player_point": True,
        "trainable_point": True,
        "server": server,
        "receiver": 3 - server,
        "server_player_id": server,
        "receiver_player_id": 3 - server,
        "point_winner": winner,
        "server_won": winner == server,
        "server_ranking": 20,
        "receiver_ranking": 40,
        "is_tiebreak_before": False,
        "transition_kind": transition_kind,
        "score_before": score_before,
        "score_after": score_after or score_before,
    }


def test_stateful_features_use_only_pre_point_score_and_prior_atomic_history():
    profiles = [
        _profile("m1", "2026-09-04T10:00:00Z", 1, 2, matches=8, surface_matches=6),
        _profile("m1", "2026-09-04T10:00:00Z", 2, 1, matches=8, surface_matches=6),
    ]
    p0 = _state_point(
        0,
        {"sets": [0, 0], "games": [[0], [0]], "points": ["30", "40"]},
        server=1,
        winner=1,
        score_after={"sets": [0, 0], "games": [[0], [0]], "points": ["40", "40"]},
    )
    p1 = _state_point(
        1,
        {"sets": [0, 0], "games": [[0], [0]], "points": ["40", "40"]},
        server=1,
        winner=2,
        score_after={"sets": [0, 0], "games": [[0], [0]], "points": ["40", "A"]},
    )
    rows, counts = build_feature_rows([p0, p1], profiles)
    assert len(rows) == 2
    first, second = rows
    assert first["break_point_against_server_before"] == 1
    assert first["server_game_point_before"] == 0
    assert first["server_point_stage_before"] == 2
    assert first["receiver_point_stage_before"] == 3
    assert second["deuce_before"] == 1
    assert second["previous_point_won_by_server"] == 1
    assert second["server_point_streak_before"] == 1
    assert second["receiver_point_streak_before"] == 0
    assert second["state_score_valid"] is True
    assert all(name in second for name in STATE_NUMERIC)
    assert counts["joined_rows_with_valid_score_state"] == 2


def test_state_lookup_does_not_read_score_after_or_current_winner_as_feature():
    base = _state_point(
        0,
        {"sets": [1, 1], "games": [[6, 4], [4, 5]], "points": ["15", "30"]},
        server=1,
        winner=1,
        score_after={"sets": [9, 9], "games": [[99], [0]], "points": ["A", "0"]},
    )
    changed = dict(base)
    changed["point_winner"] = 2
    changed["server_won"] = False
    changed["score_after"] = {"sets": [0, 2], "games": [[0], [6]], "points": ["0", "0"]}

    lookup_a, _ = _state_feature_lookup([base])
    lookup_b, _ = _state_feature_lookup([changed])
    features_a = lookup_a[("m1", 0)]
    features_b = lookup_b[("m1", 0)]
    assert {name: features_a[name] for name in STATE_NUMERIC} == {
        name: features_b[name] for name in STATE_NUMERIC
    }
    assert features_a["deciding_set_before"] == 1


def test_momentum_resets_when_atomic_event_sequence_has_a_gap():
    p0 = _state_point(
        0,
        {"sets": [0, 0], "games": [[1], [1]], "points": ["15", "0"]},
        server=1,
        winner=1,
    )
    p2 = _state_point(
        2,
        {"sets": [0, 0], "games": [[1], [1]], "points": ["30", "0"]},
        server=1,
        winner=1,
    )
    lookup, _ = _state_feature_lookup([p0, p2])
    assert lookup[("m1", 2)]["previous_point_won_by_server"] is None
    assert lookup[("m1", 2)]["server_point_streak_before"] == 0
