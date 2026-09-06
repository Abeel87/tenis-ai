from __future__ import annotations

"""Leakage-safe opponent-strength challenger for Player DNA.

This is an evaluation-only Phase-2 challenger. It measures the quality of a
player's *historical opponents* from the opponents' own strictly-prior Player
DNA snapshots, then tests whether that context improves the canonical point
scorer on the same chronological holdout / walk-forward methodology.

No adjusted feature is written back to canonical profiles and nothing here can
affect runtime, Symfonia 2.0, or Superbet PLAYABLE.
"""

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
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
        _proper_score_gains,
        _walk_forward_slices,
        build_feature_rows,
        split_chronological_by_match,
    )
except ModuleNotFoundError:  # direct execution
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
        _proper_score_gains,
        _walk_forward_slices,
        build_feature_rows,
        split_chronological_by_match,
    )

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data" / "player_dna_opponent_adjustment_audit.json"
VERSION = "player-dna-opponent-adjustment-audit-v1"
MODE = "SHADOW_CHALLENGER_EVAL_ONLY"
L5 = 5

OPPONENT_STRENGTH_NUMERIC = [
    "server_history_opponent_return_mean",
    "server_history_opponent_return_l5",
    "server_history_opponent_return_surface_mean",
    "server_history_opponent_return_surface_l5",
    "receiver_history_opponent_serve_mean",
    "receiver_history_opponent_serve_l5",
    "receiver_history_opponent_serve_surface_mean",
    "receiver_history_opponent_serve_surface_l5",
]
OPPONENT_SUPPORT_NUMERIC = [
    "server_history_opponent_overall_support",
    "server_history_opponent_surface_support",
    "receiver_history_opponent_overall_support",
    "receiver_history_opponent_surface_support",
]
OPPONENT_NUMERIC = OPPONENT_STRENGTH_NUMERIC + OPPONENT_SUPPORT_NUMERIC


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


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _rate(profile: Any, key: str) -> float | None:
    if not isinstance(profile, dict) or int(profile.get("matches") or 0) <= 0:
        return None
    value = _finite(profile.get(key))
    if value is None or value < 0.0 or value > 1.0:
        return None
    return value


def _mean(values: Iterable[float | None]) -> float | None:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return round(sum(clean) / len(clean), 6) if clean else None


def _last_mean(values: Iterable[float | None], limit: int = L5) -> float | None:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return round(sum(clean[-limit:]) / len(clean[-limit:]), 6) if clean else None


def _profile_rows(profile_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for raw in profile_rows:
        if not isinstance(raw, dict):
            continue
        if raw.get("strict_as_of") is not True:
            continue
        if raw.get("same_time_matches_count_as_prior") is not False:
            continue
        match_id = str(raw.get("target_match_id") or "").strip()
        player = _positive_int(raw.get("player_id"))
        opponent = _positive_int(raw.get("opponent_id"))
        scheduled = _parse_utc(raw.get("target_scheduled_time"))
        if (
            not match_id
            or player is None
            or opponent is None
            or player == opponent
            or scheduled is None
        ):
            continue
        row = dict(raw)
        row["_match_id"] = match_id
        row["_player"] = player
        row["_opponent"] = opponent
        row["_scheduled"] = scheduled
        row["_surface"] = str(raw.get("target_surface") or "unknown").strip().lower()
        rows.append(row)
    rows.sort(key=lambda r: (r["_scheduled"], r["_match_id"], r["_player"]))
    return rows


def _pair_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[datetime, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["_scheduled"], row["_match_id"])].append(row)

    matches = []
    for (scheduled, match_id), group in grouped.items():
        if len(group) != 2:
            continue
        first, second = sorted(group, key=lambda row: row["_player"])
        if (
            first["_player"] != second["_opponent"]
            or second["_player"] != first["_opponent"]
            or first["_surface"] != second["_surface"]
        ):
            continue
        matches.append(
            {
                "scheduled": scheduled,
                "match_id": match_id,
                "surface": first["_surface"],
                "rows": {
                    first["_player"]: first,
                    second["_player"]: second,
                },
            }
        )
    matches.sort(key=lambda row: (row["scheduled"], row["match_id"]))
    return matches


def _context(history: list[dict[str, Any]], surface: str) -> dict[str, Any]:
    # Support means usable opponent-strength evidence, not merely prior matches.
    # Require the opponent's own pre-match serve AND return profile together so
    # the candidate cannot gain signal from a disguised "matches played" proxy.
    overall_ready = [
        row
        for row in history
        if row.get("opponent_return") is not None
        and row.get("opponent_serve") is not None
    ]
    surface_ready = [
        row
        for row in history
        if row["surface"] == surface
        and row.get("opponent_surface_return") is not None
        and row.get("opponent_surface_serve") is not None
    ]
    return {
        "opponent_return_mean": _mean(
            row["opponent_return"] for row in overall_ready
        ),
        "opponent_return_l5": _last_mean(
            row["opponent_return"] for row in overall_ready
        ),
        "opponent_serve_mean": _mean(
            row["opponent_serve"] for row in overall_ready
        ),
        "opponent_serve_l5": _last_mean(
            row["opponent_serve"] for row in overall_ready
        ),
        "opponent_return_surface_mean": _mean(
            row["opponent_surface_return"] for row in surface_ready
        ),
        "opponent_return_surface_l5": _last_mean(
            row["opponent_surface_return"] for row in surface_ready
        ),
        "opponent_serve_surface_mean": _mean(
            row["opponent_surface_serve"] for row in surface_ready
        ),
        "opponent_serve_surface_l5": _last_mean(
            row["opponent_surface_serve"] for row in surface_ready
        ),
        "overall_support": len(overall_ready),
        "surface_support": len(surface_ready),
        "overall_history_matches": len(history),
        "surface_history_matches": sum(
            1 for row in history if row["surface"] == surface
        ),
    }


def build_opponent_context_index(
    profile_rows: Iterable[dict[str, Any]],
) -> tuple[dict[tuple[str, int], dict[str, Any]], dict[str, int]]:
    """Build as-of historical-opponent context without same-time leakage."""

    matches = _pair_groups(_profile_rows(profile_rows))
    history: dict[int, list[dict[str, Any]]] = defaultdict(list)
    index: dict[tuple[str, int], dict[str, Any]] = {}
    counts = defaultdict(int)

    by_time: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
    for match in matches:
        by_time[match["scheduled"]].append(match)

    for scheduled in sorted(by_time):
        same_time = sorted(by_time[scheduled], key=lambda row: row["match_id"])

        # Freeze every target context before any match at this timestamp is added.
        for match in same_time:
            for player in sorted(match["rows"]):
                index[(match["match_id"], player)] = {
                    **_context(history[player], match["surface"]),
                    "strict_as_of": True,
                    "same_time_matches_count_as_prior": False,
                }
                counts["target_player_contexts"] += 1

        for match in same_time:
            players = sorted(match["rows"])
            if len(players) != 2:
                continue
            p1, p2 = players
            for player, opponent in ((p1, p2), (p2, p1)):
                opponent_row = match["rows"][opponent]
                overall = (
                    opponent_row.get("overall_prior")
                    if isinstance(opponent_row.get("overall_prior"), dict)
                    else {}
                )
                same_surface = (
                    opponent_row.get("same_surface_prior")
                    if isinstance(opponent_row.get("same_surface_prior"), dict)
                    else {}
                )
                history[player].append(
                    {
                        "match_id": match["match_id"],
                        "scheduled": match["scheduled"],
                        "surface": match["surface"],
                        "opponent_id": opponent,
                        "opponent_return": _rate(overall, "return_win_rate"),
                        "opponent_serve": _rate(overall, "serve_win_rate"),
                        "opponent_surface_return": _rate(
                            same_surface, "return_win_rate"
                        ),
                        "opponent_surface_serve": _rate(
                            same_surface, "serve_win_rate"
                        ),
                    }
                )
                counts["historical_opponent_entries"] += 1

    counts["paired_matches"] = len(matches)
    counts["players_with_history"] = sum(1 for values in history.values() if values)
    return index, dict(counts)


def _point_identity_index(
    point_rows: Iterable[dict[str, Any]],
) -> dict[tuple[str, int], tuple[int, int]]:
    out = {}
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


def enrich_feature_rows(
    point_rows: list[dict[str, Any]],
    profile_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_rows, join_counts = build_feature_rows(point_rows, profile_rows)
    contexts, context_counts = build_opponent_context_index(profile_rows)
    identities = _point_identity_index(point_rows)

    enriched = []
    counts = defaultdict(int)
    for row in base_rows:
        key = (str(row.get("match_id") or ""), row.get("event_index"))
        identity = identities.get(key)
        if identity is None:
            counts["missing_point_identity"] += 1
            continue
        server_id, receiver_id = identity
        server = contexts.get((key[0], server_id), {})
        receiver = contexts.get((key[0], receiver_id), {})

        enriched.append(
            {
                **row,
                "server_history_opponent_return_mean": server.get(
                    "opponent_return_mean"
                ),
                "server_history_opponent_return_l5": server.get(
                    "opponent_return_l5"
                ),
                "server_history_opponent_return_surface_mean": server.get(
                    "opponent_return_surface_mean"
                ),
                "server_history_opponent_return_surface_l5": server.get(
                    "opponent_return_surface_l5"
                ),
                "receiver_history_opponent_serve_mean": receiver.get(
                    "opponent_serve_mean"
                ),
                "receiver_history_opponent_serve_l5": receiver.get(
                    "opponent_serve_l5"
                ),
                "receiver_history_opponent_serve_surface_mean": receiver.get(
                    "opponent_serve_surface_mean"
                ),
                "receiver_history_opponent_serve_surface_l5": receiver.get(
                    "opponent_serve_surface_l5"
                ),
                "server_history_opponent_overall_support": int(
                    server.get("overall_support") or 0
                ),
                "server_history_opponent_surface_support": int(
                    server.get("surface_support") or 0
                ),
                "receiver_history_opponent_overall_support": int(
                    receiver.get("overall_support") or 0
                ),
                "receiver_history_opponent_surface_support": int(
                    receiver.get("surface_support") or 0
                ),
            }
        )
        counts["enriched_rows"] += 1
        counts["rows_with_both_overall_context"] += int(
            int(server.get("overall_support") or 0) > 0
            and int(receiver.get("overall_support") or 0) > 0
        )
        counts["rows_with_both_surface_context"] += int(
            int(server.get("surface_support") or 0) > 0
            and int(receiver.get("surface_support") or 0) > 0
        )

    return enriched, {
        "base_join_counts": join_counts,
        "context_counts": context_counts,
        "enrichment_counts": dict(counts),
    }


def _positive_gains(gains: dict[str, float]) -> bool:
    return bool(
        gains["brier_gain"] > 0
        and gains["match_equal_brier_gain"] > 0
        and gains["log_loss_gain"] > 0
    )


def _evaluate_frames(train, test) -> dict[str, Any]:
    base_numeric = list(PROFILE_NUMERIC) + list(RANK_NUMERIC)
    lean_numeric = base_numeric + list(LEAN_STATE_NUMERIC)
    strength_numeric = base_numeric + list(OPPONENT_STRENGTH_NUMERIC)
    lean_strength_numeric = lean_numeric + list(OPPONENT_STRENGTH_NUMERIC)
    full_context_numeric = base_numeric + list(OPPONENT_NUMERIC)
    lean_full_context_numeric = lean_numeric + list(OPPONENT_NUMERIC)

    base, _ = _fit_candidate(train, test, base_numeric)
    strength, _ = _fit_candidate(train, test, strength_numeric)
    full_context, _ = _fit_candidate(train, test, full_context_numeric)
    lean, _ = _fit_candidate(train, test, lean_numeric)
    lean_strength, _ = _fit_candidate(train, test, lean_strength_numeric)
    lean_full_context, _ = _fit_candidate(
        train, test, lean_full_context_numeric
    )

    strength_gains_vs_base = _proper_score_gains(
        base["metrics"], strength["metrics"]
    )
    strength_gains_vs_lean = _proper_score_gains(
        lean["metrics"], lean_strength["metrics"]
    )
    full_gains_vs_base = _proper_score_gains(
        base["metrics"], full_context["metrics"]
    )
    full_gains_vs_lean = _proper_score_gains(
        lean["metrics"], lean_full_context["metrics"]
    )
    support_gains_beyond_strength = _proper_score_gains(
        lean_strength["metrics"], lean_full_context["metrics"]
    )
    return {
        "profile_plus_rank": base,
        "profile_rank_plus_opponent_strength": strength,
        "profile_rank_plus_opponent_strength_and_support": full_context,
        "lean_stateful": lean,
        "lean_stateful_plus_opponent_strength": lean_strength,
        "lean_stateful_plus_opponent_strength_and_support": lean_full_context,
        "opponent_strength_gains_vs_profile_plus_rank": strength_gains_vs_base,
        "opponent_strength_gains_vs_lean_stateful": strength_gains_vs_lean,
        "full_context_gains_vs_profile_plus_rank": full_gains_vs_base,
        "full_context_gains_vs_lean_stateful": full_gains_vs_lean,
        "support_gains_beyond_strength": support_gains_beyond_strength,
        "positive_strength_vs_profile_plus_rank": _positive_gains(
            strength_gains_vs_base
        ),
        "positive_strength_vs_lean_stateful": _positive_gains(
            strength_gains_vs_lean
        ),
        "support_improves_all_primary_scores_beyond_strength": _positive_gains(
            support_gains_beyond_strength
        ),
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
            folds.append(
                {
                    **meta,
                    "status": "INSUFFICIENT_FOLD_SAMPLE",
                    "train_points": int(len(train)),
                    "test_points": int(len(test)),
                }
            )
            continue

        result = _evaluate_frames(train, test)
        folds.append(
            {
                **meta,
                "status": (
                    "POSITIVE_OPPONENT_CONTEXT_FOLD"
                    if result["positive_strength_vs_lean_stateful"]
                    else "MIXED_OR_NEGATIVE_OPPONENT_CONTEXT_FOLD"
                ),
                "train_points": int(len(train)),
                "test_points": int(len(test)),
                **result,
            }
        )

    completed = [
        row
        for row in folds
        if "opponent_strength_gains_vs_lean_stateful" in row
    ]
    positive = [
        row
        for row in completed
        if row.get("positive_strength_vs_lean_stateful") is True
    ]

    def mean_gain(key: str, metric: str) -> float | None:
        values = [float(row[key][metric]) for row in completed]
        return round(sum(values) / len(values), 6) if values else None

    return {
        "mode": "SAME_EXPANDING_TRAIN_DISJOINT_WINDOWS_AS_CANONICAL_SCORER",
        "folds": folds,
        "completed_folds": len(completed),
        "positive_folds_vs_lean_stateful": len(positive),
        "robust_positive_vs_lean_stateful": bool(
            len(completed) == 3 and len(positive) == 3
        ),
        "mean_gains_vs_lean_stateful": {
            "brier_gain": mean_gain(
                "opponent_strength_gains_vs_lean_stateful", "brier_gain"
            ),
            "match_equal_brier_gain": mean_gain(
                "opponent_strength_gains_vs_lean_stateful",
                "match_equal_brier_gain",
            ),
            "log_loss_gain": mean_gain(
                "opponent_strength_gains_vs_lean_stateful", "log_loss_gain"
            ),
        },
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
        "opponent_strength_numeric_features": list(OPPONENT_STRENGTH_NUMERIC),
        "opponent_support_numeric_features": list(OPPONENT_SUPPORT_NUMERIC),
        "opponent_numeric_features": list(OPPONENT_NUMERIC),
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "training_join_enabled": False,
        "canonical_profile_write_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "promotion_gate": False,
        "opponent_support_contract": {
            "support_counts_only_bidirectional_pre_match_serve_return_profiles": True,
            "raw_prior_match_count_is_not_an_opponent_strength_feature": True,
            "support_features_are_separate_uncertainty_diagnostic": True,
            "primary_success_gate_uses_strength_rates_without_support_features": True,
            "no_modeling_support_threshold_activated": True,
        },
        "source_limitations": {
            "reliable_first_serve_in_available": False,
            "reliable_first_second_serve_split_available": False,
            "reliable_ace_double_fault_fields_available": False,
            "candidate_uses_only_observed_server_receiver_point_results_and_prior_profiles": True,
        },
        "leakage_contract": {
            "historical_opponent_strength_is_from_opponents_own_pre_match_snapshot": True,
            "target_match_not_added_to_its_own_history": True,
            "same_timestamp_matches_never_count_as_prior": True,
            "stable_provider_player_ids_only": True,
            "future_match_results_not_used": True,
        },
        "signal": {
            "status": "NOT_EVALUATED",
            "positive_vs_profile_plus_rank": False,
            "positive_vs_lean_stateful": False,
        },
    }

    if not enough:
        report["signal"]["status"] = "INSUFFICIENT_SHADOW_SAMPLE"
        return report

    holdout_result = _evaluate_frames(train, holdout)
    walk_forward = _walk_forward(rows)
    robust = bool(walk_forward["robust_positive_vs_lean_stateful"])
    holdout_positive = bool(holdout_result["positive_strength_vs_lean_stateful"])

    report["holdout"] = holdout_result
    report["walk_forward"] = walk_forward
    report["signal"] = {
        "status": (
            "OPPONENT_CONTEXT_ROBUST_POSITIVE_SHADOW_SIGNAL"
            if holdout_positive and robust
            else "OPPONENT_CONTEXT_NOT_ROBUST_ENOUGH"
        ),
        "positive_vs_profile_plus_rank": bool(
            holdout_result["positive_strength_vs_profile_plus_rank"]
        ),
        "positive_vs_lean_stateful": holdout_positive,
        "robust_positive_vs_lean_stateful": robust,
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
