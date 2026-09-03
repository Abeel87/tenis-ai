from __future__ import annotations

"""Zero-network audit for stable player identity in restored PBP cache.

No provider semantics are guessed. The audit recursively inventories the small
identity-bearing match/profiles/meta structures (never tape rows) and emits bounded
examples so side -> stable player identity can be proven before any cross-match DNA.
"""

import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT = ROOT / "frontend" / "data" / "player_identity_audit.json"
VERSION = "player-identity-audit-v2"
MAX_DEPTH = 5
MAX_EXAMPLES = 5


def _read(path: Path) -> dict[str, Any] | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _shape(value: Any) -> str:
    if isinstance(value, dict): return "dict"
    if isinstance(value, list): return "list"
    return type(value).__name__


def _interesting(path: str) -> bool:
    p = path.casefold()
    return any(token in p for token in ("player", "profile", "home", "away", "winner", "loser", "team", "participant", "roster", ".id", "name"))


def _walk(value: Any, path: str, depth: int = 0):
    if depth > MAX_DEPTH:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield child_path, child
            yield from _walk(child, child_path, depth + 1)
    elif isinstance(value, list):
        for idx, child in enumerate(value[:4]):
            child_path = f"{path}[]"
            yield child_path, child
            yield from _walk(child, child_path, depth + 1)


def _safe_example(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _safe_example(v) for k, v in list(value.items())[:20]}
    if isinstance(value, list):
        return [_safe_example(v) for v in value[:6]]
    return repr(value)


def inspect_payload(payload: dict[str, Any]) -> dict[str, Any]:
    roots = {name: payload.get(name) for name in ("match", "profiles", "meta") if name in payload}
    paths: dict[str, dict[str, Any]] = {}
    for root, value in roots.items():
        paths[root] = {"type": _shape(value), "value": value}
        for path, child in _walk(value, root):
            if _interesting(path):
                paths[path] = {"type": _shape(child), "value": child}
    return paths


def build() -> dict[str, Any]:
    matches = 0
    path_matches: Counter[str] = Counter()
    path_types: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, list[Any]] = defaultdict(list)

    for path in sorted(CACHE.glob("*.json.gz")) if CACHE.exists() else ():
        payload = _read(path)
        if payload is None:
            continue
        matches += 1
        seen = set()
        for field, item in inspect_payload(payload).items():
            if field not in seen:
                path_matches[field] += 1
                seen.add(field)
            path_types[field][item["type"]] += 1
            if len(examples[field]) < MAX_EXAMPLES:
                examples[field].append({"match_id": path.name.removesuffix(".json.gz"), "value": _safe_example(item["value"])})

    fields = {
        field: {
            "matches": path_matches[field],
            "coverage": round(path_matches[field] / matches, 6) if matches else 0.0,
            "types": dict(path_types[field]),
            "examples": examples[field],
        }
        for field in sorted(path_matches)
    }
    report = {
        "version": VERSION,
        "network_calls": 0,
        "matches": matches,
        "source": "restored data/cache/pbp_v7/matches/*.json.gz",
        "nested_identity_schema": fields,
        "gate": "AUDIT_ONLY_NO_IDENTITY_JOIN",
        "note": "Nested match/profiles/meta schema only; tape excluded. Examples prove structure but do not by themselves authorize side-to-player semantics.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"matches": matches, "fields": len(fields)}, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
