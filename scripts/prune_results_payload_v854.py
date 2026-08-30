#!/usr/bin/env python3
from __future__ import annotations

"""Tenis AI v8.5.4 — safe publication pruning for ``results.json``.

``player_trends.py`` embeds up to 20 raw historical source rows twice per player
(`recent_matches` and `recent_surface_matches`) in every current match. The
frontend trend views use the aggregate 5/10/20 ``all``/``surface`` windows and
BASIC PBP summaries, not those duplicated raw rows.

This publication-only pass removes only those two raw diagnostic arrays. It does
not modify model probabilities, aggregate tendency metrics, current match data,
Superbet/PLAYABLE data, SHADOW data, training/history files or settlement data.
The regular FULL build recreates the raw source rows before all model/enrichment
steps and this script runs again only when preparing the frontend payload.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "frontend" / "data" / "results.json"
VERSION = "v8.5.4-results-publication-prune"
REMOVED_TENDENCY_KEYS = ("recent_matches", "recent_surface_matches")


def _compact_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def prune_rows(rows: list[dict]) -> dict:
    removed_fields = 0
    affected_profiles = 0
    removed_items = 0

    for match in rows:
        if not isinstance(match, dict):
            continue
        tendencies = match.get("tendencies_v71")
        if not isinstance(tendencies, dict):
            continue
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

    return {
        "version": VERSION,
        "matches": len(rows),
        "affected_profiles": affected_profiles,
        "removed_fields": removed_fields,
        "removed_items": removed_items,
        "removed_keys": list(REMOVED_TENDENCY_KEYS),
    }


def prune_results(path: Path = RESULTS_PATH) -> dict:
    if not path.exists():
        return {"version": VERSION, "status": "missing", "path": str(path)}

    before = path.stat().st_size
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return {
            "version": VERSION,
            "status": "skipped-non-list",
            "path": str(path),
            "before_bytes": before,
        }

    stats = prune_rows(data)
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
    }


def main() -> None:
    print(json.dumps(prune_results(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
