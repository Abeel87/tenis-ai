from backend.player_dna_matchup_challenger import (
    FEATURE_NAME,
    MATCHUP_NUMERIC,
    enrich_feature_rows,
    evaluate,
)


def _profile(match_id, when, player, opponent, *, serve, ret):
    return {
        "target_match_id": match_id,
        "target_scheduled_time": when,
        "player_id": player,
        "opponent_id": opponent,
        "strict_as_of": True,
        "same_time_matches_count_as_prior": False,
        "overall_prior": {
            "matches": 5,
            "serve_win_rate": serve,
            "return_win_rate": ret,
        },
        "same_surface_prior": {
            "matches": 3,
            "serve_win_rate": serve - 0.01,
            "return_win_rate": ret - 0.01,
        },
    }


def _point(match_id, when):
    return {
        "match_id": match_id,
        "event_index": 0,
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
        "is_tiebreak_before": False,
    }


def test_matchup_enrichment_builds_one_nonlinear_serve_return_interaction():
    when = "2026-09-06T10:00:00Z"
    profiles = [
        _profile("m1", when, 1, 2, serve=0.70, ret=0.38),
        _profile("m1", when, 2, 1, serve=0.62, ret=0.40),
    ]

    rows, counts = enrich_feature_rows([_point("m1", when)], profiles)

    assert len(rows) == 1
    assert MATCHUP_NUMERIC == [FEATURE_NAME]
    assert rows[0][FEATURE_NAME] == 0.70 * (1.0 - 0.40)
    assert counts["enrichment_counts"]["rows_with_matchup_feature"] == 1
    assert (
        counts["enrichment_counts"]["rows_in_min3_cohort_with_matchup_feature"]
        == 1
    )


def test_matchup_challenger_remains_single_family_and_shadow_only():
    report = evaluate([])
    contract = report["contract"]
    leakage = report["leakage_contract"]
    signal = report["signal"]

    assert report["mode"] == "SHADOW_MATCHUP_CHALLENGER_EVAL_ONLY"
    assert report["phase"] == "PHASE_3_MATCHUP_ENGINE"
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

    assert contract["single_predeclared_matchup_family_only"] is True
    assert contract["primary_family"] == "overall_serve_vs_return_nonlinear_interaction"
    assert contract["uses_existing_canonical_profile_rates_only"] is True
    assert (
        contract["reference_already_contains_individual_serve_and_return_main_effects"]
        is True
    )
    assert contract["feature_is_nonlinear_interaction_not_linear_relabel"] is True
    assert contract["same_surface_interaction_excluded_from_this_challenger"] is True
    assert contract["hold_break_bp_early_game_tiebreak_interactions_excluded"] is True
    assert contract["no_interaction_family_screen"] is True
    assert contract["no_support_threshold_tuning"] is True
    assert contract["uses_existing_scorer_min_prior_matches"] is True
    assert (
        contract["historical_success_requires_holdout_and_three_walk_forward_folds"]
        is True
    )
    assert contract["all_three_proper_scores_must_improve"] is True
    assert contract["fresh_confirmation_required_before_any_activation"] is True

    assert leakage["canonical_strict_as_of_profiles_only"] is True
    assert leakage["same_timestamp_matches_never_count_as_prior"] is True
    assert leakage["stable_provider_player_ids_only"] is True
    assert leakage["target_point_outcome_not_used_in_matchup_feature"] is True
    assert leakage["matchup_feature_is_pre_match_only"] is True
    assert leakage["current_target_match_never_contributes_to_its_own_profile"] is True

    assert signal["status"] == "INSUFFICIENT_MATCHUP_SHADOW_SAMPLE"
    assert signal["fresh_confirmation_required"] is True
    assert signal["candidate_may_replace_reference"] is False
