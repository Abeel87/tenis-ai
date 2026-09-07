from datetime import datetime, timezone

from backend.player_dna_shadow_profiles import build_snapshots_from_rows


def _point(
    match_id,
    when,
    p1,
    p2,
    server,
    winner,
    surface="hard",
    event_index=0,
    points=("0", "0"),
    transition_kind="point_score_changed",
    atomic_reason="atomic_point_step",
    trainable_point=True,
    atomic_transition=True,
    context_ready=True,
):
    receiver = p2 if server == p1 else p1
    server_side = 1 if server == p1 else 2
    receiver_side = 3 - server_side
    return {
        "match_id": match_id,
        "event_index": event_index,
        "match_scheduled_time": when,
        "surface": surface,
        "tour": "ATP",
        "match_format": "BO3",
        "round_code": "R32",
        "p1_player_id": p1,
        "p2_player_id": p2,
        "server_player_id": server,
        "receiver_player_id": receiver,
        "server": server_side,
        "receiver": receiver_side,
        "point_winner": 1 if winner == p1 else 2,
        "server_won": winner == server,
        "receiver_won": winner == receiver,
        "is_tiebreak_before": False,
        "context_ready_player_point": bool(context_ready),
        "trainable_point": bool(trainable_point),
        "atomic_transition": bool(atomic_transition),
        "atomic_reason": atomic_reason,
        "transition_kind": transition_kind,
        "score_before": {
            "sets": [0, 0],
            "games": [[0], [0]],
            "points": list(points),
        },
        "p1_ranking": 10,
        "p2_ranking": 20,
    }


def _snapshot(rows, match_id, player_id):
    return next(
        row for row in rows
        if row["target_match_id"] == match_id and row["player_id"] == player_id
    )


def test_profile_snapshot_uses_only_strictly_prior_matches():
    rows = [
        _point("m1", "2026-09-01T10:00:00Z", 1, 2, 1, 1, event_index=0),
        _point("m1", "2026-09-01T10:00:00Z", 1, 2, 2, 1, event_index=1),
        _point("m2", "2026-09-02T10:00:00Z", 1, 3, 1, 3, event_index=0),
    ]
    snapshots, summary = build_snapshots_from_rows(rows)

    m1 = _snapshot(snapshots, "m1", 1)
    assert m1["overall_prior"]["matches"] == 0
    assert m1["overall_prior"]["serve_win_rate"] is None

    m2 = _snapshot(snapshots, "m2", 1)
    assert m2["overall_prior"]["matches"] == 1
    assert m2["overall_prior"]["serve_points"] == 1
    assert m2["overall_prior"]["serve_wins"] == 1
    assert m2["overall_prior"]["serve_win_rate"] == 1.0
    assert m2["overall_prior"]["return_points"] == 1
    assert m2["overall_prior"]["return_wins"] == 1
    assert m2["overall_prior"]["return_win_rate"] == 1.0
    assert summary["training_join_enabled"] is False
    assert summary["profile_threshold_activation_enabled"] is False


def test_same_time_matches_cannot_see_each_other():
    rows = [
        _point("m1", "2026-09-01T10:00:00Z", 1, 2, 1, 1),
        _point("m2", "2026-09-01T10:00:00Z", 1, 3, 1, 1),
        _point("m3", "2026-09-02T10:00:00Z", 1, 4, 1, 1),
    ]
    snapshots, summary = build_snapshots_from_rows(rows)
    assert _snapshot(snapshots, "m1", 1)["overall_prior"]["matches"] == 0
    assert _snapshot(snapshots, "m2", 1)["overall_prior"]["matches"] == 0
    assert _snapshot(snapshots, "m3", 1)["overall_prior"]["matches"] == 2
    assert summary["same_time_groups"] == 1
    assert summary["same_time_matches_count_as_prior"] is False


def test_same_surface_profile_is_separate_from_overall_history():
    rows = [
        _point("hard-old", "2026-09-01T10:00:00Z", 1, 2, 1, 1, surface="hard"),
        _point("clay-old", "2026-09-02T10:00:00Z", 1, 3, 1, 3, surface="clay"),
        _point("hard-target", "2026-09-03T10:00:00Z", 1, 4, 1, 1, surface="hard"),
    ]
    snapshots, _ = build_snapshots_from_rows(rows)
    target = _snapshot(snapshots, "hard-target", 1)
    assert target["overall_prior"]["matches"] == 2
    assert target["same_surface_prior"]["matches"] == 1


def test_non_strict_rows_never_enter_profile_history():
    bad = _point("bad", "2026-09-01T10:00:00Z", 1, 2, 1, 1)
    bad["context_ready_player_point"] = False
    good = _point("good", "2026-09-02T10:00:00Z", 1, 3, 1, 1)
    snapshots, summary = build_snapshots_from_rows([bad, good])
    target = _snapshot(snapshots, "good", 1)
    assert target["overall_prior"]["matches"] == 0
    assert summary["strict_matches"] == 1
    assert summary["source_counts"]["non_strict_rows_skipped"] == 1


def test_current_profiles_exclude_entire_current_card_from_history():
    from backend.player_dna_shadow_profiles import build_current_target_profiles

    point_rows = [
        _point("old", "2026-09-01T10:00:00Z", 1, 9, 1, 1),
        # Current-card match already present in PBP must never leak into later target.
        _point("current-a", "2026-09-04T09:00:00Z", 1, 2, 1, 1),
    ]
    targets = [
        {
            "id": "current-a",
            "scheduled_time": "2026-09-04T09:00:00Z",
            "p1_id": 1,
            "p2_id": 2,
            "p1": "One",
            "p2": "Two",
            "surface": "hard",
            "tour": "atp",
            "best_of": 3,
            "p1_rank": 11,
            "p2_rank": 22,
        },
        {
            "id": "current-b",
            "scheduled_time": "2026-09-04T12:00:00Z",
            "p1_id": 1,
            "p2_id": 3,
            "p1": "One",
            "p2": "Three",
            "surface": "hard",
            "tour": "atp",
            "best_of": 3,
            "p1_rank": 11,
            "p2_rank": 33,
        },
    ]
    snapshots, summary = build_current_target_profiles(point_rows, targets)
    a = _snapshot(snapshots, "current-a", 1)
    b = _snapshot(snapshots, "current-b", 1)
    assert a["overall_prior"]["matches"] == 1
    assert b["overall_prior"]["matches"] == 1
    assert a["mode"] == "SHADOW_CURRENT_AS_OF_PROFILE"
    assert a["player_ranking"] == 11
    assert a["opponent_ranking"] == 22
    assert b["player_ranking"] == 11
    assert b["opponent_ranking"] == 33
    assert b["current_card_excluded_from_history"] is True
    assert summary["excluded_current_history_matches"] == 1


def test_current_profiles_require_stable_provider_ids():
    from backend.player_dna_shadow_profiles import build_current_target_profiles

    snapshots, summary = build_current_target_profiles([], [{
        "id": "bad",
        "scheduled_time": "2026-09-04T10:00:00Z",
        "p1_id": None,
        "p2_id": 2,
        "surface": "hard",
        "tour": "atp",
        "best_of": 3,
    }])
    assert snapshots == []
    assert summary["targets_seen"] == 0
    assert summary["rejected_targets"]["missing_stable_identity_or_time"] == 1


def test_current_profiles_fallback_to_latest_strict_prior_provider_ranking():
    from backend.player_dna_shadow_profiles import build_current_target_profiles

    p1_old = _point("p1-old", "2026-09-01T10:00:00Z", 1, 9, 1, 1)
    p1_old["p1_ranking"] = 77
    p1_old["p2_ranking"] = 190

    p2_old = _point("p2-old", "2026-09-02T10:00:00Z", 2, 8, 2, 2)
    p2_old["p1_ranking"] = 88
    p2_old["p2_ranking"] = 155

    snapshots, summary = build_current_target_profiles(
        [p1_old, p2_old],
        [{
            "id": "current",
            "scheduled_time": "2026-09-03T10:00:00Z",
            "p1_id": 1,
            "p2_id": 2,
            "p1": "One",
            "p2": "Two",
            "surface": "hard",
            "tour": "challenger",
            "best_of": 3,
            "p1_rank": None,
            "p2_rank": None,
        }],
    )

    p1 = _snapshot(snapshots, "current", 1)
    p2 = _snapshot(snapshots, "current", 2)
    assert p1["player_ranking"] == 77
    assert p2["player_ranking"] == 88
    assert p1["player_ranking_source"] == "latest_strict_prior_provider_match_context"
    assert p2["player_ranking_source"] == "latest_strict_prior_provider_match_context"
    assert p1["player_ranking_source_match_id"] == "p1-old"
    assert p2["player_ranking_source_match_id"] == "p2-old"
    ranking = summary["ranking_context"]
    assert ranking["provider_backed_only"] is True
    assert ranking["name_or_fuzzy_fallback_forbidden"] is True
    assert ranking["strict_prior_provider_context_fallback_enabled"] is True
    assert ranking["snapshots_with_prior_provider_player_rank"] == 2


def test_current_fixture_ranking_wins_over_prior_provider_ranking():
    from backend.player_dna_shadow_profiles import build_current_target_profiles

    old = _point("old-rank", "2026-09-01T10:00:00Z", 1, 2, 1, 1)
    old["p1_ranking"] = 77
    old["p2_ranking"] = 88
    snapshots, summary = build_current_target_profiles(
        [old],
        [{
            "id": "current-rank",
            "scheduled_time": "2026-09-03T10:00:00Z",
            "p1_id": 1,
            "p2_id": 2,
            "p1": "One",
            "p2": "Two",
            "surface": "hard",
            "tour": "challenger",
            "best_of": 3,
            "p1_rank": 11,
            "p2_rank": 22,
        }],
    )
    p1 = _snapshot(snapshots, "current-rank", 1)
    p2 = _snapshot(snapshots, "current-rank", 2)
    assert p1["player_ranking"] == 11
    assert p2["player_ranking"] == 22
    assert p1["player_ranking_source"] == "current_fixture_provider"
    assert p2["player_ranking_source"] == "current_fixture_provider"
    assert summary["ranking_context"]["snapshots_with_current_fixture_player_rank"] == 2



def test_canonical_profile_exposes_exact_l5_l10_l20_windows_without_changing_baseline():
    rows = []
    for day in range(1, 9):
        rows.append(
            _point(
                f"m{day}",
                f"2026-08-{day:02d}T10:00:00Z",
                1,
                100 + day,
                1,
                1,
                surface="hard",
            )
        )

    snapshots, summary = build_snapshots_from_rows(rows)
    target = _snapshot(snapshots, "m8", 1)
    rolling = target["rolling_prior"]["all_surface"]["windows"]

    assert target["overall_prior"]["matches"] == 7
    assert rolling["L5"]["requested_matches"] == 5
    assert rolling["L5"]["matches_used"] == 5
    assert rolling["L5"]["matches"] == 5
    assert rolling["L5"]["window_full"] is True
    assert rolling["L5"]["match_coverage"] == 1.0
    assert rolling["L10"]["matches_used"] == 7
    assert rolling["L10"]["window_full"] is False
    assert rolling["L10"]["match_coverage"] == 0.7
    assert rolling["L20"]["matches_used"] == 7
    assert rolling["L20"]["match_coverage"] == 0.35
    assert target["rolling_prior"]["all_surface"]["trend"]["serve_l5_minus_l20"] == 0.0

    rolling_summary = summary["features"]["rolling_prior"]
    assert rolling_summary["windows"] == [5, 10, 20]
    assert rolling_summary["training_join_enabled"] is False
    assert rolling_summary["shrinkage_activation_enabled"] is False
    assert rolling_summary["shrinkage_requires_separate_data_driven_gate"] is True


def test_canonical_rolling_same_surface_uses_only_prior_matching_surface():
    rows = [
        _point("h1", "2026-08-01T10:00:00Z", 1, 2, 1, 1, surface="hard"),
        _point("c1", "2026-08-02T10:00:00Z", 1, 3, 1, 1, surface="clay"),
        _point("h2", "2026-08-03T10:00:00Z", 1, 4, 1, 1, surface="hard"),
        _point("c2", "2026-08-04T10:00:00Z", 1, 5, 1, 1, surface="clay"),
        _point("target", "2026-08-05T10:00:00Z", 1, 6, 1, 1, surface="hard"),
    ]
    snapshots, _ = build_snapshots_from_rows(rows)
    target = _snapshot(snapshots, "target", 1)
    same_surface = target["rolling_prior"]["same_surface"]

    assert same_surface["surface"] == "hard"
    assert same_surface["windows"]["L5"]["matches_used"] == 2
    assert same_surface["windows"]["L10"]["matches_used"] == 2
    assert same_surface["windows"]["L20"]["matches_used"] == 2
    assert target["overall_prior"]["matches"] == 4
    assert target["same_surface_prior"]["matches"] == 2


def test_canonical_rolling_windows_keep_same_timestamp_isolation():
    rows = [
        _point("same-a", "2026-08-01T10:00:00Z", 1, 2, 1, 1),
        _point("same-b", "2026-08-01T10:00:00Z", 1, 3, 1, 1),
        _point("later", "2026-08-02T10:00:00Z", 1, 4, 1, 1),
    ]
    snapshots, _ = build_snapshots_from_rows(rows)

    a = _snapshot(snapshots, "same-a", 1)["rolling_prior"]["all_surface"]["windows"]["L5"]
    b = _snapshot(snapshots, "same-b", 1)["rolling_prior"]["all_surface"]["windows"]["L5"]
    later = _snapshot(snapshots, "later", 1)["rolling_prior"]["all_surface"]["windows"]["L5"]

    assert a["matches_used"] == 0
    assert b["matches_used"] == 0
    assert later["matches_used"] == 2


def test_current_card_exclusion_applies_to_canonical_rolling_windows_too():
    from backend.player_dna_shadow_profiles import build_current_target_profiles

    point_rows = [
        _point("old", "2026-08-01T10:00:00Z", 1, 9, 1, 1),
        _point("current-a", "2026-08-04T09:00:00Z", 1, 2, 1, 1),
    ]
    targets = [
        {
            "id": "current-a",
            "scheduled_time": "2026-08-04T09:00:00Z",
            "p1_id": 1,
            "p2_id": 2,
            "p1": "One",
            "p2": "Two",
            "surface": "hard",
            "tour": "atp",
            "best_of": 3,
        },
        {
            "id": "current-b",
            "scheduled_time": "2026-08-04T12:00:00Z",
            "p1_id": 1,
            "p2_id": 3,
            "p1": "One",
            "p2": "Three",
            "surface": "hard",
            "tour": "atp",
            "best_of": 3,
        },
    ]

    snapshots, summary = build_current_target_profiles(point_rows, targets)
    a = _snapshot(snapshots, "current-a", 1)
    b = _snapshot(snapshots, "current-b", 1)

    assert a["rolling_prior"]["all_surface"]["windows"]["L5"]["matches_used"] == 1
    assert b["rolling_prior"]["all_surface"]["windows"]["L5"]["matches_used"] == 1
    assert summary["rolling_profiles"]["windows"] == [5, 10, 20]
    assert summary["rolling_profiles"]["training_join_enabled"] is False
    assert summary["rolling_profiles"]["shrinkage_activation_enabled"] is False



def test_canonical_profiles_include_pressure_rates_without_scorer_activation():
    rows = [
        # P1 saves a break point, wins a deuce point, then loses a 30:30 point.
        _point("pressure-old", "2026-09-01T10:00:00Z", 1, 2, 1, 1, event_index=1, points=("30", "40")),
        _point("pressure-old", "2026-09-01T10:00:00Z", 1, 2, 1, 1, event_index=2, points=("40", "40")),
        _point("pressure-old", "2026-09-01T10:00:00Z", 1, 2, 1, 2, event_index=3, points=("30", "30")),
        # Three proven P1 service games: hold, break against, hold.
        _point(
            "pressure-old", "2026-09-01T10:00:00Z", 1, 2, 1, 1,
            event_index=10, points=("40", "30"),
            transition_kind="game_score_changed", atomic_reason="atomic_game_boundary",
        ),
        # P1 breaks P2 on the first observed P1 return game.
        _point(
            "pressure-old", "2026-09-01T10:00:00Z", 1, 2, 2, 1,
            event_index=20, points=("40", "30"),
            transition_kind="game_score_changed", atomic_reason="atomic_game_boundary",
        ),
        _point(
            "pressure-old", "2026-09-01T10:00:00Z", 1, 2, 1, 2,
            event_index=30, points=("30", "40"),
            transition_kind="game_score_changed", atomic_reason="atomic_game_boundary",
        ),
        _point(
            "pressure-old", "2026-09-01T10:00:00Z", 1, 2, 1, 1,
            event_index=40, points=("40", "15"),
            transition_kind="game_score_changed", atomic_reason="atomic_game_boundary",
        ),
        _point("pressure-target", "2026-09-02T10:00:00Z", 1, 3, 1, 1),
    ]

    snapshots, summary = build_snapshots_from_rows(rows)
    target = _snapshot(snapshots, "pressure-target", 1)
    overall = target["overall_prior"]
    same_surface = target["same_surface_prior"]
    l5 = target["rolling_prior"]["all_surface"]["windows"]["L5"]

    assert overall["service_games"] == 3
    assert overall["holds"] == 2
    assert overall["hold_rate"] == 0.666667
    assert overall["return_games"] == 1
    assert overall["breaks"] == 1
    assert overall["break_rate"] == 1.0

    assert overall["bp_faced"] == 2
    assert overall["bp_saved"] == 1
    assert overall["bp_save_rate"] == 0.5
    assert overall["bp_chances"] == 1
    assert overall["bp_converted"] == 1
    assert overall["bp_conversion_rate"] == 1.0

    assert overall["deuce_serve_points"] == 1
    assert overall["deuce_serve_wins"] == 1
    assert overall["deuce_serve_win_rate"] == 1.0
    assert overall["thirty_all_serve_points"] == 1
    assert overall["thirty_all_serve_wins"] == 0
    assert overall["thirty_all_serve_win_rate"] == 0.0

    assert overall["early_service_game_1"] == 1
    assert overall["early_service_game_1_holds"] == 1
    assert overall["early_service_game_1_hold_rate"] == 1.0
    assert overall["early_service_game_2"] == 1
    assert overall["early_service_game_2_holds"] == 0
    assert overall["early_service_game_2_hold_rate"] == 0.0
    assert overall["early_service_game_3"] == 1
    assert overall["early_service_game_3_holds"] == 1
    assert overall["early_service_game_3_hold_rate"] == 1.0
    assert overall["early_return_game_1"] == 1
    assert overall["early_return_game_1_breaks"] == 1
    assert overall["early_return_game_1_break_rate"] == 1.0

    assert same_surface["hold_rate"] == overall["hold_rate"]
    assert l5["hold_rate"] == overall["hold_rate"]
    assert l5["bp_save_rate"] == overall["bp_save_rate"]
    assert target["rolling_prior"]["all_surface"]["trend"]["hold_l5_minus_l10"] == 0.0
    assert target["rolling_prior"]["all_surface"]["trend"]["bp_save_l5_minus_l20"] == 0.0

    contract = summary["pressure_profiles"]
    assert contract["included_in_canonical_profiles"] is True
    assert contract["training_join_enabled"] is False
    assert contract["scorer_feature_activation_enabled"] is False
    assert contract["strict_atomic_game_boundaries_only"] is True
    assert contract["set_boundary_reconstruction_enabled"] is False
    assert contract["missing_game_reconstruction_enabled"] is False
    assert "hold_rate" in summary["features"]["overall_prior"]
    assert summary["features"]["rolling_prior"]["pressure_rates_in_windows"] is True


def test_set_boundary_is_not_reconstructed_into_pressure_profile():
    rows = [
        _point("boundary-old", "2026-09-01T10:00:00Z", 1, 2, 1, 1, event_index=1),
        _point(
            "boundary-old", "2026-09-01T10:00:00Z", 1, 2, 1, 1,
            event_index=2, points=("40", "30"),
            transition_kind="set_score_changed",
            atomic_reason="set_boundary_not_yet_proven",
            trainable_point=False,
            atomic_transition=False,
            context_ready=False,
        ),
        _point("boundary-target", "2026-09-02T10:00:00Z", 1, 3, 1, 1),
    ]

    snapshots, summary = build_snapshots_from_rows(rows)
    target = _snapshot(snapshots, "boundary-target", 1)
    assert target["overall_prior"]["matches"] == 1
    assert target["overall_prior"]["service_games"] == 0
    assert target["overall_prior"]["holds"] == 0
    assert target["overall_prior"]["hold_rate"] is None
    assert summary["source_counts"]["set_boundary_not_yet_proven_rows_excluded"] == 1
    assert summary["pressure_profiles"]["set_boundary_reconstruction_enabled"] is False


def test_current_card_exclusion_also_blocks_pressure_history():
    from backend.player_dna_shadow_profiles import build_current_target_profiles

    old_hold = _point(
        "old-pressure", "2026-09-01T10:00:00Z", 1, 9, 1, 1,
        event_index=1, points=("40", "15"),
        transition_kind="game_score_changed", atomic_reason="atomic_game_boundary",
    )
    current_break = _point(
        "current-pressure-a", "2026-09-04T09:00:00Z", 1, 2, 1, 2,
        event_index=1, points=("30", "40"),
        transition_kind="game_score_changed", atomic_reason="atomic_game_boundary",
    )
    targets = [
        {
            "id": "current-pressure-a",
            "scheduled_time": "2026-09-04T09:00:00Z",
            "p1_id": 1,
            "p2_id": 2,
            "p1": "One",
            "p2": "Two",
            "surface": "hard",
            "tour": "atp",
            "best_of": 3,
        },
        {
            "id": "current-pressure-b",
            "scheduled_time": "2026-09-04T12:00:00Z",
            "p1_id": 1,
            "p2_id": 3,
            "p1": "One",
            "p2": "Three",
            "surface": "hard",
            "tour": "atp",
            "best_of": 3,
        },
    ]

    snapshots, summary = build_current_target_profiles(
        [old_hold, current_break],
        targets,
    )
    later = _snapshot(snapshots, "current-pressure-b", 1)
    assert later["overall_prior"]["service_games"] == 1
    assert later["overall_prior"]["holds"] == 1
    assert later["overall_prior"]["hold_rate"] == 1.0
    assert later["rolling_prior"]["all_surface"]["windows"]["L5"]["service_games"] == 1
    assert summary["excluded_current_history_matches"] == 1
    assert summary["pressure_profiles"]["scorer_feature_activation_enabled"] is False



def _service_split_match(match_id, when, p1, p2, surface="hard"):
    scheduled = datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone(timezone.utc)
    return {
        "match_id": match_id,
        "scheduled": scheduled,
        "surface": surface,
        "p1": p1,
        "p2": p2,
        "raw_ratios_only": True,
        "terminal_stats_snapshot": True,
        "stable_pbp_provider_ids": True,
        "contrib": {
            p1: {
                "first_serve_matches": 1,
                "first_serve_points": 40,
                "first_serve_wins": 28,
                "second_serve_matches": 1,
                "second_serve_points": 20,
                "second_serve_wins": 10,
                "first_return_matches": 1,
                "first_return_points": 35,
                "first_return_wins": 14,
                "second_return_matches": 1,
                "second_return_points": 18,
                "second_return_wins": 9,
            },
            p2: {
                "first_serve_matches": 1,
                "first_serve_points": 35,
                "first_serve_wins": 21,
                "second_serve_matches": 1,
                "second_serve_points": 18,
                "second_serve_wins": 9,
                "first_return_matches": 1,
                "first_return_points": 40,
                "first_return_wins": 12,
                "second_return_matches": 1,
                "second_return_points": 20,
                "second_return_wins": 10,
            },
        },
    }


def test_canonical_profile_includes_terminal_pbp_service_splits_only_from_prior_match():
    rows = [
        _point("m1", "2026-09-01T10:00:00Z", 1, 2, 1, 1),
        _point("m2", "2026-09-02T10:00:00Z", 1, 3, 1, 1),
    ]
    splits = [
        _service_split_match("m1", "2026-09-01T10:00:00Z", 1, 2),
        _service_split_match("m2", "2026-09-02T10:00:00Z", 1, 3),
    ]

    snapshots, summary = build_snapshots_from_rows(
        rows,
        service_split_matches=splits,
    )

    first = _snapshot(snapshots, "m1", 1)
    target = _snapshot(snapshots, "m2", 1)

    assert first["overall_prior"]["first_serve_matches"] == 0
    assert first["overall_prior"]["first_serve_win_rate"] is None

    assert target["overall_prior"]["first_serve_matches"] == 1
    assert target["overall_prior"]["first_serve_points"] == 40
    assert target["overall_prior"]["first_serve_wins"] == 28
    assert target["overall_prior"]["first_serve_win_rate"] == 0.7
    assert target["overall_prior"]["second_serve_win_rate"] == 0.5
    assert target["overall_prior"]["first_return_win_rate"] == 0.4
    assert target["overall_prior"]["second_return_win_rate"] == 0.5

    contract = summary["service_split_profiles"]
    assert contract["included_in_canonical_profiles"] is True
    assert contract["stable_pbp_provider_ids_only"] is True
    assert contract["historical_csv_id_namespace_used"] is False
    assert contract["raw_ratios_only"] is True
    assert contract["training_join_enabled"] is False
    assert contract["scorer_feature_activation_enabled"] is False


def test_canonical_service_splits_preserve_same_timestamp_isolation():
    when = "2026-09-01T10:00:00Z"
    rows = [
        _point("m1", when, 1, 2, 1, 1),
        _point("m2", when, 1, 3, 1, 1),
        _point("later", "2026-09-02T10:00:00Z", 1, 4, 1, 1),
    ]
    splits = [
        _service_split_match("m1", when, 1, 2),
        _service_split_match("m2", when, 1, 3),
    ]

    snapshots, _ = build_snapshots_from_rows(rows, service_split_matches=splits)

    assert _snapshot(snapshots, "m1", 1)["overall_prior"]["first_serve_matches"] == 0
    assert _snapshot(snapshots, "m2", 1)["overall_prior"]["first_serve_matches"] == 0
    assert _snapshot(snapshots, "later", 1)["overall_prior"]["first_serve_matches"] == 2


def test_canonical_service_split_join_rejects_identity_time_or_surface_mismatch():
    rows = [
        _point("m1", "2026-09-01T10:00:00Z", 1, 2, 1, 1, surface="hard"),
        _point("m2", "2026-09-02T10:00:00Z", 1, 3, 1, 1, surface="hard"),
    ]
    bad = _service_split_match(
        "m1",
        "2026-09-01T10:00:00Z",
        1,
        999,
        surface="hard",
    )

    snapshots, summary = build_snapshots_from_rows(
        rows,
        service_split_matches=[bad],
    )

    target = _snapshot(snapshots, "m2", 1)
    assert target["overall_prior"]["first_serve_matches"] == 0
    assert summary["source_counts"]["service_split_identity_time_surface_mismatch"] == 1


def test_service_split_support_readiness_counts_prior_matches_not_points():
    rows = [
        _point("m1", "2026-09-01T10:00:00Z", 1, 2, 1, 1),
        _point("m2", "2026-09-02T10:00:00Z", 1, 3, 1, 1),
        _point("m3", "2026-09-03T10:00:00Z", 1, 4, 1, 1),
        _point("m4", "2026-09-04T10:00:00Z", 1, 5, 1, 1),
    ]
    splits = [
        _service_split_match("m1", "2026-09-01T10:00:00Z", 1, 2),
        _service_split_match("m2", "2026-09-02T10:00:00Z", 1, 3),
        _service_split_match("m3", "2026-09-03T10:00:00Z", 1, 4),
    ]

    _, summary = build_snapshots_from_rows(rows, service_split_matches=splits)

    first = summary["service_split_readiness_any_surface"]["first_serve"]
    assert first["1"]["targets"] > 0
    assert first["3"]["targets"] > 0
    assert first["5"]["targets"] == 0



def _trend_fixture_rows(*, rising: bool):
    rows = []
    # 20 strict prior matches + one target. Each prior match contributes one
    # P1 service point, so the rolling serve rates are exact and transparent.
    for day in range(1, 21):
        if rising:
            winner = 2 if day <= 15 else 1
        else:
            winner = 1 if day <= 15 else 2
        rows.append(
            _point(
                f"trend-{day:02d}",
                f"2026-08-{day:02d}T10:00:00Z",
                1,
                2,
                1,
                winner,
                surface="hard",
            )
        )
    rows.append(
        _point(
            "trend-target",
            "2026-08-21T10:00:00Z",
            1,
            3,
            1,
            1,
            surface="hard",
        )
    )
    return rows


def test_master_plan_rising_l5_vs_weaker_l20_is_exposed_without_activation():
    snapshots, summary = build_snapshots_from_rows(
        _trend_fixture_rows(rising=True)
    )
    target = _snapshot(snapshots, "trend-target", 1)
    rolling = target["rolling_prior"]["all_surface"]
    trend = rolling["trend"]

    assert rolling["windows"]["L5"]["serve_win_rate"] == 1.0
    assert rolling["windows"]["L20"]["serve_win_rate"] == 0.25
    assert trend["serve_l5_minus_l20"] == 0.75

    # The long baseline remains the canonical prior; the trend is diagnostic.
    assert target["overall_prior"]["serve_win_rate"] == 0.25
    policy = target["rolling_prior"]["policy"]
    assert policy["raw_windows_are_diagnostic_only"] is True
    assert policy["training_join_enabled"] is False
    assert policy["shrinkage_activation_enabled"] is False
    assert policy["long_baseline_remains_overall_prior"] is True
    assert summary["features"]["rolling_prior"]["training_join_enabled"] is False


def test_master_plan_falling_l5_vs_strong_l20_is_exposed_without_activation():
    snapshots, _ = build_snapshots_from_rows(
        _trend_fixture_rows(rising=False)
    )
    target = _snapshot(snapshots, "trend-target", 1)
    rolling = target["rolling_prior"]["all_surface"]
    trend = rolling["trend"]

    assert rolling["windows"]["L5"]["serve_win_rate"] == 0.0
    assert rolling["windows"]["L20"]["serve_win_rate"] == 0.75
    assert trend["serve_l5_minus_l20"] == -0.75

    # No hidden recency replacement of the baseline is allowed.
    assert target["overall_prior"]["serve_win_rate"] == 0.75
    assert target["rolling_prior"]["policy"]["training_join_enabled"] is False
    assert target["rolling_prior"]["policy"]["shrinkage_activation_enabled"] is False
