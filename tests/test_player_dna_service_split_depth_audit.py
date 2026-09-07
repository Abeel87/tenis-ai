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



def test_stats_capture_gap_finds_cached_raw_outside_profile_path(monkeypatch):
    _patch_identity_and_final(monkeypatch)

    payload = {
        "match": {
            "scheduled_time": "2026-09-06T10:00:00Z",
            "surface": "Hard",
        },
        "profiles": [],
        "provider_archive": {
            "late_stats": _raw_stats(),
        },
    }

    report = audit_payloads([payload])
    capture = report["stats_capture_gap"]

    assert capture["matches_without_stats_profiles"] == 1
    assert capture["no_stats_capture_reasons"]["no_profile_entries"] == 1
    assert capture["reasons_account_for_all_missing_stats"] is True
    assert (
        capture["alternate_raw_evidence"]["all_four_raw_cached_elsewhere"]
        == 1
    )
    assert capture["alternate_raw_accounts_for_all_missing_stats"] is True
    assert capture["alternate_raw_max_slots_histogram"]["8"] == 1
    assert capture["by_surface"]["hard"]["stable_matches"] == 1
    assert capture["by_surface"]["hard"]["with_stats_profiles"] == 0
    assert capture["by_surface"]["hard"]["stats_profile_rate"] == 0.0
    assert capture["by_scheduled_month"]["2026-09"]["without_stats_profiles"] == 1
    assert report["contract"]["alternate_raw_container_scan_diagnostic_only"] is True
    assert report["contract"]["alternate_raw_container_authorized_for_history"] is False


def test_stats_capture_gap_distinguishes_profile_without_input_state(monkeypatch):
    _patch_identity_and_final(monkeypatch)

    report = audit_payloads([
        {
            "profiles": [
                {"created_at": "2026-09-06T12:00:00Z"},
            ],
        }
    ])
    capture = report["stats_capture_gap"]

    assert capture["no_stats_capture_reasons"]["profiles_without_input_state"] == 1
    assert (
        capture["alternate_raw_evidence"]["no_raw_stats_like_container_found"]
        == 1
    )
    assert capture["alternate_raw_max_slots_histogram"]["0"] == 1


def test_stats_capture_gap_distinguishes_input_state_without_stats_dict(monkeypatch):
    _patch_identity_and_final(monkeypatch)

    report = audit_payloads([
        {
            "profiles": [
                {
                    "created_at": "2026-09-06T12:00:00Z",
                    "input_state": {"score": _score([6, 3])},
                },
            ],
        }
    ])
    capture = report["stats_capture_gap"]

    assert (
        capture["no_stats_capture_reasons"]["input_state_without_stats_dict"]
        == 1
    )
    assert capture["reasons_account_for_all_missing_stats"] is True



def _identity_only(monkeypatch):
    monkeypatch.setattr(
        "backend.player_dna_service_split_depth_audit.player_identity_map",
        lambda payload: {1: {"id": 101}, 2: {"id": 202}},
    )


def _scaled_raw_stats():
    side = {
        "firstServePointsAccuracy": "15/20 (75%)",
        "secondServePointsAccuracy": "6/10 (60%)",
        "firstReturnPoints": "5/15 (33%)",
        "secondReturnPoints": "4/10 (40%)",
    }
    return {"p1": dict(side), "p2": dict(side)}


def test_partial_raw_validation_pairs_late_snapshot_with_terminal_truth(monkeypatch):
    _identity_only(monkeypatch)

    partial = _profile([5, 4], created_at="2026-09-06T12:00:00Z")
    partial["input_state"]["stats"] = _scaled_raw_stats()
    terminal = _profile([6, 4], created_at="2026-09-06T12:10:00Z")

    payload = {
        "profiles": [partial, terminal],
        "tape": [
            {"sets": [1, 0], "games": [5, 4]},
            {"sets": [2, 0], "games": [6, 4]},
        ],
    }

    report = audit_payloads([payload])
    validation = report["partial_raw_terminal_validation"]

    assert validation["paired_terminal_matches_with_preterminal_all_four_raw"] == 1
    assert validation["overall"]["matches"] == 1
    assert validation["overall"]["field_comparisons"] == 8
    assert validation["overall"]["mean_abs_error_pp"] == 0.0
    assert validation["overall"]["within_5pp_rate"] == 1.0
    assert validation["overall"]["raw_count_monotonic_match_rate"] == 1.0

    at90 = validation["by_minimum_game_progress"]["0.9"]
    assert at90["matches"] == 1
    assert at90["mean_abs_error_pp"] == 0.0

    gate = validation["predeclared_future_gate"]
    assert gate["activation_enabled"] is False
    assert report["contract"]["partial_raw_validation_diagnostic_only"] is True
    assert report["contract"]["partial_raw_authorized_for_canonical_history"] is False
    assert report["contract"]["partial_raw_gate_activation_enabled"] is False


def test_partial_raw_validation_counts_nonterminal_candidates_by_game_progress(monkeypatch):
    _identity_only(monkeypatch)

    partial = _profile([5, 4], created_at="2026-09-06T12:00:00Z")
    partial["input_state"]["stats"] = _scaled_raw_stats()

    payload = {
        "profiles": [partial],
        "tape": [
            {"sets": [1, 0], "games": [5, 4]},
            {"sets": [2, 0], "games": [6, 4]},
        ],
    }

    report = audit_payloads([payload])
    validation = report["partial_raw_terminal_validation"]

    assert report["counts"]["raw_all_four_outside_terminal_proof_matches"] == 1
    assert validation["raw_without_terminal_progress_known_matches"] == 1
    assert (
        validation["raw_without_terminal_candidates_by_progress"]["0.9"]["matches"]
        == 1
    )
    assert (
        validation["raw_without_terminal_candidates_by_progress"]["0.95"]["matches"]
        == 0
    )


def test_partial_raw_validation_detects_nonmonotonic_counts(monkeypatch):
    _identity_only(monkeypatch)

    partial = _profile([5, 4], created_at="2026-09-06T12:00:00Z")
    terminal = _profile([6, 4], created_at="2026-09-06T12:10:00Z")
    partial["input_state"]["stats"]["p1"]["firstServePointsAccuracy"] = "31/41 (76%)"

    payload = {
        "profiles": [partial, terminal],
        "tape": [
            {"sets": [1, 0], "games": [5, 4]},
            {"sets": [2, 0], "games": [6, 4]},
        ],
    }

    report = audit_payloads([payload])
    validation = report["partial_raw_terminal_validation"]

    assert validation["overall"]["matches"] == 1
    assert validation["overall"]["raw_count_monotonic_match_rate"] == 0.0



def _tape_with_score_changes(count=120, final_games=(6, 4)):
    rows = []
    for i in range(count + 1):
        rows.append({
            "sets": [1, 0] if i < count else [2, 0],
            "games": [5, 4] if i < count else list(final_games),
            "points": [i, 0],
        })
    return rows


def _late_raw_stats_95pct():
    side = {
        "firstServePointsAccuracy": "29/38 (76%)",
        "secondServePointsAccuracy": "11/19 (58%)",
        "firstReturnPoints": "10/30 (33%)",
        "secondReturnPoints": "8/20 (40%)",
    }
    return {"p1": dict(side), "p2": dict(side)}


def test_tape_point_coverage_calibrates_terminal_raw_denominators(monkeypatch):
    _identity_only(monkeypatch)

    terminal = _profile([6, 4], created_at="2026-09-06T12:10:00Z")
    payload = {
        "profiles": [terminal],
        "tape": _tape_with_score_changes(120),
    }

    report = audit_payloads([payload])
    validation = report["partial_raw_terminal_validation"]
    calibration = validation["tape_point_coverage_calibration"]

    assert calibration["matches"] == 1
    assert calibration["median_terminal_service_denominator_to_tape_events"] == 1.0
    assert calibration["within_5pct_of_one_rate"] == 1.0
    assert calibration["within_10pct_of_one_rate"] == 1.0
    assert report["contract"]["tape_point_coverage_diagnostic_only"] is True
    assert report["contract"]["tape_point_coverage_authorized_as_terminal_proof"] is False


def test_partial_raw_validation_bins_by_tape_point_coverage(monkeypatch):
    _identity_only(monkeypatch)

    partial = _profile([5, 4], created_at="2026-09-06T12:00:00Z")
    partial["input_state"]["stats"] = _late_raw_stats_95pct()
    terminal = _profile([6, 4], created_at="2026-09-06T12:10:00Z")

    payload = {
        "profiles": [partial, terminal],
        "tape": _tape_with_score_changes(120),
    }

    report = audit_payloads([payload])
    validation = report["partial_raw_terminal_validation"]

    assert validation["by_minimum_tape_point_coverage"]["0.95"]["matches"] == 1
    assert validation["by_minimum_tape_point_coverage"]["0.98"]["matches"] == 0
    assert (
        validation["overall"]["matches"]
        == 1
    )


def test_nonterminal_raw_candidates_are_counted_by_tape_point_coverage(monkeypatch):
    _identity_only(monkeypatch)

    partial = _profile([5, 4], created_at="2026-09-06T12:00:00Z")
    partial["input_state"]["stats"] = _late_raw_stats_95pct()

    payload = {
        "profiles": [partial],
        "tape": _tape_with_score_changes(120),
    }

    report = audit_payloads([payload])
    validation = report["partial_raw_terminal_validation"]
    candidates = validation[
        "raw_without_terminal_candidates_by_tape_point_coverage"
    ]

    assert validation["raw_without_terminal_tape_coverage_known_matches"] == 1
    assert candidates["0.95"]["matches"] == 1
    assert candidates["0.98"]["matches"] == 0



def _timed_final_tape():
    return [
        {
            "sets": [1, 0],
            "games": [5, 4],
            "points": [40, 30],
            "timestamp": "2026-09-06T12:09:55Z",
        },
        {
            "sets": [2, 0],
            "games": [6, 4],
            "points": [0, 0],
            "timestamp": "2026-09-06T12:10:00Z",
        },
    ]


def test_post_final_point_raw_snapshot_is_validated_against_terminal_truth(monkeypatch):
    _identity_only(monkeypatch)

    candidate = _profile([5, 4], created_at="2026-09-06T12:10:05Z")
    terminal = _profile([6, 4], created_at="2026-09-06T12:10:20Z")

    payload = {
        "profiles": [candidate, terminal],
        "tape": _timed_final_tape(),
    }

    report = audit_payloads([payload])
    timing = report["post_final_point_timing_validation"]

    assert timing["paired_nonterminal_after_tape_matches"] == 1
    assert timing["overall"]["matches"] == 1
    assert timing["overall"]["field_comparisons"] == 8
    assert timing["overall"]["mean_abs_error_pp"] == 0.0
    assert timing["overall"]["exact_raw_count_field_rate"] == 1.0
    assert timing["overall"]["all_raw_counts_exact_match_rate"] == 1.0
    assert timing["overall"]["raw_count_monotonic_match_rate"] == 1.0
    assert timing["by_minimum_seconds_after_last_tape"]["5"]["matches"] == 1
    assert timing["by_minimum_seconds_after_last_tape"]["15"]["matches"] == 0
    assert (
        timing["terminal_raw_profile_timing"]["median_seconds_after_last_tape"]
        == 20.0
    )
    assert report["contract"]["post_final_point_timing_diagnostic_only"] is True
    assert (
        report["contract"]["post_final_point_snapshot_authorized_for_history"]
        is False
    )


def test_pre_final_point_raw_snapshot_is_not_post_final_candidate(monkeypatch):
    _identity_only(monkeypatch)

    candidate = _profile([5, 4], created_at="2026-09-06T12:09:59Z")
    terminal = _profile([6, 4], created_at="2026-09-06T12:10:20Z")

    report = audit_payloads([
        {
            "profiles": [candidate, terminal],
            "tape": _timed_final_tape(),
        }
    ])
    timing = report["post_final_point_timing_validation"]

    assert timing["paired_nonterminal_after_tape_matches"] == 0
    assert timing["overall"]["matches"] == 0


def test_nonterminal_only_post_final_raw_is_counted_as_candidate(monkeypatch):
    _identity_only(monkeypatch)

    candidate = _profile([5, 4], created_at="2026-09-06T12:10:30Z")

    report = audit_payloads([
        {
            "profiles": [candidate],
            "tape": _timed_final_tape(),
        }
    ])
    timing = report["post_final_point_timing_validation"]
    candidates = timing[
        "raw_without_terminal_candidates_by_minimum_seconds_after_last_tape"
    ]

    assert report["counts"]["raw_all_four_outside_terminal_proof_matches"] == 1
    assert timing["raw_without_terminal_timing_known_matches"] == 1
    assert candidates["0"]["matches"] == 1
    assert candidates["30"]["matches"] == 1
    assert candidates["60"]["matches"] == 0
