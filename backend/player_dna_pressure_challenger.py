from __future__ import annotations

"""Leakage-safe pressure-profile challenger for Player DNA.

This is the first SHADOW challenger that consumes the canonical pressure
profiles added to player_dna_shadow_profiles.py. The primary gate uses
hold/break + break-point rates only. Early service/return-game rates are fitted
separately as diagnostics and can never make the primary gate pass.

Nothing in this module writes canonical profiles, changes runtime scoring,
touches PROD, Symfonia 2.0, or Superbet PLAYABLE, or auto-promotes a model.
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
OUT = ROOT / "frontend" / "data" / "player_dna_pressure_challenger.json"
VERSION = "player-dna-pressure-challenger-v1"
MODE = "SHADOW_PRESSURE_CHALLENGER_EVAL_ONLY"
ROLLING_WINDOWS = ("L5", "L10", "L20")

PRIMARY_SERVER_RATES = ("hold_rate", "bp_save_rate")
PRIMARY_RECEIVER_RATES = ("break_rate", "bp_conversion_rate")
EARLY_SERVER_RATES = tuple(
    f"early_service_game_{index}_hold_rate" for index in (1, 2, 3)
)
EARLY_RECEIVER_RATES = tuple(
    f"early_return_game_{index}_break_rate" for index in (1, 2, 3)
)


def _contexts() -> tuple[str, ...]:
    return (
        "overall",
        "surface",
        *(f"all_{window.lower()}" for window in ROLLING_WINDOWS),
        *(f"surface_{window.lower()}" for window in ROLLING_WINDOWS),
    )


PROFILE_CONTEXTS = _contexts()


def _feature_names(
    server_rates: Iterable[str],
    receiver_rates: Iterable[str],
) -> list[str]:
    names: list[str] = []
    for context in PROFILE_CONTEXTS:
        names.extend(f"server_{context}_{rate}" for rate in server_rates)
        names.extend(f"receiver_{context}_{rate}" for rate in receiver_rates)
    return names


PRESSURE_PRIMARY_NUMERIC = _feature_names(
    PRIMARY_SERVER_RATES,
    PRIMARY_RECEIVER_RATES,
)
EARLY_GAME_DIAGNOSTIC_NUMERIC = _feature_names(
    EARLY_SERVER_RATES,
    EARLY_RECEIVER_RATES,
)


def _finite_rate(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        return None
    return number


def _context_profile(profile: dict[str, Any], context: str) -> dict[str, Any]:
    if context == "overall":
        raw = profile.get("overall_prior")
        return raw if isinstance(raw, dict) else {}
    if context == "surface":
        raw = profile.get("same_surface_prior")
        return raw if isinstance(raw, dict) else {}

    rolling = profile.get("rolling_prior")
    if not isinstance(rolling, dict):
        return {}
    if context.startswith("all_"):
        family = rolling.get("all_surface")
        window = context.removeprefix("all_").upper()
    elif context.startswith("surface_"):
        family = rolling.get("same_surface")
        window = context.removeprefix("surface_").upper()
    else:
        return {}
    if not isinstance(family, dict):
        return {}
    windows = family.get("windows")
    if not isinstance(windows, dict):
        return {}
    raw = windows.get(window)
    return raw if isinstance(raw, dict) else {}


def _pair_features(
    server_profile: dict[str, Any],
    receiver_profile: dict[str, Any],
) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for context in PROFILE_CONTEXTS:
        server = _context_profile(server_profile, context)
        receiver = _context_profile(receiver_profile, context)
        for rate in PRIMARY_SERVER_RATES:
            out[f"server_{context}_{rate}"] = _finite_rate(server.get(rate))
        for rate in PRIMARY_RECEIVER_RATES:
            out[f"receiver_{context}_{rate}"] = _finite_rate(receiver.get(rate))
        for rate in EARLY_SERVER_RATES:
            out[f"server_{context}_{rate}"] = _finite_rate(server.get(rate))
        for rate in EARLY_RECEIVER_RATES:
            out[f"receiver_{context}_{rate}"] = _finite_rate(receiver.get(rate))
    return out


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

        rows.append({**row, **_pair_features(server, receiver)})
        counts["enriched_rows"] += 1
        counts["rows_with_any_primary_pressure_rate"] += int(
            any(rows[-1].get(name) is not None for name in PRESSURE_PRIMARY_NUMERIC)
        )
        counts["rows_with_any_early_game_rate"] += int(
            any(rows[-1].get(name) is not None for name in EARLY_GAME_DIAGNOSTIC_NUMERIC)
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
    reference_numeric = (
        list(PROFILE_NUMERIC) + list(RANK_NUMERIC) + list(LEAN_STATE_NUMERIC)
    )
    primary_numeric = reference_numeric + list(PRESSURE_PRIMARY_NUMERIC)
    early_numeric = primary_numeric + list(EARLY_GAME_DIAGNOSTIC_NUMERIC)

    reference, _ = _fit_candidate(train, test, reference_numeric)
    primary, _ = _fit_candidate(train, test, primary_numeric)
    early, _ = _fit_candidate(train, test, early_numeric)

    primary_gains = _proper_score_gains(
        reference["metrics"],
        primary["metrics"],
    )
    early_gains = _proper_score_gains(
        primary["metrics"],
        early["metrics"],
    )
    return {
        "lean_stateful_reference": reference,
        "lean_stateful_plus_pressure_primary": primary,
        "lean_stateful_plus_pressure_primary_plus_early_game_diagnostic": early,
        "pressure_primary_gains_vs_lean_stateful": primary_gains,
        "early_game_diagnostic_gains_beyond_pressure_primary": early_gains,
        "pressure_primary_positive_all_proper_scores": _positive_gains(primary_gains),
        "early_game_diagnostic_positive_all_proper_scores": _positive_gains(early_gains),
    }


def _walk_forward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    folds = []
    for train_rows, test_rows, meta in _walk_forward_slices(rows):
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
                "status": "INSUFFICIENT_FOLD_SAMPLE",
                "train_points": int(len(train)),
                "test_points": int(len(test)),
            })
            continue

        result = _evaluate_frames(train, test)
        folds.append({
            **meta,
            "status": (
                "POSITIVE_PRESSURE_PRIMARY_FOLD"
                if result["pressure_primary_positive_all_proper_scores"]
                else "MIXED_OR_NEGATIVE_PRESSURE_PRIMARY_FOLD"
            ),
            "train_points": int(len(train)),
            "test_points": int(len(test)),
            **result,
        })

    completed = [
        row for row in folds
        if "pressure_primary_gains_vs_lean_stateful" in row
    ]
    positive = [
        row for row in completed
        if row.get("pressure_primary_positive_all_proper_scores") is True
    ]

    def mean_gain(metric: str) -> float | None:
        values = [
            float(row["pressure_primary_gains_vs_lean_stateful"][metric])
            for row in completed
        ]
        return round(sum(values) / len(values), 6) if values else None

    return {
        "mode": "SAME_EXPANDING_TRAIN_DISJOINT_WINDOWS_AS_CANONICAL_SCORER",
        "folds": folds,
        "completed_folds": len(completed),
        "positive_pressure_primary_folds": len(positive),
        "robust_positive_pressure_primary": bool(
            len(completed) == 3 and len(positive) == 3
        ),
        "mean_pressure_primary_gains": {
            "brier_gain": mean_gain("brier_gain"),
            "match_equal_brier_gain": mean_gain("match_equal_brier_gain"),
            "log_loss_gain": mean_gain("log_loss_gain"),
        },
        "same_timestamp_groups_not_split": True,
        "test_windows_disjoint": True,
    }


def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    train_all, holdout_all, split = split_chronological_by_match(rows)
    train = _frame(_cohort(train_all, EVAL_MIN_PRIOR_MATCHES))
    holdout = _frame(_cohort(holdout_all, EVAL_MIN_PRIOR_MATCHES))

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
        "evaluation_min_prior_matches": EVAL_MIN_PRIOR_MATCHES,
        "all_enriched_points": len(rows),
        "train_points_after_support_gate": int(len(train)),
        "holdout_points_after_support_gate": int(len(holdout)),
        "pressure_primary_numeric_features": list(PRESSURE_PRIMARY_NUMERIC),
        "early_game_diagnostic_numeric_features": list(EARLY_GAME_DIAGNOSTIC_NUMERIC),
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "training_join_enabled": False,
        "canonical_profile_write_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "promotion_gate": False,
        "candidate_may_replace_reference": False,
        "pressure_contract": {
            "primary_family": "hold_break_plus_break_point",
            "primary_uses_hold_rate": True,
            "primary_uses_break_rate": True,
            "primary_uses_bp_save_rate": True,
            "primary_uses_bp_conversion_rate": True,
            "primary_uses_overall_prior": True,
            "primary_uses_same_surface_prior": True,
            "primary_uses_rolling_l5_l10_l20": True,
            "primary_raw_support_counts_are_features": False,
            "deuce_and_thirty_all_are_not_in_first_primary_challenger": True,
            "early_game_is_diagnostic_only": True,
            "early_game_cannot_make_primary_gate_pass": True,
            "primary_gate_compares_against_current_lean_stateful_reference": True,
            "primary_gate_requires_holdout_and_three_walk_forward_folds": True,
            "primary_gate_requires_positive_brier_match_equal_brier_and_log_loss": True,
        },
        "leakage_contract": {
            "canonical_strict_as_of_profiles_only": True,
            "same_timestamp_matches_never_count_as_prior": True,
            "stable_provider_player_ids_only": True,
            "target_point_outcome_not_used_in_profile_features": True,
            "profile_features_are_pre_match_only": True,
            "current_target_match_never_contributes_to_its_own_profile": True,
            "set_boundary_or_missing_game_reconstruction_not_introduced_here": True,
        },
        "signal": {
            "status": "NOT_EVALUATED",
            "pressure_primary_positive_holdout": False,
            "pressure_primary_robust_walk_forward": False,
            "early_game_diagnostic_affects_primary_signal": False,
        },
    }

    if not enough:
        report["signal"]["status"] = "INSUFFICIENT_SHADOW_SAMPLE"
        return report

    holdout_result = _evaluate_frames(train, holdout)
    walk_forward = _walk_forward(rows)
    holdout_positive = bool(
        holdout_result["pressure_primary_positive_all_proper_scores"]
    )
    robust = bool(walk_forward["robust_positive_pressure_primary"])

    report["holdout"] = holdout_result
    report["walk_forward"] = walk_forward
    report["signal"] = {
        "status": (
            "PRESSURE_PRIMARY_ROBUST_POSITIVE_SHADOW_SIGNAL"
            if holdout_positive and robust
            else "PRESSURE_PRIMARY_NOT_ROBUST_ENOUGH"
        ),
        "pressure_primary_positive_holdout": holdout_positive,
        "pressure_primary_robust_walk_forward": robust,
        "early_game_diagnostic_affects_primary_signal": False,
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
