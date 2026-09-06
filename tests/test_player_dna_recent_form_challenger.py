from backend.player_dna_recent_form_challenger import (
    RECENT_FORM_MIN_PRIOR_MATCHES,
    RECENT_FORM_NUMERIC,
    RECENT_FORM_WINDOW,
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
            "matches": 7,
            "serve_win_rate": serve - 0.02,
            "return_win_rate": ret - 0.02,
        },
        "same_surface_prior": {
            "matches": 5,
            "serve_win_rate": serve - 0.01,
            "return_win_rate": ret - 0.01,
        },
        "rolling_prior": {
            "all_surface": {
                "windows": {
                    "L5": {
                        "matches": 5,
                        "matches_used": 5,
                        "window_full": True,
                        "serve_win_rate": serve,
                        "return_win_rate": ret,
                    }
                }
            },
            "same_surface": {
                "windows": {
                    "L5": {
                        "matches": 4,
                        "matches_used": 4,
                        "window_full": False,
                        "serve_win_rate": serve - 0.03,
                        "return_win_rate": ret - 0.03,
                    }
                }
            },
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


def test_recent_form_enrichment_uses_canonical_all_surface_l5_rates():
    when = "2026-09-06T10:00:00Z"
    profiles = [
        _profile("m1", when, 1, 2, serve=0.69, ret=0.38),
        _profile("m1", when, 2, 1, serve=0.63, ret=0.43),
    ]

    rows, counts = enrich_feature_rows([_point("m1", when)], profiles)

    assert len(rows) == 1
    row = rows[0]
    assert row["server_all_l5_serve_win_rate"] == 0.69
    assert row["receiver_all_l5_return_win_rate"] == 0.43
    assert counts["enrichment_counts"]["enriched_rows"] == 1
    assert counts["enrichment_counts"]["rows_with_both_l5_rates"] == 1
    assert counts["enrichment_counts"]["rows_with_both_players_l5_full"] == 1


def test_recent_form_family_is_narrow_and_support_counts_are_not_features():
    assert RECENT_FORM_WINDOW == "L5"
    assert RECENT_FORM_MIN_PRIOR_MATCHES == 5
    assert RECENT_FORM_NUMERIC == [
        "server_all_l5_serve_win_rate",
        "receiver_all_l5_return_win_rate",
    ]
    assert all("matches" not in name for name in RECENT_FORM_NUMERIC)
    assert all("support" not in name for name in RECENT_FORM_NUMERIC)


def test_recent_form_challenger_remains_shadow_only_without_sample():
    report = evaluate([])
    contract = report["contract"]
    leakage = report["leakage_contract"]
    signal = report["signal"]

    assert report["mode"] == "SHADOW_RECENT_FORM_CHALLENGER_EVAL_ONLY"
    assert report["production_influence"] is False
    assert report["runtime_scoring_enabled"] is False
    assert report["training_join_enabled"] is False
    assert report["canonical_profile_write_enabled"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False
    assert report["auto_promote"] is False
    assert report["promotion_gate"] is False
    assert report["candidate_may_replace_reference"] is False

    assert contract["primary_family"] == "all_surface_l5_serve_return"
    assert contract["single_predeclared_family_only"] is True
    assert contract["l5_is_shortest_canonical_complete_rolling_window"] is True
    assert contract["both_players_require_five_prior_matches"] is True
    assert contract["raw_support_counts_are_model_features"] is False
    assert contract["same_surface_rolling_excluded_from_this_challenger"] is True
    assert contract["l10_l20_excluded_from_this_challenger"] is True
    assert contract["no_post_hoc_family_screen"] is True
    assert contract["primary_reference_is_current_lean_stateful"] is True
    assert contract["historical_success_requires_holdout_and_three_walk_forward_folds"] is True
    assert contract["all_three_proper_scores_must_improve"] is True
    assert contract["fresh_confirmation_required_before_any_activation"] is True

    assert leakage["canonical_strict_as_of_profiles_only"] is True
    assert leakage["same_timestamp_matches_never_count_as_prior"] is True
    assert leakage["stable_provider_player_ids_only"] is True
    assert leakage["target_point_outcome_not_used_in_profile_features"] is True
    assert leakage["profile_features_are_pre_match_only"] is True
    assert leakage["current_target_match_never_contributes_to_its_own_profile"] is True

    assert signal["status"] == "INSUFFICIENT_RECENT_FORM_SHADOW_SAMPLE"
    assert signal["fresh_confirmation_required"] is True
    assert signal["candidate_may_replace_reference"] is False
