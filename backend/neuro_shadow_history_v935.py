from __future__ import annotations

"""Persistent history store for NEURO SHADOW predictions.

This module is intentionally not imported by production update/playable/symphony
paths. It writes only dedicated NEURO SHADOW files and keeps predictions
append-only by prediction_key. Settlement updates existing rows without changing
the original probability or selection identity.
"""

import json
from pathlib import Path
from typing import Any, Iterable

from backend.neuro_shadow_tracker_v935 import register_predictions, settle_prediction, summarize

VERSION = "neuro-shadow-history-v9.3.6"
MODE = "SHADOW"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY_PATH = ROOT / "frontend" / "data" / "neuro_shadow_history_v935.json"
DEFAULT_STATS_PATH = ROOT / "frontend" / "data" / "neuro_shadow_stats_v935.json"


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_history(path: Path = DEFAULT_HISTORY_PATH) -> list[dict[str, Any]]:
    value = _read_json(path, [])
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def merge_registered(existing: Iterable[dict[str, Any]], incoming: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Append new prediction keys while preserving the first immutable forecast."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in (existing, incoming):
        for row in source or []:
            if not isinstance(row, dict):
                continue
            key = str(row.get("prediction_key") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(dict(row))
    return merged


def _persist_registered(
    existing: list[dict[str, Any]],
    registered: list[dict[str, Any]],
    *,
    history_path: Path,
    stats_path: Path,
) -> dict[str, Any]:
    merged = merge_registered(existing, registered)
    _write_json_atomic(history_path, merged)
    stats = summarize(merged)
    _write_json_atomic(stats_path, stats)
    return {
        "version": VERSION,
        "mode": MODE,
        "before": len(existing),
        "registered": len(registered),
        "added": len(merged) - len(existing),
        "total": len(merged),
        "history_path": str(history_path),
        "stats_path": str(stats_path),
        "production_influence": False,
        "playable_influence": False,
    }


def append_predictions(
    match: dict[str, Any],
    shadow_rows: list[dict[str, Any]],
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    stats_path: Path = DEFAULT_STATS_PATH,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Persist new SHADOW predictions without mutating prior forecasts."""
    existing = load_history(history_path)
    registered = register_predictions(match, shadow_rows, created_at=created_at)
    return _persist_registered(existing, registered, history_path=history_path, stats_path=stats_path)


def append_prediction_batches(
    batches: Iterable[tuple[dict[str, Any], list[dict[str, Any]]]],
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    stats_path: Path = DEFAULT_STATS_PATH,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Persist many match batches with one history read, one merge and one write.

    Hourly capture can touch dozens of matches and thousands of selections. The
    old per-match append path repeatedly rewrote the entire growing history and
    stats files, turning one refresh into O(matches * history_size) file I/O.
    This batch path preserves the exact same first-forecast immutability while
    making the persistence cost O(history_size + new_predictions).
    """
    existing = load_history(history_path)
    registered: list[dict[str, Any]] = []
    for match, shadow_rows in batches or []:
        if not isinstance(match, dict) or not shadow_rows:
            continue
        registered.extend(register_predictions(match, shadow_rows, created_at=created_at))
    return _persist_registered(existing, registered, history_path=history_path, stats_path=stats_path)


def _final_key(final: dict[str, Any]) -> str | None:
    value = final.get("match_id") if final.get("match_id") is not None else final.get("id")
    return str(value) if value is not None else None


def settle_history(
    finals: Iterable[dict[str, Any]],
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    stats_path: Path = DEFAULT_STATS_PATH,
) -> dict[str, Any]:
    """Settle pending or retryable unverifiable rows against final match records.

    HIT/MISS/VOID are terminal and remain immutable. ``unverifiable`` is
    intentionally retryable so later settlement coverage or newly available
    final evidence can recover old SHADOW rows without changing the original
    forecast probability or selection identity.
    """
    rows = load_history(history_path)
    final_map = {
        key: final
        for final in finals or []
        if isinstance(final, dict)
        for key in [_final_key(final)]
        if key
    }

    settled_now = 0
    retried_unverifiable = 0
    recovered_unverifiable = 0
    out: list[dict[str, Any]] = []
    for row in rows:
        previous = row.get("settlement")
        if previous not in {None, "unverifiable"}:
            out.append(row)
            continue
        match_id = row.get("match_id")
        final = final_map.get(str(match_id)) if match_id is not None else None
        if final is None:
            out.append(row)
            continue
        if previous == "unverifiable":
            retried_unverifiable += 1
        settled = settle_prediction(row, final)
        current = settled.get("settlement")
        if previous is None and current is not None:
            settled_now += 1
        elif previous == "unverifiable" and current != "unverifiable":
            recovered_unverifiable += 1
        out.append(settled)

    _write_json_atomic(history_path, out)
    stats = summarize(out)
    _write_json_atomic(stats_path, stats)
    return {
        "version": VERSION,
        "mode": MODE,
        "total": len(out),
        "settled_now": settled_now,
        "retried_unverifiable": retried_unverifiable,
        "recovered_unverifiable": recovered_unverifiable,
        "pending": sum(1 for row in out if row.get("settlement") is None),
        "unverifiable": sum(1 for row in out if row.get("settlement") == "unverifiable"),
        "scored": stats.get("scored", 0),
        "production_influence": False,
        "playable_influence": False,
    }
