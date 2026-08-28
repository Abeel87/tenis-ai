from __future__ import annotations

"""Tenis AI v9.3B — settlement/statistics for deep MODEL/RAW Symphony.

This tracker is deliberately separate from ``symphony_tracker_v90d``.  The old
tracker keeps its existing operator-aware learning history; this file observes
the new v9.3A MODEL/RAW lattice only and never feeds PROD, SHADOW, PLAYABLE or
AUTO learning.

Rules:
- freeze the latest strictly pre-match deep Symphony snapshot;
- settle every 2..6-leg composition against the canonical scenario feed;
- reuse the old settlement rules where possible and the canonical signal
  settlement rules for the newly mapped v9.2.4 families;
- second-set checkpoint markets stay UNKNOWN until real PBP settlement exists;
- publish separate MODEL/RAW statistics, market-family accuracy and joint
  calibration; never mix them with Superbet PLAYABLE accuracy.
"""

from collections import defaultdict
from datetime import datetime, timezone
import json
import math

try:
    from . import symphony_tracker_v90d as base
    from .signal_settlement import settle_signal
except ImportError:
    import symphony_tracker_v90d as base
    from signal_settlement import settle_signal

VERSION = "v9.3B"
MODE = "MODEL_RAW_DEEP_STATS_ONLY"
REPORT_PATH = base.OUT / "symphony_model_v93.json"
HISTORY_PATH = base.OUT / "symphony_model_history_v93.json"
STATS_PATH = base.OUT / "symphony_model_stats_v93.json"
SETTLEMENT_PATH = base.SETTLEMENT_PATH
META_PATH = base.META_PATH

# Capture the legacy evaluator before _settle_deep temporarily patches the
# module-level function used by v9.0D. Calling base.evaluate_leg from inside the
# wrapper after that patch would recurse into this wrapper forever.
LEGACY_EVALUATE_LEG = base.evaluate_leg

PBP_ONLY_MARKETS = {"set2_game_state"}
FINAL_SCORE_FAMILIES = {
    "any_set_to_nil",
    "set2_exact_score",
    "exact_sets",
    "match_games_parity",
    "set1_games_parity",
    "set2_games_parity",
    "p1_exactly_1_set",
    "p1_exactly_2_sets",
    "p2_exactly_1_set",
    "p2_exactly_2_sets",
    "p1_wins_a_set",
    "p2_wins_a_set",
    "set_handicap",
}


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def evaluate_model_leg(leg: dict, actual: dict, p1: str, p2: str):
    """Extend v9.0D settlement without guessing unavailable path evidence."""
    existing = LEGACY_EVALUATE_LEG(leg, actual, p1, p2)
    if existing is not None:
        return existing

    market = base._canonical_market(leg.get("market"))
    if market in PBP_ONLY_MARKETS:
        # Final set score does not reconstruct a checkpoint after 2/4/6 games.
        return None

    final = dict(actual or {})
    final.setdefault("p1", p1)
    final.setdefault("p2", p2)
    verdict = settle_signal(dict(leg), final)
    if verdict == "hit":
        return True
    if verdict == "miss":
        return False
    # void / unverifiable remains UNKNOWN in a multi-leg Symphony. This is more
    # conservative than pretending a push/absent market was a win or a miss.
    return None


def _settle_deep(history: dict, feed: dict, now: datetime):
    old = base.evaluate_leg
    base.evaluate_leg = evaluate_model_leg
    try:
        return base.settle(history, feed, now)
    finally:
        base.evaluate_leg = old


def _ratio(hits: int, n: int):
    return round(100.0 * hits / n, 3) if n else None


def _sample(n: int) -> str:
    if n >= 100:
        return "strong"
    if n >= 40:
        return "medium"
    if n >= 15:
        return "small"
    return "tiny"


def _extra_stats(history: dict) -> dict:
    markets = defaultdict(lambda: {
        "resolved": 0,
        "hits": 0,
        "unknown": 0,
        "evidence": [],
        "path": [],
    })
    stories = defaultdict(lambda: {
        "full_n": 0,
        "full_hits": 0,
        "resolved": 0,
        "hits": 0,
    })
    calibration = defaultdict(lambda: {
        "n": 0,
        "hits": 0,
        "predicted": [],
    })

    for row in history.get("matches") or []:
        if str(row.get("status") or "") != "settled":
            continue
        try:
            rec = int(row.get("recommended_leg_count") or 0)
        except (TypeError, ValueError):
            rec = 0
        if rec not in base.LEG_COUNTS:
            continue

        key = str(rec)
        comp = (row.get("compositions") or {}).get(key)
        result = (((row.get("settlement") or {}).get("compositions") or {}).get(key))
        if not isinstance(comp, dict) or not isinstance(result, dict):
            continue

        selected = [x for x in (comp.get("selection") or []) if isinstance(x, dict)]
        details = [x for x in (result.get("legs_detail") or []) if isinstance(x, dict)]
        for idx, leg in enumerate(selected):
            market = base._canonical_market(leg.get("market")) or "unknown"
            bucket = markets[market]
            detail = details[idx] if idx < len(details) else {}
            verdict = str(detail.get("result") or "unknown")
            if verdict in {"hit", "miss"}:
                bucket["resolved"] += 1
                bucket["hits"] += int(verdict == "hit")
            else:
                bucket["unknown"] += 1
            evidence = _num(leg.get("evidence_score"))
            if evidence is not None:
                bucket["evidence"].append(evidence)
            path = _num(leg.get("path_probability"))
            if path is not None:
                bucket["path"].append(path)

        story = str(comp.get("story_type") or "UNKNOWN")
        s = stories[story]
        s["resolved"] += int(result.get("resolved_legs") or 0)
        s["hits"] += int(result.get("hit_legs") or 0)
        if result.get("fully_resolved"):
            s["full_n"] += 1
            full_hit = result.get("full_result") == "hit"
            s["full_hits"] += int(full_hit)

            joint = _num(comp.get("joint_probability"))
            if joint is not None:
                joint = max(0.0, min(100.0, joint))
                low = int(joint // 10) * 10
                if low >= 100:
                    low = 90
                label = f"{low}-{low + 10}%"
                c = calibration[label]
                c["n"] += 1
                c["hits"] += int(full_hit)
                c["predicted"].append(joint)

    by_market = []
    for market, b in markets.items():
        resolved = int(b["resolved"])
        by_market.append({
            "market": market,
            "resolved": resolved,
            "hits": int(b["hits"]),
            "unknown": int(b["unknown"]),
            "accuracy": _ratio(int(b["hits"]), resolved),
            "avg_evidence_score": round(sum(b["evidence"]) / len(b["evidence"]), 3) if b["evidence"] else None,
            "avg_path_probability": round(sum(b["path"]) / len(b["path"]), 3) if b["path"] else None,
            "sample": _sample(resolved),
        })
    by_market.sort(key=lambda x: (x["resolved"], x.get("accuracy") or 0.0), reverse=True)

    auto_stories = []
    for story, b in stories.items():
        auto_stories.append({
            "story_type": story,
            "full_settled": int(b["full_n"]),
            "full_hit_rate": _ratio(int(b["full_hits"]), int(b["full_n"])),
            "resolved_legs": int(b["resolved"]),
            "leg_accuracy": _ratio(int(b["hits"]), int(b["resolved"])),
        })
    auto_stories.sort(key=lambda x: (x["full_settled"], x["resolved_legs"]), reverse=True)

    calibration_rows = []
    for label, b in calibration.items():
        avg_pred = sum(b["predicted"]) / len(b["predicted"]) if b["predicted"] else None
        observed = _ratio(int(b["hits"]), int(b["n"]))
        calibration_rows.append({
            "bucket": label,
            "n": int(b["n"]),
            "hits": int(b["hits"]),
            "avg_predicted_joint": round(avg_pred, 3) if avg_pred is not None else None,
            "observed_full_hit_rate": observed,
            "calibration_gap": round(observed - avg_pred, 3) if observed is not None and avg_pred is not None else None,
        })
    calibration_rows.sort(key=lambda x: int(str(x["bucket"]).split("-")[0]))

    return {
        "auto_market_accuracy": by_market,
        "auto_story_types": auto_stories,
        "joint_calibration": calibration_rows,
    }


def aggregate(history: dict, now: datetime) -> dict:
    stats = dict(base.aggregate(history, now))
    stats.update(_extra_stats(history))
    stats.update({
        "version": VERSION,
        "mode": MODE,
        "layer": "MODEL_RAW_DEEP",
        "source_report": REPORT_PATH.name,
        "history_file": HISTORY_PATH.name,
        "analysis_only": True,
        "operator_playable": False,
    })
    contract = dict(stats.get("learning_contract") or {})
    contract.update({
        "separate_from_superbet_playable": True,
        "observation_only": True,
        "feeds_existing_auto_learning": False,
        "prices_used": False,
        "external_requests": 0,
        "set2_game_state_requires_real_pbp": True,
        "final_score_candidate_families": sorted(FINAL_SCORE_FAMILIES),
    })
    stats["learning_contract"] = contract
    return stats


def run(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    report = base._read(REPORT_PATH, {})
    feed = base._read(SETTLEMENT_PATH, {})
    history = base._read(HISTORY_PATH, {})
    report = report if isinstance(report, dict) else {}
    feed = feed if isinstance(feed, dict) else {}
    history = history if isinstance(history, dict) else {}

    history, added, updated = base.capture(report, history, now)
    history["version"] = VERSION
    history["mode"] = MODE
    history["source_report"] = REPORT_PATH.name
    history["feeds_existing_auto_learning"] = False

    history, newly_settled, newly_void = _settle_deep(history, feed, now)
    stats = aggregate(history, now)
    base._write(HISTORY_PATH, history)
    base._write(STATS_PATH, stats)

    meta = base._read(META_PATH, {})
    meta = meta if isinstance(meta, dict) else {}
    meta["symphony_model_tracker_v93"] = {
        "version": VERSION,
        "updated_at": now.isoformat(),
        "snapshots": len(history.get("matches") or []),
        "settled": stats.get("settled_matches", 0),
        "pending": stats.get("pending_matches", 0),
        "separate_from_superbet_playable": True,
        "feeds_existing_auto_learning": False,
        "prices_used": False,
        "external_requests": 0,
    }
    base._write(META_PATH, meta)

    return {
        "status": "OK",
        "version": VERSION,
        "mode": MODE,
        "captured_new": added,
        "captured_updated": updated,
        "newly_settled": newly_settled,
        "newly_void": newly_void,
        "settled_total": stats.get("settled_matches", 0),
        "pending_total": stats.get("pending_matches", 0),
        "market_families_tracked": len(stats.get("auto_market_accuracy") or []),
        "production_influence": False,
        "playable_influence": False,
        "auto_learning_influence": False,
        "external_requests": 0,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
