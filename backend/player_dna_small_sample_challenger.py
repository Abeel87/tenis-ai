from __future__ import annotations

"""Train-only small-sample shrinkage challenger for Player DNA.

This SHADOW evaluator tests whether empirical-Bayes style pseudo-point
shrinkage of canonical serve/return profile rates improves the current lean
stateful point reference.

The prior means and prior strength are selected only from the outer training
window. The outer holdout is never used for parameter selection. Nothing in
this module writes canonical profiles, changes runtime scoring, or affects
Symfonia 2.0 / Superbet PLAYABLE.
"""

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.player_dna_point_scorer import (
        LEAN_STATE_NUMERIC,
        POINTS,
        PROFILE_NUMERIC,
        PROFILES,
        RANK_NUMERIC,
        STATE_WALK_FORWARD_FRACTIONS,
        _fit_candidate,
        _frame,
        _iter_jsonl_gz,
        _metrics,
        _profile_index,
        _proper_score_gains,
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
        STATE_WALK_FORWARD_FRACTIONS,
        _fit_candidate,
        _frame,
        _iter_jsonl_gz,
        _metrics,
        _profile_index,
        _proper_score_gains,
        build_feature_rows,
        split_chronological_by_match,
    )

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data" / "player_dna_small_sample_challenger.json"

VERSION = "player-dna-small-sample-challenger-v2"
MODE = "SHADOW_SMALL_SAMPLE_SHRINKAGE_CHALLENGER_EVAL_ONLY"
PRIOR_STRENGTH_GRID = (0.0, 25.0, 50.0, 100.0, 200.0)
INNER_TRAIN_FRACTION = 0.80
SMALL_SAMPLE_MATCH_THRESHOLD = 5

# Frozen after the first leakage-safe robust historical run on PR #252.
# The artifact contained data only through this provider scheduled_time and the
# outer train-only selector chose 200 pseudo-points. Future confirmation must
# never retune either value using post-freeze labels.
FRESH_CONFIRMATION_CUTOFF = datetime(2026, 9, 7, 1, 35, tzinfo=timezone.utc)
FROZEN_FRESH_PRIOR_STRENGTH = 200.0

# Reuse the canonical outer-evaluation floor rather than inventing a separate
# promotion threshold. Meeting this floor only makes the fresh diagnostic
# evaluable; it does not promote or activate the candidate.
FRESH_MIN_POINTS = 500
FRESH_MIN_MATCHES = 20

RAW_SUPPORT_FIELDS = (
    "server_overall_serve_wins",
    "server_overall_serve_points",
    "receiver_overall_return_wins",
    "receiver_overall_return_points",
    "server_surface_serve_wins",
    "server_surface_serve_points",
    "receiver_surface_return_wins",
    "receiver_surface_return_points",
)

SHRUNK_RATE_FIELDS = (
    "server_overall_serve_rate_shrunk",
    "receiver_overall_return_rate_shrunk",
    "server_surface_serve_rate_shrunk",
    "receiver_surface_return_rate_shrunk",
)

PROFILE_SUPPORT_FIELDS = (
    "server_overall_matches",
    "receiver_overall_matches",
    "server_surface_matches",
    "receiver_surface_matches",
)

REFERENCE_NUMERIC = list(PROFILE_NUMERIC) + list(RANK_NUMERIC) + list(LEAN_STATE_NUMERIC)
SHRUNK_NUMERIC = list(SHRUNK_RATE_FIELDS) + list(PROFILE_SUPPORT_FIELDS) + list(RANK_NUMERIC) + list(LEAN_STATE_NUMERIC)


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return int(value)


def _point_identity_index(
    point_rows: Iterable[dict[str, Any]],
) -> dict[tuple[str, int], tuple[int, int]]:
    out: dict[tuple[str, int], tuple[int, int]] = {}
    for row in point_rows:
        if not isinstance(row, dict):
            continue
        match_id = str(row.get("match_id") or "").strip()
        event_index = row.get("event_index")
        server = _positive_int(row.get("server_player_id"))
        receiver = _positive_int(row.get("receiver_player_id"))
        if (
            not match_id
            or isinstance(event_index, bool)
            or not isinstance(event_index, int)
            or server is None
            or receiver is None
            or server == receiver
        ):
            continue
        out[(match_id, event_index)] = (server, receiver)
    return out


def _count(profile: dict[str, Any], key: str) -> int:
    value = profile.get(key)
    if isinstance(value, bool):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


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
    counts = Counter()

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
        if not isinstance(server, dict) or not isinstance(receiver, dict):
            counts["missing_profile_pair"] += 1
            continue

        so = server.get("overall_prior") if isinstance(server.get("overall_prior"), dict) else {}
        ro = receiver.get("overall_prior") if isinstance(receiver.get("overall_prior"), dict) else {}
        ss = server.get("same_surface_prior") if isinstance(server.get("same_surface_prior"), dict) else {}
        rs = receiver.get("same_surface_prior") if isinstance(receiver.get("same_surface_prior"), dict) else {}

        enriched = {
            **row,
            "server_overall_serve_wins": _count(so, "serve_wins"),
            "server_overall_serve_points": _count(so, "serve_points"),
            "receiver_overall_return_wins": _count(ro, "return_wins"),
            "receiver_overall_return_points": _count(ro, "return_points"),
            "server_surface_serve_wins": _count(ss, "serve_wins"),
            "server_surface_serve_points": _count(ss, "serve_points"),
            "receiver_surface_return_wins": _count(rs, "return_wins"),
            "receiver_surface_return_points": _count(rs, "return_points"),
        }
        rows.append(enriched)
        counts["enriched_rows"] += 1
        counts["rows_with_any_zero_overall_support"] += int(
            enriched["server_overall_serve_points"] == 0
            or enriched["receiver_overall_return_points"] == 0
        )
        counts["rows_with_any_overall_match_depth_below_5"] += int(
            min(
                int(enriched.get("server_overall_matches") or 0),
                int(enriched.get("receiver_overall_matches") or 0),
            ) < SMALL_SAMPLE_MATCH_THRESHOLD
        )

    return rows, {
        "base_join_counts": base_counts,
        "enrichment_counts": dict(counts),
    }


def _prior_means(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = 0
    server_wins = 0
    by_surface: dict[str, list[int]] = {}

    for row in rows:
        label = row.get("server_won")
        if label not in (0, 1):
            continue
        total += 1
        server_wins += int(label)
        surface = str(row.get("surface") or "unknown")
        bucket = by_surface.setdefault(surface, [0, 0])
        bucket[0] += int(label)
        bucket[1] += 1

    global_serve = server_wins / total if total else 0.5
    surface_serve = {
        surface: wins / n
        for surface, (wins, n) in by_surface.items()
        if n > 0
    }
    return {
        "global_serve": float(global_serve),
        "global_return": float(1.0 - global_serve),
        "surface_serve": {k: float(v) for k, v in surface_serve.items()},
        "surface_return": {k: float(1.0 - v) for k, v in surface_serve.items()},
        "points_used": int(total),
        "source": "OUTER_TRAIN_POINT_OUTCOMES_ONLY",
    }


def _posterior_rate(
    wins: Any,
    points: Any,
    prior_mean: float,
    prior_strength: float,
) -> float | None:
    try:
        w = float(wins)
        n = float(points)
        mean = float(prior_mean)
        strength = float(prior_strength)
    except (TypeError, ValueError):
        return None
    if (
        not math.isfinite(w)
        or not math.isfinite(n)
        or not math.isfinite(mean)
        or not math.isfinite(strength)
        or n < 0
        or w < 0
        or w > n
        or mean < 0
        or mean > 1
        or strength < 0
    ):
        return None
    if n <= 0:
        return mean if strength > 0 else None
    if strength == 0:
        return w / n
    return (w + strength * mean) / (n + strength)


def _apply_shrinkage(
    rows: list[dict[str, Any]],
    priors: dict[str, Any],
    strength: float,
) -> list[dict[str, Any]]:
    out = []
    surface_serve = priors.get("surface_serve") or {}
    surface_return = priors.get("surface_return") or {}
    global_serve = float(priors.get("global_serve", 0.5))
    global_return = float(priors.get("global_return", 0.5))

    for row in rows:
        surface = str(row.get("surface") or "unknown")
        serve_prior = float(surface_serve.get(surface, global_serve))
        return_prior = float(surface_return.get(surface, global_return))
        out.append({
            **row,
            "server_overall_serve_rate_shrunk": _posterior_rate(
                row.get("server_overall_serve_wins"),
                row.get("server_overall_serve_points"),
                global_serve,
                strength,
            ),
            "receiver_overall_return_rate_shrunk": _posterior_rate(
                row.get("receiver_overall_return_wins"),
                row.get("receiver_overall_return_points"),
                global_return,
                strength,
            ),
            "server_surface_serve_rate_shrunk": _posterior_rate(
                row.get("server_surface_serve_wins"),
                row.get("server_surface_serve_points"),
                serve_prior,
                strength,
            ),
            "receiver_surface_return_rate_shrunk": _posterior_rate(
                row.get("receiver_surface_return_wins"),
                row.get("receiver_surface_return_points"),
                return_prior,
                strength,
            ),
        })
    return out


def _enough(train, test, *, test_points: int = 500) -> bool:
    return bool(
        not train.empty
        and not test.empty
        and len(train) >= 1000
        and len(test) >= test_points
        and train["match_id"].nunique() >= 30
        and test["match_id"].nunique() >= 20
        and train["server_won"].nunique() == 2
        and test["server_won"].nunique() == 2
    )


def _select_strength(train_rows: list[dict[str, Any]]) -> dict[str, Any]:
    inner_train_rows, inner_validation_rows, split = split_chronological_by_match(
        train_rows,
        train_fraction=INNER_TRAIN_FRACTION,
    )
    inner_train = _frame(inner_train_rows)
    inner_validation = _frame(inner_validation_rows)
    if not _enough(inner_train, inner_validation, test_points=500):
        return {
            "status": "INSUFFICIENT_INNER_TRAIN_SELECTION_SAMPLE",
            "selected_prior_strength": None,
            "grid": list(PRIOR_STRENGTH_GRID),
            "split": split,
            "outer_test_used_for_selection": False,
            "candidates": [],
        }

    priors = _prior_means(inner_train_rows)
    candidates = []
    for strength in PRIOR_STRENGTH_GRID:
        fit = _frame(_apply_shrinkage(inner_train_rows, priors, strength))
        validation = _frame(
            _apply_shrinkage(inner_validation_rows, priors, strength)
        )
        result, _ = _fit_candidate(fit, validation, SHRUNK_NUMERIC)
        metrics = result["metrics"]
        candidates.append({
            "prior_strength": float(strength),
            "metrics": metrics,
        })

    selected = min(
        candidates,
        key=lambda row: (
            float(row["metrics"]["match_equal_brier"]),
            float(row["metrics"]["brier"]),
            float(row["metrics"]["log_loss"]),
            float(row["prior_strength"]),
        ),
    )
    return {
        "status": "SELECTED_ON_INNER_TRAIN_VALIDATION_ONLY",
        "selected_prior_strength": float(selected["prior_strength"]),
        "selection_rule": "MIN_MATCH_EQUAL_BRIER_THEN_BRIER_THEN_LOG_LOSS_THEN_LOWER_STRENGTH",
        "grid": list(PRIOR_STRENGTH_GRID),
        "split": split,
        "outer_test_used_for_selection": False,
        "prior_mean_source": "INNER_TRAIN_POINT_OUTCOMES_ONLY",
        "candidates": candidates,
    }


def _small_sample_mask(frame) -> Any:
    return (
        frame["server_overall_matches"].fillna(0).astype(int)
        .combine(
            frame["receiver_overall_matches"].fillna(0).astype(int),
            min,
        )
        < SMALL_SAMPLE_MATCH_THRESHOLD
    )


def _segment_metrics(frame, probs, mask) -> dict[str, Any] | None:
    subset = frame.loc[mask].copy()
    if subset.empty:
        return None
    return _metrics(subset, probs[mask.to_numpy(dtype=bool)])


def _evaluate_outer(
    train_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    train = _frame(train_rows)
    test = _frame(test_rows)
    if not _enough(train, test, test_points=500):
        return {
            "status": "INSUFFICIENT_OUTER_SAMPLE",
            "train_points": int(len(train)),
            "test_points": int(len(test)),
        }

    selection = _select_strength(train_rows)
    selected_strength = selection.get("selected_prior_strength")
    if selected_strength is None:
        return {
            "status": "INSUFFICIENT_INNER_SELECTION_SAMPLE",
            "train_points": int(len(train)),
            "test_points": int(len(test)),
            "strength_selection": selection,
        }

    priors = _prior_means(train_rows)
    shrunk_train = _frame(
        _apply_shrinkage(train_rows, priors, float(selected_strength))
    )
    shrunk_test = _frame(
        _apply_shrinkage(test_rows, priors, float(selected_strength))
    )

    reference, reference_probs = _fit_candidate(train, test, REFERENCE_NUMERIC)
    candidate, candidate_probs = _fit_candidate(
        shrunk_train,
        shrunk_test,
        SHRUNK_NUMERIC,
    )
    gains = _proper_score_gains(reference["metrics"], candidate["metrics"])

    mask = _small_sample_mask(test)
    reference_small = _segment_metrics(test, reference_probs, mask)
    candidate_small = _segment_metrics(test, candidate_probs, mask)
    small_gains = (
        _proper_score_gains(reference_small, candidate_small)
        if reference_small is not None and candidate_small is not None
        else None
    )

    positive = bool(
        gains["brier_gain"] > 0
        and gains["match_equal_brier_gain"] > 0
        and gains["log_loss_gain"] > 0
    )
    small_positive = bool(
        small_gains
        and small_gains["brier_gain"] > 0
        and small_gains["match_equal_brier_gain"] > 0
        and small_gains["log_loss_gain"] > 0
    )

    return {
        "status": (
            "POSITIVE_SHRINKAGE_OUTER_WINDOW"
            if positive
            else "MIXED_OR_NEGATIVE_SHRINKAGE_OUTER_WINDOW"
        ),
        "train_points": int(len(train)),
        "test_points": int(len(test)),
        "train_matches": int(train["match_id"].nunique()),
        "test_matches": int(test["match_id"].nunique()),
        "strength_selection": selection,
        "outer_train_prior_means": priors,
        "lean_stateful_raw_reference": reference,
        "lean_stateful_shrunk_profile": candidate,
        "gains_vs_raw_reference": gains,
        "positive_all_proper_scores": positive,
        "small_sample_segment": {
            "definition": "min(server_overall_matches, receiver_overall_matches) < 5",
            "points": int(mask.sum()),
            "raw_reference_metrics": reference_small,
            "shrunk_candidate_metrics": candidate_small,
            "gains_vs_raw_reference": small_gains,
            "positive_all_proper_scores": small_positive,
        },
    }


def _walk_forward_slices_all(
    rows: list[dict[str, Any]],
) -> list[tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]]:
    if not rows:
        return []

    match_times = {}
    for row in rows:
        match_id = str(row["match_id"])
        scheduled = row["scheduled_time"]
        previous = match_times.get(match_id)
        if previous is not None and previous != scheduled:
            raise ValueError(f"conflicting scheduled_time for match {match_id}")
        match_times[match_id] = scheduled

    unique_times = sorted(set(match_times.values()))
    if len(unique_times) < 20:
        return []
    n = len(unique_times)
    boundaries = [
        max(1, min(n - 1, int(n * fraction)))
        for fraction in STATE_WALK_FORWARD_FRACTIONS[:-1]
    ] + [n]
    if not (0 < boundaries[0] < boundaries[1] < boundaries[2] < boundaries[3]):
        return []

    out = []
    for fold_index in range(3):
        train_end = boundaries[fold_index]
        test_end = boundaries[fold_index + 1]
        train_times = set(unique_times[:train_end])
        test_times = set(unique_times[train_end:test_end])
        train_ids = {mid for mid, ts in match_times.items() if ts in train_times}
        test_ids = {mid for mid, ts in match_times.items() if ts in test_times}
        out.append((
            [row for row in rows if str(row["match_id"]) in train_ids],
            [row for row in rows if str(row["match_id"]) in test_ids],
            {
                "fold": fold_index + 1,
                "train_matches": len(train_ids),
                "test_matches": len(test_ids),
                "same_timestamp_split": False,
                "test_window_disjoint": True,
            },
        ))
    return out


def _walk_forward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    folds = []
    for train_rows, test_rows, meta in _walk_forward_slices_all(rows):
        result = _evaluate_outer(train_rows, test_rows)
        folds.append({**meta, **result})

    completed = [
        row for row in folds if "gains_vs_raw_reference" in row
    ]
    positive = [
        row for row in completed if row.get("positive_all_proper_scores") is True
    ]
    return {
        "mode": "EXPANDING_TRAIN_DISJOINT_WINDOWS_WITH_NESTED_TRAIN_ONLY_STRENGTH_SELECTION",
        "folds": folds,
        "completed_folds": len(completed),
        "positive_folds": len(positive),
        "robust_positive_all_three_folds": bool(
            len(completed) == 3 and len(positive) == 3
        ),
        "outer_test_used_for_parameter_selection": False,
        "same_timestamp_groups_not_split": True,
        "test_windows_disjoint": True,
    }


def _fresh_confirmation_split(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    frozen_train = []
    fresh = []
    invalid_time = 0

    for row in rows:
        scheduled = row.get("scheduled_time")
        if not isinstance(scheduled, datetime) or scheduled.tzinfo is None:
            invalid_time += 1
            continue
        scheduled = scheduled.astimezone(timezone.utc)
        if scheduled <= FRESH_CONFIRMATION_CUTOFF:
            frozen_train.append(row)
        else:
            fresh.append(row)

    def _match_count(part: list[dict[str, Any]]) -> int:
        return len({str(row.get("match_id") or "") for row in part if row.get("match_id")})

    return frozen_train, fresh, {
        "cutoff_time": FRESH_CONFIRMATION_CUTOFF.isoformat(),
        "policy": "scheduled_time <= cutoff frozen training; scheduled_time > cutoff fresh-only confirmation",
        "frozen_train_points": len(frozen_train),
        "frozen_train_matches": _match_count(frozen_train),
        "fresh_points": len(fresh),
        "fresh_matches": _match_count(fresh),
        "invalid_time_rows": invalid_time,
        "same_timestamp_crosses_cutoff": False,
    }


def _fresh_confirmation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    train_rows, fresh_rows, split = _fresh_confirmation_split(rows)
    train = _frame(train_rows)
    fresh = _frame(fresh_rows)

    fresh_matches = (
        int(fresh["match_id"].astype(str).nunique())
        if not fresh.empty and "match_id" in fresh.columns
        else 0
    )
    enough = bool(
        not train.empty
        and not fresh.empty
        and len(train) >= 1000
        and len(fresh) >= FRESH_MIN_POINTS
        and train["match_id"].astype(str).nunique() >= 30
        and fresh_matches >= FRESH_MIN_MATCHES
        and train["server_won"].nunique() == 2
        and fresh["server_won"].nunique() == 2
    )

    base = {
        "mode": "FROZEN_CANDIDATE_FRESH_ONLY_CONFIRMATION",
        "frozen_at_cutoff": FRESH_CONFIRMATION_CUTOFF.isoformat(),
        "frozen_prior_strength": FROZEN_FRESH_PRIOR_STRENGTH,
        "minimum_fresh_points_for_evaluation": FRESH_MIN_POINTS,
        "minimum_fresh_matches_for_evaluation": FRESH_MIN_MATCHES,
        "split": split,
        "parameter_reselection_enabled": False,
        "post_cutoff_labels_used_for_prior_mean": False,
        "post_cutoff_labels_used_for_prior_strength": False,
        "post_cutoff_labels_used_for_model_fit": False,
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "promotion_gate": False,
        "candidate_may_replace_reference": False,
    }
    if not enough:
        return {
            **base,
            "status": "WAITING_FOR_FRESH_SAMPLE",
            "fresh_sample_ready": False,
            "fresh_positive_all_proper_scores": None,
            "fresh_small_sample_positive_all_proper_scores": None,
        }

    priors = _prior_means(train_rows)
    shrunk_train = _frame(
        _apply_shrinkage(
            train_rows,
            priors,
            FROZEN_FRESH_PRIOR_STRENGTH,
        )
    )
    shrunk_fresh = _frame(
        _apply_shrinkage(
            fresh_rows,
            priors,
            FROZEN_FRESH_PRIOR_STRENGTH,
        )
    )

    reference, reference_probs = _fit_candidate(
        train,
        fresh,
        REFERENCE_NUMERIC,
    )
    candidate, candidate_probs = _fit_candidate(
        shrunk_train,
        shrunk_fresh,
        SHRUNK_NUMERIC,
    )
    gains = _proper_score_gains(
        reference["metrics"],
        candidate["metrics"],
    )
    positive = bool(
        gains["brier_gain"] > 0
        and gains["match_equal_brier_gain"] > 0
        and gains["log_loss_gain"] > 0
    )

    mask = _small_sample_mask(fresh)
    reference_small = _segment_metrics(fresh, reference_probs, mask)
    candidate_small = _segment_metrics(fresh, candidate_probs, mask)
    small_gains = (
        _proper_score_gains(reference_small, candidate_small)
        if reference_small is not None and candidate_small is not None
        else None
    )
    small_positive = bool(
        small_gains
        and small_gains["brier_gain"] > 0
        and small_gains["match_equal_brier_gain"] > 0
        and small_gains["log_loss_gain"] > 0
    )

    return {
        **base,
        "status": (
            "FRESH_CONFIRMATION_POSITIVE_SHADOW"
            if positive and small_positive
            else "FRESH_CONFIRMATION_MIXED_OR_NEGATIVE_SHADOW"
        ),
        "fresh_sample_ready": True,
        "frozen_train_prior_means": priors,
        "raw_reference_metrics": reference["metrics"],
        "shrunk_candidate_metrics": candidate["metrics"],
        "gains_vs_raw_reference": gains,
        "fresh_positive_all_proper_scores": positive,
        "small_sample_segment": {
            "definition": "min(server_overall_matches, receiver_overall_matches) < 5",
            "points": int(mask.sum()),
            "raw_reference_metrics": reference_small,
            "shrunk_candidate_metrics": candidate_small,
            "gains_vs_raw_reference": small_gains,
            "positive_all_proper_scores": small_positive,
        },
        "fresh_small_sample_positive_all_proper_scores": small_positive,
    }


def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    historical_rows, _fresh_rows, historical_evidence_split = _fresh_confirmation_split(rows)
    train_rows, holdout_rows, split = split_chronological_by_match(historical_rows)
    outer = _evaluate_outer(train_rows, holdout_rows)
    walk_forward = _walk_forward(historical_rows)
    fresh_confirmation = _fresh_confirmation(rows)

    holdout_positive = bool(outer.get("positive_all_proper_scores") is True)
    robust = bool(walk_forward.get("robust_positive_all_three_folds") is True)

    report: dict[str, Any] = {
        "version": VERSION,
        "mode": MODE,
        "phase": "PHASE_1_SMALL_SAMPLE_UNCERTAINTY_GATE",
        "label": "server_won",
        "split": split,
        "historical_evidence_split": historical_evidence_split,
        "all_enriched_points": len(rows),
        "prior_strength_grid": list(PRIOR_STRENGTH_GRID),
        "inner_train_fraction": INNER_TRAIN_FRACTION,
        "small_sample_match_threshold": SMALL_SAMPLE_MATCH_THRESHOLD,
        "frozen_fresh_confirmation_cutoff": FRESH_CONFIRMATION_CUTOFF.isoformat(),
        "frozen_fresh_prior_strength": FROZEN_FRESH_PRIOR_STRENGTH,
        "reference_numeric_features": list(REFERENCE_NUMERIC),
        "shrunk_numeric_features": list(SHRUNK_NUMERIC),
        "raw_support_fields_used_for_transformation_only": list(RAW_SUPPORT_FIELDS),
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "training_join_enabled": False,
        "canonical_profile_write_enabled": False,
        "simulator_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "promotion_gate": False,
        "candidate_may_replace_reference": False,
        "contract": {
            "empirical_bayes_style_pseudo_point_shrinkage_only": True,
            "same_reference_feature_family_except_shrunk_rates": True,
            "raw_support_counts_are_transformation_inputs_not_model_features": True,
            "prior_means_fit_from_outer_train_point_outcomes_only": True,
            "prior_strength_selected_inside_outer_train_only": True,
            "outer_holdout_never_used_for_parameter_selection": True,
            "same_timestamp_matches_never_split_across_train_test": True,
            "strength_grid_predeclared_before_holdout_evaluation": True,
            "zero_strength_candidate_represents_no_shrinkage": True,
            "small_sample_segment_reported_separately": True,
            "historical_success_requires_holdout_and_three_walk_forward_folds": True,
            "all_three_proper_scores_must_improve": True,
            "fresh_confirmation_required_before_any_activation": True,
            "fresh_candidate_cutoff_is_frozen": True,
            "fresh_candidate_prior_strength_is_frozen": True,
            "historical_evidence_frozen_at_fresh_cutoff": True,
            "post_cutoff_labels_cannot_retune_candidate": True,
        },
        "leakage_contract": {
            "canonical_strict_as_of_profiles_only": True,
            "stable_provider_player_ids_only": True,
            "current_target_match_never_contributes_to_its_own_profile": True,
            "outer_test_labels_not_used_for_prior_mean": True,
            "outer_test_labels_not_used_for_prior_strength": True,
            "walk_forward_strength_reselected_inside_each_fold_train_only": True,
            "post_cutoff_labels_not_used_for_historical_holdout_or_walk_forward": True,
            "fresh_confirmation_uses_only_strictly_post_cutoff_rows_for_scoring": True,
            "fresh_confirmation_trains_only_on_at_or_before_cutoff_rows": True,
        },
        "holdout": outer,
        "walk_forward": walk_forward,
        "fresh_confirmation": fresh_confirmation,
        "signal": {
            "status": (
                "SMALL_SAMPLE_SHRINKAGE_ROBUST_HISTORICAL_SIGNAL_REQUIRES_FRESH_CONFIRMATION"
                if holdout_positive and robust
                else "SMALL_SAMPLE_SHRINKAGE_NOT_ROBUST_ENOUGH"
            ),
            "positive_holdout": holdout_positive,
            "robust_walk_forward": robust,
            "fresh_confirmation_required": True,
            "fresh_confirmation_status": fresh_confirmation.get("status"),
            "fresh_confirmation_positive": (
                fresh_confirmation.get("status") == "FRESH_CONFIRMATION_POSITIVE_SHADOW"
            ),
            "candidate_may_replace_reference": False,
            "promotion_gate": False,
        },
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
    print(json.dumps({
        "version": report["version"],
        "status": report["signal"]["status"],
        "points": report["all_enriched_points"],
        "holdout_positive": report["signal"]["positive_holdout"],
        "robust_walk_forward": report["signal"]["robust_walk_forward"],
        "selected_strength": (
            (report.get("holdout") or {}).get("strength_selection") or {}
        ).get("selected_prior_strength"),
        "fresh_confirmation": (
            report.get("fresh_confirmation") or {}
        ).get("status"),
        "fresh_points": (
            ((report.get("fresh_confirmation") or {}).get("split") or {})
        ).get("fresh_points"),
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
