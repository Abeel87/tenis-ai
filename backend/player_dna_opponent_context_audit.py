from __future__ import annotations

"""Audit whether leakage-safe Player DNA history can support opponent adjustment.

This module is deliberately audit-only. It consumes the canonical as-of profile
snapshots and measures:
- whether historical opponents had their own strictly-prior serve+return profile,
- how much such opponent-strength context exists at the already-used readiness
  thresholds,
- how often two players share prior opponents overall and on the target surface.

It never changes a profile, model probability, simulator, Symfonia 2.0, or
Superbet PLAYABLE decision.
"""

import gzip
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.player_dna_shadow_profiles import OUT_JSONL as PROFILES
    from backend.player_dna_shadow_profiles import THRESHOLDS
except ModuleNotFoundError:  # direct execution
    from player_dna_shadow_profiles import OUT_JSONL as PROFILES
    from player_dna_shadow_profiles import THRESHOLDS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data" / "player_dna_opponent_context_audit.json"
VERSION = "player-dna-opponent-context-audit-v1"
GATE = "AUDIT_ONLY_NO_OPPONENT_ADJUSTMENT"


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


def iter_profile_rows(path: Path = PROFILES) -> Iterable[dict[str, Any]]:
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


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _profile_ready(profile: Any, threshold: int) -> bool:
    if not isinstance(profile, dict):
        return False
    matches = int(profile.get("matches") or 0)
    serve_points = int(profile.get("serve_points") or 0)
    return_points = int(profile.get("return_points") or 0)
    serve_rate = profile.get("serve_win_rate")
    return_rate = profile.get("return_win_rate")
    return bool(
        matches >= threshold
        and serve_points > 0
        and return_points > 0
        and isinstance(serve_rate, (int, float))
        and not isinstance(serve_rate, bool)
        and isinstance(return_rate, (int, float))
        and not isinstance(return_rate, bool)
    )


def _valid_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter]:
    counters = Counter()
    valid = []
    for raw in rows:
        counters["rows_seen"] += 1
        if not isinstance(raw, dict):
            counters["non_dict"] += 1
            continue
        if raw.get("mode") != "SHADOW_AS_OF_PROFILE":
            counters["wrong_mode"] += 1
            continue
        if raw.get("strict_as_of") is not True:
            counters["non_strict_as_of"] += 1
            continue
        if raw.get("same_time_matches_count_as_prior") is not False:
            counters["same_time_policy_invalid"] += 1
            continue

        match_id = str(raw.get("target_match_id") or "").strip()
        scheduled = _parse_utc(raw.get("target_scheduled_time"))
        player = _positive_int(raw.get("player_id"))
        opponent = _positive_int(raw.get("opponent_id"))
        if not match_id or scheduled is None or player is None or opponent is None or player == opponent:
            counters["invalid_identity_or_time"] += 1
            continue

        row = dict(raw)
        row["_scheduled"] = scheduled
        row["_match_id"] = match_id
        row["_player"] = player
        row["_opponent"] = opponent
        row["_surface"] = str(raw.get("target_surface") or "unknown").strip().lower()
        valid.append(row)
        counters["valid_rows"] += 1

    valid.sort(
        key=lambda row: (
            row["_scheduled"],
            row["_match_id"],
            row["_player"],
        )
    )
    return valid, counters


def _pair_matches(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter]:
    counters = Counter()
    matches = []
    for (scheduled, match_id), group_iter in groupby(
        rows,
        key=lambda row: (row["_scheduled"], row["_match_id"]),
    ):
        group = list(group_iter)
        if len(group) != 2:
            counters["non_pair_groups"] += 1
            continue
        first, second = group
        if (
            first["_player"] != second["_opponent"]
            or second["_player"] != first["_opponent"]
        ):
            counters["non_reciprocal_pairs"] += 1
            continue
        if first["_surface"] != second["_surface"]:
            counters["surface_conflicts"] += 1
            continue
        by_player = {
            first["_player"]: first,
            second["_player"]: second,
        }
        players = tuple(sorted(by_player))
        matches.append(
            {
                "scheduled": scheduled,
                "match_id": match_id,
                "surface": first["_surface"],
                "players": players,
                "rows": by_player,
            }
        )
        counters["paired_matches"] += 1
    matches.sort(key=lambda row: (row["scheduled"], row["match_id"]))
    return matches, counters


def _coverage_block(values: list[int], denominator: int) -> dict[str, Any]:
    values = list(values)
    if not values:
        return {
            "targets": denominator,
            "with_any": 0,
            "rate_with_any": 0.0,
            "max": 0,
            "p50": 0,
            "p75": 0,
            "p90": 0,
        }
    ordered = sorted(values)

    def percentile(q: float) -> int:
        if not ordered:
            return 0
        index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
        return int(ordered[index])

    with_any = sum(1 for value in values if value > 0)
    return {
        "targets": denominator,
        "with_any": with_any,
        "rate_with_any": round(with_any / denominator, 6) if denominator else 0.0,
        "max": max(values),
        "p50": percentile(0.50),
        "p75": percentile(0.75),
        "p90": percentile(0.90),
    }


def audit_profile_snapshots(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    valid, source_counts = _valid_rows(rows)
    matches, pair_counts = _pair_matches(valid)

    opponent_history: dict[int, set[int]] = defaultdict(set)
    opponent_surface_history: dict[int, dict[str, set[int]]] = defaultdict(
        lambda: defaultdict(set)
    )

    ready_history: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    ready_surface_history: dict[int, dict[str, dict[int, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )

    unique_ready_overall = Counter()
    unique_ready_surface = Counter()
    target_ready_overall: dict[int, Counter] = {
        threshold: Counter() for threshold in THRESHOLDS
    }
    target_ready_surface: dict[int, Counter] = {
        threshold: Counter() for threshold in THRESHOLDS
    }

    common_overall_counts: list[int] = []
    common_surface_counts: list[int] = []
    target_player_rows = 0
    provider_rank_rows = 0
    player_match_entries = 0

    for scheduled, time_group_iter in groupby(matches, key=lambda row: row["scheduled"]):
        time_group = list(time_group_iter)

        # Evaluate the entire timestamp before adding any match from it to history.
        for match in time_group:
            p1, p2 = match["players"]
            surface = match["surface"]
            common_overall_counts.append(
                len(opponent_history[p1] & opponent_history[p2])
            )
            common_surface_counts.append(
                len(
                    opponent_surface_history[p1][surface]
                    & opponent_surface_history[p2][surface]
                )
            )

            for player in (p1, p2):
                target_player_rows += 1
                row = match["rows"][player]
                if _positive_int(row.get("opponent_ranking")) is not None:
                    provider_rank_rows += 1

                for support_threshold in THRESHOLDS:
                    overall_count = int(
                        ready_history[player].get(support_threshold, 0)
                    )
                    surface_count = int(
                        ready_surface_history[player][surface].get(
                            support_threshold, 0
                        )
                    )
                    for required_history in THRESHOLDS:
                        if overall_count >= required_history:
                            target_ready_overall[support_threshold][
                                required_history
                            ] += 1
                        if surface_count >= required_history:
                            target_ready_surface[support_threshold][
                                required_history
                            ] += 1

        # Only now can these matches become history for later timestamps.
        for match in time_group:
            p1, p2 = match["players"]
            surface = match["surface"]
            for player, opponent in ((p1, p2), (p2, p1)):
                player_match_entries += 1
                opponent_row = match["rows"][opponent]
                opponent_overall = opponent_row.get("overall_prior") or {}
                opponent_surface = opponent_row.get("same_surface_prior") or {}

                for support_threshold in THRESHOLDS:
                    if _profile_ready(opponent_overall, support_threshold):
                        unique_ready_overall[support_threshold] += 1
                        ready_history[player][support_threshold] += 1
                    if _profile_ready(opponent_surface, support_threshold):
                        unique_ready_surface[support_threshold] += 1
                        ready_surface_history[player][surface][support_threshold] += 1

                opponent_history[player].add(opponent)
                opponent_surface_history[player][surface].add(opponent)

    def support_report(
        unique_ready: Counter,
        target_ready: dict[int, Counter],
    ) -> dict[str, Any]:
        out = {}
        for support_threshold in THRESHOLDS:
            ready_entries = int(unique_ready[support_threshold])
            out[str(support_threshold)] = {
                "opponent_profile_min_prior_matches": int(support_threshold),
                "unique_history_entries_ready": ready_entries,
                "unique_history_entries_total": player_match_entries,
                "unique_history_entry_rate": (
                    round(ready_entries / player_match_entries, 6)
                    if player_match_entries
                    else 0.0
                ),
                "target_player_rows": target_player_rows,
                "target_rows_with_adjustable_history": {
                    str(required): {
                        "required_ready_prior_matches": int(required),
                        "targets": int(target_ready[support_threshold][required]),
                        "rate": (
                            round(
                                int(target_ready[support_threshold][required])
                                / target_player_rows,
                                6,
                            )
                            if target_player_rows
                            else 0.0
                        ),
                    }
                    for required in THRESHOLDS
                },
            }
        return out

    report = {
        "version": VERSION,
        "gate": GATE,
        "mode": "SHADOW_OPPONENT_CONTEXT_AUDIT_ONLY",
        "network_calls": 0,
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "training_join_enabled": False,
        "opponent_adjustment_enabled": False,
        "common_opponent_feature_enabled": False,
        "strict_as_of_required": True,
        "same_time_matches_count_as_prior": False,
        "source_counts": dict(source_counts),
        "pair_counts": dict(pair_counts),
        "paired_matches": len(matches),
        "player_match_entries": player_match_entries,
        "target_player_rows": target_player_rows,
        "provider_opponent_rank_context": {
            "rows_with_positive_provider_rank": provider_rank_rows,
            "rows": target_player_rows,
            "rate": (
                round(provider_rank_rows / target_player_rows, 6)
                if target_player_rows
                else 0.0
            ),
            "rank_is_context_only_not_adjustment": True,
        },
        "common_opponent_coverage": {
            "overall": _coverage_block(common_overall_counts, len(matches)),
            "same_surface": _coverage_block(common_surface_counts, len(matches)),
            "policy": {
                "only_strictly_prior_opponents_count": True,
                "same_timestamp_group_isolated": True,
                "no_fuzzy_identity": True,
                "stable_provider_ids_only": True,
            },
        },
        "opponent_strength_history_support": {
            "overall": support_report(
                unique_ready_overall,
                target_ready_overall,
            ),
            "same_surface": support_report(
                unique_ready_surface,
                target_ready_surface,
            ),
            "policy": {
                "ready_requires_opponent_pre_match_serve_and_return_profile": True,
                "readiness_thresholds_reuse_existing_profile_audit_thresholds": list(
                    THRESHOLDS
                ),
                "no_threshold_activated_for_modeling": True,
                "no_adjusted_feature_computed_yet": True,
                "future_adjustment_must_be_walk_forward_validated": True,
            },
        },
        "next_gate": (
            "Use this measured coverage to design leakage-safe opponent-strength "
            "candidate features, then compare them against the current profile "
            "reference in chronological walk-forward. Do not activate a model "
            "threshold from this audit alone."
        ),
    }
    return report


def build() -> dict[str, Any]:
    report = audit_profile_snapshots(iter_profile_rows() or ())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
