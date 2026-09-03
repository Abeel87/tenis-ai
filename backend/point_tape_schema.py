from __future__ import annotations

"""Lossless inspection helpers for cached Live Tennis API point tapes.

This module is deliberately SHADOW/data-foundation only.  It does not change
Current Engine, Symfonia, Superbet PLAYABLE, model scores or training weights.

The first job is to learn what the provider really stores in cached point rows
before we design a canonical point-level training schema.  Unknown fields are
kept in ``raw`` instead of being silently discarded.
"""

from collections import Counter
from typing import Any, Iterable

SCHEMA_VERSION = "point-tape-audit-v1"


def _as_rows(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    tape = payload.get("tape")
    if not isinstance(tape, list):
        return []
    return [row for row in tape if isinstance(row, dict)]


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def inspect_tape_schema(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Return field coverage without assuming undocumented provider fields."""
    rows = _as_rows(payload)
    counts: Counter[str] = Counter()
    types: dict[str, Counter[str]] = {}
    for row in rows:
        for key, value in row.items():
            if not _present(value):
                continue
            counts[str(key)] += 1
            types.setdefault(str(key), Counter())[type(value).__name__] += 1

    n = len(rows)
    fields = {}
    for key in sorted(counts):
        fields[key] = {
            "present": counts[key],
            "coverage": round(counts[key] / n, 4) if n else 0.0,
            "types": dict(types[key].most_common()),
        }
    return {
        "version": SCHEMA_VERSION,
        "rows": n,
        "fields": fields,
        "meta": dict(payload.get("meta") or {}) if isinstance(payload, dict) else {},
    }


def lossless_point_rows(payload: dict[str, Any] | None, match_id: Any = None) -> list[dict[str, Any]]:
    """Expose cached rows losslessly for offline dataset building.

    We intentionally do not invent point winner, break-point, score-before or
    serve-number fields here.  Those are derived only after the schema audit
    proves which source fields are available and how score transitions behave.
    """
    out = []
    for index, row in enumerate(_as_rows(payload)):
        out.append({
            "match_id": match_id,
            "row_index": index,
            "server": row.get("server"),
            "games": row.get("games"),
            "raw": dict(row),
        })
    return out


def aggregate_schema_audit(payloads: Iterable[tuple[Any, dict[str, Any]]]) -> dict[str, Any]:
    """Aggregate provider-field coverage across many cached matches."""
    matches = 0
    rows = 0
    field_rows: Counter[str] = Counter()
    field_matches: Counter[str] = Counter()
    type_counts: dict[str, Counter[str]] = {}

    for _match_id, payload in payloads:
        report = inspect_tape_schema(payload)
        if report["rows"] <= 0:
            continue
        matches += 1
        rows += report["rows"]
        for key, info in report["fields"].items():
            field_rows[key] += int(info["present"])
            field_matches[key] += 1
            bucket = type_counts.setdefault(key, Counter())
            for typ, count in info["types"].items():
                bucket[typ] += int(count)

    fields = {}
    for key in sorted(field_rows):
        fields[key] = {
            "rows_present": field_rows[key],
            "row_coverage": round(field_rows[key] / rows, 4) if rows else 0.0,
            "matches_present": field_matches[key],
            "match_coverage": round(field_matches[key] / matches, 4) if matches else 0.0,
            "types": dict(type_counts[key].most_common()),
        }
    return {
        "version": SCHEMA_VERSION,
        "matches": matches,
        "rows": rows,
        "fields": fields,
    }
