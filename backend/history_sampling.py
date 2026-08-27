"""Sampling policy shared by reports; archived predictions are never deleted."""
from __future__ import annotations


def unique_signals(entry, layer="signals"):
    """Count identical events once per model within a match.

    In a completed standard first set, 10.5 and 11.5 have the same outcome:
    totals jump from 10 to 12. Prefer the 10.5 representation deterministically.
    Do not apply that equivalence to unfinished or nonstandard sets.
    """
    final = entry.get("result") or {}
    sets = final.get("sets") or []
    standard = bool(sets and tuple(sorted(sets[0])) in {
        (0, 6), (1, 6), (2, 6), (3, 6), (4, 6), (5, 7), (6, 7)
    } and final.get("status") == "completed")
    rows = entry.get(layer) or []
    seen = set()
    for signal in sorted(rows, key=lambda s: str(s.get("line", ""))):
        if not signal.get("market") or signal.get("pick") is None:
            yield signal
            continue
        line = signal.get("line")
        try:
            line = float(line) if line is not None else None
        except (TypeError, ValueError):
            pass
        if standard and signal.get("market") == "set1_total" and line in (10.5, 11.5):
            line = 10.5
        key = (signal.get("market"), signal.get("pick"), line,
               signal.get("checkpoint"), signal.get("source_model"),
               signal.get("tracker_version"))
        if key not in seen:
            seen.add(key)
            yield signal
