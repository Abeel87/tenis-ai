from __future__ import annotations

"""Audit which ordering should be authoritative for Player DNA point sequences.

Compares provider sequence=clean tape order against a stable timestamp sort on
real restored PBP cache. This is SHADOW/audit-only: no training join, no profile
aggregation, no PROD/Symfonia 2.0/Superbet PLAYABLE influence.
"""

import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.canonical_point_event import canonical_point_events
except ModuleNotFoundError:  # direct execution
    from canonical_point_event import canonical_point_events

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT = ROOT / "frontend" / "data" / "player_dna_ordering_authority_audit.json"
VERSION = "player-dna-ordering-authority-audit-v1"


def _read(path: Path) -> dict[str, Any] | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def cached_payloads() -> Iterable[tuple[str, dict[str, Any]]]:
    if not CACHE.exists():
        return
    for path in sorted(CACHE.glob("*.json.gz")):
        payload = _read(path)
        if payload is not None:
            yield path.name.removesuffix(".json.gz"), payload


def _timestamp_sorted_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    tape = payload.get("tape")
    if not isinstance(tape, list):
        return dict(payload), {
            "rows": 0,
            "parseable_rows": 0,
            "invalid_rows": 0,
            "order_changed": False,
            "moved_rows": 0,
            "max_displacement": 0,
        }

    rows = [row for row in tape if isinstance(row, dict)]
    decorated = []
    invalid = 0
    for index, row in enumerate(rows):
        parsed = _parse_time(row.get("timestamp"))
        if parsed is None:
            invalid += 1
        decorated.append((parsed, index, row))

    # This is deliberately an audit comparator, not a production repair.
    # Invalid timestamps stay after parseable rows while retaining original order.
    decorated.sort(
        key=lambda item: (
            item[0] is None,
            item[0] if item[0] is not None else datetime.max.replace(tzinfo=timezone.utc),
            item[1],
        )
    )
    sorted_rows = [row for _ts, _idx, row in decorated]
    original_positions = {id(row): i for i, row in enumerate(rows)}
    displacements = [abs(i - original_positions[id(row)]) for i, row in enumerate(sorted_rows)]
    moved = sum(1 for d in displacements if d)
    out = dict(payload)
    out["tape"] = sorted_rows
    return out, {
        "rows": len(rows),
        "parseable_rows": len(rows) - invalid,
        "invalid_rows": invalid,
        "order_changed": moved > 0,
        "moved_rows": moved,
        "max_displacement": max(displacements) if displacements else 0,
    }


def _event_stats(payload: dict[str, Any], match_id: str) -> dict[str, Any]:
    events = canonical_point_events(payload, match_id=match_id)
    reasons: Counter[str] = Counter()
    trainable_point = 0
    trainable_basic = 0
    for event in events:
        quality = event.get("quality") if isinstance(event.get("quality"), dict) else {}
        trainable_basic += int(bool(quality.get("trainable_basic")))
        trainable_point += int(bool(quality.get("trainable_point")))
        reasons[str(quality.get("atomic_reason"))] += 1
    return {
        "events": len(events),
        "trainable_basic": trainable_basic,
        "trainable_point": trainable_point,
        "atomic_reasons": reasons,
    }


def audit_payloads(payloads: Iterable[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    matches = 0
    rows = parseable_rows = invalid_rows = 0
    changed_matches = moved_rows = 0
    max_displacement = 0

    provider_events = provider_trainable_basic = provider_trainable_point = 0
    timestamp_events = timestamp_trainable_basic = timestamp_trainable_point = 0

    provider_reasons: Counter[str] = Counter()
    timestamp_reasons: Counter[str] = Counter()

    timestamp_better = provider_better = equal_atomic = 0
    changed_and_provider_better = changed_and_timestamp_better = changed_and_equal = 0
    largest_provider_advantage = 0
    largest_timestamp_advantage = 0

    for match_id, payload in payloads:
        if not isinstance(payload, dict):
            continue
        matches += 1

        provider = _event_stats(payload, match_id)
        sorted_payload, ordering = _timestamp_sorted_payload(payload)
        timestamp = _event_stats(sorted_payload, match_id)

        rows += int(ordering["rows"])
        parseable_rows += int(ordering["parseable_rows"])
        invalid_rows += int(ordering["invalid_rows"])
        if ordering["order_changed"]:
            changed_matches += 1
        moved_rows += int(ordering["moved_rows"])
        max_displacement = max(max_displacement, int(ordering["max_displacement"]))

        provider_events += int(provider["events"])
        provider_trainable_basic += int(provider["trainable_basic"])
        provider_trainable_point += int(provider["trainable_point"])
        timestamp_events += int(timestamp["events"])
        timestamp_trainable_basic += int(timestamp["trainable_basic"])
        timestamp_trainable_point += int(timestamp["trainable_point"])
        provider_reasons.update(provider["atomic_reasons"])
        timestamp_reasons.update(timestamp["atomic_reasons"])

        p = int(provider["trainable_point"])
        t = int(timestamp["trainable_point"])
        delta = p - t
        if delta > 0:
            provider_better += 1
            largest_provider_advantage = max(largest_provider_advantage, delta)
        elif delta < 0:
            timestamp_better += 1
            largest_timestamp_advantage = max(largest_timestamp_advantage, -delta)
        else:
            equal_atomic += 1

        if ordering["order_changed"]:
            if delta > 0:
                changed_and_provider_better += 1
            elif delta < 0:
                changed_and_timestamp_better += 1
            else:
                changed_and_equal += 1

    authority = "UNRESOLVED"
    if (
        changed_matches > 0
        and provider_trainable_point > timestamp_trainable_point
        and changed_and_provider_better > changed_and_timestamp_better
    ):
        authority = "PROVIDER_SEQUENCE_CLEAN_CANDIDATE"
    elif (
        changed_matches > 0
        and timestamp_trainable_point > provider_trainable_point
        and changed_and_timestamp_better > changed_and_provider_better
    ):
        authority = "TIMESTAMP_SORT_CANDIDATE"

    return {
        "version": VERSION,
        "gate": "AUDIT_ONLY_NO_ORDERING_ACTIVATION",
        "network_calls": 0,
        "shadow_only": True,
        "training_join_enabled": False,
        "profile_aggregation_enabled": False,
        "ordering_activation_enabled": False,
        "matches": matches,
        "raw_rows": rows,
        "parseable_timestamp_rows": parseable_rows,
        "invalid_timestamp_rows": invalid_rows,
        "timestamp_sort": {
            "matches_whose_row_order_changes": changed_matches,
            "changed_match_rate": round(changed_matches / matches, 6) if matches else 0.0,
            "moved_rows": moved_rows,
            "moved_row_rate": round(moved_rows / rows, 6) if rows else 0.0,
            "max_row_displacement": max_displacement,
        },
        "provider_sequence": {
            "events": provider_events,
            "trainable_basic": provider_trainable_basic,
            "trainable_point": provider_trainable_point,
            "atomic_reasons": dict(provider_reasons.most_common()),
        },
        "timestamp_sorted_sequence": {
            "events": timestamp_events,
            "trainable_basic": timestamp_trainable_basic,
            "trainable_point": timestamp_trainable_point,
            "atomic_reasons": dict(timestamp_reasons.most_common()),
        },
        "per_match_comparison": {
            "provider_more_atomic_matches": provider_better,
            "timestamp_more_atomic_matches": timestamp_better,
            "equal_atomic_matches": equal_atomic,
            "changed_provider_more_atomic_matches": changed_and_provider_better,
            "changed_timestamp_more_atomic_matches": changed_and_timestamp_better,
            "changed_equal_atomic_matches": changed_and_equal,
            "largest_provider_atomic_advantage": largest_provider_advantage,
            "largest_timestamp_atomic_advantage": largest_timestamp_advantage,
        },
        "ordering_authority_candidate": authority,
        "note": (
            "Evidence only. A candidate is not permission to reorder historical tapes, "
            "aggregate Player DNA profiles, or train a production model."
        ),
    }


def build() -> dict[str, Any]:
    report = audit_payloads(cached_payloads() or ())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": report["version"],
        "matches": report["matches"],
        "raw_rows": report["raw_rows"],
        "timestamp_sort": report["timestamp_sort"],
        "provider_trainable_point": report["provider_sequence"]["trainable_point"],
        "timestamp_trainable_point": report["timestamp_sorted_sequence"]["trainable_point"],
        "comparison": report["per_match_comparison"],
        "ordering_authority_candidate": report["ordering_authority_candidate"],
        "gate": report["gate"],
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
