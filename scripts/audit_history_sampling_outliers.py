"""Audit report-only history sampling outliers without mutating archived snapshots."""
from __future__ import annotations

import json
from pathlib import Path

from backend.history_sampling import unique_signals

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "frontend" / "data" / "history.json"
STANDARD_SET_SCORES = {
    (0, 6), (1, 6), (2, 6), (3, 6), (4, 6), (5, 7), (6, 7)
}


def _rows(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("history", "rows", "matches", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def _first_set(entry):
    final = entry.get("result") or {}
    sets = final.get("sets") or []
    first = sets[0] if sets else None
    try:
        pair = tuple(sorted((int(first[0]), int(first[1])))) if first and len(first) >= 2 else None
    except (TypeError, ValueError, IndexError):
        pair = None
    return final, first, pair


def main():
    payload = json.loads(HISTORY.read_text(encoding="utf-8"))
    leftovers = []
    standard_leaks = []

    for entry in _rows(payload):
        final, first, pair = _first_set(entry)
        standard = final.get("status") == "completed" and pair in STANDARD_SET_SCORES
        for signal in unique_signals(entry):
            if signal.get("result") not in {"hit", "miss"}:
                continue
            if signal.get("market") != "set1_total":
                continue
            try:
                line = float(signal.get("line"))
            except (TypeError, ValueError):
                continue
            if line != 11.5:
                continue

            row = {
                "match_key": entry.get("match_key") or entry.get("match_id"),
                "p1": entry.get("p1"),
                "p2": entry.get("p2"),
                "scheduled_time": entry.get("scheduled_time"),
                "model_version": entry.get("model_version"),
                "final_status": final.get("status"),
                "first_set": first,
                "standard_completed_set": standard,
                "label": signal.get("label"),
                "pick": signal.get("pick"),
                "result": signal.get("result"),
                "source_model": signal.get("source_model"),
            }
            leftovers.append(row)
            if standard:
                standard_leaks.append(row)

    print(f"history sampling audit: remaining reportable set1 11.5 = {len(leftovers)}")
    for row in leftovers:
        print("11.5 outlier:", json.dumps(row, ensure_ascii=False, sort_keys=True))

    if standard_leaks:
        print("ERROR: standard completed-set 11.5 leaked through canonical sampling")
        raise SystemExit(1)

    print("history sampling audit: PASS — remaining 11.5 entries are nonstandard/unresolved by design")


if __name__ == "__main__":
    main()
