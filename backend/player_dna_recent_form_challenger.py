from __future__ import annotations

"""Leakage-safe recent-form challenger for Player DNA.

This SHADOW evaluator asks whether the shortest canonical complete rolling
window (all-surface L5) adds current-form information beyond the present
lean-stateful point reference. It intentionally tests one predeclared family
only: server recent serve rate + receiver recent return rate.

No L10/L20, same-surface rolling variants, support counts, or post-hoc family
screen are used here. Even a robust historical result would require a separate
frozen fresh-confirmation gate before any activation.
"""

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.player_dna_point_scorer import (
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
OUT = ROOT / "frontend" / "data" / "player_dna_recent_form_challenger.json"

VERSION = "player-dna-recent-form-challenger-v1"
MODE = "SHADOW_RECENT_FORM_CHALLENGER_EVAL_ONLY"
RECENT_FORM_WINDOW = "L5"
RECENT_FORM_MIN_PRIOR_MATCHES = 5
RECENT_FORM_NUMERIC = [
    "server_all_l5_serve_win_rate",
    "receiver_all_l5_return_win_rate",
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


def _rolling_l5(profile: dict[str, Any]) -> dict[str, Any]:
    rolling = profile.get("rolling_prior")
    if not isinstance(rolling, dict):
        return {}
    all_surface = rolling.get("all_surface")
    if not isinstance(all_surface, dict):
        return {}
    windows = all_surface.get("windows")
    if not isinstance(windows, dict):
        return {}
    raw = windows.get(RECENT_FORM_WINDOW)
    return raw if isinstance(raw, dict) else {}


def _pair_recent_form_features(
    server_profile: dict[str, Any],
    receiver_profile: dict[str, Any],
) -> dict[str, float | None]:
    server_l5 = _rolling_l5(server_profile)
    receiver_l5 = _rolling_l5(receiver_profile)
    return {
        "server_all_l5_serve_win_rate": _finite_rate(
            server_l5.get("serve_win_rate")
        ),
        "receiver_all_l5_return_win_rate": _finite_rate(
            receiver_l5.get("return_win_rate")
        ),
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

        enriched = {**row, **_pair_recent_form_features(server, receiver)}
        rows.append(enriched)
        counts["enriched_rows"] += 1
        counts["rows_with_both_l5_rates"] += int(
            all(enriched.get(name) is not None for name in RECENT_FORM_NUMERIC)
        )
        counts["rows_with_both_players_l5_full"] += int(
            int(enriched.get("server_overall_matches") or 0)
            >= RECENT_FORM_MIN_PRIOR_MATCHES
            and int(enriched.get("receiver_overall_matches") or 0)
            >= RECENT_FORM_MIN_PRIOR_MATCHES
        )

    return rows, {
        "base_join_counts": base_counts,
        "enrichment_counts": dict(counts),
        "profile_snapshots": len(profiles),
    }


def _eligible(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cohort = _cohort(rows, RECENT_FORM_MIN_PRIOR_MATCHES)
    return [
        row
        for row in cohort
        if all(row.get(name) is not None for name in RECENT_FORM_NUMERIC)
    ]


def _positive_gains(gains: dict[str, float]) -> bool:
    return bool(
        gains["brier_gain"] > 0
        and gains["match_equal_brier_gain"] > 0
        and gains["log_loss_gain"] > 0
    )


def _evaluate_frames(train, test) -> dict[str, Any]:
    reference_numeric = (
        list(PROFILE_NUMERIC) + list(RANK_NUMERIC) + list(LEAN_STATE_NUMERIC)
    )
    candidate_numeric = reference_numeric + list(RECENT_FORM_NUMERIC)

    reference, _ = _fit_candidate(train, test, reference_numeric)
    candidate, _ = _fit_candidate(train, test, candidate_numeric)
    gains = _proper_score_gains(reference["metrics"], candidate["metrics"])

    return {
        "lean_stateful_reference": reference,
        "lean_stateful_plus_recent_form_l5": candidate,
        "recent_form_gains_vs_lean_stateful": gains,
        "positive_all_proper_scores": _positive_gains(gains),
    }


def _walk_forward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    folds = []
    for train_rows, test_rows, meta in _walk_forward_slices(rows):
        train_rows = _eligible(train_rows)
        test_rows = _eligible(test_rows)
        train = _frame(train_rows)
        test = _frame(test_rows)

        enough = (
            len(train) >= 1000
            and len(test) >= 500
            and train["match_id"].nunique() >= 30
            and test["match_id"].nunique() >= 20
            and train["server_won"].nunique() == 2
            and test["server_won"].nunique() == 2
        ) if not train.empty and not test.empty else False

        if not enough:
            folds.append({
                **meta,
                "status": "INSUFFICIENT_RECENT_FORM_FOLD_SAMPLE",
                "train_points": int(len(train)),
                "test_points": int(len(test)),
            })
            continue

        result = _evaluate_frames(train, test)
        folds.append({
            **meta,
            "status": (
                "POSITIVE_RECENT_FORM_FOLD"
                if result["positive_all_proper_scores"]
                else "MIXED_OR_NEGATIVE_RECENT_FORM_FOLD"
            ),
            "train_points": int(len(train)),
            "test_points": int(len(test)),
            **result,
        })

    completed = [
        row for row in folds if "recent_form_gains_vs_lean_stateful" in row
    ]
    positive = [
        row for row in completed if row.get("positive_all_proper_scores") is True
    ]

    def mean_gain(metric: str) -> float | None:
        values = [
            float(row["recent_form_gains_vs_lean_stateful"][metric])
            for row in completed
        ]
        return round(sum(values) / len(values), 6) if values else None

    return {
        "mode": "CANONICAL_EXPANDING_TRAIN_DISJOINT_WINDOWS_WITH_L5_ELIGIBILITY",
        "folds": folds,
        "completed_folds": len(completed),
        "positive_folds": len(positive),
        "robust_positive_all_three_folds": bool(
            len(completed) == 3 and len(positive) == 3
        ),
        "mean_gains_vs_lean_stateful": {
            "brier_gain": mean_gain("brier_gain"),
            "match_equal_brier_gain": mean_gain("match_equal_brier_gain"),
            "log_loss_gain": mean_gain("log_loss_gain"),
        },
        "same_timestamp_groups_not_split": True,
        "test_windows_disjoint": True,
    }


def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    train_all, holdout_all, split = split_chronological_by_match(rows)
    train_rows = _eligible(train_all)
    holdout_rows = _eligible(holdout_all)
    train = _frame(train_rows)
    holdout = _frame(holdout_rows)

    enough = (
        len(train) >= 1000
        and len(holdout) >= 1000
        and train["match_id"].nunique() >= 30
        and holdout["match_id"].nunique() >= 20
        and train["server_won"].nunique() == 2
        and holdout["server_won"].nunique() == 2
    ) if not train.empty and not holdout.empty else False

    report: dict[str, Any] = {
        "version": VERSION,
        "mode": MODE,
        "label": "server_won",
        "split": split,
        "all_enriched_points": len(rows),
        "recent_form_window": RECENT_FORM_WINDOW,
        "evaluation_min_prior_matches": RECENT_FORM_MIN_PRIOR_MATCHES,
        "train_points_after_l5_support_gate": int(len(train)),
        "holdout_points_after_l5_support_gate": int(len(holdout)),
        "recent_form_numeric_features": list(RECENT_FORM_NUMERIC),
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "training_join_enabled": False,
        "canonical_profile_write_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "promotion_gate": False,
        "candidate_may_replace_reference": False,
        "contract": {
            "primary_family": "all_surface_l5_serve_return",
            "single_predeclared_family_only": True,
            "l5_is_shortest_canonical_complete_rolling_window": True,
            "both_players_require_five_prior_matches": True,
            "raw_support_counts_are_model_features": False,
            "same_surface_rolling_excluded_from_this_challenger": True,
            "l10_l20_excluded_from_this_challenger": True,
            "no_post_hoc_family_screen": True,
            "primary_reference_is_current_lean_stateful": True,
            "historical_success_requires_holdout_and_three_walk_forward_folds": True,
            "all_three_proper_scores_must_improve": True,
            "fresh_confirmation_required_before_any_activation": True,
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
        report["signal"]["status"] = "INSUFFICIENT_RECENT_FORM_SHADOW_SAMPLE"
        return report

    holdout_result = _evaluate_frames(train, holdout)
    walk_forward = _walk_forward(rows)
    holdout_positive = bool(holdout_result["positive_all_proper_scores"])
    robust = bool(walk_forward["robust_positive_all_three_folds"])

    report["holdout"] = holdout_result
    report["walk_forward"] = walk_forward
    report["signal"] = {
        "status": (
            "RECENT_FORM_L5_ROBUST_HISTORICAL_SIGNAL_REQUIRES_FRESH_CONFIRMATION"
            if holdout_positive and robust
            else "RECENT_FORM_L5_NOT_ROBUST_ENOUGH"
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
