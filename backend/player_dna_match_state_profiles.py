from __future__ import annotations

"""Leakage-safe SHADOW comeback and BO5 late-set profiles for Player DNA.

This module consumes only exact provider-backed match-state evidence accepted by
player_dna_match_state_readiness. For every target match, a player's snapshot is
built from matches with scheduled_time strictly earlier than the target. Entire
same-time groups are snapshotted before any match in the group enters history.

The profiles are descriptive SHADOW evidence only. In particular, BO5 late-set
outcomes are a candidate stamina proxy, not proof of a causal stamina trait.
"""

import gzip
import json
from collections import Counter, defaultdict
from itertools import groupby
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.player_dna_match_state_readiness import inspect_payload
except ModuleNotFoundError:  # direct execution compatibility
    from player_dna_match_state_readiness import inspect_payload

ROOT = Path(__file__).resolve().parents[1]
PBP_CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT_DIR = ROOT / "data" / "derived" / "player_dna"
OUT_JSONL = OUT_DIR / "match_state_profile_snapshots.jsonl.gz"
OUT_SUMMARY = ROOT / "frontend" / "data" / "player_dna_match_state_profile_summary.json"

VERSION = "player-dna-match-state-profiles-v1"
MODE = "SHADOW_MATCH_STATE_AS_OF_PROFILE"
THRESHOLDS = (1, 3, 5, 10)

COUNT_KEYS = (
    "matches",
    "first_set_loss_exposures",
    "comeback_wins_after_first_set_loss",
    "first_set_win_exposures",
    "match_wins_after_first_set_win",
    "bo5_matches",
    "bo5_late_set_exposures",
    "bo5_late_set_wins",
    "bo5_deciding_set_exposures",
    "bo5_deciding_set_wins",
)


def _empty_stats() -> dict[str, int]:
    return {key: 0 for key in COUNT_KEYS}


def _rate(wins: int, exposures: int) -> float | None:
    return round(wins / exposures, 6) if exposures > 0 else None


def _project(stats: dict[str, int] | None) -> dict[str, Any]:
    stats = stats or _empty_stats()

    def count(key: str) -> int:
        return int(stats.get(key) or 0)

    return {
        "matches": count("matches"),
        "first_set_loss_exposures": count("first_set_loss_exposures"),
        "comeback_wins_after_first_set_loss": count(
            "comeback_wins_after_first_set_loss"
        ),
        "comeback_rate_after_first_set_loss": _rate(
            count("comeback_wins_after_first_set_loss"),
            count("first_set_loss_exposures"),
        ),
        "first_set_win_exposures": count("first_set_win_exposures"),
        "match_wins_after_first_set_win": count("match_wins_after_first_set_win"),
        "front_runner_conversion_rate": _rate(
            count("match_wins_after_first_set_win"),
            count("first_set_win_exposures"),
        ),
        "bo5_matches": count("bo5_matches"),
        "bo5_late_set_exposures": count("bo5_late_set_exposures"),
        "bo5_late_set_wins": count("bo5_late_set_wins"),
        "bo5_late_set_win_rate": _rate(
            count("bo5_late_set_wins"),
            count("bo5_late_set_exposures"),
        ),
        "bo5_deciding_set_exposures": count("bo5_deciding_set_exposures"),
        "bo5_deciding_set_wins": count("bo5_deciding_set_wins"),
        "bo5_deciding_set_win_rate": _rate(
            count("bo5_deciding_set_wins"),
            count("bo5_deciding_set_exposures"),
        ),
    }


def _accumulate(target: dict[str, int], contribution: dict[str, int]) -> None:
    for key in COUNT_KEYS:
        target[key] += int(contribution.get(key) or 0)


def _contributions(item: dict[str, Any]) -> dict[int, dict[str, int]]:
    pids = {
        1: int(item["p1_id"]),
        2: int(item["p2_id"]),
    }
    sequence = [int(side) for side in item["set_winner_sequence"]]
    match_winner = int(item["match_winner_side"])
    first_winner = int(item["first_set_winner_side"])
    first_loser = int(item["first_set_loser_side"])
    best_of = int(item["best_of"])

    out = {
        pids[1]: _empty_stats(),
        pids[2]: _empty_stats(),
    }
    for pid in out:
        out[pid]["matches"] = 1

    loser_pid = pids[first_loser]
    out[loser_pid]["first_set_loss_exposures"] = 1
    out[loser_pid]["comeback_wins_after_first_set_loss"] = int(
        match_winner == first_loser
    )

    winner_pid = pids[first_winner]
    out[winner_pid]["first_set_win_exposures"] = 1
    out[winner_pid]["match_wins_after_first_set_win"] = int(
        match_winner == first_winner
    )

    if best_of == 5:
        for pid in out:
            out[pid]["bo5_matches"] = 1

        for winner_side in sequence[2:]:
            for pid in out:
                out[pid]["bo5_late_set_exposures"] += 1
            out[pids[winner_side]]["bo5_late_set_wins"] += 1

        if len(sequence) == 5:
            for pid in out:
                out[pid]["bo5_deciding_set_exposures"] += 1
            out[pids[sequence[4]]]["bo5_deciding_set_wins"] += 1

    return out


def _source_match(payload: dict[str, Any]) -> dict[str, Any] | None:
    item = inspect_payload(payload)
    if item.get("exact_set_winner_sequence") is not True:
        return None

    match_id = str(item.get("match_id") or "").strip()
    scheduled = item.get("scheduled")
    if not match_id or not isinstance(scheduled, str) or not scheduled:
        return None

    # inspect_payload already established stable IDs, provider terminality, legal
    # format, provider winner agreement and exact atomic set-order proof.
    return {
        "match_id": match_id,
        "scheduled": scheduled,
        "surface": str(item.get("surface") or "unknown"),
        "best_of": int(item["best_of"]),
        "p1": int(item["p1_id"]),
        "p2": int(item["p2_id"]),
        "contrib": _contributions(item),
    }


def iter_payloads(cache_dir: Path = PBP_CACHE) -> Iterable[dict[str, Any]]:
    if not cache_dir.exists():
        return
    for path in sorted(cache_dir.glob("*.json.gz")):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            yield payload


def _prepare_matches(
    payloads: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    counters = Counter()
    by_id: dict[str, dict[str, Any]] = {}

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        counters["payloads_seen"] += 1
        match = _source_match(payload)
        if match is None:
            counters["payloads_rejected_by_exact_match_state_gate"] += 1
            continue

        match_id = match["match_id"]
        previous = by_id.get(match_id)
        if previous is None:
            by_id[match_id] = match
            counters["exact_source_matches"] += 1
            continue

        # Duplicate provider IDs are never double-counted. If their identity/time
        # differs, fail closed by removing the match from the usable source set.
        same = (
            previous["scheduled"] == match["scheduled"]
            and previous["surface"] == match["surface"]
            and previous["best_of"] == match["best_of"]
            and previous["p1"] == match["p1"]
            and previous["p2"] == match["p2"]
            and previous["contrib"] == match["contrib"]
        )
        if same:
            counters["exact_duplicate_payloads_skipped"] += 1
        else:
            counters["conflicting_duplicate_match_ids"] += 1
            by_id.pop(match_id, None)

    matches = list(by_id.values())
    matches.sort(key=lambda row: (row["scheduled"], row["match_id"]))
    counters["usable_exact_source_matches"] = len(matches)
    return matches, dict(counters)


def _readiness(
    snapshots: list[dict[str, Any]],
    prior_key: str,
    support_key: str,
) -> dict[str, dict[str, float | int]]:
    total = len(snapshots)
    return {
        str(threshold): {
            "targets": sum(
                1
                for row in snapshots
                if int((row.get(prior_key) or {}).get(support_key) or 0) >= threshold
            ),
            "rate": (
                round(
                    sum(
                        1
                        for row in snapshots
                        if int((row.get(prior_key) or {}).get(support_key) or 0)
                        >= threshold
                    )
                    / total,
                    6,
                )
                if total
                else 0.0
            ),
        }
        for threshold in THRESHOLDS
    }


def build_snapshots_from_payloads(
    payloads: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    matches, source_counts = _prepare_matches(payloads)

    overall: dict[int, dict[str, int]] = defaultdict(_empty_stats)
    by_surface: dict[int, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(_empty_stats)
    )
    snapshots: list[dict[str, Any]] = []
    same_time_groups = 0

    for scheduled, group_iter in groupby(matches, key=lambda row: row["scheduled"]):
        group = list(group_iter)
        if len(group) > 1:
            same_time_groups += 1

        # Strict-as-of: every match at the same provider timestamp sees the same
        # history, before any member of the group is accumulated.
        for match in group:
            for side, pid, opponent in (
                ("p1", match["p1"], match["p2"]),
                ("p2", match["p2"], match["p1"]),
            ):
                snapshots.append(
                    {
                        "version": VERSION,
                        "mode": MODE,
                        "strict_as_of": True,
                        "same_time_matches_count_as_prior": False,
                        "production_influence": False,
                        "runtime_scoring_enabled": False,
                        "training_join_enabled": False,
                        "simulator_callback_activation_enabled": False,
                        "symphony2_influence": False,
                        "superbet_playable_influence": False,
                        "target_match_id": match["match_id"],
                        "target_scheduled_time": scheduled,
                        "target_surface": match["surface"],
                        "target_format": f"BO{match['best_of']}",
                        "player_side": side,
                        "player_id": pid,
                        "opponent_id": opponent,
                        "overall_prior": _project(overall.get(pid)),
                        "same_surface_prior": _project(
                            by_surface.get(pid, {}).get(match["surface"])
                        ),
                    }
                )

        for match in group:
            for pid in (match["p1"], match["p2"]):
                contribution = match["contrib"][pid]
                _accumulate(overall[pid], contribution)
                _accumulate(by_surface[pid][match["surface"]], contribution)

    players = {int(row["player_id"]) for row in snapshots}
    summary = {
        "version": VERSION,
        "mode": MODE,
        "source": "provider-terminal exact PBP set-order evidence",
        "network_calls": 0,
        "strict_as_of_policy": (
            "source_match_scheduled_time < target_match_scheduled_time"
        ),
        "same_time_matches_count_as_prior": False,
        "player_match_snapshots": len(snapshots),
        "players": len(players),
        "same_time_groups": same_time_groups,
        "source_counts": source_counts,
        "readiness": {
            "comeback_overall": _readiness(
                snapshots,
                "overall_prior",
                "first_set_loss_exposures",
            ),
            "comeback_same_surface": _readiness(
                snapshots,
                "same_surface_prior",
                "first_set_loss_exposures",
            ),
            "bo5_late_set_overall": _readiness(
                snapshots,
                "overall_prior",
                "bo5_late_set_exposures",
            ),
            "bo5_late_set_same_surface": _readiness(
                snapshots,
                "same_surface_prior",
                "bo5_late_set_exposures",
            ),
            "bo5_deciding_set_overall": _readiness(
                snapshots,
                "overall_prior",
                "bo5_deciding_set_exposures",
            ),
        },
        "features": {
            "overall_prior": list(_project(None).keys()),
            "same_surface_prior": list(_project(None).keys()),
            "raw_support_counts_accompany_every_rate": True,
        },
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "training_join_enabled": False,
        "canonical_point_scorer_feature_activation_enabled": False,
        "simulator_callback_activation_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "contract": {
            "provider_terminal_exact_set_order_source_only": True,
            "stable_provider_ids_only": True,
            "historical_csv_id_namespace_not_used": True,
            "name_or_fuzzy_join_forbidden": True,
            "strictly_prior_matches_only": True,
            "same_timestamp_matches_never_count_as_prior": True,
            "raw_support_counts_accompany_every_rate": True,
            "comeback_is_observed_match_win_after_first_set_loss": True,
            "front_runner_conversion_is_observed_match_win_after_first_set_win": True,
            "bo5_late_sets_start_at_set_three": True,
            "bo5_deciding_set_means_set_five_only": True,
            "bo5_late_set_rate_is_descriptive_proxy_not_validated_stamina": True,
            "no_shrinkage_or_partial_pooling_applied": True,
            "no_profile_threshold_activation": True,
            "predictive_signal_not_yet_proven": True,
            "chronological_challenger_required_before_feature_activation": True,
        },
        "note": (
            "SHADOW profile build only. These exact raw rates are not scorer or "
            "simulator features until a separate chronological challenger proves "
            "predictive value and small-sample handling."
        ),
    }
    return snapshots, summary


def build() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshots, summary = build_snapshots_from_payloads(iter_payloads())

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT_JSONL, "wt", encoding="utf-8") as handle:
        for row in snapshots:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")

    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "version": summary["version"],
                "snapshots": summary["player_match_snapshots"],
                "players": summary["players"],
                "exact_source_matches": (
                    summary["source_counts"].get("usable_exact_source_matches")
                ),
                "comeback_overall_at3": (
                    summary["readiness"]["comeback_overall"]["3"]
                ),
                "bo5_late_overall_at3": (
                    summary["readiness"]["bo5_late_set_overall"]["3"]
                ),
            },
            ensure_ascii=False,
        )
    )
    return snapshots, summary


if __name__ == "__main__":
    build()
