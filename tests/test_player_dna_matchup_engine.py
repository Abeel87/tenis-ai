from backend.player_dna_current_shadow import _serve_feature_row
from backend.player_dna_matchup_engine import (
    EXPECTED_PROFILE_NUMERIC,
    MODE,
    build_matchup_packet,
    evaluate_phase3_reports,
    scorer_feature_row,
)


def _profile(
    *,
    overall_serve=0.64,
    overall_return=0.38,
    surface_serve=0.66,
    surface_return=0.40,
    overall_matches=7,
    surface_matches=4,
):
    return {
        "strict_as_of": True,
        "same_time_matches_count_as_prior": False,
        "overall_prior": {
            "serve_win_rate": overall_serve,
            "return_win_rate": overall_return,
            "matches": overall_matches,
        },
        "same_surface_prior": {
            "serve_win_rate": surface_serve,
            "return_win_rate": surface_return,
            "matches": surface_matches,
        },
    }


def test_canonical_matchup_scorer_row_preserves_current_shadow_feature_contract():
    target = {
        "id": "m1",
        "surface": " Hard ",
        "tour": "atp",
        "best_of": 3,
    }
    server = _profile(
        overall_serve=0.67,
        overall_return=0.39,
        surface_serve=0.69,
        surface_return=0.41,
        overall_matches=8,
        surface_matches=5,
    )
    receiver = _profile(
        overall_serve=0.61,
        overall_return=0.42,
        surface_serve=0.62,
        surface_return=0.44,
        overall_matches=9,
        surface_matches=6,
    )

    canonical = scorer_feature_row(target, server, receiver)
    compatibility = _serve_feature_row(target, server, receiver)

    assert compatibility == canonical
    assert canonical == {
        "match_id": "m1",
        "surface": "hard",
        "tour": "ATP",
        "match_format": "BO3",
        "server_overall_serve_rate": 0.67,
        "receiver_overall_return_rate": 0.42,
        "server_surface_serve_rate": 0.69,
        "receiver_surface_return_rate": 0.44,
        "server_overall_matches": 8,
        "receiver_overall_matches": 9,
        "server_surface_matches": 5,
        "receiver_surface_matches": 6,
    }
    assert tuple(
        key
        for key in canonical
        if key in EXPECTED_PROFILE_NUMERIC
    ) == EXPECTED_PROFILE_NUMERIC


def test_matchup_packet_is_reciprocal_and_optional_interactions_never_activate():
    target = {
        "id": "m2",
        "surface": "clay",
        "tour": "WTA",
        "best_of": 3,
    }
    p1 = _profile(
        overall_serve=0.70,
        overall_return=0.36,
        surface_serve=0.68,
        surface_return=0.37,
        overall_matches=10,
        surface_matches=5,
    )
    p2 = _profile(
        overall_serve=0.60,
        overall_return=0.45,
        surface_serve=0.59,
        surface_return=0.47,
        overall_matches=8,
        surface_matches=4,
    )

    packet = build_matchup_packet(target, p1, p2)

    assert packet["mode"] == MODE
    assert packet["production_influence"] is False
    assert packet["runtime_prediction_change"] is False
    assert packet["symphony2_influence"] is False
    assert packet["superbet_playable_influence"] is False

    p1_row = packet["p1_serving"]["scorer_feature_row"]
    p2_row = packet["p2_serving"]["scorer_feature_row"]
    assert p1_row["server_overall_serve_rate"] == 0.70
    assert p1_row["receiver_overall_return_rate"] == 0.45
    assert p2_row["server_overall_serve_rate"] == 0.60
    assert p2_row["receiver_overall_return_rate"] == 0.36

    diag = packet["p1_serving"]["diagnostics"]
    assert diag["candidate_interactions_diagnostic_only"][
        "overall_serve_return_dominance"
    ] == 0.385
    assert diag["candidate_interactions_diagnostic_only"][
        "prediction_feature_activation_enabled"
    ] is False
    assert diag["support"]["threshold_flags"]["5"]["overall"] is True
    assert diag["support"]["threshold_flags"]["5"]["same_surface"] is False

    contract = packet["feature_contract"]
    for key in (
        "nonlinear_serve_return_interaction_active",
        "opponent_strength_adjustment_active",
        "pressure_profile_interaction_active",
        "tiebreak_profile_interaction_active",
        "recent_form_interaction_active",
        "match_state_profile_interaction_active",
        "small_sample_shrinkage_active",
    ):
        assert contract[key] is False
    assert contract[
        "small_sample_shrinkage_waits_for_fresh_confirmation"
    ] is True


def _reports():
    return {
        "point_scorer": {
            "signal": {
                "legacy_profile_signal_positive": True,
            },
            "stateful_walk_forward": {
                "lean_all_three_folds_positive_on_all_primary_proper_scores": True,
            },
        },
        "serve_return_matchup": {
            "signal": {
                "status": "SERVE_RETURN_MATCHUP_NOT_ROBUST_ENOUGH",
            },
        },
        "opponent_context": {
            "signal": {
                "status": "OPPONENT_CONTEXT_NOT_ROBUST_ENOUGH",
            },
        },
        "pressure": {
            "signal": {
                "status": "PRESSURE_PRIMARY_NOT_ROBUST_ENOUGH",
            },
        },
        "tiebreak": {
            "signal": {
                "status": "TIEBREAK_PROFILE_NOT_ROBUST_ENOUGH",
            },
        },
        "recent_form": {
            "signal": {
                "status": "RECENT_FORM_L5_NOT_ROBUST_ENOUGH",
            },
        },
        "small_sample": {
            "signal": {
                "status": (
                    "SMALL_SAMPLE_SHRINKAGE_ROBUST_HISTORICAL_SIGNAL_"
                    "REQUIRES_FRESH_CONFIRMATION"
                ),
            },
            "fresh_confirmation": {
                "status": "WAITING_FOR_FRESH_SAMPLE",
            },
        },
        "match_state": {
            "tasks": {
                "comeback_bo3": {
                    "signal": {
                        "status": "NOT_ROBUST_ENOUGH",
                    },
                },
                "bo5_late_set": {
                    "signal": {
                        "status": "NOT_ROBUST_ENOUGH",
                    },
                },
            },
        },
    }


def test_phase3_closes_without_composing_individually_failed_interactions():
    report = evaluate_phase3_reports(_reports())

    assert report["phase3_complete"] is True
    assert report["phase4_ready"] is True
    assert (
        report["status"]
        == "PHASE3_COMPLETE_BASELINE_ONLY_OPTIONAL_INTERACTIONS_EXCLUDED"
    )
    assert report["approved_core"]["pre_match_profile_main_effects"] is True
    assert report["approved_core"][
        "lean_point_state_walk_forward_robust_for_phase4"
    ] is True
    assert report["small_sample_shrinkage"]["active"] is False
    assert report["small_sample_shrinkage"][
        "blocked_pending_fresh_confirmation"
    ] is True

    for item in report["excluded_optional_candidates"].values():
        assert item["active"] is False


def test_phase3_gate_fails_closed_when_required_evidence_is_missing():
    reports = _reports()
    reports["pressure"] = {}

    report = evaluate_phase3_reports(reports)

    assert report["all_required_reports_present"] is False
    assert report["phase3_complete"] is False
    assert report["phase4_ready"] is False
    assert report["status"] == "PHASE3_GATE_NOT_COMPLETE"


def test_phase3_gate_does_not_activate_shrinkage_even_after_historical_success():
    reports = _reports()
    reports["small_sample"]["fresh_confirmation"] = {
        "status": "FRESH_CONFIRMATION_POSITIVE_SHADOW",
    }

    report = evaluate_phase3_reports(reports)

    assert report["small_sample_shrinkage"]["active"] is False
    assert report["small_sample_shrinkage"][
        "blocked_pending_fresh_confirmation"
    ] is False
    # A separate activation PR would be required; this closure gate does not
    # silently convert fresh confirmation into an active scorer feature.
    assert report["phase3_complete"] is False
