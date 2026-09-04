from backend.player_dna_shadow_profiles import build_snapshots_from_rows


def _point(match_id, when, p1, p2, server, winner, surface="hard", event_index=0):
    receiver = p2 if server == p1 else p1
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
        "point_winner": 1 if winner == p1 else 2,
        "server_won": winner == server,
        "receiver_won": winner == receiver,
        "is_tiebreak_before": False,
        "context_ready_player_point": True,
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
