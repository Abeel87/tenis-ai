from backend.player_dna_profile_readiness import audit_rows


def _row(match_id, when, p1, p2, surface="hard", ready=True):
    return {
        "match_id": match_id,
        "match_scheduled_time": when,
        "p1_player_id": p1,
        "p2_player_id": p2,
        "surface": surface,
        "context_ready_player_point": ready,
    }


def test_readiness_uses_only_strictly_prior_matches_and_deduplicates_point_rows():
    rows = [
        _row("m1", "2026-09-01T10:00:00Z", 1, 2, "hard"),
        _row("m1", "2026-09-01T10:00:00Z", 1, 2, "hard"),  # another point, same match
        _row("m2", "2026-09-02T10:00:00Z", 1, 3, "clay"),
        _row("m3", "2026-09-03T10:00:00Z", 1, 4, "hard"),
    ]
    report = audit_rows(rows)
    assert report["context_ready_matches"] == 3
    assert report["players"] == 4
    assert report["player_match_targets"] == 6
    # Player 1 contributes m2 and m3 as targets with >=1 strict prior match.
    assert report["readiness_any_surface"]["1"]["targets"] == 2
    # Only m3 has a previous hard match for player 1.
    assert report["readiness_same_surface"]["1"]["targets"] == 1
    assert report["training_join_enabled"] is False
    assert report["profile_aggregation_enabled"] is False
    assert report["readiness_threshold_activation_enabled"] is False


def test_same_time_matches_never_count_as_prior_history():
    rows = [
        _row("m1", "2026-09-01T10:00:00Z", 1, 2),
        _row("m2", "2026-09-01T10:00:00Z", 1, 3),
        _row("m3", "2026-09-02T10:00:00Z", 1, 4),
    ]
    report = audit_rows(rows)
    assert report["same_time_player_groups"] == 1
    # Only the later m3 can see m1+m2. Neither same-time Sep 1 match sees the other.
    assert report["readiness_any_surface"]["1"]["targets"] == 1
    assert report["readiness_any_surface"]["3"]["targets"] == 0
    assert report["same_time_matches_count_as_prior"] is False


def test_match_without_context_ready_point_is_not_history_evidence():
    rows = [
        _row("bad", "2026-09-01T10:00:00Z", 1, 2, ready=False),
        _row("good", "2026-09-02T10:00:00Z", 1, 3, ready=True),
    ]
    report = audit_rows(rows)
    assert report["context_ready_matches"] == 1
    assert report["readiness_any_surface"]["1"]["targets"] == 0


def test_match_with_valid_context_but_no_strict_point_is_reported_not_lost():
    rows = [
        _row("no-strict", "2026-09-01T10:00:00Z", 1, 2, ready=False),
        _row("strict", "2026-09-02T10:00:00Z", 1, 3, ready=True),
    ]
    report = audit_rows(rows)
    assert report["source_matches_seen"] == 2
    assert report["context_ready_matches"] == 1
    assert report["matches_without_context_ready_points"] == 1
    assert report["player_match_targets"] == 2



def _pressure_row(
    match_id,
    when,
    *,
    p1=1,
    p2=2,
    surface="hard",
    tour="ATP",
    server=1,
    winner=1,
    points=("0", "0"),
    transition_kind="point_score_changed",
    atomic_reason="atomic_point_step",
    trainable=True,
    event_index=0,
    tiebreak=False,
):
    receiver = 3 - server
    server_pid = p1 if server == 1 else p2
    receiver_pid = p1 if receiver == 1 else p2
    return {
        "match_id": match_id,
        "match_scheduled_time": when,
        "p1_player_id": p1,
        "p2_player_id": p2,
        "surface": surface,
        "tour": tour,
        "context_ready_player_point": bool(trainable),
        "trainable_point": bool(trainable),
        "atomic_transition": bool(trainable),
        "atomic_reason": atomic_reason,
        "transition_kind": transition_kind,
        "event_index": event_index,
        "server": server,
        "receiver": receiver,
        "server_player_id": server_pid,
        "receiver_player_id": receiver_pid,
        "point_winner": winner,
        "server_won": winner == server,
        "is_tiebreak_before": tiebreak,
        "score_before": {
            "sets": [0, 0],
            "games": [[0], [0]],
            "points": list(points),
        },
    }


def test_pressure_readiness_uses_canonical_bp_deuce_and_strict_atomic_games():
    rows = [
        _pressure_row(
            "m1",
            "2026-09-01T10:00:00Z",
            server=1,
            winner=1,
            points=("30", "40"),
            event_index=1,
        ),
        _pressure_row(
            "m1",
            "2026-09-01T10:00:00Z",
            server=1,
            winner=1,
            points=("40", "40"),
            event_index=2,
        ),
        _pressure_row(
            "m1",
            "2026-09-01T10:00:00Z",
            server=1,
            winner=2,
            points=("30", "30"),
            event_index=3,
        ),
        _pressure_row(
            "m1",
            "2026-09-01T10:00:00Z",
            server=1,
            winner=1,
            points=("40", "30"),
            transition_kind="game_score_changed",
            atomic_reason="atomic_game_boundary",
            event_index=10,
        ),
        _pressure_row(
            "m1",
            "2026-09-01T10:00:00Z",
            server=1,
            winner=1,
            points=("40", "15"),
            transition_kind="game_score_changed",
            atomic_reason="atomic_game_boundary",
            event_index=20,
        ),
        _pressure_row(
            "m1",
            "2026-09-01T10:00:00Z",
            server=1,
            winner=1,
            points=("40", "0"),
            transition_kind="game_score_changed",
            atomic_reason="atomic_game_boundary",
            event_index=30,
        ),
        _row("m2", "2026-09-02T10:00:00Z", 1, 3, "hard"),
    ]

    report = audit_rows(rows)
    counts = report["pressure_evidence"]["counts"]
    assert counts["strict_atomic_games"] == 3
    assert counts["holds"] == 3
    assert counts.get("breaks", 0) == 0
    assert counts["break_point_opportunities"] == 1
    assert counts["break_points_saved"] == 1
    assert counts.get("break_points_converted", 0) == 0
    assert counts["deuce_points"] == 1
    assert counts["thirty_all_points"] == 1

    any_surface = report["pressure_readiness_any_surface"]
    same_surface = report["pressure_readiness_same_surface"]
    assert any_surface["hold"]["3"]["targets"] == 1
    assert same_surface["hold"]["3"]["targets"] == 1
    assert any_surface["bp_save"]["1"]["targets"] == 1
    assert any_surface["deuce_serve"]["1"]["targets"] == 1
    assert any_surface["thirty_all_serve"]["1"]["targets"] == 1
    assert any_surface["early_service_game_1"]["1"]["targets"] == 1
    assert any_surface["early_service_game_2"]["1"]["targets"] == 1
    assert any_surface["early_service_game_3"]["1"]["targets"] == 1

    assert report["pressure_profile_aggregation_enabled"] is False
    assert report["pressure_training_join_enabled"] is False
    assert report["pressure_feature_activation_enabled"] is False
    assert report["pressure_threshold_activation_enabled"] is False
    assert report["pressure_semantics"]["set_boundary_reconstruction_enabled"] is False
    assert report["pressure_semantics"]["missing_game_reconstruction_enabled"] is False


def test_unproven_set_boundary_never_becomes_pressure_hold_evidence():
    rows = [
        _row("m1", "2026-09-01T10:00:00Z", 1, 2, "hard"),
        _pressure_row(
            "m1",
            "2026-09-01T10:00:00Z",
            server=1,
            winner=1,
            points=("40", "30"),
            transition_kind="set_score_changed",
            atomic_reason="set_boundary_not_yet_proven",
            trainable=False,
            event_index=10,
        ),
        _row("m2", "2026-09-02T10:00:00Z", 1, 3, "hard"),
    ]

    report = audit_rows(rows)
    counts = report["pressure_evidence"]["counts"]
    assert counts.get("strict_atomic_games", 0) == 0
    assert report["pressure_evidence"]["boundary_quality"]["set_boundary_not_yet_proven"] == 1
    assert report["pressure_readiness_any_surface"]["hold"]["1"]["targets"] == 0
    assert report["pressure_readiness_same_surface"]["hold"]["1"]["targets"] == 0



def test_small_sample_shrinkage_readiness_bands_are_strict_as_of_and_diagnostic_only():
    rows = [
        _row(
            f"depth-{day:02d}",
            f"2026-08-{day:02d}T10:00:00Z",
            1,
            100 + day,
            "hard",
        )
        for day in range(1, 12)
    ]

    report = audit_rows(rows)
    readiness = report["small_sample_shrinkage_readiness"]
    any_surface = readiness["any_surface_depth_bands"]
    same_surface = readiness["same_surface_depth_bands"]

    # Player 1 contributes strict-as-of depths 0..10. Each one-off opponent
    # contributes one zero-history target.
    assert report["player_match_targets"] == 22
    assert any_surface["0"]["targets"] == 12
    assert any_surface["1-2"]["targets"] == 2
    assert any_surface["3-4"]["targets"] == 2
    assert any_surface["5-9"]["targets"] == 5
    assert any_surface["10+"]["targets"] == 1
    assert same_surface == any_surface
    assert readiness["targets_below_5_any_surface"] == 16
    assert readiness["targets_below_5_same_surface"] == 16

    policy = readiness["policy"]
    assert policy["diagnostic_only"] is True
    assert policy["shrinkage_activation_enabled"] is False
    assert policy["partial_pooling_activation_enabled"] is False
    assert policy["prior_strength_selected"] is False
    assert policy["candidate_parameter_selection_must_use_train_only_data"] is True
    assert policy["raw_small_sample_rate_must_not_be_promoted_directly"] is True
    assert policy["next_gate"] == "TRAIN_ONLY_EMPIRICAL_BAYES_OR_PARTIAL_POOLING_CHALLENGER"


def test_same_time_group_stays_zero_history_for_shrinkage_readiness():
    rows = [
        _row("same-a", "2026-09-01T10:00:00Z", 1, 2),
        _row("same-b", "2026-09-01T10:00:00Z", 1, 3),
        _row("later", "2026-09-02T10:00:00Z", 1, 4),
    ]

    report = audit_rows(rows)
    bands = report["small_sample_shrinkage_readiness"]["any_surface_depth_bands"]

    # Both same-time targets for player 1 remain at depth 0; only the later
    # match sees the two earlier matches.
    assert bands["0"]["targets"] == 5
    assert bands["1-2"]["targets"] == 1
    assert bands["3-4"]["targets"] == 0
