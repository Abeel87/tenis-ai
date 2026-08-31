from __future__ import annotations

"""Read-only NEURO market coverage audit.

Combines the canonical market registry with current Symphony2 and candidate-shadow
statistics. This module does not feed PLAYABLE, Symphony2, training, weights or
frontend runtime; it exists to make the mapping/evidence gap measurable before a
future neural SHADOW model is introduced.
"""

import json
from pathlib import Path

try:
    from .neuro_market_registry_v934 import MARKET_REGISTRY, VERSION as REGISTRY_VERSION, market_meta
except ImportError:  # pragma: no cover
    from neuro_market_registry_v934 import MARKET_REGISTRY, VERSION as REGISTRY_VERSION, market_meta

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"
SYMPHONY_STATS = DATA / "symphony2_stats.json"
CANDIDATE_STATS = DATA / "superbet_candidate_stats_v925.json"
VERSION = "neuro-market-audit-v9.3.4"


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def build_audit(symphony_stats: dict | None = None, candidate_stats: dict | None = None) -> dict:
    symphony_stats = symphony_stats if isinstance(symphony_stats, dict) else _read(SYMPHONY_STATS, {})
    candidate_stats = candidate_stats if isinstance(candidate_stats, dict) else _read(CANDIDATE_STATS, {})

    offer = ((symphony_stats.get("current_offer") or {}).get("probability_diagnostics") or {})
    per_market = offer.get("per_market") or {}
    candidate_by_market = candidate_stats.get("by_market") or {}

    rows = []
    all_markets = sorted(set(MARKET_REGISTRY) | set(per_market) | set(candidate_by_market))
    for market in all_markets:
        meta = market_meta(market)
        current = per_market.get(market) if isinstance(per_market.get(market), dict) else {}
        shadow = candidate_by_market.get(market) if isinstance(candidate_by_market.get(market), dict) else {}
        offered = int(current.get("offered_selections") or 0)
        scored = int(current.get("scored_selections") or 0)
        unscored = int(current.get("unscored_zero_support") or 0)
        support_rows = int(current.get("support_rows") or 0)
        settled = int(shadow.get("settled") or 0)
        rows.append({
            "canonical_market": market,
            "family": meta.get("family"),
            "sources": list(meta.get("sources") or []),
            "coverage_status": meta.get("coverage_status"),
            "neuro_eligible": bool(meta.get("neuro_eligible")),
            "pbp_required": bool(meta.get("pbp_required")),
            "offered": offered,
            "scored": scored,
            "unscored": unscored,
            "coverage_pct": round(scored * 100.0 / offered, 2) if offered else None,
            "symphony_support_rows": support_rows,
            "candidate_captured": int(shadow.get("captured") or 0),
            "candidate_settled": settled,
            "candidate_accuracy": shadow.get("accuracy"),
            "candidate_brier": shadow.get("brier"),
            "candidate_review_ready": bool(shadow.get("review_ready")),
            "candidate_promotion_status": shadow.get("promotion_status"),
        })

    current_rows = [row for row in rows if row["offered"] > 0]
    exact_offer = sum(row["offered"] for row in current_rows)
    scored = sum(row["scored"] for row in current_rows)
    unscored = sum(row["unscored"] for row in current_rows)

    status_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    for row in current_rows:
        status_counts[row["coverage_status"]] = status_counts.get(row["coverage_status"], 0) + row["offered"]
        family_counts[row["family"]] = family_counts.get(row["family"], 0) + row["offered"]

    mapping_gap = sum(
        row["unscored"] for row in current_rows
        if "MAPPING_GAP" in str(row["coverage_status"] or "")
    )
    evidence_gap = sum(
        row["unscored"] for row in current_rows
        if "SETTLEMENT_GAP" in str(row["coverage_status"] or "")
        or row["coverage_status"] == "EXISTING_SHADOW_EVIDENCE"
    )
    pbp_gap = sum(row["unscored"] for row in current_rows if row["coverage_status"] == "PBP_GAP")
    true_neuro = sum(
        row["unscored"] for row in current_rows
        if str(row["coverage_status"] or "").startswith("TRUE_NEURO_CANDIDATE")
    )

    return {
        "version": VERSION,
        "registry_version": REGISTRY_VERSION,
        "contract": {
            "read_only": True,
            "production_influence": False,
            "playable_influence": False,
            "symphony_prod_influence": False,
        },
        "summary": {
            "exact_operator_selections": exact_offer,
            "scored": scored,
            "unscored": unscored,
            "coverage_pct": round(scored * 100.0 / exact_offer, 2) if exact_offer else None,
            "mapping_gap_unscored": mapping_gap,
            "evidence_gap_unscored": evidence_gap,
            "pbp_gap_unscored": pbp_gap,
            "true_neuro_candidate_unscored": true_neuro,
            "status_offer_counts": dict(sorted(status_counts.items())),
            "family_offer_counts": dict(sorted(family_counts.items())),
        },
        "markets": rows,
    }


if __name__ == "__main__":  # manual audit helper only
    print(json.dumps(build_audit(), ensure_ascii=False, indent=2))
