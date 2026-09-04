from __future__ import annotations

"""Zero-network gate for Player DNA context distributions and point chronology.

This is audit-only. It does not join match context into Player DNA training rows,
aggregate player profiles, train models, or affect PROD/Symfonia 2.0/PLAYABLE.
"""

import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.canonical_point_event import canonical_point_events
    from backend.player_dna_match_context import resolve_match_context
except ModuleNotFoundError:  # direct execution
    from canonical_point_event import canonical_point_events
    from player_dna_match_context import resolve_match_context

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT = ROOT / "frontend" / "data" / "player_dna_context_time_audit.json"
VERSION = "player-dna-context-time-audit-v1"


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


def _read(path: Path) -> dict[str, Any] | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def cached_payloads() -> Iterable[tuple[str, dict[str, Any]]]:
    if not CACHE.exists():
        return
    for path in sorted(CACHE.glob("*.json.gz")):
        payload = _read(path)
        if payload is not None:
            yield path.name.removesuffix(".json.gz"), payload


def audit_payloads(payloads: Iterable[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    matches = valid_context = rejected_context = 0
    matches_with_events = matches_with_parseable_events = 0
    matches_with_non_monotonic_events = 0
    events_total = parseable_event_times = invalid_event_times = 0
    events_before_scheduled = events_at_or_after_scheduled = 0
    min_offset_seconds = max_offset_seconds = None

    surfaces: Counter[str] = Counter()
    tours: Counter[str] = Counter()
    formats: Counter[str] = Counter()
    rounds: Counter[str] = Counter()
    indoor: Counter[str] = Counter()
    qualifying: Counter[str] = Counter()
    ranking_coverage: Counter[str] = Counter()

    for match_id, payload in payloads:
        if not isinstance(payload, dict):
            continue
        matches += 1
        context = resolve_match_context(payload)
        if context is None:
            rejected_context += 1
            continue

        valid_context += 1
        if context.get("surface") is not None:
            surfaces[str(context["surface"])] += 1
        if context.get("tour") is not None:
            tours[str(context["tour"])] += 1
        if context.get("format") is not None:
            formats[str(context["format"])] += 1
        if context.get("round_code") is not None:
            rounds[str(context["round_code"])] += 1
        if context.get("indoor") is not None:
            indoor[str(bool(context["indoor"])).lower()] += 1
        if context.get("is_qualifying") is not None:
            qualifying[str(bool(context["is_qualifying"])).lower()] += 1

        p1 = context.get("p1") if isinstance(context.get("p1"), dict) else {}
        p2 = context.get("p2") if isinstance(context.get("p2"), dict) else {}
        ranking_coverage["p1_present"] += int(p1.get("ranking") is not None)
        ranking_coverage["p2_present"] += int(p2.get("ranking") is not None)
        ranking_coverage["both_present"] += int(p1.get("ranking") is not None and p2.get("ranking") is not None)

        scheduled = _parse_utc(context.get("scheduled_time"))
        if scheduled is None:
            # Strict resolver should already prevent this; keep the audit defensive.
            rejected_context += 1
            valid_context -= 1
            continue

        events = canonical_point_events(payload, match_id=match_id)
        if events:
            matches_with_events += 1

        last_time: datetime | None = None
        match_parseable = False
        match_non_monotonic = False
        for event in events:
            events_total += 1
            current = _parse_utc(event.get("timestamp_after"))
            if current is None:
                invalid_event_times += 1
                continue
            parseable_event_times += 1
            match_parseable = True
            if last_time is not None and current < last_time:
                match_non_monotonic = True
            last_time = current

            offset = (current - scheduled).total_seconds()
            if offset < 0:
                events_before_scheduled += 1
            else:
                events_at_or_after_scheduled += 1
            min_offset_seconds = offset if min_offset_seconds is None else min(min_offset_seconds, offset)
            max_offset_seconds = offset if max_offset_seconds is None else max(max_offset_seconds, offset)

        if match_parseable:
            matches_with_parseable_events += 1
        if match_non_monotonic:
            matches_with_non_monotonic_events += 1

    chronology_clean = (
        parseable_event_times > 0
        and invalid_event_times == 0
        and matches_with_non_monotonic_events == 0
        and events_before_scheduled == 0
    )

    return {
        "version": VERSION,
        "gate": "AUDIT_ONLY_NO_PROFILE_AGGREGATION",
        "network_calls": 0,
        "shadow_only": True,
        "training_join_enabled": False,
        "profile_aggregation_enabled": False,
        "matches": matches,
        "valid_context_matches": valid_context,
        "rejected_context_matches": rejected_context,
        "context_coverage": round(valid_context / matches, 6) if matches else 0.0,
        "distributions": {
            "surface": dict(surfaces.most_common()),
            "tour": dict(tours.most_common()),
            "format": dict(formats.most_common()),
            "round_code": dict(rounds.most_common()),
            "indoor": dict(indoor.most_common()),
            "is_qualifying": dict(qualifying.most_common()),
        },
        "ranking_coverage": {
            "p1_present": ranking_coverage["p1_present"],
            "p2_present": ranking_coverage["p2_present"],
            "both_present": ranking_coverage["both_present"],
            "p1_rate": round(ranking_coverage["p1_present"] / valid_context, 6) if valid_context else 0.0,
            "p2_rate": round(ranking_coverage["p2_present"] / valid_context, 6) if valid_context else 0.0,
            "both_rate": round(ranking_coverage["both_present"] / valid_context, 6) if valid_context else 0.0,
        },
        "time_ordering": {
            "matches_with_events": matches_with_events,
            "matches_with_parseable_events": matches_with_parseable_events,
            "events_total": events_total,
            "parseable_event_times": parseable_event_times,
            "invalid_event_times": invalid_event_times,
            "matches_with_non_monotonic_events": matches_with_non_monotonic_events,
            "events_before_scheduled": events_before_scheduled,
            "events_at_or_after_scheduled": events_at_or_after_scheduled,
            "min_offset_seconds": round(min_offset_seconds, 6) if min_offset_seconds is not None else None,
            "max_offset_seconds": round(max_offset_seconds, 6) if max_offset_seconds is not None else None,
            "chronology_clean_candidate": chronology_clean,
        },
        "note": (
            "Audit only. chronology_clean_candidate is evidence for the next gate, "
            "not permission to aggregate profiles or train Player DNA."
        ),
    }


def build() -> dict[str, Any]:
    report = audit_payloads(cached_payloads() or ())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": report["version"],
        "matches": report["matches"],
        "valid_context_matches": report["valid_context_matches"],
        "context_coverage": report["context_coverage"],
        "time_ordering": report["time_ordering"],
        "gate": report["gate"],
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
