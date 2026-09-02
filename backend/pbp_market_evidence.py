from __future__ import annotations

"""Granular PBP / Early Hold market evidence.

The legacy ``early_hold_v7.ready`` contract intentionally stays strict: it means
that the complete EHS path is available for both players.  This module adds an
independent per-market evidence layer so a missing third service game or game-6
checkpoint cannot unnecessarily hide evidence for earlier checkpoints.

This layer is descriptive / model-input evidence only.  It does not overwrite
Current, CatBoost, TabPFN, Adaptive PROD, Superbet PLAYABLE or Symphony scores.
"""

from typing import Any

VERSION = "v9.4.0-pbp-market-evidence"
MIN_MARKET_MATCHES = 5


def _num(value: Any, default=None):
    try:
        x = float(value)
        return x if x == x else default
    except (TypeError, ValueError):
        return default


def _metric(profile: dict, key: str, window: str = "5") -> dict:
    tendencies = profile.get("pbp_tendencies") or {}
    all_windows = tendencies.get("all") or {}
    metrics = (all_windows.get(str(window)) or {}).get("metrics") or {}
    row = metrics.get(key) or {}
    n = int(_num(row.get("n"), 0) or 0)
    pct = _num(row.get("pct"))
    return {
        "n": n,
        "pct": round(pct, 1) if pct is not None else None,
        "ready": bool(n >= MIN_MARKET_MATCHES and pct is not None),
    }


def _pair(p1: dict, p2: dict, key: str) -> dict:
    a, b = _metric(p1, key), _metric(p2, key)
    ready = bool(a["ready"] and b["ready"])
    return {
        "ready": ready,
        "p1": a,
        "p2": b,
        "sample_floor": min(a["n"], b["n"]),
        "evidence_mean_pct": round((a["pct"] + b["pct"]) / 2.0, 1) if ready else None,
    }


def _winner_pair(p1: dict, p2: dict) -> dict:
    a, b = _metric(p1, "set1_win"), _metric(p2, "set1_win")
    ready = bool(a["ready"] and b["ready"])
    if not ready:
        return {"ready": False, "p1": a, "p2": b, "sample_floor": min(a["n"], b["n"])}
    # Two independent historical rates are evidence, not a calibrated market P.
    # Normalising them makes the directional comparison readable without claiming
    # this is the production probability used by any model.
    pa, pb = max(0.0, a["pct"]), max(0.0, b["pct"])
    total = pa + pb
    if total <= 0:
        p1_share = p2_share = 50.0
    else:
        p1_share, p2_share = 100.0 * pa / total, 100.0 * pb / total
    return {
        "ready": True,
        "p1": a,
        "p2": b,
        "sample_floor": min(a["n"], b["n"]),
        "directional_share": {"p1": round(p1_share, 1), "p2": round(p2_share, 1)},
    }


def build_market_evidence(match: dict) -> dict:
    early = match.get("early_hold_v7") or {}
    p1 = early.get("p1") or {}
    p2 = early.get("p2") or {}

    service_holds = {}
    for service_no in (1, 2, 3):
        key = f"hold{service_no}"
        service_holds[str(service_no)] = {
            "p1": _metric(p1, key),
            "p2": _metric(p2, key),
        }
        service_holds[str(service_no)]["ready"] = bool(
            service_holds[str(service_no)]["p1"]["ready"]
            and service_holds[str(service_no)]["p2"]["ready"]
        )

    checkpoints = {
        "2": _pair(p1, p2, "after2_11"),
        "4": _pair(p1, p2, "after4_22"),
        "6": _pair(p1, p2, "after6_33"),
    }
    sequence = _pair(p1, p2, "sequence_11_22_33")
    set1_totals = {
        "8.5": _pair(p1, p2, "set1_over_8.5"),
        "9.5": _pair(p1, p2, "set1_over_9.5"),
    }
    set1_winner = _winner_pair(p1, p2)

    ready_markets = []
    if checkpoints["2"]["ready"]:
        ready_markets.append("game_state@2")
    if checkpoints["4"]["ready"]:
        ready_markets.append("game_state@4")
    if checkpoints["6"]["ready"]:
        ready_markets.append("game_state@6")
    if sequence["ready"]:
        ready_markets.append("game_state_sequence_1:1-2:2-3:3")
    for line, row in set1_totals.items():
        if row["ready"]:
            ready_markets.append(f"set1_total_over_{line}")
    if set1_winner["ready"]:
        ready_markets.append("set1_winner")
    for service_no, row in service_holds.items():
        if row["ready"]:
            ready_markets.append(f"service_hold_{service_no}")

    return {
        "version": VERSION,
        "mode": "EVIDENCE_ONLY",
        "legacy_full_ehs_ready": bool(early.get("ready")),
        "market_ready": bool(ready_markets),
        "min_matches_per_metric": MIN_MARKET_MATCHES,
        "ready_markets": ready_markets,
        "service_holds": service_holds,
        "game_state": checkpoints,
        "balanced_sequence": sequence,
        "set1_total": set1_totals,
        "set1_winner": set1_winner,
        "production_math_changed": False,
        "playable_influence": False,
        "symphony_prod_influence": False,
    }


def enrich_market_evidence(match: dict) -> dict:
    out = dict(match)
    early = dict(out.get("early_hold_v7") or {})
    if not early:
        return out
    evidence = build_market_evidence(out)
    early["market_evidence_v940"] = evidence
    early["market_ready"] = evidence["market_ready"]
    early["ready_markets"] = evidence["ready_markets"]
    out["early_hold_v7"] = early
    return out
