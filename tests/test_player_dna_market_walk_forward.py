from datetime import datetime, timedelta, timezone

from backend.player_dna_market_walk_forward import (
    FOLD_MIN_MARKET_N,
    fold_verdict,
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
