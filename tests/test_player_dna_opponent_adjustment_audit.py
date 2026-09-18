import pandas as pd

from backend.player_dna_opponent_adjustment_audit import (
    ADJUSTED_PERFORMANCE_NUMERIC,
    ADJUSTED_SUPPORT_NUMERIC,
    OPPONENT_NUMERIC,
    OPPONENT_STRENGTH_NUMERIC,
    OPPONENT_SUPPORT_NUMERIC,
    RAW_ADJUSTMENT_BASE_NUMERIC,
    _performance_vs_expectation_residual,
    build_opponent_context_index,
    build_target_adjustment_index,
    evaluate,
)


def _prior(matches, serve, ret, hold=0.80, brk=0.20):
    if matches <= 0:
        return {
            "matches": 0,
            "serve_points": 0,
            "serve_wins": 0,
            "serve_win_rate": None,
            "return_points": 0,
            "return_wins": 0,
            "return_win_rate": None,
            "service_games": 0,
            "holds": 0,
            "hold_rate": None,
            "return_games": 0,
            "breaks": 0,
            "break_rate": None,
        }
    serve_points = matches * 100
    return_points = matches * 100
    service_games = matches * 10
    return_games = matches * 10
    return {
        "matches": matches,
        "serve_points": serve_points,
        "serve_wins": round(serve_points * serve),
        "serve_win_rate": serve,
        "return_points": return_points,
        "return_wins": round(return_points * ret),
        "return_win_rate": ret,
        "service_games": service_games,
        "holds": round(service_games * hold),
        "hold_rate": hold,
        "return_games": return_games,
        "breaks": round(return_games * brk),
        "break_rate": brk,
    }


def _match_rows(
    match_id,
    when,
    p1,
    p2,
    *,
    surface="hard",
    p1_prior=(0, 0.60, 0.40),
    p2_prior=(0, 0.60, 0.40),
    p1_surface_prior=None,
    p2_surface_prior=None,
):
    p1_surface_prior = p1_prior if p1_surface_prior is None else p1_surface_prior
    p2_surface_prior = p2_prior if p2_surface_prior is None else p2_surface_prior

    def row(player, opponent, side, prior, surface_prior):
        return {
            "mode": "SHADOW_AS_OF_PROFILE",
            "strict_as_of": True,
            "same_time_matches_count_as_prior": False,
            "target_match_id": match_id,
            "target_scheduled_time": when,
            "target_surface": surface,
            "target_tour": "atp",
            "target_format": "BO3",
            "player_side": side,
            "player_id": player,
            "opponent_id": opponent,
            "overall_prior": _prior(*prior),
            "same_surface_prior": _prior(*surface_prior),
        }

    return [
        row(p1, p2, "p1", p1_prior, p1_surface_prior),
        row(p2, p1, "p2", p2_prior, p2_surface_prior),
    ]


def test_same_timestamp_matches_never_enter_each_others_opponent_history():
    rows = []
    rows += _match_rows(
        "a-x",
        "2026-01-01T10:00:00Z",
        1,
        9,
        p2_prior=(3, 0.70, 0.30),
    )
    rows += _match_rows(
        "a-y",
        "2026-01-01T10:00:00Z",
        1,
        8,
        p2_prior=(4, 0.65, 0.35),
    )
    rows += _match_rows(
        "a-z",
        "2026-01-02T10:00:00Z",
        1,
        7,
        p2_prior=(5, 0.66, 0.34),
    )

    index, counts = build_opponent_context_index(rows)

    same_a = index[("a-x", 1)]
    same_b = index[("a-y", 1)]
    later = index[("a-z", 1)]

    assert same_a["overall_support"] == 0
    assert same_b["overall_support"] == 0
    assert later["overall_support"] == 2
    assert later["opponent_return_mean"] == 0.325
    assert later["opponent_serve_mean"] == 0.675
    assert later["same_time_matches_count_as_prior"] is False
    assert counts["paired_matches"] == 3


def test_future_match_never_enters_earlier_opponent_history():
    rows = []
    rows += _match_rows(
        "future",
        "2026-01-03T10:00:00Z",
        1,
        9,
        p2_prior=(5, 0.90, 0.10),
    )
    rows += _match_rows(
        "past",
        "2026-01-01T10:00:00Z",
        1,
        8,
        p2_prior=(3, 0.64, 0.36),
    )
    rows += _match_rows(
        "target",
        "2026-01-02T10:00:00Z",
        1,
        7,
        p2_prior=(4, 0.62, 0.38),
    )

    index, _ = build_opponent_context_index(rows)
    target = index[("target", 1)]
    future = index[("future", 1)]

    assert target["overall_support"] == 1
    assert target["opponent_serve_mean"] == 0.64
    assert target["opponent_return_mean"] == 0.36
    assert future["overall_support"] == 2


def test_opponent_context_uses_opponents_own_pre_match_profile():
    rows = []
    rows += _match_rows(
        "a-x",
        "2026-01-01T10:00:00Z",
        1,
        9,
        p1_prior=(8, 0.90, 0.10),
        p2_prior=(4, 0.62, 0.38),
    )
    rows += _match_rows(
        "a-b",
        "2026-01-02T10:00:00Z",
        1,
        2,
        p1_prior=(9, 0.88, 0.12),
        p2_prior=(2, 0.55, 0.45),
    )

    index, _ = build_opponent_context_index(rows)
    target = index[("a-b", 1)]

    assert target["opponent_serve_mean"] == 0.62
    assert target["opponent_return_mean"] == 0.38
    assert target["overall_support"] == 1


def test_l5_uses_only_five_most_recent_historical_opponents():
    rows = []
    return_rates = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45]
    for idx, ret in enumerate(return_rates, start=1):
        rows += _match_rows(
            f"m{idx}",
            f"2026-01-{idx:02d}T10:00:00Z",
            1,
            100 + idx,
            p2_prior=(3, 1.0 - ret, ret),
        )

    rows += _match_rows(
        "target",
        "2026-01-10T10:00:00Z",
        1,
        999,
        p2_prior=(3, 0.60, 0.40),
    )

    index, _ = build_opponent_context_index(rows)
    target = index[("target", 1)]

    assert target["overall_support"] == 6
    assert target["opponent_return_mean"] == 0.325
    assert target["opponent_return_l5"] == 0.35


def test_same_surface_context_ignores_other_surface_matches():
    rows = []
    rows += _match_rows(
        "hard-1",
        "2026-01-01T10:00:00Z",
        1,
        9,
        surface="hard",
        p2_prior=(3, 0.70, 0.30),
        p2_surface_prior=(3, 0.68, 0.32),
    )
    rows += _match_rows(
        "clay-1",
        "2026-01-02T10:00:00Z",
        1,
        8,
        surface="clay",
        p2_prior=(3, 0.60, 0.40),
        p2_surface_prior=(3, 0.58, 0.42),
    )
    rows += _match_rows(
        "target",
        "2026-01-03T10:00:00Z",
        1,
        7,
        surface="hard",
        p2_prior=(3, 0.64, 0.36),
    )

    index, _ = build_opponent_context_index(rows)
    target = index[("target", 1)]

    assert target["overall_support"] == 2
    assert target["surface_support"] == 1
    assert target["opponent_return_surface_mean"] == 0.32
    assert target["opponent_serve_surface_mean"] == 0.68


def test_support_counts_only_usable_bidirectional_opponent_profiles():
    rows = []
    rows += _match_rows(
        "missing-profile",
        "2026-01-01T10:00:00Z",
        1,
        9,
        p2_prior=(0, 0.60, 0.40),
    )
    rows += _match_rows(
        "ready-profile",
        "2026-01-02T10:00:00Z",
        1,
        8,
        p2_prior=(3, 0.64, 0.36),
    )
    rows += _match_rows(
        "target",
        "2026-01-03T10:00:00Z",
        1,
        7,
        p2_prior=(3, 0.62, 0.38),
    )

    index, _ = build_opponent_context_index(rows)
    target = index[("target", 1)]

    assert target["overall_history_matches"] == 2
    assert target["overall_support"] == 1
    assert target["opponent_serve_mean"] == 0.64
    assert target["opponent_return_mean"] == 0.36


def test_primary_opponent_strength_features_exclude_support_proxy():
    strength = set(OPPONENT_STRENGTH_NUMERIC)
    support = set(OPPONENT_SUPPORT_NUMERIC)

    assert strength
    assert support
    assert strength.isdisjoint(support)
    assert set(OPPONENT_NUMERIC) == strength | support
    assert all("support" not in name for name in OPPONENT_STRENGTH_NUMERIC)
    assert all("support" in name for name in OPPONENT_SUPPORT_NUMERIC)


def test_logic06_count_pooled_expected_rates_and_residuals():
    rows = _match_rows(
        "target",
        "2026-02-01T10:00:00Z",
        1,
        2,
        p1_prior=(4, 0.70, 0.30, 0.80, 0.20),
        p2_prior=(2, 0.60, 0.40, 0.70, 0.30),
    )

    index, counts = build_target_adjustment_index(rows)
    p1 = index[("target", 1)]["overall"]

    assert counts["paired_matches"] == 1
    assert counts["target_directions"] == 2
    assert p1["serve"]["expected_rate"] == 0.666667
    assert p1["serve"]["residual"] == 0.033333
    assert p1["return"]["expected_rate"] == 0.333333
    assert p1["return"]["residual"] == -0.033333
    assert p1["hold"]["expected_rate"] == 0.766667
    assert p1["hold"]["residual"] == 0.033333
    assert p1["break"]["expected_rate"] == 0.233333
    assert p1["break"]["residual"] == -0.033333
    assert p1["serve"]["pooled_sample"] == 600
    assert p1["hold"]["pooled_sample"] == 60


def test_logic06_surface_split_uses_same_surface_counts_not_overall_counts():
    rows = _match_rows(
        "target",
        "2026-02-01T10:00:00Z",
        1,
        2,
        surface="clay",
        p1_prior=(4, 0.80, 0.20, 0.90, 0.10),
        p2_prior=(4, 0.80, 0.20, 0.90, 0.10),
        p1_surface_prior=(2, 0.60, 0.40, 0.70, 0.30),
        p2_surface_prior=(2, 0.60, 0.40, 0.70, 0.30),
    )

    index, _ = build_target_adjustment_index(rows)
    target = index[("target", 1)]

    assert target["overall"]["serve"]["expected_rate"] == 0.8
    assert target["surface"]["serve"]["expected_rate"] == 0.6
    assert target["overall"]["hold"]["expected_rate"] == 0.9
    assert target["surface"]["hold"]["expected_rate"] == 0.7
    assert target["surface_name"] == "clay"


def test_logic06_expectation_ignores_target_labels_and_source_row_order():
    rows = _match_rows(
        "target",
        "2026-02-01T10:00:00Z",
        1,
        2,
        p1_prior=(4, 0.70, 0.30, 0.80, 0.20),
        p2_prior=(2, 0.60, 0.40, 0.70, 0.30),
    )
    rows[0]["target_server_won"] = True
    rows[0]["target_hold"] = True
    first, _ = build_target_adjustment_index(rows)

    changed = [dict(row) for row in reversed(rows)]
    changed[0]["target_server_won"] = False
    changed[0]["target_hold"] = False
    second, _ = build_target_adjustment_index(changed)

    assert first[("target", 1)] == second[("target", 1)]
    assert first[("target", 1)]["target_outcome_used_in_expectation"] is False
    assert first[("target", 1)]["strict_as_of"] is True
    assert first[("target", 1)]["same_time_matches_count_as_prior"] is False


def test_logic06_missing_side_fails_closed_without_strength_proxy():
    rows = _match_rows(
        "target",
        "2026-02-01T10:00:00Z",
        1,
        2,
        p1_prior=(4, 0.70, 0.30, 0.80, 0.20),
        p2_prior=(0, 0.60, 0.40),
    )

    index, counts = build_target_adjustment_index(rows)
    p1 = index[("target", 1)]["overall"]

    assert p1["serve"]["expected_rate"] is None
    assert p1["serve"]["residual"] is None
    assert p1["serve"]["both_sides_available"] is False
    assert p1["serve"]["player_sample"] == 400
    assert p1["serve"]["opponent_sample"] == 0
    assert counts["overall_all_four_available"] == 0


def test_logic06_primary_features_exclude_support_diagnostics():
    adjusted = set(ADJUSTED_PERFORMANCE_NUMERIC)
    support = set(ADJUSTED_SUPPORT_NUMERIC)
    raw = set(RAW_ADJUSTMENT_BASE_NUMERIC)

    assert adjusted
    assert support
    assert raw
    assert adjusted.isdisjoint(support)
    assert raw.isdisjoint(support)
    assert all("sample" not in name and "support" not in name for name in adjusted)
    assert all("sample" in name for name in support)


def _residual_frame(feature, values, labels):
    rows = []
    for value, label in zip(values, labels):
        row = {name: None for name in OPPONENT_STRENGTH_NUMERIC}
        row[feature] = value
        row["server_won"] = label
        rows.append(row)
    return pd.DataFrame(rows)


def test_residual_bins_use_train_only_boundaries():
    feature = OPPONENT_STRENGTH_NUMERIC[0]
    train = _residual_frame(feature, [0.10, 0.20, 0.30, 0.40], [0, 1, 0, 1])
    holdout_a = _residual_frame(feature, [0.15, 0.35], [1, 0])
    holdout_b = _residual_frame(feature, [-99.0, 99.0], [1, 0])

    first = _performance_vs_expectation_residual(train, holdout_a, [0.50, 0.50])
    second = _performance_vs_expectation_residual(train, holdout_b, [0.50, 0.50])

    expected = {"q25": 0.175, "q50": 0.25, "q75": 0.325}
    assert first["feature_diagnostics"][feature]["train_quartiles"] == expected
    assert second["feature_diagnostics"][feature]["train_quartiles"] == expected
    assert first["binning_policy"]["holdout_values_do_not_define_boundaries"] is True
    assert first["binning_policy"]["holdout_labels_do_not_define_boundaries"] is True
    assert first["feature_activation_enabled"] is False
    assert first["production_gate"] is False


def test_insufficient_sample_still_hard_blocks_promotion_and_rank_is_benchmark_only():
    report = evaluate([])

    assert report["signal"]["status"] == "INSUFFICIENT_SHADOW_SAMPLE"
    assert report["logic06_signal"]["status"] == "INSUFFICIENT_SHADOW_SAMPLE"
    assert report["candidate_may_replace_reference"] is False
    assert report["promotion_gate"] is False
    assert report["signal"]["candidate_may_replace_reference"] is False
    assert report["signal"]["promotion_gate"] is False
    assert report["logic06_signal"]["candidate_may_replace_reference"] is False
    assert report["logic06_signal"]["promotion_gate"] is False
    assert report["ranking_benchmark_contract"]["manual_rank_multiplier_used"] is False
    assert report["ranking_benchmark_contract"]["rank_is_benchmark_not_strength_definition"] is True
    assert report["context_provenance"]["event_level"]["available_in_this_audit_input"] is False
    assert report["context_provenance"]["event_level"]["inferred_from_tour_or_name"] is False

    contract = report["logic06_contract"]
    assert contract["count_pooling_only_no_manual_weights"] is True
    assert contract["expectations_use_strict_prior_profiles_only"] is True
    assert contract["target_outcome_used_in_expectation"] is False
    assert contract["raw_vs_adjusted_same_chronological_test"] is True
    assert contract["support_is_diagnostic_not_strength"] is True
    assert contract["support_threshold_activated"] is False
    assert contract["player_dna_overwrite_enabled"] is False
    assert contract["feature_activation_enabled"] is False
    assert contract["production_gate"] is False
