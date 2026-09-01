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

VERSION = "neuro-shadow-tracker-v9.3.5"
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


def prediction_key(match: dict[str, Any], row: dict[str, Any]) -> str:
    match_id = match.get("match_id") or match.get("id") or f"{match.get('p1')}|{match.get('p2')}|{match.get('scheduled_time')}"
    return "|".join(
        str(x or "")
        for x in (
            match_id,
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
                "match_id": match.get("match_id") or match.get("id"),
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
                "tracker_version": VERSION,
                "mode": MODE,
                "operator_playable": False,
                "production_influence": False,
                "playable_influence": False,
                "created_at": created_at,
                "settlement": None,
            }
        )
    return out


def settle_prediction(
    prediction: dict[str, Any],
    final: dict[str, Any],
    *,
    settled_at: str | None = None,
) -> dict[str, Any]:
    """Settle one registered prediction using the shared tennis settlement rules."""
    row = dict(prediction)
    signal = {
        "market": row.get("market"),
        "pick": row.get("pick"),
        "line": row.get("line"),
        "player": row.get("player"),
    }
    status = settle_signal_live(signal, final)
    row["settlement"] = status
    row["settled_at"] = settled_at or datetime.now(timezone.utc).isoformat()
    values = _row_metrics(row)
    if values is not None:
        brier, log_loss = values
        row["target"] = 1.0 if status == "hit" else 0.0
        row["brier"] = brier
        row["log_loss"] = log_loss
    else:
        row.pop("target", None)
        row.pop("brier", None)
        row.pop("log_loss", None)
    return row


def _group_key(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    return "|".join(str(row.get(field) or "unknown") for field in fields)


def summarize(rows: list[dict[str, Any]], *, calibration_bins: int = 10) -> dict[str, Any]:
    """Compute non-leaky metrics from settled hit/miss rows only.

    Metrics are recomputed from immutable probability + settlement rather than
    trusting cached metric fields. VOID and unverifiable rows stay visible in
    counts but never enter Brier, log-loss, accuracy or calibration denominators.
    """
    all_rows = [row for row in rows or [] if isinstance(row, dict)]
    scored = [
        row for row in all_rows
        if row.get("settlement") in SCORED_STATUSES and _prob(row.get("probability")) is not None
    ]

    def metrics(group: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(group)
        if not n:
            return {"n": 0, "accuracy": None, "brier": None, "log_loss": None}
        hits = sum(1 for row in group if row.get("settlement") == "hit")
        pairs = [_row_metrics(row) for row in group]
        pairs = [pair for pair in pairs if pair is not None]
        if not pairs:
            return {"n": 0, "accuracy": None, "brier": None, "log_loss": None}
        return {
            "n": n,
            "accuracy": hits / n,
            "brier": sum(pair[0] for pair in pairs) / n,
            "log_loss": sum(pair[1] for pair in pairs) / n,
        }

    bins = max(2, int(calibration_bins))
    calibration = []
    for idx in range(bins):
        lo, hi = idx / bins, (idx + 1) / bins
        bucket = []
        for row in scored:
            p = float(row["probability"])
            if (lo <= p < hi) or (idx == bins - 1 and lo <= p <= hi):
                bucket.append(row)
        if not bucket:
            continue
        calibration.append(
            {
                "from": lo,
                "to": hi,
                "n": len(bucket),
                "mean_probability": sum(float(row["probability"]) for row in bucket) / len(bucket),
                "hit_rate": sum(1 for row in bucket if row.get("settlement") == "hit") / len(bucket),
            }
        )

    by_market: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_surface: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_source_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scored:
        by_market[_group_key(row, ("market",))].append(row)
        by_surface[_group_key(row, ("surface",))].append(row)
        by_source_model[_group_key(row, ("source_model",))].append(row)

    status_counts = defaultdict(int)
    for row in all_rows:
        status_counts[str(row.get("settlement") or "pending")] += 1

    return {
        "version": VERSION,
        "mode": MODE,
        "production_influence": False,
        "playable_influence": False,
        "total": len(all_rows),
        "scored": len(scored),
        "status_counts": dict(status_counts),
        "overall": metrics(scored),
        "by_market": {key: metrics(group) for key, group in sorted(by_market.items())},
        "by_surface": {key: metrics(group) for key, group in sorted(by_surface.items())},
        "by_source_model": {key: metrics(group) for key, group in sorted(by_source_model.items())},
        "calibration": calibration,
    }
