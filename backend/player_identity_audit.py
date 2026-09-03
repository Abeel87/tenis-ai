from __future__ import annotations

"""Zero-network audit for stable player identity in restored PBP cache.

This gate intentionally does not guess provider semantics. It inventories payload/meta
keys and values that may bind match side 1/2 to stable player identifiers. The report
must be reviewed before Player DNA is grouped across matches.
"""

import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT = ROOT / "frontend" / "data" / "player_identity_audit.json"
VERSION = "player-identity-audit-v1"


def _read(path: Path) -> dict[str, Any] | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _shape(value: Any) -> str:
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    return type(value).__name__


def _candidate_key(key: str) -> bool:
    k = key.casefold()
    return any(token in k for token in ("player", "home", "away", "winner", "loser", "team", "participant", "roster"))


def inspect_payload(payload: dict[str, Any]) -> dict[str, Any]:
    top = {str(k): _shape(v) for k, v in payload.items() if k != "tape"}
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    candidates: dict[str, Any] = {}
    for prefix, obj in (("top", payload), ("meta", meta)):
        for key, value in obj.items():
            if key == "tape" or not _candidate_key(str(key)):
                continue
            candidates[f"{prefix}.{key}"] = {"type": _shape(value), "value": value}
    return {"top_level": top, "meta_keys": {str(k): _shape(v) for k, v in meta.items()}, "identity_candidates": candidates}


def build() -> dict[str, Any]:
    matches = 0
    top_keys: Counter[str] = Counter()
    meta_keys: Counter[str] = Counter()
    candidate_matches: Counter[str] = Counter()
    candidate_types: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, list[Any]] = defaultdict(list)

    for path in sorted(CACHE.glob("*.json.gz")) if CACHE.exists() else ():
        payload = _read(path)
        if payload is None:
            continue
        matches += 1
        info = inspect_payload(payload)
        for key in info["top_level"]:
            top_keys[key] += 1
        for key in info["meta_keys"]:
            meta_keys[key] += 1
        for key, item in info["identity_candidates"].items():
            candidate_matches[key] += 1
            candidate_types[key][item["type"]] += 1
            if len(examples[key]) < 5:
                examples[key].append({"match_id": path.name.removesuffix(".json.gz"), "value": item["value"]})

    report = {
        "version": VERSION,
        "network_calls": 0,
        "matches": matches,
        "source": "restored data/cache/pbp_v7/matches/*.json.gz",
        "top_level_key_match_coverage": dict(top_keys.most_common()),
        "meta_key_match_coverage": dict(meta_keys.most_common()),
        "identity_candidates": {
            key: {
                "matches": candidate_matches[key],
                "coverage": round(candidate_matches[key] / matches, 6) if matches else 0.0,
                "types": dict(candidate_types[key]),
                "examples": examples[key],
            }
            for key in sorted(candidate_matches)
        },
        "gate": "AUDIT_ONLY_NO_IDENTITY_JOIN",
        "note": "Candidate key names are discovery hints only. No side-to-player mapping is accepted until examples and coverage prove provider semantics.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"matches": matches, "candidates": list(report["identity_candidates"])}, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
