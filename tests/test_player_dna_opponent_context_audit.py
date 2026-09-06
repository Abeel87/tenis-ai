from backend.player_dna_opponent_context_audit import audit_profile_snapshots


def _prior(matches):
    if matches <= 0:
        return {
            "matches": 0,
            "serve_points": 0,
            "serve_wins": 0,
            "serve_win_rate": None,
            "return_points": 0,
            "return_wins": 0,
            "return_win_rate": None,
            "tiebreak_points": 0,
            "tiebreak_wins": 0,
            "tiebreak_win_rate": None,
        }
    return {
        "matches": matches,
        "serve_points": matches * 10,
        "serve_wins": matches * 6,
        "serve_win_rate": 0.6,
        "return_points": matches * 10,
        "return_wins": matches * 4,
        "return_win_rate": 0.4,
        "tiebreak_points": 0,
        "tiebreak_wins": 0,
        "tiebreak_win_rate": None,
    }


def _match_rows(
    match_id,
    when,
    p1,
    p2,
    *,
    surface="hard",
    p1_prior=0,
    p2_prior=0,
    p1_surface_prior=None,
    p2_surface_prior=None,
):
    p1_surface_prior = p1_prior if p1_surface_prior is None else p1_surface_prior
    p2_surface_prior = p2_prior if p2_surface_prior is None else p2_surface_prior

    def row(player, opponent, side, prior_matches, surface_prior_matches, rank):
        return {
            "version": "player-dna-shadow-profiles-v1",
            "mode": "SHADOW_AS_OF_PROFILE",
            "strict_as_of": True,
            "same_time_matches_count_as_prior": False,
            "training_join_enabled": False,
            "production_influence": False,
            "target_match_id": match_id,
            "target_scheduled_time": when,
            "target_surface": surface,
            "player_side": side,
            "player_id": player,
            "opponent_id": opponent,
            "opponent_ranking": rank,
            "overall_prior": _prior(prior_matches),
            "same_surface_prior": _prior(surface_prior_matches),
        }

    return [
        row(p1, p2, "p1", p1_prior, p1_surface_prior, 20),
        row(p2, p1, "p2", p2_prior, p2_surface_prior, 10),
    ]


def test_common_opponent_is_counted_only_after_both_histories_are_strictly_prior():
    rows = []
    rows += _match_rows("a-x", "2026-01-01T10:00:00Z", 1, 9)
    rows += _match_rows("b-x", "2026-01-02T10:00:00Z", 2, 9)
    rows += _match_rows("a-b", "2026-01-03T10:00:00Z", 1, 2)

    report = audit_profile_snapshots(rows)
    overall = report["common_opponent_coverage"]["overall"]
    same_surface = report["common_opponent_coverage"]["same_surface"]

    assert report["paired_matches"] == 3
    assert overall["targets"] == 3
    assert overall["with_any"] == 1
    assert overall["rate_with_any"] == 0.333333
    assert overall["max"] == 1
    assert same_surface["with_any"] == 1
    assert report["common_opponent_coverage"]["policy"]["only_strictly_prior_opponents_count"] is True


def test_same_timestamp_matches_do_not_create_common_opponent_for_each_other():
    rows = []
    rows += _match_rows("a-x", "2026-01-01T10:00:00Z", 1, 9)
    rows += _match_rows("b-x", "2026-01-01T10:00:00Z", 2, 9)
    rows += _match_rows("a-b-same-time", "2026-01-01T10:00:00Z", 1, 2)
    rows += _match_rows("a-b-later", "2026-01-02T10:00:00Z", 1, 2)

    report = audit_profile_snapshots(rows)
    overall = report["common_opponent_coverage"]["overall"]

    assert report["paired_matches"] == 4
    # The same-time A-B target sees no A-X/B-X history. Only the later target can.
    assert overall["with_any"] == 1
    assert report["same_time_matches_count_as_prior"] is False
    assert report["common_opponent_coverage"]["policy"]["same_timestamp_group_isolated"] is True


def test_opponent_strength_history_support_uses_opponents_own_pre_match_profile():
    rows = []
    # For player 1, opponent 9 already had 3 prior matches before a-x.
    # Player 1 itself had none; readiness must come from opponent row 9, not row 1.
    rows += _match_rows(
        "a-x",
        "2026-01-01T10:00:00Z",
        1,
        9,
        p1_prior=0,
        p2_prior=3,
    )
    rows += _match_rows(
        "a-b",
        "2026-01-02T10:00:00Z",
        1,
        2,
        p1_prior=1,
        p2_prior=0,
    )

    report = audit_profile_snapshots(rows)
    support = report["opponent_strength_history_support"]["overall"]

    assert report["player_match_entries"] == 4
    # Threshold 1 also counts the later a-b history entry for player 2 because
    # opponent 1 legitimately has one strictly-prior match by then.
    assert support["1"]["unique_history_entries_ready"] == 2
    # Threshold 3 isolates the intended a-x case: only opponent 9 had three
    # strictly-prior matches before that historical entry.
    assert support["3"]["unique_history_entries_ready"] == 1
    assert support["5"]["unique_history_entries_ready"] == 0
    assert support["3"]["target_rows_with_adjustable_history"]["1"]["targets"] == 1
    assert support["3"]["target_rows_with_adjustable_history"]["1"]["rate"] == 0.25

    same_surface = report["opponent_strength_history_support"]["same_surface"]
    assert same_surface["3"]["unique_history_entries_ready"] == 1

    policy = report["opponent_strength_history_support"]["policy"]
    assert policy["ready_requires_opponent_pre_match_serve_and_return_profile"] is True
    assert policy["readiness_thresholds_reuse_existing_profile_audit_thresholds"] == [1, 3, 5, 10]
    assert policy["no_threshold_activated_for_modeling"] is True
    assert policy["no_adjusted_feature_computed_yet"] is True
    assert policy["future_adjustment_must_be_walk_forward_validated"] is True
    assert report["opponent_adjustment_enabled"] is False
    assert report["training_join_enabled"] is False
