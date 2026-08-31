#!/usr/bin/env python3
from __future__ import annotations

"""Tenis AI v8.5.5 — safe publication pruning for ``results.json``.

Only publication-only or strictly redundant structures are removed. Model math,
training/history, exact Superbet PLAYABLE selection matching and settlement inputs
remain untouched. The regular FULL build recreates calculation data before this
publication pass.
"""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "frontend" / "data" / "results.json"
VERSION = "v8.5.5-results-publication-prune"
REMOVED_TENDENCY_KEYS = ("recent_matches", "recent_surface_matches")
# Diagnostic-only shadow coverage is published separately and has no frontend
# consumer in the repository. Keeping it duplicated inside every match adds ~3.5 MB.
REMOVED_SUPERBET_PUBLICATION_KEYS = ("coverage_shadow_signals",)


def _compact_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _payload_contributors(rows: list[dict], limit: int = 18) -> dict:
    top_bytes: dict[str, int] = defaultdict(int)
    top_count: dict[str, int] = defaultdict(int)
    nested_bytes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for match in rows:
        if not isinstance(match, dict):
            continue
        for key, value in match.items():
            try:
                top_bytes[str(key)] += len(_compact_bytes(value))
                top_count[str(key)] += 1
            except (TypeError, ValueError):
                continue
            if isinstance(value, dict):
                for child_key, child_value in value.items():
                    try:
                        nested_bytes[str(key)][str(child_key)] += len(_compact_bytes(child_value))
                    except (TypeError, ValueError):
                        continue
    ordered = sorted(top_bytes, key=lambda k: (-top_bytes[k], k))[:limit]
    nested = {}
    for key in ordered:
        children = nested_bytes.get(key)
        if not children:
            continue
        child_order = sorted(children, key=lambda k: (-children[k], k))[:12]
        nested[key] = [{"key": child, "bytes": children[child]} for child in child_order]
    return {
        "top_level": [{"key": key, "bytes": top_bytes[key], "matches": top_count[key]} for key in ordered],
        "nested": nested,
    }


def _verified_autolearn_index(signals, by_key) -> bool:
    if not isinstance(signals, list) or not isinstance(by_key, dict):
        return False
    expected = {}
    for row in signals:
        if not isinstance(row, dict) or row.get("key") is None:
            return False
        key = str(row["key"])
        if key in expected:
            return False
        expected[key] = row
    return expected == by_key


def prune_rows(rows: list[dict]) -> dict:
    removed_fields = 0
    affected_profiles = 0
    removed_items = 0
    autolearn_indexes_removed = 0
    autolearn_index_mismatches = 0
    autolearn_index_bytes_removed = 0
    superbet_fields_removed = 0
    superbet_bytes_removed = 0

    for match in rows:
        if not isinstance(match, dict):
            continue

        tendencies = match.get("tendencies_v71")
        if isinstance(tendencies, dict):
            for side in ("p1", "p2"):
                profile = tendencies.get(side)
                if not isinstance(profile, dict):
                    continue
                touched = False
                for key in REMOVED_TENDENCY_KEYS:
                    if key not in profile:
                        continue
                    value = profile.pop(key)
                    removed_fields += 1
                    if isinstance(value, list):
                        removed_items += len(value)
                    touched = True
                if touched:
                    affected_profiles += 1

        superbet = match.get("superbet_market_v91")
        if isinstance(superbet, dict):
            for key in REMOVED_SUPERBET_PUBLICATION_KEYS:
                if key in superbet:
                    value = superbet.pop(key)
                    superbet_fields_removed += 1
                    try:
                        superbet_bytes_removed += len(_compact_bytes(value))
                    except (TypeError, ValueError):
                        pass

        autolearn = match.get("autolearn_v84")
        if not isinstance(autolearn, dict) or "by_key" not in autolearn:
            continue
        signals = autolearn.get("signals")
        by_key = autolearn.get("by_key")
        if _verified_autolearn_index(signals, by_key):
            autolearn_index_bytes_removed += len(_compact_bytes(by_key))
            autolearn.pop("by_key", None)
            autolearn_indexes_removed += 1
        else:
            autolearn_index_mismatches += 1

    return {
        "version": VERSION,
        "matches": len(rows),
        "affected_profiles": affected_profiles,
        "removed_fields": removed_fields,
        "removed_items": removed_items,
        "removed_keys": list(REMOVED_TENDENCY_KEYS),
        "superbet_publication_prune": {
            "removed_keys": list(REMOVED_SUPERBET_PUBLICATION_KEYS),
            "removed_fields": superbet_fields_removed,
            "estimated_value_bytes_removed": superbet_bytes_removed,
        },
        "autolearn_by_key": {
            "removed_verified_indexes": autolearn_indexes_removed,
            "mismatches_preserved": autolearn_index_mismatches,
            "estimated_value_bytes_removed": autolearn_index_bytes_removed,
            "canonical_signals_preserved": True,
            "strict_equality_required": True,
        },
    }


def prune_results(path: Path = RESULTS_PATH) -> dict:
    if not path.exists():
        return {"version": VERSION, "status": "missing", "path": str(path)}
    before = path.stat().st_size
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return {"version": VERSION, "status": "skipped-non-list", "path": str(path), "before_bytes": before}
    stats = prune_rows(data)
    contributors = _payload_contributors(data)
    payload = _compact_bytes(data)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)
    after = path.stat().st_size
    return {
        **stats,
        "status": "ok",
        "path": str(path),
        "before_bytes": before,
        "after_bytes": after,
        "saved_bytes": before - after,
        "saved_pct": round((before - after) * 100.0 / before, 2) if before else 0.0,
        "payload_contributors_after_prune": contributors,
    }


def main() -> None:
    print(json.dumps(prune_results(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
