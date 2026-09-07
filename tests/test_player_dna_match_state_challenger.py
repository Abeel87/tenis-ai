from datetime import datetime, timedelta, timezone

import pytest

from backend.player_dna_match_state_challenger import (
    MODE,
    _posterior_rate,
    _predict_rows,
    _split_chronological_by_match,
    build_feature_rows,
    evaluate,
    evaluate_task,
)


def _payload(
    sequence,
    *,
    match_id,
    scheduled,
    p1=101,
    p2=202,
    surface="hard",
):
    sets = [0, 0]
    tape = [{"sets": [0, 0], "games": [0, 0], "points": ["0", "0"]}]
    for winner in sequence:
        sets[winner - 1] += 1
        tape.append(
            {
                "sets": list(sets),
                "games": [6, 4],
                "points": ["0", "0"],
            }
        )
    score = {"sets": list(sets), "games": [6, 4], "points": ["0", "0"]}
    return {
        "match": {
            "id": match_id,
            "scheduled_time": scheduled,
            "surface": surface,
            "format": "BO5" if max(sets) == 3 else "BO3",
            "status": "completed",
            "outcome": "completed",
            "event_status": "Finished",
            "winner": sequence[-1],
            "withdrew": None,
            "score": score,
            "players": {
                "p1": {"id": p1, "name": "Alpha"},
                "p2": {"id": p2, "name": "Beta"},
            },
        },
        "profiles": [],
        "tape": tape,
    }


def _profile(
    match_id,
    player_id,
    *,
    comeback_wins=0,
    comeback_exp=0,
    front_wins=0,
    front_exp=0,
    late_wins=0,
    late_exp=0,
):
    return {
        "target_match_id": match_id,
        "player_id": player_id,
        "overall_prior": {
            "comeback_wins_after_first_set_loss": comeback_wins,
            "first_set_loss_exposures": comeback_exp,
            "match_wins_after_first_set_win": front_wins,
            "first_set_win_exposures": front_exp,
            "bo5_late_set_wins": late_wins,
            "bo5_late_set_exposures": late_exp,
        },
    }


def test_posterior_rate_shrinks_raw_count_toward_train_prior():
    assert _posterior_rate(1, 1, 0.2, 0.0) == 1.0
    assert _posterior_rate(1, 1, 0.2, 4.0) == pytest.approx(0.36)
    assert _posterior_rate(0, 0, 0.2, 4.0) == 0.2


def test_fixed_half_half_candidate_equals_context_prior_without_player_support():
    row = {
        "surface": "hard",
        "side_a_wins": 0,
        "side_a_exposures": 0,
        "side_b_wins": 0,
        "side_b_exposures": 0,
    }
    priors = {
        "global_event_rate": 0.3,
        "surface_event_rates": {"hard": 0.25},
    }

    baseline, candidate = _predict_rows([row], priors, 5.0)

    assert baseline == [0.25]
    assert candidate == [0.25]


def test_player_profiles_move_candidate_in_expected_direction():
    priors = {
        "global_event_rate": 0.5,
        "surface_event_rates": {"hard": 0.5},
    }
    high_event = {
        "surface": "hard",
        "side_a_wins": 8,
        "side_a_exposures": 10,
        "side_b_wins": 2,
        "side_b_exposures": 10,
    }
    low_event = {
        "surface": "hard",
        "side_a_wins": 2,
        "side_a_exposures": 10,
        "side_b_wins": 8,
        "side_b_exposures": 10,
    }

    _, probs = _predict_rows([high_event, low_event], priors, 3.0)

    assert probs[0] > 0.5
    assert probs[1] < 0.5
    assert probs[0] > probs[1]


def test_chronological_split_never_splits_same_timestamp_group():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        {"match_id": "a", "scheduled_time": t0, "label": 0},
        {"match_id": "b", "scheduled_time": t0, "label": 1},
        {"match_id": "c", "scheduled_time": t0 + timedelta(days=1), "label": 0},
        {"match_id": "d", "scheduled_time": t0 + timedelta(days=2), "label": 1},
    ]

    train, test, meta = _split_chronological_by_match(rows, 0.5)

    train_ids = {row["match_id"] for row in train}
    test_ids = {row["match_id"] for row in test}
    assert not (train_ids & test_ids)
    assert meta["same_timestamp_split"] is False
    assert not ({"a", "b"} & train_ids and {"a", "b"} & test_ids)


def test_feature_builder_uses_exact_profiles_for_bo3_and_bo5_tasks():
    bo3 = _payload(
        [1, 2, 2],
        match_id="bo3",
        scheduled="2026-09-01T10:00:00Z",
    )
    bo5 = _payload(
        [1, 2, 1, 2, 1],
        match_id="bo5",
        scheduled="2026-09-02T10:00:00Z",
        p1=303,
        p2=404,
    )
    profiles = [
        _profile("bo3", 101, front_wins=4, front_exp=5),
        _profile("bo3", 202, comeback_wins=2, comeback_exp=4),
        _profile("bo5", 303, late_wins=5, late_exp=8),
        _profile("bo5", 404, late_wins=3, late_exp=8),
    ]

    rows, counts = build_feature_rows([bo3, bo5], profiles)

    assert len(rows["comeback_bo3"]) == 1
    comeback = rows["comeback_bo3"][0]
    assert comeback["label"] == 1
    assert comeback["side_a_player_id"] == 202
    assert comeback["side_a_wins"] == 2
    assert comeback["side_a_exposures"] == 4
    assert comeback["side_b_player_id"] == 101
    assert comeback["side_b_wins"] == 4
    assert comeback["side_b_exposures"] == 5

    assert len(rows["bo5_late_set"]) == 3
    assert [row["set_number"] for row in rows["bo5_late_set"]] == [3, 4, 5]
    assert [row["label"] for row in rows["bo5_late_set"]] == [1, 0, 1]
    assert counts["comeback_bo3_rows"] == 1
    assert counts["bo5_late_set_rows"] == 3


def _synthetic_comeback_rows(n=1200):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(n):
        label = index % 2
        if label == 1:
            a_wins, b_wins = 9, 1
        else:
            a_wins, b_wins = 1, 9
        rows.append(
            {
                "task": "comeback_bo3",
                "match_id": f"m{index:04d}",
                "scheduled_time": start + timedelta(hours=index),
                "surface": "hard",
                "label": label,
                "side_a_wins": a_wins,
                "side_a_exposures": 10,
                "side_b_wins": b_wins,
                "side_b_exposures": 10,
            }
        )
    return rows


def test_chronological_comeback_challenger_can_detect_stable_historical_signal():
    result = evaluate_task("comeback_bo3", _synthetic_comeback_rows())

    assert result["holdout"]["status"] == "EVALUATED"
    assert result["holdout"]["positive_all_proper_scores"] is True
    assert result["walk_forward"]["robust_positive_all_three_folds"] is True
    assert (
        result["signal"]["status"]
        == "ROBUST_HISTORICAL_SIGNAL_REQUIRES_INCREMENTAL_SCORER_TEST"
    )
    assert result["signal"]["feature_activation_authorized"] is False


def test_top_level_contract_never_activates_match_state_features():
    report = evaluate({"comeback_bo3": [], "bo5_late_set": []})
    contract = report["contract"]

    assert report["mode"] == MODE
    assert report["production_influence"] is False
    assert report["runtime_scoring_enabled"] is False
    assert report["training_join_enabled"] is False
    assert report["canonical_point_scorer_feature_activation_enabled"] is False
    assert report["simulator_callback_activation_enabled"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False
    assert report["promotion_gate"] is False

    assert contract["canonical_strict_as_of_match_state_profiles_only"] is True
    assert contract["strength_selected_inside_outer_train_only"] is True
    assert contract["outer_holdout_never_used_for_strength_selection"] is True
    assert contract["same_timestamp_matches_never_split"] is True
    assert contract["incremental_over_current_scorer_not_yet_tested"] is True
    assert contract["fresh_confirmation_required_before_any_activation"] is True
