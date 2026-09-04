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
