from __future__ import annotations

"""Audit cached PBP tapes with zero network calls.

Usage from repository root:
    python backend/point_tape_audit.py

Writes frontend/data/point_tape_schema_audit.json.  This is diagnostic only.
"""

import gzip
import json
from pathlib import Path

from point_tape_schema import aggregate_schema_audit

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT = ROOT / "frontend" / "data" / "point_tape_schema_audit.json"


def _read(path: Path):
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def cached_payloads():
    if not CACHE.exists():
        return
    for path in sorted(CACHE.glob("*.json.gz")):
        payload = _read(path)
        if payload is not None:
            yield path.name.removesuffix(".json.gz"), payload


def main() -> int:
    report = aggregate_schema_audit(cached_payloads())
    report["source"] = "data/cache/pbp_v7/matches/*.json.gz"
    report["network_calls"] = 0
    report["purpose"] = "discover-real-provider-fields-before-point-level-schema"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "matches": report["matches"],
        "rows": report["rows"],
        "fields": list(report["fields"]),
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
