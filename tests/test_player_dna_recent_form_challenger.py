from backend.player_dna_recent_form_challenger import (
    RECENT_FORM_MIN_PRIOR_MATCHES,
    RECENT_FORM_NUMERIC,
    RECENT_FORM_WINDOW,
    enrich_feature_rows,
    evaluate,
)


def _profile(match_id, when, player, opponent, *, serve, ret):
    return {
        "target_match_id": match_id,
        "target_scheduled_time": when,
        "player_id": player,
        "opponent_id": opponent,
        "strict_as_of": True,
        "same_time_matches_count_as_prior": False,
        "overall_prior": {
            "matches": 7,
            "serve_win_rate": serve - 0.02,
            "return_win_rate": ret - 0.02,
        },
        "same_surface_prior": {
            "matches": 5,
            "serve_win_rate": serve - 0.01,
            "return_win_rate": ret - 0.01,
        },
        "rolling_prior": {
            "all_surface": {
                "windows": {
                    "L5": {
                        "matches": 5,
                        "matches_used": 5,
                        "window_full": True,
                        "serve_win_rate": serve,
                        "return_win_rate": ret,
                    }
                }
            },
            "same_surface": {
                "windows": {
                    "L5": {
                        "matches": 4,
                        "matches_used": 4,
                        "window_full": False,
                        "serve_win_rate": serve - 0.03,
                        "return_win_rate": ret - 0.03,
                    }
                }
            },
        },
    }


def _point(match_id, when):
    return {
        "match_id": match_id,
        "event_index": 0,
        "match_scheduled_time": when,
        "surface": "hard",
        "tour": "ATP",
        "match_format": "BO3",
        "context_ready_player_point": True,
        "server_player_id": 1,
        "receiver_player_id": 2,
        "server_won": True,
        "server_ranking": 20,
        "receiver_ranking": 40,
        "is_tiebreak_before": False,
    }


def test_recent_form_enrichment_uses_canonical_all_surface_l5_rates():
    when = "2026-09-06T10:00:00Z"
    profiles = [
        _profile("m1", when, 1, 2, serve=0.69, ret=0.38),
        _profile("m1", when, 2, 1, serve=0.63, ret=0.43),
    ]

    rows, counts = enrich_feature_rows([_point("m1", when)], profiles)

    assert len(rows) == 1
    row = rows[0]
    assert row["server_all_l5_serve_win_rate"] == 0.69
    assert row["receiver_all_l5_return_win_rate"] == 0.43
    assert counts["enrichment_counts"]["enriched_rows"] == 1
    assert counts["enrichment_counts"]["rows_with_both_l5_rates"] == 1
    assert counts["enrichment_counts"]["rows_with_both_players_l5_full"] == 1


def test_recent_form_family_is_narrow_and_support_counts_are_not_features():
    assert RECENT_FORM_WINDOW == "L5"
    assert RECENT_FORM_MIN_PRIOR_MATCHES == 5
    assert RECENT_FORM_NUMERIC == [
        "server_all_l5_serve_win_rate",
        "receiver_all_l5_return_win_rate",
    ]
    assert all("matches" not in name for name in RECENT_FORM_NUMERIC)
    assert all("support" not in name for name in RECENT_FORM_NUMERIC)


def test_recent_form_challenger_remains_shadow_only_without_sample():
    report = evaluate([])
    contract = report["contract"]
    leakage = report["leakage_contract"]
    signal = report["signal"]

    assert report["mode"] == "SHADOW_RECENT_FORM_CHALLENGER_EVAL_ONLY"
    assert report["production_influence"] is False
    assert report["runtime_scoring_enabled"] is False
    assert report["training_join_enabled"] is False
    assert report["canonical_profile_write_enabled"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False
    assert report["auto_promote"] is False
    assert report["promotion_gate"] is False
    assert report["candidate_may_replace_reference"] is False

    assert contract["primary_family"] == "all_surface_l5_serve_return"
    assert contract["single_predeclared_family_only"] is True
    assert contract["l5_is_shortest_canonical_complete_rolling_window"] is True
    assert contract["both_players_require_five_prior_matches"] is True
    assert contract["raw_support_counts_are_model_features"] is False
    assert contract["same_surface_rolling_excluded_from_this_challenger"] is True
    assert contract["l10_l20_excluded_from_this_challenger"] is True
    assert contract["no_post_hoc_family_screen"] is True
    assert contract["primary_reference_is_current_lean_stateful"] is True
    assert contract["historical_success_requires_holdout_and_three_walk_forward_folds"] is True
    assert contract["all_three_proper_scores_must_improve"] is True
    assert contract["fresh_confirmation_required_before_any_activation"] is True

    assert leakage["canonical_strict_as_of_profiles_only"] is True
    assert leakage["same_timestamp_matches_never_count_as_prior"] is True
    assert leakage["stable_provider_player_ids_only"] is True
    assert leakage["target_point_outcome_not_used_in_profile_features"] is True
    assert leakage["profile_features_are_pre_match_only"] is True
    assert leakage["current_target_match_never_contributes_to_its_own_profile"] is True

    assert signal["status"] == "INSUFFICIENT_RECENT_FORM_SHADOW_SAMPLE"
    assert signal["fresh_confirmation_required"] is True
    assert signal["candidate_may_replace_reference"] is False


# LOGIC-07 Player State shares this test owner so Point Tape executes the
# dedicated state tests without adding a parallel workflow.
from datetime import datetime, timezone

import backend.player_dna_player_state_shadow as player_state


def _state_contrib(
    serve_wins=6,
    serve_points=10,
    return_wins=4,
    return_points=10,
    holds=3,
    service_games=4,
    breaks=1,
    return_games=4,
):
    return {
        "serve_wins": serve_wins,
        "serve_points": serve_points,
        "return_wins": return_wins,
        "return_points": return_points,
        "holds": holds,
        "service_games": service_games,
        "breaks": breaks,
        "return_games": return_games,
    }


def _state_match(match_id, when, surface, p1, p2, *, p1_rank=50, p2_rank=70, p1_contrib=None, p2_contrib=None):
    return {
        "match_id": match_id,
        "scheduled": datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone(timezone.utc),
        "surface": surface,
        "p1": p1,
        "p2": p2,
        "p1_ranking": p1_rank,
        "p2_ranking": p2_rank,
        "contrib": {
            p1: p1_contrib or _state_contrib(),
            p2: p2_contrib or _state_contrib(serve_wins=5, return_wins=5, holds=2, breaks=2),
        },
    }


def _state_profile(match_id, when, surface, player, opponent, *, matches=5):
    return {
        "target_match_id": match_id,
        "target_scheduled_time": when,
        "target_surface": surface,
        "player_id": player,
        "opponent_id": opponent,
        "strict_as_of": True,
        "same_time_matches_count_as_prior": False,
        "overall_prior": {
            "matches": matches,
            "serve_points": 100 if matches else 0,
            "serve_wins": 62 if matches else 0,
            "return_points": 100 if matches else 0,
            "return_wins": 38 if matches else 0,
            "service_games": 40 if matches else 0,
            "holds": 30 if matches else 0,
            "return_games": 40 if matches else 0,
            "breaks": 10 if matches else 0,
            "serve_win_rate": 0.62 if matches else None,
            "return_win_rate": 0.38 if matches else None,
            "hold_rate": 0.75 if matches else None,
            "break_rate": 0.25 if matches else None,
        },
        "same_surface_prior": {
            "matches": matches,
            "serve_points": 80 if matches else 0,
            "serve_wins": 48 if matches else 0,
            "return_points": 80 if matches else 0,
            "return_wins": 32 if matches else 0,
            "service_games": 32 if matches else 0,
            "holds": 24 if matches else 0,
            "return_games": 32 if matches else 0,
            "breaks": 8 if matches else 0,
            "serve_win_rate": 0.60 if matches else None,
            "return_win_rate": 0.40 if matches else None,
            "hold_rate": 0.75 if matches else None,
            "break_rate": 0.25 if matches else None,
        },
        "rolling_prior": {
            "all_surface": {
                "windows": {
                    "L5": {
                        "requested_matches": 5,
                        "matches_used": min(matches, 5),
                        "window_full": matches >= 5,
                        "match_coverage": min(matches, 5) / 5,
                        "serve_win_rate": 0.64 if matches else None,
                        "return_win_rate": 0.39 if matches else None,
                        "hold_rate": 0.76 if matches else None,
                        "break_rate": 0.26 if matches else None,
                    }
                },
                "trend": {
                    "serve_l5_minus_l10": 0.01,
                    "serve_l5_minus_l20": 0.02,
                    "return_l5_minus_l10": -0.01,
                    "return_l5_minus_l20": 0.0,
                    "hold_l5_minus_l10": 0.01,
                    "hold_l5_minus_l20": 0.02,
                    "break_l5_minus_l10": -0.01,
                    "break_l5_minus_l20": 0.0,
                },
            },
            "same_surface": {
                "windows": {
                    "L5": {
                        "requested_matches": 5,
                        "matches_used": min(matches, 5),
                        "window_full": matches >= 5,
                        "match_coverage": min(matches, 5) / 5,
                        "serve_win_rate": 0.61 if matches else None,
                        "return_win_rate": 0.40 if matches else None,
                        "hold_rate": 0.74 if matches else None,
                        "break_rate": 0.24 if matches else None,
                    }
                },
                "trend": {},
            },
        },
    }


def _profiles_for(matches):
    rows = []
    for index, match in enumerate(matches):
        when = match["scheduled"].isoformat()
        support = 0 if index == 0 else 5
        rows.extend(
            [
                _state_profile(match["match_id"], when, match["surface"], match["p1"], match["p2"], matches=support),
                _state_profile(match["match_id"], when, match["surface"], match["p2"], match["p1"], matches=support),
            ]
        )
    return rows


def _find_state(rows, match_id, player):
    return next(
        row for row in rows
        if row["target_match_id"] == match_id and row["player_id"] == player
    )


def test_player_state_is_strict_as_of_and_future_or_same_time_results_do_not_leak(monkeypatch):
    first = _state_match("m1", "2026-01-01T10:00:00Z", "hard", 1, 2)
    same_a = _state_match(
        "m2a",
        "2026-02-01T10:00:00Z",
        "hard",
        1,
        3,
        p1_contrib=_state_contrib(serve_wins=10, return_wins=10, holds=4, breaks=4),
    )
    same_b = _state_match(
        "m2b",
        "2026-02-01T10:00:00Z",
        "hard",
        1,
        4,
        p1_contrib=_state_contrib(serve_wins=0, return_wins=0, holds=0, breaks=0),
    )
    future = _state_match(
        "m3",
        "2026-03-01T10:00:00Z",
        "clay",
        1,
        5,
        p1_contrib=_state_contrib(serve_wins=10, return_wins=10, holds=4, breaks=4),
    )
    matches = [future, same_b, first, same_a]
    profiles = _profiles_for(sorted(matches, key=lambda row: (row["scheduled"], row["match_id"])))

    monkeypatch.setattr(
        player_state,
        "build_target_adjustment_index",
        lambda rows: ({}, {"target_directions": 0}),
    )
    states, counts = player_state.build_historical_state_rows(matches, profiles)

    a = _find_state(states, "m2a", 1)
    b = _find_state(states, "m2b", 1)
    assert a["current_season"]["matches"] == 1
    assert b["current_season"]["matches"] == 1
    assert a["current_season"] == b["current_season"]
    assert a["target_match_outcome_used_in_state"] is False
    assert b["target_match_outcome_used_in_state"] is False
    assert counts["same_time_groups"] == 1

    altered_future = dict(future)
    altered_future["contrib"] = {
        **future["contrib"],
        1: _state_contrib(serve_wins=0, return_wins=0, holds=0, breaks=0),
    }
    states_2, _ = player_state.build_historical_state_rows(
        [altered_future, same_a, first, same_b],
        profiles,
    )
    assert _find_state(states_2, "m2a", 1)["current_season"] == a["current_season"]


def test_player_state_keeps_seasons_and_surfaces_separate(monkeypatch):
    prior_year = _state_match("y1", "2025-12-01T10:00:00Z", "hard", 1, 2)
    current_clay = _state_match("y2", "2026-01-10T10:00:00Z", "clay", 1, 3)
    target_hard = _state_match("y3", "2026-02-10T10:00:00Z", "hard", 1, 4)
    matches = [target_hard, current_clay, prior_year]
    profiles = _profiles_for(sorted(matches, key=lambda row: row["scheduled"]))
    monkeypatch.setattr(player_state, "build_target_adjustment_index", lambda rows: ({}, {}))

    states, _ = player_state.build_historical_state_rows(matches, profiles)
    target = _find_state(states, "y3", 1)

    assert target["current_season"]["matches"] == 1
    assert target["previous_season"]["matches"] == 1
    assert target["current_surface_state"]["current_season"]["matches"] == 0
    assert target["current_surface_state"]["previous_season"]["matches"] == 1
    assert target["provenance"]["surface_isolated"] is True
    assert target["provenance"]["season_boundary"].startswith("UTC calendar year")


def test_player_state_rank_and_gap_scenarios_are_descriptive_without_cause_inference(monkeypatch):
    before_gap = _state_match("g1", "2026-01-01T10:00:00Z", "hard", 1, 2, p1_rank=100)
    return_match = _state_match("g2", "2026-05-05T10:00:00Z", "hard", 1, 3, p1_rank=80)
    after_return = _state_match("g3", "2026-05-20T10:00:00Z", "hard", 1, 4, p1_rank=78)
    matches = [before_gap, return_match, after_return]
    profiles = _profiles_for(matches)
    monkeypatch.setattr(player_state, "build_target_adjustment_index", lambda rows: ({}, {}))

    states, _ = player_state.build_historical_state_rows(matches, profiles)
    returned = _find_state(states, "g2", 1)
    rank = returned["ranking_momentum"]
    assert rank["effective_rank"] == 80
    assert rank["source"] == "target_provider_context"
    assert rank["latest_prior_rank"] == 100
    assert rank["delta_vs_latest_prior"] == -20

    scenarios = returned["inactivity"]["scenarios"]
    assert scenarios["30"]["current_gap_exceeds_scenario"] is True
    assert scenarios["60"]["current_gap_exceeds_scenario"] is True
    assert scenarios["90"]["current_gap_exceeds_scenario"] is True
    assert scenarios["180"]["current_gap_exceeds_scenario"] is False
    assert all(item["cause_inferred"] is False for item in scenarios.values())
    assert all(item["injury_or_medical_inference"] is False for item in scenarios.values())

    later = _find_state(states, "g3", 1)
    assert later["inactivity"]["scenarios"]["30"]["matches_since_observed_gap"] == 1


def test_player_state_reuses_logic06_expectation_owner_for_realized_trend(monkeypatch):
    first = _state_match(
        "a1",
        "2026-01-01T10:00:00Z",
        "hard",
        1,
        2,
        p1_contrib=_state_contrib(serve_wins=7, serve_points=10),
    )
    second = _state_match("a2", "2026-02-01T10:00:00Z", "hard", 1, 3)
    profiles = _profiles_for([first, second])
    calls = {"count": 0}

    component = lambda expected: {
        "raw_rate": 0.6,
        "expected_rate": expected,
        "residual": 0.1,
        "player_sample": 100,
        "opponent_sample": 100,
        "pooled_sample": 200,
        "minimum_side_sample": 100,
        "both_sides_available": True,
    }
    adjustment = {
        "overall": {
            "serve": component(0.5),
            "return": component(0.4),
            "hold": component(0.6),
            "break": component(0.2),
        },
        "surface": {
            "serve": component(0.5),
            "return": component(0.4),
            "hold": component(0.6),
            "break": component(0.2),
        },
    }

    def fake_logic06(rows):
        calls["count"] += 1
        return {
            ("a1", 1): adjustment,
            ("a1", 2): adjustment,
            ("a2", 1): adjustment,
            ("a2", 3): adjustment,
        }, {"target_directions": 4}

    monkeypatch.setattr(player_state, "build_target_adjustment_index", fake_logic06)
    states, _ = player_state.build_historical_state_rows([first, second], profiles)

    target = _find_state(states, "a2", 1)
    trend = target["opponent_adjusted_performance_trend"]
    assert calls["count"] == 1
    assert trend["expectation_owner"].endswith("build_target_adjustment_index")
    assert trend["support"]["all_prior_matches"] == 1
    assert trend["all_prior_mean"]["serve"] == 0.2
    assert trend["probability_feature_enabled"] is False


def test_player_state_l5_current_engine_and_prod_contracts_remain_closed():
    report = player_state.build_state_report(
        [],
        [],
        recent_form_evidence={
            "signal": {
                "status": "RECENT_FORM_L5_NOT_ROBUST_ENOUGH",
                "positive_holdout": False,
                "robust_walk_forward": False,
                "fresh_confirmation_required": True,
            }
        },
    )

    assert report["mode"] == "SHADOW_PLAYER_STATE_DESCRIPTIVE_ONLY"
    assert report["recent_form_evidence"]["source_status"] == "RECENT_FORM_L5_NOT_ROBUST_ENOUGH"
    assert report["recent_form_evidence"]["l5_state_activation_enabled"] is False
    assert report["recent_form_evidence"]["l5_probability_feature_enabled"] is False
    assert report["gap_policy"]["single_magic_cutoff_selected"] is False
    assert report["gap_policy"]["scenario_windows_days"] == [30, 60, 90, 180]

    for key in (
        "production_influence",
        "runtime_scoring_enabled",
        "training_join_enabled",
        "canonical_profile_write_enabled",
        "player_dna_overwrite",
        "current_engine_write_enabled",
        "current_engine_recalculation_enabled",
        "probability_created",
        "weights_created",
        "thresholds_created",
        "feature_activation",
        "symphony2_influence",
        "superbet_playable_influence",
        "auto_promote",
        "candidate_may_replace_reference",
        "promotion_gate",
    ):
        assert report[key] is False

    reference = player_state._current_engine_reference(
        {
            "id": "cur1",
            "model_ready": True,
            "model_confidence": 0.73,
            "p1_probability": 0.61,
            "other": {"untouched": True},
        }
    )
    assert reference["read_only"] is True
    assert reference["recomputed"] is False
    assert reference["selected_existing_fields"]["p1_probability"] == 0.61
