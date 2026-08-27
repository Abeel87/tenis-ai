from __future__ import annotations

"""Guarded historical prior for Symphony AUTO leg-count selection.

Historical performance is intentionally a small tie-breaker.  Current-match
math remains dominant.  History is activated only when at least two leg-count
buckets have enough fully settled compositions and resolved individual legs.
"""

from copy import deepcopy

VERSION = "v9.0D"
MAX_HISTORY_BONUS = 4.0


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def apply_historical_leg_learning(intelligence: dict, stats: dict | None) -> dict:
    out = deepcopy(intelligence or {})
    options = out.get("options") or []
    leg_stats = (stats or {}).get("leg_counts") or {}

    ready = {}
    for key, row in leg_stats.items():
        if not isinstance(row, dict) or not row.get("history_weight_ready"):
            continue
        quality = row.get("normalized_quality")
        if quality is None:
            continue
        try:
            ready[int(key)] = float(quality)
        except (TypeError, ValueError):
            continue

    # One isolated bucket is not enough to decide which leg count is better.
    active = len(ready) >= 2
    baseline = (sum(ready.values()) / len(ready)) if active else None

    eligible = []
    for row in options:
        legs = int(row.get("legs") or 0)
        current = float(row.get("auto_utility") or -999.0)
        bonus = 0.0
        sample = leg_stats.get(str(legs)) or {}
        if active and legs in ready:
            bonus = _clamp((ready[legs] - baseline) * 0.35, -MAX_HISTORY_BONUS, MAX_HISTORY_BONUS)
        row["historical_quality"] = ready.get(legs)
        row["historical_full_settled"] = int(sample.get("full_settled") or 0)
        row["historical_leg_resolved"] = int(sample.get("resolved_legs") or 0)
        row["history_weight_ready"] = bool(sample.get("history_weight_ready"))
        row["history_bonus"] = round(bonus, 3)
        row["auto_utility_with_history"] = round(current + bonus, 3)
        if row.get("eligible"):
            eligible.append(row)

    pool = eligible or options
    if pool:
        recommended = max(
            pool,
            key=lambda x: (float(x.get("auto_utility_with_history") or -999.0), int(x.get("legs") or 0)),
        )
        out["recommended"] = int(recommended.get("legs"))

    out["historical_learning_active"] = active
    out["historical_ready_leg_counts"] = sorted(ready)
    out["historical_baseline_quality"] = round(baseline, 3) if baseline is not None else None
    out["mode"] = "CURRENT_MATCH_PLUS_HISTORY" if active else out.get("mode", "CURRENT_MATCH_MATH")
    if active:
        rec = next((x for x in options if int(x.get("legs") or 0) == int(out.get("recommended") or 0)), None)
        if rec:
            extra = (
                f"; historia {int(rec['legs'])}-leg: jakość norm. "
                f"{float(rec.get('historical_quality') or 0):.1f}, bonus {float(rec.get('history_bonus') or 0):+.1f}"
            )
            out["reason"] = str(out.get("reason") or "") + extra
    return out
