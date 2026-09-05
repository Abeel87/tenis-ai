from datetime import datetime, timedelta, timezone

from backend.player_dna_market_walk_forward import (
    FOLD_MIN_MARKET_N,
    SEGMENT_MIN_MARKET_N,
    aggregate_segment_diagnostics,
    build_segment_consensus_shadow_policy,
    fold_verdict,
    segment_verdict,
    summarize_walk_forward,
    walk_forward_fold_specs,
)


def _feature(match_id, when):
    return {
        "match_id": match_id,
        "scheduled_time": when,
    }


def _comparison(*, matched=180, positive=True):
    binary = {}
    for market in (
        "match_p1_win",
        "first_set_p1_win",
        "first_set_tiebreak",
        "first_set_over_8.5",
        "first_set_over_9.5",
        "early_1:1",
    ):
        binary[market] = {
            "n": FOLD_MIN_MARKET_N + 10,
            "dynamic_better_on_brier_and_log_loss": positive,
            "brier_gain_vs_profile_only": 0.01 if positive else -0.01,
            "log_loss_gain_vs_profile_only": 0.02 if positive else -0.02,
        }
    return {
        "signal": (
            "DYNAMIC_LEAN_STATEFUL_E2E_PROMISING_SHADOW"
            if positive
            else "DYNAMIC_LEAN_STATEFUL_E2E_MIXED_OR_NO_GAIN"
        ),
        "matched_settled_matches": matched,
        "binary_markets_vs_profile_only": binary,
    }


def test_walk_forward_fold_specs_are_disjoint_and_never_split_same_timestamp_groups():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(20):
        when = start + timedelta(days=index // 2)
        rows.append(_feature(f"m{index}", when))

    specs = walk_forward_fold_specs(rows)
    assert len(specs) == 3
    assert [spec["train_fraction_target"] for spec in specs] == [0.55, 0.70, 0.85]
    assert all(spec["same_timestamp_split"] is False for spec in specs)

    eval_sets = [set(spec["eval_ids"]) for spec in specs]
    assert not (eval_sets[0] & eval_sets[1])
    assert not (eval_sets[0] & eval_sets[2])
    assert not (eval_sets[1] & eval_sets[2])

    for spec in specs:
        assert set(spec["train_ids"]).isdisjoint(spec["eval_ids"])


def test_fold_verdict_requires_support_and_primary_market_repeatability():
    positive = fold_verdict(_comparison(matched=180, positive=True))
    assert positive["support_sufficient"] is True
    assert positive["primary_match_and_first_set_better_on_both"] is True
    assert positive["repeatable_gain"] is True

    weak = _comparison(matched=180, positive=True)
    weak["binary_markets_vs_profile_only"]["match_p1_win"][
        "dynamic_better_on_brier_and_log_loss"
    ] = False
    verdict = fold_verdict(weak)
    assert verdict["support_sufficient"] is True
    assert verdict["primary_match_and_first_set_better_on_both"] is False
    assert verdict["repeatable_gain"] is False


def test_walk_forward_summary_requires_repeatability_across_multiple_folds():
    folds = []
    for index in range(3):
        comparison = _comparison(matched=180, positive=index < 2)
        folds.append({
            "fold": index + 1,
            "status": "FOLD_COMPLETE",
            "comparison": comparison,
            "verdict": fold_verdict(comparison),
        })

    aggregate = _comparison(matched=540, positive=True)
    summary = summarize_walk_forward(folds, aggregate)
    assert summary["completed_folds"] == 3
    assert summary["supported_folds"] == 3
    assert summary["repeatable_gain_folds"] == 2
    assert summary["primary_repeatability"]["match_p1_win"]["positive_both_folds"] == 2
    assert summary["primary_repeatability"]["first_set_p1_win"]["positive_both_folds"] == 2
    assert summary["signal"] == "DYNAMIC_LEAN_MARKET_WALK_FORWARD_ROBUST_SHADOW"


def test_walk_forward_summary_stays_shadow_mixed_when_only_one_fold_repeats():
    folds = []
    for index in range(3):
        comparison = _comparison(matched=180, positive=index == 0)
        folds.append({
            "fold": index + 1,
            "status": "FOLD_COMPLETE",
            "comparison": comparison,
            "verdict": fold_verdict(comparison),
        })

    aggregate = _comparison(matched=540, positive=True)
    summary = summarize_walk_forward(folds, aggregate)
    assert summary["repeatable_gain_folds"] == 1
    assert summary["signal"] == "DYNAMIC_LEAN_MARKET_WALK_FORWARD_MIXED_OR_NO_GAIN"


def test_walk_forward_summary_reports_insufficient_when_only_one_fold_has_support():
    supported = _comparison(matched=180, positive=True)
    unsupported = _comparison(matched=60, positive=True)
    folds = [
        {
            "fold": 1,
            "status": "FOLD_COMPLETE",
            "comparison": supported,
            "verdict": fold_verdict(supported),
        },
        {
            "fold": 2,
            "status": "FOLD_COMPLETE",
            "comparison": unsupported,
            "verdict": fold_verdict(unsupported),
        },
        {
            "fold": 3,
            "status": "FOLD_COMPLETE",
            "comparison": unsupported,
            "verdict": fold_verdict(unsupported),
        },
    ]

    aggregate = _comparison(matched=501, positive=True)
    summary = summarize_walk_forward(folds, aggregate)
    assert summary["completed_folds"] == 3
    assert summary["supported_folds"] == 1
    assert summary["aggregate_matched_settled_matches"] == 501
    assert summary["aggregate_promising"] is True
    assert summary["signal"] == "INSUFFICIENT_DYNAMIC_LEAN_MARKET_WALK_FORWARD_SAMPLE"


def _segment_binary(direction_by_market=None):
    direction_by_market = direction_by_market or {}
    out = {}
    for market in (
        "match_p1_win",
        "first_set_p1_win",
        "first_set_tiebreak",
        "first_set_over_8.5",
        "first_set_over_9.5",
        "early_1:1",
    ):
        direction = direction_by_market.get(market, "positive")
        positive = direction == "positive"
        negative = direction == "negative"
        out[market] = {
            "n": SEGMENT_MIN_MARKET_N + 5,
            "dynamic_better_on_brier_and_log_loss": positive,
            "brier_gain_vs_profile_only": 0.01 if positive else (-0.01 if negative else 0.0),
            "log_loss_gain_vs_profile_only": 0.02 if positive else (-0.02 if negative else 0.0),
        }
    return out


def test_segment_verdict_requires_real_segment_support_and_tracks_primary_direction():
    binary = _segment_binary()
    verdict = segment_verdict(binary, 45)
    assert verdict["support_sufficient"] is True
    assert verdict["broad_positive"] is True
    assert verdict["primary_both_positive"] is True
    assert verdict["primary"]["match_p1_win"]["positive_both"] is True
    assert verdict["primary"]["first_set_p1_win"]["positive_both"] is True

    weak = segment_verdict(binary, 20)
    assert weak["support_sufficient"] is False
    assert weak["broad_positive"] is False
    assert weak["primary_both_positive"] is False


def test_segment_consensus_policy_requires_tour_surface_agreement_and_keeps_conflicts_shadow_only():
    def market(*, positive=False, negative=False):
        return {
            "repeatable_positive": positive,
            "repeatable_negative": negative,
            "mean_brier_gain_vs_profile_only": 0.01 if positive else (-0.01 if negative else 0.0),
            "mean_log_loss_gain_vs_profile_only": 0.02 if positive else (-0.02 if negative else 0.0),
            "strict_consensus_positive": positive,
            "strict_consensus_negative": negative,
        }

    aggregate = {
        "dimensions": {
            "tour": {
                "challenger": {
                    "markets": {
                        "match_p1_win": market(positive=True),
                        "first_set_p1_win": market(positive=True),
                        "first_set_over_9.5": market(negative=True),
                    }
                }
            },
            "surface": {
                "hard": {
                    "markets": {
                        "match_p1_win": market(positive=True),
                        "first_set_p1_win": market(negative=True),
                        "first_set_over_9.5": market(negative=True),
                    }
                }
            },
            "tour_surface": {
                "challenger|hard": {
                    "supported_folds": 0,
                    "markets": {},
                }
            },
        }
    }

    policy = build_segment_consensus_shadow_policy(aggregate)
    assert policy["mode"] == "SHADOW_SEGMENT_CONSENSUS_DIAGNOSTIC_ONLY"
    assert policy["production_influence"] is False
    assert policy["runtime_switch_enabled"] is False
    assert policy["joint_segment_backtest_claim"] is False
    assert policy["prospective_validation_required"] is True
    consensus_rules = policy["policy"]
    assert consensus_rules["dynamic_candidate_requires_positive_mean_brier_and_log_loss_per_marginal"] is True
    assert consensus_rules["profile_reference_requires_negative_mean_brier_and_log_loss_per_marginal"] is True
    assert consensus_rules["count_repeatability_without_mean_direction_is_insufficient"] is True

    row = policy["segments"]["challenger|hard"]
    assert row["markets"]["match_p1_win"]["decision"] == "CONSENSUS_DYNAMIC_CANDIDATE"
    assert row["markets"]["first_set_p1_win"]["decision"] == "CONFLICT"
    assert row["markets"]["first_set_over_9.5"]["decision"] == "CONSENSUS_PROFILE_REFERENCE"
    assert row["markets"]["match_p1_win"]["joint_segment_directly_validated"] is False
    assert "match_p1_win" in row["dynamic_candidate_markets"]
    assert "first_set_p1_win" in row["conflict_markets"]
    assert "first_set_over_9.5" in row["profile_reference_markets"]


def test_segment_aggregate_identifies_repeatable_positive_and_negative_market_patterns():
    folds = []
    for fold_no in (1, 2, 3):
        directions = {}
        if fold_no in (1, 2):
            directions["first_set_over_9.5"] = "negative"
        if fold_no == 3:
            directions["first_set_over_9.5"] = "positive"
        binary = _segment_binary(directions)
        segment = {
            "matched_settled_matches": 50,
            "binary_markets_vs_profile_only": binary,
            "verdict": segment_verdict(binary, 50),
        }
        folds.append({
            "fold": fold_no,
            "segments": {
                "tour": {"atp": segment},
                "surface": {"hard": segment},
                "tour_surface": {"atp|hard": segment},
            },
        })

    aggregate = aggregate_segment_diagnostics(folds)
    atp = aggregate["dimensions"]["tour"]["atp"]
    assert atp["supported_folds"] == 3
    assert atp["markets"]["match_p1_win"]["repeatable_positive"] is True
    assert atp["markets"]["match_p1_win"]["strict_consensus_positive"] is True
    assert atp["markets"]["first_set_p1_win"]["repeatable_positive"] is True
    assert atp["markets"]["first_set_p1_win"]["strict_consensus_positive"] is True
    assert atp["markets"]["first_set_over_9.5"]["repeatable_negative"] is True
    assert atp["markets"]["first_set_over_9.5"]["strict_consensus_negative"] is True
    assert "match_p1_win" in atp["repeatable_positive_markets"]
    assert "first_set_over_9.5" in atp["repeatable_negative_markets"]

    positive_watch = aggregate["watchlist"]["repeatable_positive"]
    negative_watch = aggregate["watchlist"]["repeatable_negative"]
    assert any(
        row["dimension"] == "tour"
        and row["segment"] == "atp"
        and row["market"] == "match_p1_win"
        for row in positive_watch
    )
    assert any(
        row["dimension"] == "tour"
        and row["segment"] == "atp"
        and row["market"] == "first_set_over_9.5"
        for row in negative_watch
    )


def test_segment_consensus_rejects_repeatable_count_signal_when_mean_direction_disagrees():
    def market(*, repeatable_positive=False, repeatable_negative=False, mean_brier=0.0, mean_log_loss=0.0):
        return {
            "repeatable_positive": repeatable_positive,
            "repeatable_negative": repeatable_negative,
            "mean_brier_gain_vs_profile_only": mean_brier,
            "mean_log_loss_gain_vs_profile_only": mean_log_loss,
            "strict_consensus_positive": bool(
                repeatable_positive and mean_brier > 0.0 and mean_log_loss > 0.0
            ),
            "strict_consensus_negative": bool(
                repeatable_negative and mean_brier < 0.0 and mean_log_loss < 0.0
            ),
        }

    aggregate = {
        "dimensions": {
            "tour": {
                "challenger": {
                    "markets": {
                        "early_2:2": market(
                            repeatable_positive=True,
                            mean_brier=-0.000099,
                            mean_log_loss=-0.000155,
                        ),
                        "first_set_p1_win": market(
                            repeatable_positive=True,
                            mean_brier=0.001,
                            mean_log_loss=0.002,
                        ),
                    }
                }
            },
            "surface": {
                "hard": {
                    "markets": {
                        "early_2:2": market(
                            repeatable_positive=True,
                            mean_brier=0.001,
                            mean_log_loss=0.002,
                        ),
                        "first_set_p1_win": market(
                            repeatable_negative=True,
                            mean_brier=0.0001,
                            mean_log_loss=0.0002,
                        ),
                    }
                }
            },
            "tour_surface": {
                "challenger|hard": {
                    "supported_folds": 0,
                    "markets": {},
                }
            },
        }
    }

    policy = build_segment_consensus_shadow_policy(aggregate)
    row = policy["segments"]["challenger|hard"]

    early = row["markets"]["early_2:2"]
    assert early["tour_repeatable_positive"] is True
    assert early["tour_strict_consensus_positive"] is False
    assert early["surface_strict_consensus_positive"] is True
    assert early["decision"] == "INSUFFICIENT_OR_MIXED"
    assert "early_2:2" not in row["dynamic_candidate_markets"]

    first_set = row["markets"]["first_set_p1_win"]
    assert first_set["tour_strict_consensus_positive"] is True
    assert first_set["surface_repeatable_negative"] is True
    assert first_set["surface_strict_consensus_negative"] is False
    assert first_set["decision"] == "INSUFFICIENT_OR_MIXED"
    assert "first_set_p1_win" not in row["conflict_markets"]
