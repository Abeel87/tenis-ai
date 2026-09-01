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


def _primary_gap_class(status: str, *, scored: int, pbp_required: bool, review_ready: bool) -> str:
    """Assign one exclusive current-state class so counts never double-count."""
    if scored > 0 or status == "EXISTING_SUPPORTED":
        return "SUPPORTED"
    if pbp_required or status == "PBP_GAP":
        return "PBP_GAP"
    if review_ready or status == "EXISTING_SHADOW_EVIDENCE":
        return "SHADOW_EVIDENCE"
    if "SETTLEMENT_GAP" in status:
        return "SETTLEMENT_GAP"
    if "MAPPING_GAP" in status:
        return "MAPPING_GAP"
    if status.startswith("TRUE_NEURO_CANDIDATE"):
        return "TRUE_NEURO_CANDIDATE"
    return "UNASSIGNED"


def _next_action(gap_class: str) -> str:
    return {
        "SUPPORTED": "KEEP_BASELINE_AND_COMPARE_NEURO_SHADOW",
        "PBP_GAP": "COLLECT_OR_MAP_PBP_STATE_EVIDENCE",
        "SHADOW_EVIDENCE": "REVIEW_EXISTING_SHADOW_BEFORE_NEW_MODEL",
        "SETTLEMENT_GAP": "FIX_OR_MATURE_EXACT_LINE_SETTLEMENT",
        "MAPPING_GAP": "WIRE_EXISTING_MODEL_FAMILY_TO_CANONICAL_MARKET",
        "TRUE_NEURO_CANDIDATE": "COLLECT_SAMPLE_THEN_TRAIN_NEURAL_SPECIALIST",
        "UNASSIGNED": "MANUAL_CLASSIFICATION_REQUIRED",
    }[gap_class]


def _priority_score(*, unscored: int, gap_class: str, review_ready: bool, settled: int) -> int:
    """Audit triage only; higher means more useful to work on first."""
    base = min(max(int(unscored), 0), 5000)
    class_bonus = {
        "SHADOW_EVIDENCE": 4000,
        "MAPPING_GAP": 3000,
        "SETTLEMENT_GAP": 2500,
        "PBP_GAP": 1500,
        "TRUE_NEURO_CANDIDATE": 500,
        "UNASSIGNED": 0,
        "SUPPORTED": -5000,
    }[gap_class]
    evidence_bonus = min(max(int(settled), 0), 500)
    if review_ready:
        evidence_bonus += 1500
    return base + class_bonus + evidence_bonus


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
        review_ready = bool(shadow.get("review_ready"))
        status = str(meta.get("coverage_status") or "UNASSIGNED")
        pbp_required = bool(meta.get("pbp_required"))
        gap_class = _primary_gap_class(
            status,
            scored=scored,
            pbp_required=pbp_required,
            review_ready=review_ready,
        )
        rows.append({
            "canonical_market": market,
            "family": meta.get("family"),
            "sources": list(meta.get("sources") or []),
            "coverage_status": status,
            "primary_gap_class": gap_class,
            "next_action": _next_action(gap_class),
            "priority_score": _priority_score(
                unscored=unscored,
                gap_class=gap_class,
                review_ready=review_ready,
                settled=settled,
            ),
            "neuro_eligible": bool(meta.get("neuro_eligible")),
            "pbp_required": pbp_required,
            "offered": offered,
            "scored": scored,
            "unscored": unscored,
            "coverage_pct": round(scored * 100.0 / offered, 2) if offered else None,
            "symphony_support_rows": support_rows,
            "candidate_captured": int(shadow.get("captured") or 0),
            "candidate_settled": settled,
            "candidate_accuracy": shadow.get("accuracy"),
            "candidate_brier": shadow.get("brier"),
            "candidate_review_ready": review_ready,
            "candidate_promotion_status": shadow.get("promotion_status"),
        })

    current_rows = [row for row in rows if row["offered"] > 0]
    exact_offer = sum(row["offered"] for row in current_rows)
    scored = sum(row["scored"] for row in current_rows)
    unscored = sum(row["unscored"] for row in current_rows)

    status_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    gap_counts: dict[str, int] = {}
    for row in current_rows:
        status_counts[row["coverage_status"]] = status_counts.get(row["coverage_status"], 0) + row["offered"]
        family_counts[row["family"]] = family_counts.get(row["family"], 0) + row["offered"]
        gap = row["primary_gap_class"]
        gap_counts[gap] = gap_counts.get(gap, 0) + row["unscored"]

    priority = sorted(
        [row for row in current_rows if row["unscored"] > 0],
        key=lambda row: (-row["priority_score"], -row["unscored"], row["canonical_market"]),
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
            "exclusive_unscored_by_gap_class": dict(sorted(gap_counts.items())),
            "status_offer_counts": dict(sorted(status_counts.items())),
            "family_offer_counts": dict(sorted(family_counts.items())),
        },
        "priority_queue": [
            {
                "canonical_market": row["canonical_market"],
                "family": row["family"],
                "unscored": row["unscored"],
                "primary_gap_class": row["primary_gap_class"],
                "next_action": row["next_action"],
                "priority_score": row["priority_score"],
            }
            for row in priority
        ],
        "markets": rows,
    }


if __name__ == "__main__":  # manual audit helper only
    print(json.dumps(build_audit(), ensure_ascii=False, indent=2))