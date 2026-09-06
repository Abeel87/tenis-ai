from __future__ import annotations

"""Leakage-safe tiebreak-profile challenger for Player DNA.

The canonical Player DNA profile already tracks tiebreak points/wins strictly
as-of each target match. This evaluator asks one narrow question: on tiebreak
points only, do pre-match player tiebreak rates add proper-score information
beyond the existing pre-match profile+rank reference?

The candidate is historical SHADOW evidence only. Even a robust result cannot
change the simulator tiebreak policy, runtime scoring, PROD, Symfonia 2.0, or
Superbet PLAYABLE without a separate frozen fresh-confirmation gate.
"""

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.player_dna_point_scorer import (
        EVAL_MIN_PRIOR_MATCHES,
        LEAN_STATE_NUMERIC,
        POINTS,
        PROFILE_NUMERIC,
        PROFILES,
        RANK_NUMERIC,
        _cohort,
        _fit_candidate,
        _frame,
        _iter_jsonl_gz,
        _profile_index,
        _proper_score_gains,
        _walk_forward_slices,
        build_feature_rows,
        split_chronological_by_match,
    )
except ModuleNotFoundError:  # direct execution compatibility
    from player_dna_point_scorer import (
        EVAL_MIN_PRIOR_MATCHES,
        LEAN_STATE_NUMERIC,
        POINTS,
        PROFILE_NUMERIC,
        PROFILES,
        RANK_NUMERIC,
        _cohort,
        _fit_candidate,
        _frame,
        _iter_jsonl_gz,
        _profile_index,
        _proper_score_gains,
        _walk_forward_slices,
        build_feature_rows,
        split_chronological_by_match,
    )

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data" / "player_dna_tiebreak_challenger.json"
VERSION = "player-dna-tiebreak-challenger-v1"
MODE = "SHADOW_TIEBREAK_CHALLENGER_EVAL_ONLY"

TIEBREAK_PROFILE_NUMERIC = [
    "server_overall_tiebreak_win_rate",
    "receiver_overall_tiebreak_win_rate",
    "server_surface_tiebreak_win_rate",
    "receiver_surface_tiebreak_win_rate",
]


def _finite_rate(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        return None
    return number


def _point_identity_index(
    point_rows: Iterable[dict[str, Any]],
) -> dict[tuple[str, int], tuple[int, int]]:
    out: dict[tuple[str, int], tuple[int, int]] = {}
    for row in point_rows:
        if not isinstance(row, dict):
            continue
        match_id = str(row.get("match_id") or "").strip()
        event_index = row.get("event_index")
        server = row.get("server_player_id")
        receiver = row.get("receiver_player_id")
        if (
            not match_id
            or isinstance(event_index, bool)
            or not isinstance(event_index, int)
            or isinstance(server, bool)
            or not isinstance(server, int)
            or isinstance(receiver, bool)
            or not isinstance(receiver, int)
            or server <= 0
            or receiver <= 0
            or server == receiver
        ):
            continue
        out[(match_id, event_index)] = (server, receiver)
    return out


def _pair_tiebreak_features(
    server_profile: dict[str, Any],
    receiver_profile: dict[str, Any],
) -> dict[str, float | None]:
    so = (
        server_profile.get("overall_prior")
        if isinstance(server_profile.get("overall_prior"), dict)
        else {}
    )
    ro = (
        receiver_profile.get("overall_prior")
        if isinstance(receiver_profile.get("overall_prior"), dict)
        else {}
    )
    ss = (
        server_profile.get("same_surface_prior")
        if isinstance(server_profile.get("same_surface_prior"), dict)
        else {}
    )
    rs = (
        receiver_profile.get("same_surface_prior")
        if isinstance(receiver_profile.get("same_surface_prior"), dict)
        else {}
    )
    return {
        "server_overall_tiebreak_win_rate": _finite_rate(so.get("tiebreak_win_rate")),
        "receiver_overall_tiebreak_win_rate": _finite_rate(ro.get("tiebreak_win_rate")),
        "server_surface_tiebreak_win_rate": _finite_rate(ss.get("tiebreak_win_rate")),
        "receiver_surface_tiebreak_win_rate": _finite_rate(rs.get("tiebreak_win_rate")),
    }


def enrich_feature_rows(
    point_rows: Iterable[dict[str, Any]],
    profile_rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    point_rows = [row for row in point_rows if isinstance(row, dict)]
    profile_rows = [row for row in profile_rows if isinstance(row, dict)]
    base_rows, base_counts = build_feature_rows(point_rows, profile_rows)
    profiles = _profile_index(profile_rows)
    identities = _point_identity_index(point_rows)

    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = defaultdict(int)
    for row in base_rows:
        if not bool(row.get("is_tiebreak")):
            continue

        counts["tiebreak_base_rows"] += 1
        match_id = str(row.get("match_id") or "").strip()
        event_index = row.get("event_index")
        if isinstance(event_index, bool) or not isinstance(event_index, int):
            counts["missing_event_identity"] += 1
            continue

        identity = identities.get((match_id, event_index))
        if identity is None:
            counts["missing_event_identity"] += 1
            continue
        server_id, receiver_id = identity
        server = profiles.get((match_id, server_id))
        receiver = profiles.get((match_id, receiver_id))
        if server is None or receiver is None:
            counts["missing_as_of_profile_pair"] += 1
            continue

        enriched = {**row, **_pair_tiebreak_features(server, receiver)}
        rows.append(enriched)
        counts["enriched_tiebreak_rows"] += 1
        counts["rows_with_both_overall_tiebreak_rates"] += int(
            enriched.get("server_overall_tiebreak_win_rate") is not None
            and enriched.get("receiver_overall_tiebreak_win_rate") is not None
        )
        counts["rows_with_both_surface_tiebreak_rates"] += int(
            enriched.get("server_surface_tiebreak_win_rate") is not None
            and enriched.get("receiver_surface_tiebreak_win_rate") is not None
        )

    return rows, {
        "base_join_counts": base_counts,
        "enrichment_counts": dict(counts),
        "profile_snapshots": len(profiles),
    }


def _positive_gains(gains: dict[str, float]) -> bool:
    return bool(
        gains["brier_gain"] > 0
        and gains["match_equal_brier_gain"] > 0
        and gains["log_loss_gain"] > 0
    )


def _evaluate_frames(train, test) -> dict[str, Any]:
    pre_match_reference_numeric = list(PROFILE_NUMERIC) + list(RANK_NUMERIC)
    candidate_numeric = pre_match_reference_numeric + list(TIEBREAK_PROFILE_NUMERIC)
    lean_reference_numeric = (
        list(PROFILE_NUMERIC) + list(RANK_NUMERIC) + list(LEAN_STATE_NUMERIC)
    )
    lean_plus_tiebreak_numeric = lean_reference_numeric + list(TIEBREAK_PROFILE_NUMERIC)

    pre_match_reference, _ = _fit_candidate(
        train, test, pre_match_reference_numeric
    )
    candidate, _ = _fit_candidate(train, test, candidate_numeric)
    lean_reference, _ = _fit_candidate(train, test, lean_reference_numeric)
    lean_plus_tiebreak, _ = _fit_candidate(
        train, test, lean_plus_tiebreak_numeric
    )

    primary_gains = _proper_score_gains(
        pre_match_reference["metrics"], candidate["metrics"]
    )
    lean_gains = _proper_score_gains(
        lean_reference["metrics"], lean_plus_tiebreak["metrics"]
    )
    return {
        "pre_match_profile_rank_reference": pre_match_reference,
        "pre_match_profile_rank_plus_tiebreak_profile": candidate,
        "lean_stateful_diagnostic_reference": lean_reference,
        "lean_stateful_plus_tiebreak_profile_diagnostic": lean_plus_tiebreak,
        "tiebreak_profile_gains_vs_pre_match_reference": primary_gains,
        "tiebreak_profile_gains_vs_lean_stateful_diagnostic": lean_gains,
        "primary_positive_all_proper_scores": _positive_gains(primary_gains),
        "diagnostic_positive_all_proper_scores": _positive_gains(lean_gains),
    }


def _walk_forward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    folds = []
    for train_rows, test_rows, meta in _walk_forward_slices(rows):
        train = _frame(train_rows)
        test = _frame(test_rows)
        enough = (
            len(train) >= 500
            and len(test) >= 150
            and train["match_id"].nunique() >= 20
            and test["match_id"].nunique() >= 10
            and train["server_won"].nunique() == 2
            and test["server_won"].nunique() == 2
        ) if not train.empty and not test.empty else False

        if not enough:
            folds.append({
                **meta,
                "status": "INSUFFICIENT_TIEBREAK_FOLD_SAMPLE",
                "train_points": int(len(train)),
                "test_points": int(len(test)),
            })
            continue

        result = _evaluate_frames(train, test)
        folds.append({
            **meta,
            "status": (
                "POSITIVE_TIEBREAK_PROFILE_FOLD"
                if result["primary_positive_all_proper_scores"]
                else "MIXED_OR_NEGATIVE_TIEBREAK_PROFILE_FOLD"
            ),
            "train_points": int(len(train)),
            "test_points": int(len(test)),
            **result,
        })

    completed = [
        row for row in folds
        if "tiebreak_profile_gains_vs_pre_match_reference" in row
    ]
    positive = [
        row for row in completed
        if row.get("primary_positive_all_proper_scores") is True
    ]

    def mean_gain(metric: str) -> float | None:
        values = [
            float(row["tiebreak_profile_gains_vs_pre_match_reference"][metric])
            for row in completed
        ]
        return round(sum(values) / len(values), 6) if values else None

    return {
        "mode": "EXPANDING_TRAIN_DISJOINT_TIME_WINDOWS_ON_TIEBREAK_ROWS",
        "completed_folds": len(completed),
        "positive_folds": len(positive),
        "robust_positive_all_three_folds": bool(
            len(completed) == 3 and len(positive) == 3
        ),
        "mean_gains_vs_pre_match_reference": {
            "brier_gain": mean_gain("brier_gain"),
            "match_equal_brier_gain": mean_gain("match_equal_brier_gain"),
            "log_loss_gain": mean_gain("log_loss_gain"),
        },
        "same_timestamp_groups_not_split": True,
        "test_windows_disjoint": True,
        "folds": folds,
    }


def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    train_all, holdout_all, split = split_chronological_by_match(rows)
    train = _frame(_cohort(train_all, EVAL_MIN_PRIOR_MATCHES))
    holdout = _frame(_cohort(holdout_all, EVAL_MIN_PRIOR_MATCHES))

    enough = (
        len(train) >= 1000
        and len(holdout) >= 500
        and train["match_id"].nunique() >= 50
        and holdout["match_id"].nunique() >= 30
        and train["server_won"].nunique() == 2
        and holdout["server_won"].nunique() == 2
    ) if not train.empty and not holdout.empty else False

    report: dict[str, Any] = {
        "version": VERSION,
        "mode": MODE,
        "label": "server_won",
        "regime": "TIEBREAK_POINTS_ONLY",
        "split": split,
        "evaluation_min_prior_matches": EVAL_MIN_PRIOR_MATCHES,
        "all_enriched_tiebreak_points": len(rows),
        "train_points_after_support_gate": int(len(train)),
        "holdout_points_after_support_gate": int(len(holdout)),
        "tiebreak_profile_numeric_features": list(TIEBREAK_PROFILE_NUMERIC),
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "training_join_enabled": False,
        "canonical_profile_write_enabled": False,
        "simulator_tiebreak_policy_changed": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "promotion_gate": False,
        "candidate_may_replace_reference": False,
        "contract": {
            "canonical_tiebreak_profile_only": True,
            "primary_candidate_is_pre_match_only": True,
            "raw_tiebreak_support_counts_are_features": False,
            "overall_prior_used": True,
            "same_surface_prior_used": True,
            "rolling_tiebreak_family_not_screened_in_first_challenger": True,
            "primary_reference_is_profile_plus_rank": True,
            "lean_stateful_comparison_is_diagnostic_only": True,
            "historical_success_requires_holdout_and_three_walk_forward_folds": True,
            "all_three_proper_scores_must_improve": True,
            "fresh_confirmation_required_before_simulator_integration": True,
        },
        "leakage_contract": {
            "canonical_strict_as_of_profiles_only": True,
            "same_timestamp_matches_never_count_as_prior": True,
            "stable_provider_player_ids_only": True,
            "target_point_outcome_not_used_in_profile_features": True,
            "profile_features_are_pre_match_only": True,
            "current_target_match_never_contributes_to_its_own_profile": True,
        },
        "signal": {
            "status": "NOT_EVALUATED",
            "positive_holdout": False,
            "robust_walk_forward": False,
            "fresh_confirmation_required": True,
            "candidate_may_replace_reference": False,
        },
    }

    if not enough:
        report["signal"]["status"] = "INSUFFICIENT_TIEBREAK_SHADOW_SAMPLE"
        return report

    holdout_result = _evaluate_frames(train, holdout)
    walk_forward = _walk_forward(rows)
    holdout_positive = bool(holdout_result["primary_positive_all_proper_scores"])
    robust = bool(walk_forward["robust_positive_all_three_folds"])

    report["holdout"] = holdout_result
    report["walk_forward"] = walk_forward
    report["signal"] = {
        "status": (
            "TIEBREAK_PROFILE_ROBUST_HISTORICAL_SIGNAL_REQUIRES_FRESH_CONFIRMATION"
            if holdout_positive and robust
            else "TIEBREAK_PROFILE_NOT_ROBUST_ENOUGH"
        ),
        "positive_holdout": holdout_positive,
        "robust_walk_forward": robust,
        "fresh_confirmation_required": True,
        "candidate_may_replace_reference": False,
        "promotion_gate": False,
    }
    return report


def build() -> dict[str, Any]:
    point_rows = list(_iter_jsonl_gz(POINTS) or ())
    profile_rows = list(_iter_jsonl_gz(PROFILES) or ())
    rows, build_counts = enrich_feature_rows(point_rows, profile_rows)
    report = evaluate(rows)
    report["build_counts"] = build_counts

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
