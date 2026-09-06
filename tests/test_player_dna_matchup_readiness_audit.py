from backend.player_dna_matchup_readiness_audit import (
    INTERACTIONS,
    NOT_CANONICALLY_AVAILABLE,
    audit_profile_snapshots,
)


def _prior(matches=5, *, complete=True):
    values = {
        "matches": matches,
        "serve_win_rate": 0.66,
        "return_win_rate": 0.38,
        "hold_rate": 0.82,
        "break_rate": 0.24,
        "bp_save_rate": 0.61,
        "bp_conversion_rate": 0.42,
        "deuce_serve_win_rate": 0.58,
        "deuce_return_win_rate": 0.44,
        "thirty_all_serve_win_rate": 0.57,
        "thirty_all_return_win_rate": 0.45,
        "early_service_game_1_hold_rate": 0.84,
        "early_return_game_1_break_rate": 0.22,
        "early_service_game_2_hold_rate": 0.83,
        "early_return_game_2_break_rate": 0.23,
        "early_service_game_3_hold_rate": 0.81,
        "early_return_game_3_break_rate": 0.25,
        "tiebreak_win_rate": 0.54,
    }
    if not complete:
        values["tiebreak_win_rate"] = None
    return values


def _row(match_id, when, player, opponent, *, overall=5, surface=5, complete=True):
    return {
        "version": "player-dna-shadow-profiles-v1",
        "mode": "SHADOW_AS_OF_PROFILE",
        "strict_as_of": True,
        "same_time_matches_count_as_prior": False,
        "target_match_id": match_id,
        "target_scheduled_time": when,
        "target_surface": "hard",
        "player_id": player,
        "opponent_id": opponent,
        "overall_prior": _prior(overall, complete=complete),
        "same_surface_prior": _prior(surface, complete=complete),
    }


def test_matchup_readiness_requires_reciprocal_strict_pair_and_counts_both_directions():
    rows = [
        _row("m1", "2026-09-06T10:00:00Z", 1, 2),
        _row("m1", "2026-09-06T10:00:00Z", 2, 1),
    ]

    report = audit_profile_snapshots(rows)

    assert report["paired_matches"] == 1
    assert report["directional_matchups"] == 2
    assert report["pair_counts"]["paired_matches"] == 1

    for context in ("overall", "same_surface"):
        for interaction_name in INTERACTIONS:
            at5 = report["coverage"][context][interaction_name]["by_threshold"]["5"]
            assert at5["ready_directions"] == 2
            assert at5["directions"] == 2
            assert at5["rate"] == 1.0
        assert (
            report["full_match_coverage"][context]["5"][
                "matches_ready_for_all_current_interactions"
            ]
            == 1
        )


def test_matchup_readiness_exposes_partial_feature_coverage_without_inventing_signal():
    rows = [
        _row("m1", "2026-09-06T10:00:00Z", 1, 2, complete=False),
        _row("m1", "2026-09-06T10:00:00Z", 2, 1, complete=False),
    ]

    report = audit_profile_snapshots(rows)

    serve = report["coverage"]["overall"]["serve_vs_return"]["by_threshold"]["5"]
    tb = report["coverage"]["overall"]["tiebreak_vs_tiebreak"]["by_threshold"]["5"]
    assert serve["ready_directions"] == 2
    assert tb["ready_directions"] == 0
    assert (
        report["full_match_coverage"]["overall"]["5"][
            "matches_ready_for_all_current_interactions"
        ]
        == 0
    )


def test_matchup_readiness_is_phase3_audit_only_and_lists_master_plan_gaps():
    report = audit_profile_snapshots([])

    assert report["mode"] == "SHADOW_MATCHUP_READINESS_AUDIT_ONLY"
    assert report["gate"] == "AUDIT_ONLY_NO_MATCHUP_FEATURES"
    assert report["phase"] == "PHASE_3_MATCHUP_ENGINE_READINESS"
    assert report["production_influence"] is False
    assert report["runtime_scoring_enabled"] is False
    assert report["training_join_enabled"] is False
    assert report["matchup_feature_activation_enabled"] is False
    assert report["canonical_profile_write_enabled"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False

    contract = report["contract"]
    for key in (
        "canonical_strict_as_of_profiles_only",
        "same_timestamp_matches_never_count_as_prior",
        "stable_provider_player_ids_only",
        "reciprocal_target_match_pairs_only",
        "no_fuzzy_identity",
        "no_matchup_score_computed",
        "no_interaction_weight_tuned",
        "no_model_threshold_activated",
        "coverage_is_readiness_not_signal",
        "future_matchup_candidate_requires_chronological_walk_forward",
    ):
        assert contract[key] is True

    assert "first_serve_vs_first_return" in NOT_CANONICALLY_AVAILABLE
    assert "second_serve_vs_second_return" in NOT_CANONICALLY_AVAILABLE
    assert "ace_vs_contact_return" in NOT_CANONICALLY_AVAILABLE
    assert "double_fault_vs_return_pressure" in NOT_CANONICALLY_AVAILABLE
    assert "first_set_vs_first_set" in NOT_CANONICALLY_AVAILABLE
    assert "stamina_long_match_bo5" in NOT_CANONICALLY_AVAILABLE
