"""PBP profile-supply recovery contract.

This module intentionally does not alter production probabilities.  It provides a
small, deterministic helper for deciding whether an existing cached PBP profile
contains enough per-market observations to feed v9.4.0 granular evidence.
"""

MIN_OBSERVATIONS = 5


def metric_ready(metric: dict | None, minimum: int = MIN_OBSERVATIONS) -> bool:
    row = metric or {}
    try:
        n = int(row.get("n") or 0)
        pct = float(row.get("pct"))
    except (TypeError, ValueError):
        return False
    return n >= minimum and pct == pct


def profile_has_market_supply(profile: dict | None, minimum: int = MIN_OBSERVATIONS) -> bool:
    profile = profile or {}
    windows = ((profile.get("pbp_tendencies") or {}).get("all") or {})
    metrics = ((windows.get("5") or {}).get("metrics") or {})
    keys = (
        "hold1", "hold2", "hold3",
        "after2_11", "after4_22", "after6_33",
        "sequence_11_22_33", "set1_over_8.5", "set1_over_9.5", "set1_win",
    )
    return any(metric_ready(metrics.get(key), minimum) for key in keys)
