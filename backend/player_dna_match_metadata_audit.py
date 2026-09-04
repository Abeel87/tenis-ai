from __future__ import annotations

"""Zero-network audit of match metadata available to future Player DNA features.

This module only inventories cached provider fields and coverage. It does not
join metadata into the point dataset, train a model, or affect PROD/Symfonia 2.0.
"""

import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT = ROOT / "frontend" / "data" / "player_dna_match_metadata_audit.json"
MAX_DEPTH = 5
SAMPLE_VALUES_PER_PATH = 3


def _read(path: Path) -> dict[str, Any] | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    if value is None:
        return "null"
    return type(value).__name__


def _walk(value: Any, prefix: str = "", depth: int = 0):
    if depth > MAX_DEPTH:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path, child
            yield from _walk(child, path, depth + 1)
    elif isinstance(value, list):
        for child in value[:2]:
            path = f"{prefix}[]"
            yield path, child
            yield from _walk(child, path, depth + 1)


def audit_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    matches = 0
    path_presence: Counter[str] = Counter()
    path_nonempty: Counter[str] = Counter()
    path_types: dict[str, Counter[str]] = {}
    samples: dict[str, list[Any]] = {}
    top_level_keys: Counter[str] = Counter()
    match_keys: Counter[str] = Counter()

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        matches += 1
        for key in payload:
            top_level_keys[str(key)] += 1
        match = payload.get("match")
        if isinstance(match, dict):
            for key in match:
                match_keys[str(key)] += 1

        # A list can expose the same provider path several times inside one
        # match. Coverage is per match, so presence/non-empty counters must be
        # incremented at most once per path for each payload.
        seen_presence: set[str] = set()
        seen_nonempty: set[str] = set()
        for path, value in _walk(payload):
            if path not in seen_presence:
                path_presence[path] += 1
                seen_presence.add(path)
            if _nonempty(value) and path not in seen_nonempty:
                path_nonempty[path] += 1
                seen_nonempty.add(path)
            path_types.setdefault(path, Counter())[_type_name(value)] += 1
            if _nonempty(value) and not isinstance(value, (dict, list)):
                bucket = samples.setdefault(path, [])
                normalized = value if isinstance(value, (str, int, float, bool)) else str(value)
                if normalized not in bucket and len(bucket) < SAMPLE_VALUES_PER_PATH:
                    bucket.append(normalized)

    rows = []
    for path, present in path_presence.most_common():
        nonempty = path_nonempty[path]
        rows.append({
            "path": path,
            "present": present,
            "present_rate": round(present / matches, 6) if matches else 0.0,
            "nonempty": nonempty,
            "nonempty_rate": round(nonempty / matches, 6) if matches else 0.0,
            "types": dict(path_types[path].most_common()),
            "samples": samples.get(path, []),
        })

    likely_context = [
        row for row in rows
        if any(token in row["path"].casefold() for token in (
            "date", "time", "start", "surface", "court", "ground", "tournament",
            "league", "event", "rank", "seed", "country", "round", "season",
        ))
    ]

    return {
        "version": "player-dna-match-metadata-audit-v1",
        "gate": "AUDIT_ONLY_NO_FEATURE_JOIN",
        "network_calls": 0,
        "matches": matches,
        "top_level_keys": dict(top_level_keys.most_common()),
        "match_keys": dict(match_keys.most_common()),
        "likely_context_paths": likely_context,
        "all_paths": rows,
        "note": "Inventory only. Path names are provider evidence, not yet approved semantics for training.",
    }


def build() -> dict[str, Any]:
    payloads = []
    if CACHE.exists():
        for path in sorted(CACHE.glob("*.json.gz")):
            payload = _read(path)
            if payload is not None:
                payloads.append(payload)
    report = audit_payloads(payloads)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": report["version"],
        "matches": report["matches"],
        "likely_context_paths": len(report["likely_context_paths"]),
        "gate": report["gate"],
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
