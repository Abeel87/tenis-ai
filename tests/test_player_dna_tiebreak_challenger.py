from backend.player_dna_tiebreak_challenger import (
    TIEBREAK_PROFILE_NUMERIC,
    enrich_feature_rows,
    evaluate,
)


def _prior(matches, *, serve, ret, tiebreak):
    return {
        "matches": matches,
        "serve_win_rate": serve,
        "return_win_rate": ret,
        "tiebreak_points": 24,
        "tiebreak_wins": round(24 * tiebreak),
        "tiebreak_win_rate": tiebreak,
    }


def _profile(match_id, when, player, opponent, *, strong):
    if strong:
        overall = _prior(8, serve=0.67, ret=0.37, tiebreak=0.58)
        surface = _prior(6, serve=0.66, ret=0.36, tiebreak=0.56)
    else:
        overall = _prior(9, serve=0.62, ret=0.41, tiebreak=0.47)
        surface = _prior(7, serve=0.61, ret=0.42, tiebreak=0.45)
    return {
        "target_match_id": match_id,
        "target_scheduled_time": when,
        "target_surface": "hard",
        "player_id": player,
        "opponent_id": opponent,
        "strict_as_of": True,
        "same_time_matches_count_as_prior": False,
        "overall_prior": overall,
        "same_surface_prior": surface,
    }


def _point(match_id, when, *, tiebreak=True, event_index=0):
    return {
        "match_id": match_id,
        "event_index": event_index,
        "match_scheduled_time": when,
        "surface": "hard",
        "tour": "ATP",
        "match_format": "BO3",
        "context_ready_player_point": True,
        "server_player_id": 1,
        "receiver_player_id": 2,
        "server_won": True,
        "server_ranking": 20,
        "receiver_ranking": 40,
        "server": 1,
        "receiver": 2,
        "point_winner": 1,
        "trainable_point": True,
        "transition_kind": "point_score_changed",
        "is_tiebreak_before": tiebreak,
        "score_before": {
            "sets": [0, 0],
            "games": [[6], [6]] if tiebreak else [[2], [2]],
            "points": ["1", "0"] if tiebreak else ["15", "0"],
        },
    }


def test_tiebreak_enrichment_uses_only_canonical_pre_match_tiebreak_rates():
    when = "2026-09-06T10:00:00Z"
    profiles = [
        _profile("m1", when, 1, 2, strong=True),
        _profile("m1", when, 2, 1, strong=False),
    ]
    points = [
        _point("m1", when, tiebreak=True, event_index=0),
        _point("m1", when, tiebreak=False, event_index=1),
    ]

    rows, counts = enrich_feature_rows(points, profiles)

    assert len(rows) == 1
    row = rows[0]
    assert row["is_tiebreak"] == 1
    assert row["server_overall_tiebreak_win_rate"] == 0.58
    assert row["receiver_overall_tiebreak_win_rate"] == 0.47
    assert row["server_surface_tiebreak_win_rate"] == 0.56
    assert row["receiver_surface_tiebreak_win_rate"] == 0.45
    assert counts["enrichment_counts"]["tiebreak_base_rows"] == 1
    assert counts["enrichment_counts"]["enriched_tiebreak_rows"] == 1
    assert counts["enrichment_counts"]["rows_with_both_overall_tiebreak_rates"] == 1
    assert counts["enrichment_counts"]["rows_with_both_surface_tiebreak_rates"] == 1


def test_tiebreak_primary_family_is_small_and_contains_no_support_proxy():
    assert TIEBREAK_PROFILE_NUMERIC == [
        "server_overall_tiebreak_win_rate",
        "receiver_overall_tiebreak_win_rate",
        "server_surface_tiebreak_win_rate",
        "receiver_surface_tiebreak_win_rate",
    ]
    assert all("points" not in name for name in TIEBREAK_PROFILE_NUMERIC)
    assert all("wins" not in name for name in TIEBREAK_PROFILE_NUMERIC)
    assert all("support" not in name for name in TIEBREAK_PROFILE_NUMERIC)


def test_tiebreak_challenger_is_historical_shadow_only_without_sample():
    report = evaluate([])
    contract = report["contract"]
    leakage = report["leakage_contract"]
    signal = report["signal"]

    assert report["mode"] == "SHADOW_TIEBREAK_CHALLENGER_EVAL_ONLY"
    assert report["regime"] == "TIEBREAK_POINTS_ONLY"
    assert report["production_influence"] is False
    assert report["runtime_scoring_enabled"] is False
    assert report["training_join_enabled"] is False
    assert report["canonical_profile_write_enabled"] is False
    assert report["simulator_tiebreak_policy_changed"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False
    assert report["auto_promote"] is False
    assert report["promotion_gate"] is False
    assert report["candidate_may_replace_reference"] is False

    assert contract["canonical_tiebreak_profile_only"] is True
    assert contract["primary_candidate_is_pre_match_only"] is True
    assert contract["raw_tiebreak_support_counts_are_features"] is False
    assert contract["rolling_tiebreak_family_not_screened_in_first_challenger"] is True
    assert contract["primary_reference_is_profile_plus_rank"] is True
    assert contract["lean_stateful_comparison_is_diagnostic_only"] is True
    assert contract["historical_success_requires_holdout_and_three_walk_forward_folds"] is True
    assert contract["all_three_proper_scores_must_improve"] is True
    assert contract["fresh_confirmation_required_before_simulator_integration"] is True

    assert leakage["canonical_strict_as_of_profiles_only"] is True
    assert leakage["same_timestamp_matches_never_count_as_prior"] is True
    assert leakage["stable_provider_player_ids_only"] is True
    assert leakage["target_point_outcome_not_used_in_profile_features"] is True
    assert leakage["profile_features_are_pre_match_only"] is True
    assert leakage["current_target_match_never_contributes_to_its_own_profile"] is True

    assert signal["status"] == "INSUFFICIENT_TIEBREAK_SHADOW_SAMPLE"
    assert signal["fresh_confirmation_required"] is True
    assert signal["candidate_may_replace_reference"] is False
