import pandas as pd
import pytest

from backend.player_dna_point_probability_engine import (
    EXPECTED_POINT_PROBABILITY_NUMERIC,
    MODE,
    POINT_PROBABILITY_NUMERIC,
    evaluate_phase4_reports,
    fit_point_probability_model,
    point_probability_feature_row,
    point_probability_feature_row_from_prematch,
    predict_server_point_probability,
    prematch_feature_with_rank,
    support_diagnostics,
)
from backend.player_dna_point_scorer import (
    LEAN_STATE_NUMERIC,
    PROFILE_NUMERIC,
    RANK_NUMERIC,
    predict_logistic_row,
)


def _profile(
    *,
    player_id=1,
    serve=0.64,
    ret=0.38,
    surface_serve=0.66,
    surface_ret=0.40,
    overall_matches=8,
    surface_matches=5,
):
    return {
        "target_match_id": "m1",
        "target_surface": "hard",
        "target_tour": "ATP",
        "target_format": "BO3",
        "player_id": player_id,
        "overall_prior": {
            "serve_win_rate": serve,
            "return_win_rate": ret,
            "matches": overall_matches,
        },
        "same_surface_prior": {
            "serve_win_rate": surface_serve,
            "return_win_rate": surface_ret,
            "matches": surface_matches,
        },
    }


def _state():
    return {
        "server": 1,
        "receiver": 2,
        "best_of": 3,
        "sets": [0, 0],
        "games": [2, 1],
        "server_points": "30",
        "receiver_points": "15",
        "is_tiebreak": False,
    }


def test_phase4_feature_order_is_exact_canonical_contract():
    assert tuple(PROFILE_NUMERIC) == EXPECTED_POINT_PROBABILITY_NUMERIC[:8]
    assert tuple(POINT_PROBABILITY_NUMERIC) == EXPECTED_POINT_PROBABILITY_NUMERIC
    assert tuple(POINT_PROBABILITY_NUMERIC) == (
        tuple(PROFILE_NUMERIC)
        + tuple(RANK_NUMERIC)
        + tuple(LEAN_STATE_NUMERIC)
    )


def test_prematch_builder_uses_phase3_matchup_main_effects_plus_rank():
    server = _profile(
        player_id=1,
        serve=0.67,
        ret=0.36,
        surface_serve=0.69,
        surface_ret=0.37,
        overall_matches=9,
        surface_matches=6,
    )
    receiver = _profile(
        player_id=2,
        serve=0.61,
        ret=0.44,
        surface_serve=0.62,
        surface_ret=0.46,
        overall_matches=10,
        surface_matches=7,
    )

    row = prematch_feature_with_rank(
        server,
        receiver,
        server_rank=12.0,
        receiver_rank=31.0,
    )

    assert row["surface"] == "hard"
    assert row["tour"] == "ATP"
    assert row["match_format"] == "BO3"
    assert row["server_overall_serve_rate"] == 0.67
    assert row["receiver_overall_return_rate"] == 0.44
    assert row["server_surface_serve_rate"] == 0.69
    assert row["receiver_surface_return_rate"] == 0.46
    assert row["server_rank"] == 12.0
    assert row["receiver_rank"] == 31.0


def test_point_feature_row_adds_only_validated_lean_pre_point_state():
    server = _profile(player_id=1)
    receiver = _profile(player_id=2)

    row = point_probability_feature_row(
        server,
        receiver,
        server_rank=15.0,
        receiver_rank=30.0,
        simulation_state=_state(),
    )

    for name in POINT_PROBABILITY_NUMERIC:
        assert name in row
    assert row["sets_completed_before"] == 0
    assert row["current_set_games_total_before"] == 3
    assert row["server_point_stage_before"] == 2
    assert row["receiver_point_stage_before"] == 1
    assert "previous_point_won_by_server" not in row
    assert "is_tiebreak" not in row


def test_phase4_standard_game_adapter_rejects_tiebreak_state():
    prematch = prematch_feature_with_rank(
        _profile(player_id=1),
        _profile(player_id=2),
        server_rank=20.0,
        receiver_rank=40.0,
    )
    state = _state()
    state["is_tiebreak"] = True

    with pytest.raises(ValueError):
        point_probability_feature_row_from_prematch(prematch, state)


def test_phase4_fit_and_predict_are_exact_wrapper_over_canonical_logistic():
    rows = []
    for i in range(60):
        row = {
            "match_id": f"m{i // 6}",
            "server_won": bool(i % 3),
            "surface": "hard" if i % 2 else "clay",
            "tour": "ATP",
            "match_format": "BO3",
        }
        for j, name in enumerate(POINT_PROBABILITY_NUMERIC):
            row[name] = ((i + j) % 11) / 10.0
        row["server_overall_matches"] = 5 + (i % 4)
        row["receiver_overall_matches"] = 5 + ((i + 1) % 4)
        row["server_surface_matches"] = 3 + (i % 3)
        row["receiver_surface_matches"] = 3 + ((i + 1) % 3)
        row["server_rank"] = 10 + i
        row["receiver_rank"] = 80 - i
        rows.append(row)

    frame = pd.DataFrame(rows)
    model = fit_point_probability_model(frame)

    assert model["converged"] is True
    feature = rows[-1]
    wrapped = predict_server_point_probability(model, feature)
    direct = predict_logistic_row(model, feature)
    assert wrapped == pytest.approx(direct, abs=1e-12)
    assert 0.0 <= wrapped <= 1.0


def test_support_diagnostics_expose_raw_counts_without_fake_confidence_class():
    server = _profile(
        player_id=1,
        overall_matches=8,
        surface_matches=3,
    )
    receiver = _profile(
        player_id=2,
        overall_matches=5,
        surface_matches=2,
    )

    report = support_diagnostics(server, receiver)

    assert report["minimum_overall_prior_matches"] == 5
    assert report["minimum_same_surface_prior_matches"] == 2
    assert report["support_flags"]["5"]["overall"] is True
    assert report["support_flags"]["3"]["same_surface"] is False
    assert report["uncertainty_classification_enabled"] is False
    assert report[
        "raw_support_exposed_instead_of_arbitrary_confidence_bucket"
    ] is True


def _phase3():
    return {
        "phase3_complete": True,
        "phase4_ready": True,
    }


def _point_scorer():
    return {
        "signal": {
            "lean_stateful_improves_profile_plus_rank_on_all_primary_proper_scores": True,
        },
        "stateful_walk_forward": {
            "lean_all_three_folds_positive_on_all_primary_proper_scores": True,
            "lean_superior_to_full_on_all_three_folds": True,
        },
        "lean_stateful_comparison": {
            "lean_feature_count": len(LEAN_STATE_NUMERIC),
        },
        "stateful_context_contract": {
            "features_use_score_before_only": True,
            "score_after_used_as_feature": False,
            "current_point_winner_used_as_feature": False,
            "lean_state_numeric_features": list(LEAN_STATE_NUMERIC),
            "lean_dropped_state_groups": ["tiebreak_context", "prior_momentum"],
        },
    }


def test_phase4_gate_closes_on_existing_robust_lean_baseline_only():
    report = evaluate_phase4_reports(_phase3(), _point_scorer())

    assert report["mode"] == MODE
    assert report["phase4_complete"] is True
    assert report["phase5_ready"] is True
    assert report["status"] == "PHASE4_COMPLETE_CANONICAL_LEAN_LOGISTIC_BASELINE"
    assert report["evidence"]["robust_three_fold_walk_forward"] is True
    assert report["evidence"]["score_before_only"] is True

    for value in report["excluded_until_separate_gate"].values():
        assert value is True

    assert report["production_influence"] is False
    assert report["runtime_switch_enabled"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False


def test_phase4_gate_fails_closed_if_phase3_or_walk_forward_contract_breaks():
    scorer = _point_scorer()
    scorer["stateful_walk_forward"][
        "lean_all_three_folds_positive_on_all_primary_proper_scores"
    ] = False

    report = evaluate_phase4_reports(_phase3(), scorer)

    assert report["phase4_complete"] is False
    assert report["phase5_ready"] is False
    assert report["status"] == "PHASE4_GATE_NOT_COMPLETE"
