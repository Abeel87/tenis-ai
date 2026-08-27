from __future__ import annotations

"""Tenis AI v9.0C.4 helpers for Tennis Symphony.

Adds three-way serve comparison markets (P1 / draw / P2), coverage-first
ranking and automatic 2..6 leg-count intelligence. This module is additive and
does not write to PROD, Adaptive or SHADOW outputs.
"""

import math
from copy import deepcopy
from typing import Any, Callable

try:
    from .symphony_evidence_v90c import augment_match as augment_match_v90c
except ImportError:
    from symphony_evidence_v90c import augment_match as augment_match_v90c

VERSION = "v9.0C.4"
COMPARISON_MARKETS = {"most_aces", "most_double_faults", "most_aces_plus_df"}


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _poisson_pmf(mean: float) -> list[float]:
    """Finite Poisson PMF with enough tail coverage for tennis serve props."""
    mean = max(0.0, float(mean))
    if mean == 0.0:
        return [1.0]
    limit = max(24, int(math.ceil(mean + 10.0 * math.sqrt(mean + 1.0) + 12.0)))
    values = [math.exp(-mean)]
    for k in range(1, limit + 1):
        values.append(values[-1] * mean / k)
    z = sum(values)
    return [v / z for v in values] if z > 0 else [1.0]


def three_way_poisson(mean_a: float, mean_b: float) -> dict[str, float]:
    """P(A>B), P(A=B), P(B>A) for independent Poisson counts.

    This is explicitly an evidence approximation for serve-comparison markets;
    it is not promoted to exact match-path joint probability.
    """
    pa = _poisson_pmf(mean_a)
    pb = _poisson_pmf(mean_b)
    n = max(len(pa), len(pb))
    pa += [0.0] * (n - len(pa))
    pb += [0.0] * (n - len(pb))

    cdf_b = []
    running = 0.0
    for v in pb:
        running += v
        cdf_b.append(running)

    a_win = sum(pa[k] * (cdf_b[k - 1] if k > 0 else 0.0) for k in range(n))
    draw = sum(pa[k] * pb[k] for k in range(n))
    b_win = max(0.0, 1.0 - a_win - draw)
    z = a_win + draw + b_win
    if z <= 0:
        return {"p1": 1 / 3, "draw": 1 / 3, "p2": 1 / 3}
    return {"p1": a_win / z, "draw": draw / z, "p2": b_win / z}


def _market_mean(props: dict, side: str, field: str):
    block = ((props.get(side) or {}).get(field) or {})
    if block.get("ready") is False:
        return None
    return _num(block.get("mean"))


def _comparison_signal(market: str, pick: str, label: str, probability: float) -> dict:
    pct = max(0.0, min(100.0, 100.0 * float(probability)))
    return {
        "key": f"{market}|{pick}",
        "market": market,
        "pick": pick,
        "label": label,
        "score": round(pct, 3),
        "symphony_raw_probability": round(pct, 4),
        "symphony_market_adapter": VERSION,
        "symphony_source": "serve_props_v72_compare",
        "symphony_approximation": "independent_poisson_comparison",
        "exact_path_supported": False,
    }


def serve_comparison_signals(match: dict) -> list[dict]:
    props = match.get("serve_props_v72") or {}
    if not isinstance(props, dict) or not props.get("ready"):
        return []

    p1 = str(match.get("p1") or "P1")
    p2 = str(match.get("p2") or "P2")
    ace1, ace2 = _market_mean(props, "p1", "aces"), _market_mean(props, "p2", "aces")
    df1, df2 = _market_mean(props, "p1", "double_faults"), _market_mean(props, "p2", "double_faults")

    rows: list[dict] = []

    def add_family(market: str, title: str, mean1, mean2):
        if mean1 is None or mean2 is None:
            return
        probs = three_way_poisson(mean1, mean2)
        rows.extend([
            _comparison_signal(market, p1, f"{title} · {p1}", probs["p1"]),
            _comparison_signal(market, "draw", f"{title} · remis", probs["draw"]),
            _comparison_signal(market, p2, f"{title} · {p2}", probs["p2"]),
        ])

    add_family("most_aces", "Najwięcej asów", ace1, ace2)
    add_family("most_double_faults", "Najwięcej podwójnych błędów", df1, df2)
    if None not in (ace1, ace2, df1, df2):
        add_family("most_aces_plus_df", "Najwięcej asów + podwójnych błędów", ace1 + df1, ace2 + df2)
    return rows


def augment_match_c4(match: dict) -> tuple[dict, dict]:
    """Extend v9.0C evidence with serve-comparison families."""
    cloned, meta = augment_match_v90c(match)
    cloned = deepcopy(cloned)
    auto = dict(cloned.get("autolearn_v84") or {})
    existing = [dict(x) for x in (auto.get("signals") or []) if isinstance(x, dict)]
    signatures = {
        (str(x.get("market") or ""), str(x.get("pick") or "").casefold())
        for x in existing
    }

    added = []
    for row in serve_comparison_signals(match):
        sig = (str(row.get("market") or ""), str(row.get("pick") or "").casefold())
        if sig in signatures:
            continue
        signatures.add(sig)
        existing.append(row)
        added.append(row)

    auto["signals"] = existing
    cloned["autolearn_v84"] = auto

    meta = dict(meta)
    meta["version"] = VERSION
    meta["catalog_size"] = int(meta.get("catalog_size") or 0) + len(added)
    meta["composer_added"] = int(meta.get("composer_added") or 0) + len(added)
    families = dict(meta.get("families") or {})
    by_key = dict(meta.get("by_key") or {})
    for row in added:
        families[row["market"]] = int(families.get(row["market"]) or 0) + 1
        by_key[row["key"]] = row
    meta["families"] = families
    meta["by_key"] = by_key
    meta["serve_comparison_added"] = len(added)
    return cloned, meta


def coverage_first_metrics(base_metrics: Callable):
    """Wrap the v9.0B scorer so unsupported evidence cannot dominate exact paths."""
    def metrics(match, combo, outcomes):
        out = dict(base_metrics(match, combo, outcomes))
        coverage = float(out.get("path_coverage") or 0.0)
        supported = int(out.get("supported_legs") or 0)
        joint = out.get("joint_supported_only")
        score = float(out.get("score") or 0.0)

        # Real-data v9.0C showed 0%-coverage serve props winning at ~90/100.
        # Penalise missing common-path support while preserving evidence-only
        # candidates as alternatives instead of pretending they are exact joint.
        adjustment = -28.0 * (1.0 - coverage)
        if coverage >= 0.999:
            adjustment += 5.0
        elif coverage >= 0.75:
            adjustment += 2.0
        if supported >= 2 and joint is not None:
            adjustment += 2.0
        out["coverage_adjustment"] = round(adjustment, 4)
        out["score"] = max(0.0, min(100.0, score + adjustment))
        return out
    return metrics


def comparison_compatible(base_compatible: Callable):
    """Comparison markets are mutually exclusive P1/draw/P2 families."""
    def compatible(a, b):
        if not base_compatible(a, b):
            return False
        if a.market == b.market and a.market in COMPARISON_MARKETS:
            return False
        return True
    return compatible


def leg_count_intelligence(match_row: dict) -> dict:
    """Rank 2..6 leg compositions without blindly defaulting to two legs."""
    comps = match_row.get("compositions") or {}
    options = []
    for legs in range(2, 7):
        comp = comps.get(str(legs))
        if not isinstance(comp, dict):
            continue
        score = float(comp.get("symphony_score") or 0.0)
        coverage = float(comp.get("path_coverage") or 0.0)
        joint = _num(comp.get("joint_probability"))
        frag_rows = comp.get("fragility") or []
        fragility = _num((frag_rows[0] or {}).get("fragility"), 0.0) if frag_rows else 0.0
        options.append({
            "legs": legs,
            "symphony_score": round(score, 2),
            "path_coverage": round(coverage, 3),
            "joint_probability": joint,
            "fragility": round(float(fragility or 0.0), 2),
        })

    if not options:
        return {"recommended": None, "mode": "NO_DATA", "options": []}

    best_score = max(x["symphony_score"] for x in options)
    eligible = []
    for row in options:
        score = row["symphony_score"]
        coverage = row["path_coverage"]
        fragility = row["fragility"]
        score_drop = max(0.0, best_score - score)
        collapse_penalty = max(0.0, score_drop - 6.0) * 1.35
        coverage_penalty = 0.0 if coverage >= 0.75 else (8.0 if coverage >= 0.5 else 18.0)
        richness_bonus = 2.6 * (row["legs"] - 2)
        joint_bonus = min(5.0, float(row["joint_probability"] or 0.0) / 15.0) if row["joint_probability"] is not None else 0.0
        utility = score + 14.0 * coverage + richness_bonus + joint_bonus - 0.12 * fragility - collapse_penalty - coverage_penalty
        row["auto_utility"] = round(utility, 2)
        row["score_drop_from_best"] = round(score_drop, 2)
        row["eligible"] = bool(score >= 70.0 and coverage >= 0.5 and score_drop <= 14.0)
        if row["eligible"]:
            eligible.append(row)

    pool = eligible or options
    recommended = max(pool, key=lambda x: (x.get("auto_utility", -999.0), x["legs"]))
    rec_legs = int(recommended["legs"])
    next_row = next((x for x in options if x["legs"] == rec_legs + 1), None)
    reason = (
        f"{rec_legs} zdarzenia: score {recommended['symphony_score']:.1f}, "
        f"coverage {recommended['path_coverage'] * 100:.0f}%"
    )
    if next_row:
        reason += (
            f"; {next_row['legs']}. noga zmienia score o "
            f"{next_row['symphony_score'] - recommended['symphony_score']:+.1f} "
            f"i coverage o {(next_row['path_coverage'] - recommended['path_coverage']) * 100:+.0f} pp"
        )

    return {
        "version": VERSION,
        "recommended": rec_legs,
        "mode": "CURRENT_MATCH_MATH",
        "historical_learning_active": False,
        "reason": reason,
        "options": options,
    }
