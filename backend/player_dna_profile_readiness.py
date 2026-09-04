from __future__ import annotations

"""Audit real historical depth available to future Player DNA profiles.

The audit consumes the already-built SHADOW point dataset. It never aggregates
or activates a player profile and never trains a model. Historical readiness is
strictly as-of: only matches with scheduled_time < target scheduled_time count.
"""

import gzip
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "data" / "derived" / "player_dna" / "point_events.jsonl.gz"
OUT = ROOT / "frontend" / "data" / "player_dna_profile_readiness.json"
VERSION = "player-dna-profile-readiness-audit-v1"
THRESHOLDS = (1, 3, 5, 10, 20)


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


def iter_point_rows(path: Path = POINTS) -> Iterable[dict[str, Any]]:
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


def _percentile(sorted_values: list[int], fraction: float) -> int | None:
    if not sorted_values:
        return None
    index = min(len(sorted_values) - 1, max(0, int((len(sorted_values) - 1) * fraction)))
    return int(sorted_values[index])


def audit_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    matches: dict[str, dict[str, Any]] = {}
    total_rows = context_ready_rows = 0
    invalid_match_time_rows = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        total_rows += 1
        match_id = str(row.get("match_id") or "").strip()
        scheduled = _parse_utc(row.get("match_scheduled_time"))
        if not match_id or scheduled is None:
            invalid_match_time_rows += 1
            continue

        p1 = row.get("p1_player_id")
        p2 = row.get("p2_player_id")
        if isinstance(p1, bool) or not isinstance(p1, int):
            continue
        if isinstance(p2, bool) or not isinstance(p2, int):
            continue

        if row.get("context_ready_player_point") is True:
            context_ready_rows += 1

        entry = matches.setdefault(match_id, {
            "match_id": match_id,
            "scheduled": scheduled,
            "surface": row.get("surface"),
            "p1": p1,
            "p2": p2,
            "has_context_ready_point": False,
        })
        if entry["scheduled"] != scheduled or entry["p1"] != p1 or entry["p2"] != p2:
            # Conflicting per-match identity/time context must not be silently merged.
            entry["conflict"] = True
        if row.get("context_ready_player_point") is True:
            entry["has_context_ready_point"] = True

    source_matches = [entry for entry in matches.values() if not entry.get("conflict")]
    valid_matches = [
        entry for entry in source_matches
        if entry.get("has_context_ready_point") is True
    ]

    player_matches: dict[int, list[dict[str, Any]]] = defaultdict(list)
    surface_counts: Counter[str] = Counter()
    for match in valid_matches:
        surface = str(match.get("surface") or "unknown")
        surface_counts[surface] += 1
        for pid in (match["p1"], match["p2"]):
            player_matches[int(pid)].append(match)

    per_player_match_depth: list[int] = []
    total_threshold_hits = Counter()
    surface_threshold_hits = Counter()
    same_time_player_groups = 0
    targets = 0

    for pid, history in player_matches.items():
        history.sort(key=lambda m: (m["scheduled"], m["match_id"]))
        time_counts = Counter(m["scheduled"] for m in history)
        same_time_player_groups += sum(1 for count in time_counts.values() if count > 1)

        for target in history:
            targets += 1
            prior = [m for m in history if m["scheduled"] < target["scheduled"]]
            same_surface_prior = [
                m for m in prior
                if str(m.get("surface") or "unknown") == str(target.get("surface") or "unknown")
            ]
            total_depth = len(prior)
            surface_depth = len(same_surface_prior)
            per_player_match_depth.append(total_depth)
            for threshold in THRESHOLDS:
                if total_depth >= threshold:
                    total_threshold_hits[threshold] += 1
                if surface_depth >= threshold:
                    surface_threshold_hits[threshold] += 1

    player_match_counts = sorted(len(history) for history in player_matches.values())
    depth_sorted = sorted(per_player_match_depth)

    def readiness(counter: Counter[int]) -> dict[str, dict[str, Any]]:
        return {
            str(threshold): {
                "targets": int(counter[threshold]),
                "rate": round(counter[threshold] / targets, 6) if targets else 0.0,
            }
            for threshold in THRESHOLDS
        }

    return {
        "version": VERSION,
        "gate": "AUDIT_ONLY_NO_PROFILE_AGGREGATION",
        "network_calls": 0,
        "shadow_only": True,
        "strict_as_of_policy": "prior_match_scheduled_time < target_match_scheduled_time",
        "same_time_matches_count_as_prior": False,
        "training_join_enabled": False,
        "profile_aggregation_enabled": False,
        "readiness_threshold_activation_enabled": False,
        "point_rows": total_rows,
        "context_ready_point_rows": context_ready_rows,
        "invalid_match_time_rows": invalid_match_time_rows,
        "source_matches_seen": len(source_matches),
        "context_ready_matches": len(valid_matches),
        "matches_without_context_ready_points": len(source_matches) - len(valid_matches),
        "players": len(player_matches),
        "player_match_targets": targets,
        "surface_match_counts": dict(surface_counts.most_common()),
        "player_match_depth": {
            "min": player_match_counts[0] if player_match_counts else None,
            "p50": _percentile(player_match_counts, 0.50),
            "p75": _percentile(player_match_counts, 0.75),
            "p90": _percentile(player_match_counts, 0.90),
            "max": player_match_counts[-1] if player_match_counts else None,
            "players_ge_1": sum(v >= 1 for v in player_match_counts),
            "players_ge_3": sum(v >= 3 for v in player_match_counts),
            "players_ge_5": sum(v >= 5 for v in player_match_counts),
            "players_ge_10": sum(v >= 10 for v in player_match_counts),
            "players_ge_20": sum(v >= 20 for v in player_match_counts),
        },
        "prior_history_depth": {
            "p50": _percentile(depth_sorted, 0.50),
            "p75": _percentile(depth_sorted, 0.75),
            "p90": _percentile(depth_sorted, 0.90),
            "max": depth_sorted[-1] if depth_sorted else None,
        },
        "readiness_any_surface": readiness(total_threshold_hits),
        "readiness_same_surface": readiness(surface_threshold_hits),
        "same_time_player_groups": same_time_player_groups,
        "note": (
            "Evidence only. No minimum-history threshold is activated here. "
            "The next gate must choose any threshold from measured coverage and leakage-safe validation."
        ),
    }


def build() -> dict[str, Any]:
    report = audit_rows(iter_point_rows() or ())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": report["version"],
        "source_matches_seen": report["source_matches_seen"],
        "context_ready_matches": report["context_ready_matches"],
        "matches_without_context_ready_points": report["matches_without_context_ready_points"],
        "players": report["players"],
        "targets": report["player_match_targets"],
        "readiness_any_surface": report["readiness_any_surface"],
        "readiness_same_surface": report["readiness_same_surface"],
        "same_time_player_groups": report["same_time_player_groups"],
        "gate": report["gate"],
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
