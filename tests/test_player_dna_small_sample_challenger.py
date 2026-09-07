from datetime import datetime, timezone

from backend.player_dna_small_sample_challenger import (
    MODE,
    PRIOR_STRENGTH_GRID,
    SMALL_SAMPLE_MATCH_THRESHOLD,
    _apply_shrinkage,
    _posterior_rate,
    _prior_means,
    evaluate,
)


def _row(match_id, when, *, won, surface="hard", points=20, wins=12, matches=1):
    return {
        "match_id": match_id,
        "scheduled_time": datetime.fromisoformat(
            when.replace("Z", "+00:00")
        ).astimezone(timezone.utc),
        "event_index": 0,
        "surface": surface,
        "tour": "ATP",
        "match_format": "BO3",
        "server_won": int(won),
        "server_rank": 20,
        "receiver_rank": 40,
        "server_overall_matches": matches,
        "receiver_overall_matches": matches,
        "server_surface_matches": matches,
        "receiver_surface_matches": matches,
        "server_overall_serve_rate": wins / points if points else None,
        "receiver_overall_return_rate": (points - wins) / points if points else None,
        "server_surface_serve_rate": wins / points if points else None,
        "receiver_surface_return_rate": (points - wins) / points if points else None,
        "server_overall_serve_wins": wins,
        "server_overall_serve_points": points,
        "receiver_overall_return_wins": points - wins,
        "receiver_overall_return_points": points,
        "server_surface_serve_wins": wins,
        "server_surface_serve_points": points,
        "receiver_surface_return_wins": points - wins,
        "receiver_surface_return_points": points,
        "server_point_stage_before": 0,
        "receiver_point_stage_before": 0,
        "deuce_before": 0,
        "server_advantage_before": 0,
        "receiver_advantage_before": 0,
        "server_game_point_before": 0,
        "break_point_against_server_before": 0,
        "sets_completed_before": 0,
        "set_diff_server_before": 0,
        "current_set_games_total_before": 0,
        "current_set_game_diff_server_before": 0,
        "late_set_before": 0,
        "deciding_set_before": 0,
    }


def test_posterior_rate_pulls_small_sample_more_than_large_sample():
    prior = 0.60
    strength = 50.0

    small = _posterior_rate(4, 4, prior, strength)
    large = _posterior_rate(400, 400, prior, strength)

    assert small is not None
    assert large is not None
    assert 0.0 <= small <= 1.0
    assert 0.0 <= large <= 1.0
    assert abs(small - prior) < abs(large - prior)
    assert small < large


def test_zero_strength_is_exact_raw_rate_and_zero_support_stays_missing():
    assert _posterior_rate(7, 10, 0.61, 0.0) == 0.7
    assert _posterior_rate(0, 0, 0.61, 0.0) is None
    assert _posterior_rate(0, 0, 0.61, 25.0) == 0.61


def test_prior_means_use_only_rows_supplied_and_surface_specific_training_outcomes():
    train = [
        _row("a", "2026-09-01T10:00:00Z", won=1, surface="hard"),
        _row("b", "2026-09-02T10:00:00Z", won=1, surface="hard"),
        _row("c", "2026-09-03T10:00:00Z", won=0, surface="clay"),
    ]

    priors = _prior_means(train)

    assert priors["points_used"] == 3
    assert priors["global_serve"] == 2 / 3
    assert priors["global_return"] == 1 / 3
    assert priors["surface_serve"]["hard"] == 1.0
    assert priors["surface_return"]["hard"] == 0.0
    assert priors["surface_serve"]["clay"] == 0.0
    assert priors["source"] == "OUTER_TRAIN_POINT_OUTCOMES_ONLY"


def test_apply_shrinkage_uses_surface_prior_and_does_not_change_support_counts():
    row = _row(
        "x",
        "2026-09-04T10:00:00Z",
        won=1,
        surface="hard",
        points=10,
        wins=10,
        matches=2,
    )
    priors = {
        "global_serve": 0.60,
        "global_return": 0.40,
        "surface_serve": {"hard": 0.70},
        "surface_return": {"hard": 0.30},
    }

    shrunk = _apply_shrinkage([row], priors, 10.0)[0]

    assert shrunk["server_overall_serve_rate_shrunk"] == 0.8
    assert shrunk["server_surface_serve_rate_shrunk"] == 0.85
    assert shrunk["receiver_overall_return_rate_shrunk"] == 0.2
    assert shrunk["receiver_surface_return_rate_shrunk"] == 0.15
    assert shrunk["server_overall_matches"] == 2
    assert shrunk["server_overall_serve_points"] == 10


def test_empty_evaluation_keeps_shrinkage_challenger_shadow_only():
    report = evaluate([])
    contract = report["contract"]
    leakage = report["leakage_contract"]

    assert report["mode"] == MODE
    assert report["prior_strength_grid"] == list(PRIOR_STRENGTH_GRID)
    assert report["small_sample_match_threshold"] == SMALL_SAMPLE_MATCH_THRESHOLD
    assert report["production_influence"] is False
    assert report["runtime_scoring_enabled"] is False
    assert report["training_join_enabled"] is False
    assert report["canonical_profile_write_enabled"] is False
    assert report["simulator_influence"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False
    assert report["auto_promote"] is False
    assert report["promotion_gate"] is False
    assert report["candidate_may_replace_reference"] is False

    assert contract["prior_means_fit_from_outer_train_point_outcomes_only"] is True
    assert contract["prior_strength_selected_inside_outer_train_only"] is True
    assert contract["outer_holdout_never_used_for_parameter_selection"] is True
    assert contract["strength_grid_predeclared_before_holdout_evaluation"] is True
    assert contract["zero_strength_candidate_represents_no_shrinkage"] is True
    assert contract["fresh_confirmation_required_before_any_activation"] is True

    assert leakage["outer_test_labels_not_used_for_prior_mean"] is True
    assert leakage["outer_test_labels_not_used_for_prior_strength"] is True
    assert leakage["walk_forward_strength_reselected_inside_each_fold_train_only"] is True
    assert report["signal"]["candidate_may_replace_reference"] is False
    assert report["signal"]["fresh_confirmation_required"] is True
