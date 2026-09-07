from backend.player_dna_service_split_depth_audit import (
    RAW_SLOTS,
    _profile_has_all_four_raw_both,
    _profile_is_terminal,
    audit_payloads,
)


def _score(games):
    return {"sets": [2, 0], "games": games}


def _raw_stats():
    side = {
        "firstServePointsAccuracy": "30/40 (75%)",
        "secondServePointsAccuracy": "12/20 (60%)",
        "firstReturnPoints": "10/30 (33%)",
        "secondReturnPoints": "8/20 (40%)",
    }
    return {"p1": dict(side), "p2": dict(side)}


def _profile(games, *, raw=True, created_at="2026-09-06T12:00:00Z"):
    return {
        "created_at": created_at,
        "input_state": {
            "score": _score(games),
            "stats": _raw_stats() if raw else {"p1": {}, "p2": {}},
        },
    }


def _patch_identity_and_final(monkeypatch):
    monkeypatch.setattr(
        "backend.player_dna_service_split_depth_audit.player_identity_map",
        lambda payload: {1: {"id": 101}, 2: {"id": 202}},
    )
    monkeypatch.setattr(
        "backend.player_dna_service_split_depth_audit._final_tape_score",
        lambda payload: ("[2, 0]", "[6, 3]"),
    )


def test_terminal_and_raw_helpers_are_strict():
    final = ("[2, 0]", "[6, 3]")
    good = _profile([6, 3])
    nonterminal = _profile([5, 3])
    missing_raw = _profile([6, 3], raw=False)

    assert _profile_is_terminal(good, final) is True
    assert _profile_is_terminal(nonterminal, final) is False
    assert _profile_has_all_four_raw_both(good) is True
    assert _profile_has_all_four_raw_both(missing_raw) is False


def test_audit_identifies_selector_only_recovery_without_changing_selector(monkeypatch):
    _patch_identity_and_final(monkeypatch)

    payload = {
        "profiles": [
            _profile([6, 3], created_at="2026-09-06T12:00:00Z"),
            # Later stats-bearing profile regresses to a non-terminal score.
            # The audit may diagnose the earlier terminal snapshot, but it must
            # not silently change the canonical selector.
            _profile([5, 3], created_at="2026-09-06T12:01:00Z"),
        ]
    }

    report = audit_payloads([payload])
    counts = report["counts"]
    comparison = report["comparison"]

    assert counts["latest_terminal_all_four_raw_matches"] == 0
    assert counts["matches_with_any_terminal_all_four_raw"] == 1
    assert counts["recoverable_if_latest_rule_is_only_blocker"] == 1
    assert comparison["potentially_recoverable_matches"] == 1
    assert comparison["safe_selection_change_proven"] is False
    assert comparison["safe_terminal_relaxation_proven"] is False
    assert report["contract"]["canonical_profile_selection_changed"] is False
    assert report["contract"]["runtime_activation_enabled"] is False


def test_audit_separates_raw_depth_from_terminal_proof_gap(monkeypatch):
    _patch_identity_and_final(monkeypatch)

    payload = {
        "profiles": [
            _profile([5, 3], created_at="2026-09-06T12:00:00Z"),
        ]
    }

    report = audit_payloads([payload])
    counts = report["counts"]
    comparison = report["comparison"]
    funnel = report["depth_funnel"]

    assert counts["matches_with_stats_profiles"] == 1
    assert counts["matches_with_any_all_four_raw_profile"] == 1
    assert counts["matches_with_any_terminal_profile"] == 0
    assert counts["matches_with_any_terminal_all_four_raw"] == 0
    assert counts["raw_all_four_outside_terminal_proof_matches"] == 1
    assert comparison["any_profile_all_four_raw_matches"] == 1
    assert comparison["raw_all_four_outside_terminal_proof_matches"] == 1
    assert comparison["terminal_proof_capture_rate_of_any_raw_all_four"] == 0.0
    assert funnel["all_four_raw_present_without_terminal_proof"] == 1
    assert funnel["dominant_observed_gap"] == "all_four_raw_present_without_terminal_proof"
    assert funnel["funnel_accounts_for_all_stable_matches"] is True
    assert report["score_gap_kinds"]["sets_match_games_differ"] == 1


def test_audit_identifies_raw_capture_gap_after_stats_profile(monkeypatch):
    _patch_identity_and_final(monkeypatch)

    payload = {
        "profiles": [
            _profile([6, 3], raw=False),
        ]
    }

    report = audit_payloads([payload])
    counts = report["counts"]
    funnel = report["depth_funnel"]

    assert counts["matches_with_stats_profiles"] == 1
    assert counts["matches_with_any_terminal_profile"] == 1
    assert counts["matches_with_any_all_four_raw_profile"] == 0
    assert counts["matches_with_stats_but_no_any_all_four_raw"] == 1
    assert counts["terminal_profile_missing_all_four_raw_matches"] == 1
    assert funnel["stats_profiles_but_no_all_four_raw_snapshot"] == 1
    assert funnel["funnel_accounts_for_all_stable_matches"] is True
    for slot in RAW_SLOTS:
        assert (
            report["raw_slot_coverage"][slot][
                "matches_with_raw_in_any_stats_profile"
            ]
            == 0
        )


def test_audit_funnel_counts_missing_stats_as_separate_stage(monkeypatch):
    _patch_identity_and_final(monkeypatch)

    report = audit_payloads([{"profiles": []}])
    counts = report["counts"]
    funnel = report["depth_funnel"]

    assert counts["matches_without_stats_profiles"] == 1
    assert counts["matches_with_stats_profiles"] == 0
    assert funnel["no_stats_profile"] == 1
    assert funnel["funnel_accounting_matches"] == 1
    assert funnel["funnel_accounts_for_all_stable_matches"] is True
    assert report["score_gap_kinds"]["no_stats_profile"] == 1
