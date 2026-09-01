from __future__ import annotations

"""NEURO SHADOW prediction registry, settlement and scoring metrics.

This module is deliberately isolated from production generation. It provides
pure helpers for recording SHADOW predictions, settling them with the shared
settlement contract and computing calibration metrics later.
"""

import copy
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from backend.signal_settlement import settle_signal_live

VERSION = "neuro-shadow-tracker-v9.3.15"
MODE = "SHADOW"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False

SCORED_STATUSES = {"hit", "miss"}
IGNORED_STATUSES = {"void", "unverifiable"}


def _prob(value: Any) -> float | None:
    try:
        p = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(p) or not 0.0 <= p <= 1.0:
        return None
    return p


def _row_metrics(row: dict[str, Any]) -> tuple[float, float] | None:
    p = _prob(row.get("probability"))
    status = row.get("settlement")
    if p is None or status not in SCORED_STATUSES:
        return None
    y = 1.0 if status == "hit" else 0.0
    brier = (p - y) ** 2
    eps = 1e-12
    pc = min(1.0 - eps, max(eps, p))
    log_loss = -(y * math.log(pc) + (1.0 - y) * math.log(1.0 - pc))
    return brier, log_loss


def _key_part(value: Any) -> str:
    """Serialize identity fields without collapsing valid falsy values like 0.0."""
    return "" if value is None else str(value)


def _match_id(match: dict[str, Any]) -> Any:
    """Preserve valid falsy IDs; only fall back when an ID is genuinely absent."""
    match_id = match.get("match_id")
    if match_id is not None:
        return match_id
    match_id = match.get("id")
    if match_id is not None:
        return match_id
    return f"{match.get('p1')}|{match.get('p2')}|{match.get('scheduled_time')}"


def prediction_key(match: dict[str, Any], row: dict[str, Any]) -> str:
    return "|".join(
        _key_part(x)
        for x in (
            _match_id(match),
            row.get("market"),
            row.get("pick"),
            row.get("line"),
            row.get("player"),
            row.get("source_market_id"),
            row.get("source_outcome_id"),
        )
    )


def register_predictions(
    match: dict[str, Any], rows: list[dict[str, Any]], *, created_at: str | None = None
) -> list[dict[str, Any]]:
    """Create immutable-style registry rows from already-adapted SHADOW output."""
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        p = _prob(row.get("probability"))
        if p is None or row.get("mode") != "SHADOW" or row.get("operator_playable") is not False:
            continue
        key = prediction_key(match, row)
        if key in seen:
            continue
        seen.add(key)
        feature_snapshot = row.get("feature_snapshot") if isinstance(row.get("feature_snapshot"), dict) else None
        out.append(
            {
                "prediction_key": key,
                "match_id": _match_id(match),
                "p1": match.get("p1") or match.get("participant1Name"),
                "p2": match.get("p2") or match.get("participant2Name"),
                "scheduled_time": match.get("scheduled_time") or match.get("start_time"),
                "surface": match.get("surface"),
                "tour": match.get("tour"),
                "market": row.get("market"),
                "pick": row.get("pick"),
                "line": row.get("line"),
                "player": row.get("player"),
                "probability": p,
                "probability_kind": row.get("probability_kind"),
                "feature_snapshot": copy.deepcopy(feature_snapshot) if feature_snapshot else None,
                "operator": row.get("operator") or "Superbet",
                "source_market_id": row.get("source_market_id"),
                "source_outcome_id": row.get("source_outcome_id"),
                "adapter_version": row.get("adapter_version"),
                "source_model": row.get("source_model"),
                "mode": MODE,
                "operator_playable": False,
                "production_influence": False,
                "playable_influence": False,
                "created_at": created_at,
                "settlement": None,
                "target": None,
                "settled_at": None,
                "brier": None,
                "log_loss": None,
            }
        )
    return out


def settle_prediction(
    row: dict[str, Any], final: dict[str, Any], *, settled_at: str | None = None
) -> dict[str, Any]:
    """Settle a stored SHADOW row without changing its original forecast fields."""
    out = copy.deepcopy(row)
    status = settle_signal_live(out, final)
    out["settlement"] = status
    out["settled_at"] = settled_at or datetime.now(timezone.utc).isoformat()
    if status in SCORED_STATUSES:
        out["target"] = 1.0 if status == "hit" else 0.0
        metrics = _row_metrics(out)
        if metrics:
            out["brier"], out["log_loss"] = metrics
    else:
        out["target"] = None
        out["brier"] = None
        out["log_loss"] = None
    return out


def _calibration(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bins: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        p = _prob(row.get("probability"))
        if p is None or row.get("settlement") not in SCORED_STATUSES:
            continue
        idx = min(9, int(p * 10))
        bins[idx].append(row)
    out = []
    for idx in range(10):
        bucket = bins.get(idx) or []
        if not bucket:
            continue
        probs = [_prob(row.get("probability")) for row in bucket]
        probs = [p for p in probs if p is not None]
        hits = sum(1 for row in bucket if row.get("settlement") == "hit")
        out.append({
            "from": idx / 10.0,
            "to": (idx + 1) / 10.0,
            "n": len(bucket),
            "avg_probability": sum(probs) / len(probs),
            "hit_rate": hits / len(bucket),
        })
    return out


def _metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if row.get("settlement") in SCORED_STATUSES and _prob(row.get("probability")) is not None]
    if not scored:
        return {"n": 0, "hits": 0, "misses": 0, "accuracy": None, "brier": None, "log_loss": None}
    hits = sum(1 for row in scored if row.get("settlement") == "hit")
    briers = [float(row["brier"]) for row in scored if row.get("brier") is not None]
    losses = [float(row["log_loss"]) for row in scored if row.get("log_loss") is not None]
    return {
        "n": len(scored),
        "hits": hits,
        "misses": len(scored) - hits,
        "accuracy": hits / len(scored),
        "brier": sum(briers) / len(briers) if briers else None,
        "log_loss": sum(losses) / len(losses) if losses else None,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return read-only evidence metrics; VOID/unverifiable never count as scored."""
    rows = [row for row in rows or [] if isinstance(row, dict)]
    scored = [row for row in rows if row.get("settlement") in SCORED_STATUSES]
    by_market: dict[str, dict[str, Any]] = {}
    for market in sorted({str(row.get("market") or "unknown") for row in rows}):
        subset = [row for row in rows if str(row.get("market") or "unknown") == market]
        by_market[market] = _metric_summary(subset)
    return {
        "version": VERSION,
        "mode": MODE,
        "total_predictions": len(rows),
        "scored": len(scored),
        "pending": sum(1 for row in rows if row.get("settlement") is None),
        "void": sum(1 for row in rows if row.get("settlement") == "void"),
        "unverifiable": sum(1 for row in rows if row.get("settlement") == "unverifiable"),
        "overall": _metric_summary(rows),
        "by_market": by_market,
        "calibration": _calibration(rows),
        "production_influence": False,
        "playable_influence": False,
    }
