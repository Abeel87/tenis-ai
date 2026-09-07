from __future__ import annotations

"""Chronological SHADOW challenger for comeback and BO5 late-set Player DNA profiles.

This module tests whether the newly built strict-as-of match-state profiles carry
predictive information beyond a train-only context prior. It does not wire the
profiles into the canonical point scorer or simulator.

Primary predeclared tasks:
1. BO3 comeback: after player A loses set 1, predict whether A wins the match.
2. BO5 late set: before the match, predict whether p1 wins each set from set 3 on.

For each task the baseline is a train-only surface-specific event rate (falling
back to the train global rate). The challenger uses a fixed 50/50 blend of two
empirical-Bayes-style player estimates:

    P(event) = 0.5 * P_A(event) + 0.5 * (1 - P_B(opposite_event))

Only the pseudo-count strength is selected, from a fixed grid, inside the outer
train period. Same-timestamp matches are never split across train/test.

A historical win here is only a signal gate. Incremental value over the current
canonical scorer is deliberately NOT claimed or tested in this PR.
"""

import gzip
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.player_dna_match_state_profiles import (
        OUT_JSONL as PROFILE_SNAPSHOTS,
        iter_payloads,
    )
    from backend.player_dna_match_state_readiness import inspect_payload
except ModuleNotFoundError:  # direct execution compatibility
    from player_dna_match_state_profiles import (
        OUT_JSONL as PROFILE_SNAPSHOTS,
        iter_payloads,
    )
    from player_dna_match_state_readiness import inspect_payload

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data" / "player_dna_match_state_challenger.json"

VERSION = "player-dna-match-state-challenger-v1"
MODE = "SHADOW_MATCH_STATE_CHALLENGER_EVAL_ONLY"
STRENGTH_GRID = (0.0, 1.0, 3.0, 5.0, 10.0, 20.0)
OUTER_TRAIN_FRACTION = 0.80
INNER_TRAIN_FRACTION = 0.80
WALK_FORWARD_FRACTIONS = (0.55, 0.70, 0.85, 1.0)

TASK_MINIMUMS = {
    "comeback_bo3": {
        "train_rows": 800,
        "test_rows": 150,
        "train_matches": 500,
        "test_matches": 100,
    },
    "bo5_late_set": {
        "train_rows": 100,
        "test_rows": 25,
        "train_matches": 30,
        "test_matches": 8,
    },
}


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _iter_jsonl_gz(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def _profile_index(
    rows: Iterable[dict[str, Any]],
) -> dict[tuple[str, int], dict[str, Any]]:
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        match_id = str(row.get("target_match_id") or "").strip()
        pid = row.get("player_id")
        if (
            not match_id
            or isinstance(pid, bool)
            or not isinstance(pid, int)
            or pid <= 0
        ):
            continue
        key = (match_id, int(pid))
        if key in out:
            raise ValueError(f"duplicate match-state profile snapshot: {key}")
        out[key] = row
    return out


def _count(prior: dict[str, Any], key: str) -> int:
    value = prior.get(key)
    if isinstance(value, bool):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def build_feature_rows(
    payloads: Iterable[dict[str, Any]],
    profile_rows: Iterable[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    profiles = _profile_index(profile_rows)
    comeback_rows: list[dict[str, Any]] = []
    bo5_rows: list[dict[str, Any]] = []
    counts = Counter()

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        counts["payloads_seen"] += 1
        item = inspect_payload(payload)
        if item.get("exact_set_winner_sequence") is not True:
            counts["payloads_rejected_by_exact_match_state_gate"] += 1
            continue

        match_id = str(item.get("match_id") or "").strip()
        scheduled = _parse_utc(item.get("scheduled"))
        if not match_id or scheduled is None:
            counts["exact_rows_missing_match_identity_or_time"] += 1
            continue

        p1 = int(item["p1_id"])
        p2 = int(item["p2_id"])
        p1_profile = profiles.get((match_id, p1))
        p2_profile = profiles.get((match_id, p2))
        if not isinstance(p1_profile, dict) or not isinstance(p2_profile, dict):
            counts["exact_matches_missing_profile_pair"] += 1
            continue

        p1_prior = (
            p1_profile.get("overall_prior")
            if isinstance(p1_profile.get("overall_prior"), dict)
            else {}
        )
        p2_prior = (
            p2_profile.get("overall_prior")
            if isinstance(p2_profile.get("overall_prior"), dict)
            else {}
        )
        surface = str(item.get("surface") or "unknown").strip().casefold() or "unknown"
        best_of = int(item["best_of"])
        sequence = [int(side) for side in item["set_winner_sequence"]]

        if best_of == 3:
            loser_side = int(item["first_set_loser_side"])
            winner_side = int(item["first_set_winner_side"])
            match_winner = int(item["match_winner_side"])
            loser_pid = p1 if loser_side == 1 else p2
            winner_pid = p1 if winner_side == 1 else p2
            loser_prior = p1_prior if loser_side == 1 else p2_prior
            winner_prior = p1_prior if winner_side == 1 else p2_prior

            comeback_rows.append(
                {
                    "task": "comeback_bo3",
                    "match_id": match_id,
                    "scheduled_time": scheduled,
                    "surface": surface,
                    "label": int(match_winner == loser_side),
                    "side_a_player_id": loser_pid,
                    "side_b_player_id": winner_pid,
                    "side_a_wins": _count(
                        loser_prior,
                        "comeback_wins_after_first_set_loss",
                    ),
                    "side_a_exposures": _count(
                        loser_prior,
                        "first_set_loss_exposures",
                    ),
                    "side_b_wins": _count(
                        winner_prior,
                        "match_wins_after_first_set_win",
                    ),
                    "side_b_exposures": _count(
                        winner_prior,
                        "first_set_win_exposures",
                    ),
                }
            )
            counts["comeback_bo3_rows"] += 1

        if best_of == 5:
            for set_number, winner_side in enumerate(sequence[2:], start=3):
                bo5_rows.append(
                    {
                        "task": "bo5_late_set",
                        "match_id": match_id,
                        "scheduled_time": scheduled,
                        "surface": surface,
                        "set_number": int(set_number),
                        "label": int(winner_side == 1),
                        "side_a_player_id": p1,
                        "side_b_player_id": p2,
                        "side_a_wins": _count(p1_prior, "bo5_late_set_wins"),
                        "side_a_exposures": _count(
                            p1_prior,
                            "bo5_late_set_exposures",
                        ),
                        "side_b_wins": _count(p2_prior, "bo5_late_set_wins"),
                        "side_b_exposures": _count(
                            p2_prior,
                            "bo5_late_set_exposures",
                        ),
                    }
                )
                counts["bo5_late_set_rows"] += 1

    return {
        "comeback_bo3": comeback_rows,
        "bo5_late_set": bo5_rows,
    }, {
        "profile_snapshots_indexed": len(profiles),
        **dict(counts),
    }


def _split_chronological_by_match(
    rows: list[dict[str, Any]],
    train_fraction: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not rows:
        return [], [], {
            "cutoff_time": None,
            "train_matches": 0,
            "holdout_matches": 0,
            "same_timestamp_split": False,
        }

    match_times: dict[str, datetime] = {}
    for row in rows:
        match_id = str(row["match_id"])
        scheduled = row["scheduled_time"]
        if not isinstance(scheduled, datetime):
            raise ValueError("scheduled_time must be datetime")
        previous = match_times.get(match_id)
        if previous is not None and previous != scheduled:
            raise ValueError(f"conflicting scheduled_time for match {match_id}")
        match_times[match_id] = scheduled

    ordered = sorted(match_times.items(), key=lambda pair: (pair[1], pair[0]))
    if len(ordered) < 2:
        return rows, [], {
            "cutoff_time": None,
            "train_matches": len(ordered),
            "holdout_matches": 0,
            "same_timestamp_split": False,
        }

    desired = max(1, min(len(ordered) - 1, int(len(ordered) * train_fraction)))
    cutoff = ordered[desired][1]
    train_ids = {mid for mid, ts in ordered if ts < cutoff}
    holdout_ids = {mid for mid, ts in ordered if ts >= cutoff}

    train = [row for row in rows if str(row["match_id"]) in train_ids]
    holdout = [row for row in rows if str(row["match_id"]) in holdout_ids]

    train_times = {match_times[mid] for mid in train_ids}
    holdout_times = {match_times[mid] for mid in holdout_ids}
    return train, holdout, {
        "cutoff_time": cutoff.isoformat(),
        "train_matches": len(train_ids),
        "holdout_matches": len(holdout_ids),
        "same_timestamp_split": bool(train_times & holdout_times),
        "policy": "all matches before cutoff train; cutoff timestamp and later test",
    }


def _context_priors(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = 0
    wins = 0
    by_surface: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        label = row.get("label")
        if label not in (0, 1):
            continue
        total += 1
        wins += int(label)
        bucket = by_surface[str(row.get("surface") or "unknown")]
        bucket[0] += int(label)
        bucket[1] += 1

    global_rate = wins / total if total else 0.5
    surface_rates = {
        surface: bucket[0] / bucket[1]
        for surface, bucket in by_surface.items()
        if bucket[1] > 0
    }
    return {
        "global_event_rate": float(global_rate),
        "surface_event_rates": {
            key: float(value)
            for key, value in surface_rates.items()
        },
        "rows_used": int(total),
        "source": "TRAIN_LABELS_ONLY",
    }


def _baseline_for_row(row: dict[str, Any], priors: dict[str, Any]) -> float:
    surface = str(row.get("surface") or "unknown")
    surface_rates = priors.get("surface_event_rates") or {}
    value = surface_rates.get(surface, priors.get("global_event_rate", 0.5))
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.5
    return min(1.0, max(0.0, number))


def _posterior_rate(
    wins: Any,
    exposures: Any,
    prior_mean: float,
    strength: float,
) -> float:
    try:
        w = float(wins)
        n = float(exposures)
        mean = float(prior_mean)
        k = float(strength)
    except (TypeError, ValueError):
        return float(prior_mean)

    if (
        not math.isfinite(w)
        or not math.isfinite(n)
        or not math.isfinite(mean)
        or not math.isfinite(k)
        or n < 0
        or w < 0
        or w > n
        or mean < 0
        or mean > 1
        or k < 0
    ):
        return float(prior_mean)

    if n <= 0:
        return mean
    if k <= 0:
        return w / n
    return (w + k * mean) / (n + k)


def _predict_rows(
    rows: list[dict[str, Any]],
    priors: dict[str, Any],
    strength: float,
) -> tuple[list[float], list[float]]:
    baseline: list[float] = []
    candidate: list[float] = []

    for row in rows:
        base = _baseline_for_row(row, priors)
        a = _posterior_rate(
            row.get("side_a_wins"),
            row.get("side_a_exposures"),
            base,
            strength,
        )
        b_success = _posterior_rate(
            row.get("side_b_wins"),
            row.get("side_b_exposures"),
            1.0 - base,
            strength,
        )
        p = 0.5 * a + 0.5 * (1.0 - b_success)
        baseline.append(base)
        candidate.append(min(1.0, max(0.0, p)))

    return baseline, candidate


def _metrics(
    rows: list[dict[str, Any]],
    probs: list[float],
) -> dict[str, Any]:
    if len(rows) != len(probs):
        raise ValueError("row/probability length mismatch")
    if not rows:
        return {
            "rows": 0,
            "matches": 0,
            "positive_rate": None,
            "brier": None,
            "match_equal_brier": None,
            "log_loss": None,
            "accuracy": None,
        }

    labels = [int(row["label"]) for row in rows]
    clipped = [min(1 - 1e-6, max(1e-6, float(p))) for p in probs]
    squared = [(y - p) ** 2 for y, p in zip(labels, clipped)]
    losses = [
        -(y * math.log(p) + (1 - y) * math.log(1 - p))
        for y, p in zip(labels, clipped)
    ]
    correct = [
        int((p >= 0.5) == (y == 1))
        for y, p in zip(labels, clipped)
    ]

    by_match: dict[str, list[float]] = defaultdict(list)
    for row, error in zip(rows, squared):
        by_match[str(row["match_id"])].append(error)

    match_equal = (
        sum(sum(values) / len(values) for values in by_match.values())
        / len(by_match)
    )

    return {
        "rows": len(rows),
        "matches": len(by_match),
        "positive_rate": round(sum(labels) / len(labels), 6),
        "brier": round(sum(squared) / len(squared), 6),
        "match_equal_brier": round(match_equal, 6),
        "log_loss": round(sum(losses) / len(losses), 6),
        "accuracy": round(sum(correct) / len(correct), 6),
    }


def _gains(
    reference: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, float]:
    return {
        "brier_gain": round(
            float(reference["brier"]) - float(candidate["brier"]),
            6,
        ),
        "match_equal_brier_gain": round(
            float(reference["match_equal_brier"])
            - float(candidate["match_equal_brier"]),
            6,
        ),
        "log_loss_gain": round(
            float(reference["log_loss"]) - float(candidate["log_loss"]),
            6,
        ),
    }


def _positive_all(gains: dict[str, float] | None) -> bool:
    return bool(
        gains
        and gains["brier_gain"] > 0
        and gains["match_equal_brier_gain"] > 0
        and gains["log_loss_gain"] > 0
    )


def _support_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    any_support = [
        row
        for row in rows
        if int(row.get("side_a_exposures") or 0) > 0
        or int(row.get("side_b_exposures") or 0) > 0
    ]
    both_support = [
        row
        for row in rows
        if int(row.get("side_a_exposures") or 0) > 0
        and int(row.get("side_b_exposures") or 0) > 0
    ]
    return {
        "rows": len(rows),
        "rows_with_any_player_support": len(any_support),
        "rows_with_both_players_supported": len(both_support),
        "any_support_rate": round(len(any_support) / len(rows), 6) if rows else 0.0,
        "both_support_rate": round(len(both_support) / len(rows), 6) if rows else 0.0,
    }


def _sample_enough(
    task: str,
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
) -> bool:
    minimums = TASK_MINIMUMS[task]
    train_matches = {str(row["match_id"]) for row in train}
    test_matches = {str(row["match_id"]) for row in test}
    return bool(
        len(train) >= minimums["train_rows"]
        and len(test) >= minimums["test_rows"]
        and len(train_matches) >= minimums["train_matches"]
        and len(test_matches) >= minimums["test_matches"]
        and len({int(row["label"]) for row in train}) == 2
        and len({int(row["label"]) for row in test}) == 2
    )


def _select_strength(
    task: str,
    outer_train: list[dict[str, Any]],
) -> dict[str, Any]:
    inner_train, inner_test, split = _split_chronological_by_match(
        outer_train,
        INNER_TRAIN_FRACTION,
    )
    if not _sample_enough(task, inner_train, inner_test):
        return {
            "status": "INSUFFICIENT_INNER_SAMPLE",
            "selected_strength": None,
            "split": split,
            "candidates": [],
        }

    priors = _context_priors(inner_train)
    candidates = []
    for strength in STRENGTH_GRID:
        baseline_probs, candidate_probs = _predict_rows(
            inner_test,
            priors,
            strength,
        )
        reference_metrics = _metrics(inner_test, baseline_probs)
        candidate_metrics = _metrics(inner_test, candidate_probs)
        gains = _gains(reference_metrics, candidate_metrics)
        candidates.append(
            {
                "strength": float(strength),
                "reference_metrics": reference_metrics,
                "candidate_metrics": candidate_metrics,
                "gains_vs_context_prior": gains,
            }
        )

    selected = min(
        candidates,
        key=lambda row: (
            float(row["candidate_metrics"]["brier"]),
            float(row["candidate_metrics"]["match_equal_brier"]),
            float(row["candidate_metrics"]["log_loss"]),
            float(row["strength"]),
        ),
    )
    return {
        "status": "SELECTED_INSIDE_OUTER_TRAIN_ONLY",
        "selected_strength": float(selected["strength"]),
        "split": split,
        "train_context_priors": priors,
        "candidates": candidates,
    }


def _evaluate_train_test(
    task: str,
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
) -> dict[str, Any]:
    if not _sample_enough(task, train, test):
        return {
            "status": "INSUFFICIENT_SAMPLE",
            "train_rows": len(train),
            "test_rows": len(test),
            "train_matches": len({str(row["match_id"]) for row in train}),
            "test_matches": len({str(row["match_id"]) for row in test}),
            "minimums": TASK_MINIMUMS[task],
            "positive_all_proper_scores": False,
        }

    selection = _select_strength(task, train)
    selected = selection.get("selected_strength")
    if not isinstance(selected, (int, float)):
        return {
            "status": "INSUFFICIENT_INNER_SELECTION_SAMPLE",
            "train_rows": len(train),
            "test_rows": len(test),
            "strength_selection": selection,
            "positive_all_proper_scores": False,
        }

    priors = _context_priors(train)
    reference_probs, candidate_probs = _predict_rows(test, priors, float(selected))
    reference_metrics = _metrics(test, reference_probs)
    candidate_metrics = _metrics(test, candidate_probs)
    gains = _gains(reference_metrics, candidate_metrics)

    supported_rows = [
        row
        for row in test
        if int(row.get("side_a_exposures") or 0) > 0
        or int(row.get("side_b_exposures") or 0) > 0
    ]
    supported_reference = None
    supported_candidate = None
    supported_gains = None
    if supported_rows:
        sr, sc = _predict_rows(supported_rows, priors, float(selected))
        supported_reference = _metrics(supported_rows, sr)
        supported_candidate = _metrics(supported_rows, sc)
        supported_gains = _gains(supported_reference, supported_candidate)

    return {
        "status": "EVALUATED",
        "selected_strength": float(selected),
        "strength_selection": selection,
        "train_context_priors": priors,
        "train_support": _support_summary(train),
        "test_support": _support_summary(test),
        "reference_metrics": reference_metrics,
        "candidate_metrics": candidate_metrics,
        "gains_vs_context_prior": gains,
        "positive_all_proper_scores": _positive_all(gains),
        "supported_subset": {
            "rows": len(supported_rows),
            "reference_metrics": supported_reference,
            "candidate_metrics": supported_candidate,
            "gains_vs_context_prior": supported_gains,
            "positive_all_proper_scores": _positive_all(supported_gains),
        },
    }


def _walk_forward_slices(
    rows: list[dict[str, Any]],
) -> list[tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]]:
    if not rows:
        return []

    match_times: dict[str, datetime] = {}
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
        for fraction in WALK_FORWARD_FRACTIONS[:-1]
    ] + [n]
    if not (
        0 < boundaries[0] < boundaries[1] < boundaries[2] < boundaries[3]
    ):
        return []

    result = []
    for fold_index in range(3):
        train_end = boundaries[fold_index]
        test_end = boundaries[fold_index + 1]
        train_times = set(unique_times[:train_end])
        test_times = set(unique_times[train_end:test_end])
        train_ids = {
            mid for mid, ts in match_times.items()
            if ts in train_times
        }
        test_ids = {
            mid for mid, ts in match_times.items()
            if ts in test_times
        }
        train = [row for row in rows if str(row["match_id"]) in train_ids]
        test = [row for row in rows if str(row["match_id"]) in test_ids]
        result.append(
            (
                train,
                test,
                {
                    "fold": fold_index + 1,
                    "train_matches": len(train_ids),
                    "test_matches": len(test_ids),
                    "test_start": (
                        unique_times[train_end].isoformat()
                        if train_end < n
                        else None
                    ),
                    "test_end_exclusive": (
                        unique_times[test_end].isoformat()
                        if test_end < n
                        else None
                    ),
                    "same_timestamp_split": False,
                    "test_window_disjoint": True,
                },
            )
        )
    return result


def _walk_forward(
    task: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    folds = []
    for train, test, meta in _walk_forward_slices(rows):
        result = _evaluate_train_test(task, train, test)
        folds.append({
            **meta,
            **result,
        })

    completed = [row for row in folds if row.get("status") == "EVALUATED"]
    positive = [
        row
        for row in completed
        if row.get("positive_all_proper_scores") is True
    ]

    def mean_gain(key: str) -> float | None:
        values = [
            float(row["gains_vs_context_prior"][key])
            for row in completed
        ]
        return round(sum(values) / len(values), 6) if values else None

    return {
        "mode": "EXPANDING_TRAIN_DISJOINT_TEST_WINDOWS",
        "folds": folds,
        "completed_folds": len(completed),
        "positive_folds": len(positive),
        "robust_positive_all_three_folds": bool(
            len(completed) == 3 and len(positive) == 3
        ),
        "mean_gains_vs_context_prior": {
            "brier_gain": mean_gain("brier_gain"),
            "match_equal_brier_gain": mean_gain("match_equal_brier_gain"),
            "log_loss_gain": mean_gain("log_loss_gain"),
        },
        "same_timestamp_groups_not_split": True,
        "test_windows_disjoint": True,
    }


def evaluate_task(
    task: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if task not in TASK_MINIMUMS:
        raise ValueError(f"unknown task: {task}")

    train, holdout, split = _split_chronological_by_match(
        rows,
        OUTER_TRAIN_FRACTION,
    )
    holdout_result = _evaluate_train_test(task, train, holdout)
    walk_forward = _walk_forward(task, rows)
    holdout_positive = bool(
        holdout_result.get("positive_all_proper_scores") is True
    )
    robust = bool(
        walk_forward.get("robust_positive_all_three_folds") is True
    )

    if holdout_result.get("status") != "EVALUATED":
        status = "INSUFFICIENT_HISTORICAL_SAMPLE"
    elif holdout_positive and robust:
        status = "ROBUST_HISTORICAL_SIGNAL_REQUIRES_INCREMENTAL_SCORER_TEST"
    else:
        status = "NOT_ROBUST_ENOUGH"

    return {
        "task": task,
        "rows": len(rows),
        "matches": len({str(row["match_id"]) for row in rows}),
        "support": _support_summary(rows),
        "outer_split": split,
        "holdout": holdout_result,
        "walk_forward": walk_forward,
        "signal": {
            "status": status,
            "positive_holdout": holdout_positive,
            "robust_walk_forward": robust,
            "incremental_over_current_scorer_tested": False,
            "fresh_confirmation_tested": False,
            "feature_activation_authorized": False,
        },
    }


def evaluate(
    rows_by_task: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    tasks = {
        task: evaluate_task(task, list(rows_by_task.get(task) or []))
        for task in ("comeback_bo3", "bo5_late_set")
    }

    return {
        "version": VERSION,
        "mode": MODE,
        "phase": "PHASE_3_MATCH_STATE_PROFILE_SIGNAL_GATE",
        "strength_grid": list(STRENGTH_GRID),
        "outer_train_fraction": OUTER_TRAIN_FRACTION,
        "inner_train_fraction": INNER_TRAIN_FRACTION,
        "walk_forward_fractions": list(WALK_FORWARD_FRACTIONS),
        "task_minimums": TASK_MINIMUMS,
        "tasks": tasks,
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "training_join_enabled": False,
        "canonical_profile_write_enabled": False,
        "canonical_point_scorer_feature_activation_enabled": False,
        "simulator_callback_activation_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "promotion_gate": False,
        "contract": {
            "canonical_strict_as_of_match_state_profiles_only": True,
            "stable_provider_player_ids_only": True,
            "no_name_or_fuzzy_join": True,
            "bo3_comeback_is_primary_comeback_task": True,
            "bo5_excluded_from_comeback_task_to_avoid_format_duration_confound": True,
            "bo5_late_set_means_set_three_and_later": True,
            "player_profile_family_is_overall_prior_only": True,
            "same_surface_player_profile_excluded_from_primary_challenger": True,
            "surface_is_context_prior_only": True,
            "context_prior_fit_from_train_labels_only": True,
            "fixed_half_half_player_blend": True,
            "only_pseudo_count_strength_is_selected": True,
            "strength_grid_predeclared": True,
            "strength_selected_inside_outer_train_only": True,
            "outer_holdout_never_used_for_strength_selection": True,
            "same_timestamp_matches_never_split": True,
            "walk_forward_uses_expanding_train_and_disjoint_test_windows": True,
            "all_three_proper_scores_required_for_positive_fold": True,
            "historical_signal_requires_positive_holdout_and_three_positive_folds": True,
            "incremental_over_current_scorer_not_yet_tested": True,
            "fresh_confirmation_required_before_any_activation": True,
            "bo5_late_set_rate_remains_descriptive_stamina_proxy": True,
        },
        "note": (
            "Historical signal gate only. A robust result permits an incremental "
            "test against the current canonical scorer; it does not authorize "
            "runtime scoring, simulator callbacks, Symfonia or PLAYABLE."
        ),
    }


def build() -> dict[str, Any]:
    profile_rows = list(_iter_jsonl_gz(PROFILE_SNAPSHOTS) or ())
    payloads = list(iter_payloads() or ())
    rows_by_task, build_counts = build_feature_rows(payloads, profile_rows)
    report = evaluate(rows_by_task)
    report["build_counts"] = build_counts

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "version": report["version"],
                "comeback": report["tasks"]["comeback_bo3"]["signal"],
                "bo5_late_set": report["tasks"]["bo5_late_set"]["signal"],
                "build_counts": build_counts,
            },
            ensure_ascii=False,
        )
    )
    return report


if __name__ == "__main__":
    build()
