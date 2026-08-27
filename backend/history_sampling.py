"""Sampling policy shared by reports; archived predictions are never deleted."""
from __future__ import annotations


def _canonical_set1_total_signal(signal, standard):
    """Return a report-only canonical copy for equivalent standard-set lines.

    In a completed standard first set, 10.5 and 11.5 have the same binary
    outcome because the set total jumps from 10 directly to 12. Historical
    snapshots remain untouched; reports consistently expose the 10.5 label.
    """
    if not standard or signal.get("market") != "set1_total":
        return signal

    line = signal.get("line")
    try:
        line = float(line) if line is not None else None
    except (TypeError, ValueError):
        return signal

    if line not in (10.5, 11.5):
        return signal

    out = dict(signal)
    out["line"] = 10.5
    label = str(out.get("label") or "")
    if label:
        out["label"] = label.replace("11.5", "10.5")
    return out


def unique_signals(entry, layer="signals"):
    """Count identical events once per model within a match.

    In a completed standard first set, 10.5 and 11.5 have the same outcome:
    totals jump from 10 to 12. Prefer and expose the 10.5 representation
    deterministically. Do not apply that equivalence to unfinished or
    nonstandard sets. Archived predictions are never mutated.
    """
    final = entry.get("result") or {}
    sets = final.get("sets") or []
    standard = bool(sets and tuple(sorted(sets[0])) in {
        (0, 6), (1, 6), (2, 6), (3, 6), (4, 6), (5, 7), (6, 7)
    } and final.get("status") == "completed")
    rows = entry.get(layer) or []
    seen = set()
    for raw_signal in sorted(rows, key=lambda s: str(s.get("line", ""))):
        signal = _canonical_set1_total_signal(raw_signal, standard)
        if not signal.get("market") or signal.get("pick") is None:
            yield signal
            continue
        line = signal.get("line")
        try:
            line = float(line) if line is not None else None
        except (TypeError, ValueError):
            pass
        key = (signal.get("market"), signal.get("pick"), line,
               signal.get("checkpoint"), signal.get("source_model"),
               signal.get("tracker_version"))
        if key not in seen:
            seen.add(key)
            yield signal
