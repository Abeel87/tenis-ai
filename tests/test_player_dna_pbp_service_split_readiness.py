from backend.player_dna_pbp_service_split_readiness import (
    MODE,
    audit_payloads,
    inspect_payload,
    terminal_raw_service_split_match,
)


def _payload(*, terminal=True, mismatch=False):
    final_games = [[6, 4], [4, 2]]
    snapshot_games = final_games if terminal else [[3, 1], [2, 1]]
    p2_first_raw = "18/40 (45%)" if mismatch else "22/40 (55%)"
    return {
        "match": {
            "id": "m1",
            "scheduled_time": "2026-09-01T10:00:00Z",
            "surface": "hard",
            "players": {
                "p1": {"id": 101, "name": "Alpha"},
                "p2": {"id": 202, "name": "Beta"},
            }
        },
        "profiles": [
            {
                "created_at": "2026-09-01T12:00:00Z",
                "input_state": {
                    "score": {
                        "sets": [1, 0],
                        "games": snapshot_games,
                        "points": ["0", "0"],
                    },
                    "stats": {
                        "derived": {
                            "p1_first_serve_win_pct": 0.70,
                            "p1_second_serve_win_pct": 0.50,
                            "p1_first_return_win_pct": 0.40,
                            "p1_second_return_win_pct": 0.55,
                            "p2_first_serve_win_pct": 0.55,
                            "p2_second_serve_win_pct": 0.45,
                            "p2_first_return_win_pct": 0.30,
                            "p2_second_return_win_pct": 0.50,
                        },
                        "p1": {
                            "firstServePointsAccuracy": "28/40 (70%)",
                            "secondServePointsAccuracy": "10/20 (50%)",
                            "firstReturnPoints": "16/40 (40%)",
                            "secondReturnPoints": "11/20 (55%)",
                        },
                        "p2": {
                            "firstServePointsAccuracy": p2_first_raw,
                            "secondServePointsAccuracy": "9/20 (45%)",
                            "firstReturnPoints": "12/40 (30%)",
                            "secondReturnPoints": "10/20 (50%)",
                        },
                    },
                },
            }
        ],
        "tape": [
            {"sets": [0, 0], "games": [[0], [0]], "points": ["0", "0"]},
            {"sets": [1, 0], "games": final_games, "points": ["0", "0"]},
        ],
    }


def test_pbp_native_split_audit_uses_stable_provider_sides_and_raw_ratios():
    item = inspect_payload(_payload())

    assert item["stable_identity"] is True
    assert item["stats_profile"] is True
    assert item["terminal_score_match"] is True
    assert item["all_four_splits_both_players"] is True
    assert item["split_values"]["p1"]["first_serve_win_rate"] == 0.70
    assert item["split_values"]["p1"]["first_serve_win_rate_source"] == "raw_ratio"
    assert item["split_values"]["p2"]["second_return_win_rate"] == 0.50
    assert item["raw_vs_derived_checks"] == 8
    assert item["raw_vs_derived_agreements"] == 8


def test_pbp_native_split_audit_rejects_nonterminal_snapshot_for_terminal_gate():
    report = audit_payloads([_payload(terminal=False)] * 120)

    assert report["mode"] == MODE
    assert report["matches_with_all_four_splits_both_players"] == 120
    assert report["terminal_matches_with_all_four_splits"] == 0
    assert report["readiness"]["material_terminal_sample"] is False
    assert report["readiness"]["source_ready_for_canonical_profile_design"] is False


def test_pbp_native_split_audit_semantic_gate_detects_raw_derived_conflict():
    report = audit_payloads([_payload(mismatch=True)] * 120)

    consistency = report["raw_vs_derived_consistency"]
    assert consistency["checks"] == 960
    assert consistency["agreements_within_2pp"] == 840
    assert consistency["semantic_consistency_gate_passed"] is False
    assert report["readiness"]["source_ready_for_canonical_profile_design"] is False


def test_pbp_native_split_audit_passes_readiness_only_with_material_terminal_consistency():
    report = audit_payloads([_payload()] * 120)

    assert report["stable_identity_matches"] == 120
    assert report["terminal_matches_with_all_four_splits"] == 120
    assert report["raw_vs_derived_consistency"]["semantic_consistency_gate_passed"] is True
    assert report["readiness"]["material_terminal_sample"] is True
    assert report["readiness"]["source_ready_for_canonical_profile_design"] is True
    assert report["readiness"]["predictive_signal_proven"] is False

    assert report["production_influence"] is False
    assert report["runtime_scoring_enabled"] is False
    assert report["profile_build_enabled"] is False
    assert report["training_join_enabled"] is False
    assert report["matchup_feature_activation_enabled"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False

    contract = report["contract"]
    assert contract["pbp_native_provider_ids_only"] is True
    assert contract["historical_csv_id_namespace_not_used"] is True
    assert contract["name_or_fuzzy_join_forbidden"] is True
    assert contract["profile_build_requires_separate_gate"] is True
    assert contract["chronological_backtest_required_after_profile_gate"] is True


def test_pbp_native_split_audit_requires_stable_identity():
    bad = _payload()
    bad["match"]["players"]["p1"]["id"] = "101"

    item = inspect_payload(bad)

    assert item == {"stable_identity": False}



def test_terminal_raw_service_split_match_exposes_exact_counts_only():
    item = terminal_raw_service_split_match(_payload(), match_id="m1")

    assert item is not None
    assert item["match_id"] == "m1"
    assert item["p1"] == 101
    assert item["p2"] == 202
    assert item["raw_ratios_only"] is True
    assert item["terminal_stats_snapshot"] is True

    p1 = item["contrib"][101]
    assert p1["first_serve_matches"] == 1
    assert p1["first_serve_wins"] == 28
    assert p1["first_serve_points"] == 40
    assert p1["second_serve_wins"] == 10
    assert p1["second_serve_points"] == 20
    assert p1["first_return_wins"] == 16
    assert p1["first_return_points"] == 40
    assert p1["second_return_wins"] == 11
    assert p1["second_return_points"] == 20


def test_terminal_raw_service_split_match_rejects_nonterminal_snapshot():
    assert terminal_raw_service_split_match(
        _payload(terminal=False),
        match_id="m1",
    ) is None
