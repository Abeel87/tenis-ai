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
