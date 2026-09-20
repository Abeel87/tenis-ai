from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "prediction-ledger-shadow-v1"
MODE = "SHADOW_ONLY"
OWNER = "autolearn_v84"
POPULATION_ALL = "ALL"


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _prediction_id(row: dict[str, Any], producer_version: str) -> str:
    identity = {
        "schema_version": SCHEMA_VERSION,
        "match_key": row.get("match_key"),
        "candidate_key": row.get("candidate_key"),
        "scheduled_time": row.get("scheduled_time"),
        "producer_owner": OWNER,
        "producer_version": producer_version,
    }
    return "pred_" + _canonical_sha256(identity).split(":", 1)[1]


def _score(value: Any, owner: str, version: str) -> dict[str, Any]:
    if value is None:
        return {"available": False, "value": None, "owner": owner, "version": version}
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"invalid frozen score for {owner}")
    return {
        "available": True,
        "value": round(float(value), 12),
        "owner": owner,
        "version": version,
    }


def _readiness_reference(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        key: value.get(key)
        for key in (
            "mode", "available", "status", "reason", "generated_at",
            "results_snapshot_contract", "results_snapshot_sha256",
        )
        if key in value
    }


def capture_rows(
    current_rows: list[dict[str, Any]],
    current_probs: list[Any],
    catboost_probs: list[Any],
    tabpfn_probs: list[Any],
    *,
    now: datetime,
    producer_version: str = "v8.4B",
    readiness_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not (len(current_rows) == len(current_probs) == len(catboost_probs) == len(tabpfn_probs)):
        raise ValueError("prediction arrays must align exactly")
    captured_at = _parse_dt(now)
    if captured_at is None:
        raise ValueError("capture time must be valid")
    out: list[dict[str, Any]] = []
    for index, row in enumerate(current_rows):
        scheduled = _parse_dt(row.get("scheduled_time"))
        if scheduled is None or captured_at >= scheduled:
            continue
        match_key = str(row.get("match_key") or "").strip()
        candidate = str(row.get("candidate_key") or "").strip()
        if not match_key or not candidate:
            continue
        context = {k: v for k, v in row.items() if k != "target"}
        item = {
            "schema_version": SCHEMA_VERSION,
            "prediction_id": _prediction_id(row, producer_version),
            "mode": MODE,
            "capture_stage": "PRE_SELECTION",
            "population_tags": [POPULATION_ALL],
            "match_key": match_key,
            "candidate_identity": candidate,
            "candidate_key": candidate,
            "market": row.get("market"),
            "pick": row.get("pick"),
            "line": None if row.get("line") == -1 else row.get("line"),
            "scheduled_time": scheduled.isoformat(),
            "captured_at": captured_at.isoformat(),
            "producer": {"owner": OWNER, "version": producer_version},
            "score_semantics": "probability_0_1",
            "model_scores": {
                "current": _score(current_probs[index], "current_engine", "autolearn_calibrated_current"),
                "catboost": _score(catboost_probs[index], "catboost_autolearn", "catboost_v84"),
                "tabpfn": _score(tabpfn_probs[index], "tabpfn_challenger", "TabPFN-2_V2"),
            },
            "context_snapshot_sha256": _canonical_sha256(context),
            "context_snapshot_provenance": "autolearn_v84.current_rows_pre_selection",
            "readiness_snapshot": _readiness_reference(readiness_snapshot),
            "selection_facts": {
                "model_available": {
                    "current": current_probs[index] is not None,
                    "catboost": catboost_probs[index] is not None,
                    "tabpfn": tabpfn_probs[index] is not None,
                },
                "generator_selected": None,
                "playable": None,
                "symphony_selected": None,
                "ineed_selected": None,
            },
            "production_influence": False,
            "runtime_gating_enabled": False,
            "learning_consumer_enabled": False,
            "telemetry_consumer_enabled": False,
            "settlement_enabled": False,
            "settlement": {
                "key": f"{match_key}::{candidate}",
                "result": None, "source": None, "settled_at": None,
            },
            "immutable_after_match_start": True,
        }
        out.append(item)
    return out


def merge_ledger(existing: Any, captured: list[dict[str, Any]], *, now: datetime) -> dict[str, Any]:
    if isinstance(existing, dict) and existing and existing.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("prediction ledger schema mismatch")
    prior_rows = existing.get("rows") if isinstance(existing, dict) else []
    prior_rows = prior_rows if isinstance(prior_rows, list) else []
    by_id: dict[str, dict[str, Any]] = {}
    for row in prior_rows:
        if not isinstance(row, dict) or not row.get("prediction_id"):
            continue
        prediction_id = str(row["prediction_id"])
        if prediction_id in by_id:
            raise ValueError("duplicate prediction_id in existing ledger")
        by_id[prediction_id] = row
    added = 0
    for row in captured:
        prediction_id = str(row.get("prediction_id") or "")
        if not prediction_id or prediction_id in by_id:
            continue
        by_id[prediction_id] = row
        added += 1
    rows = sorted(by_id.values(), key=lambda r: (str(r.get("scheduled_time")), str(r.get("prediction_id"))))
    available_counts = {
        name: sum(1 for row in rows if ((row.get("model_scores") or {}).get(name) or {}).get("available") is True)
        for name in ("current", "catboost", "tabpfn")
    }
    common_count = sum(
        1 for row in rows
        if all(((row.get("model_scores") or {}).get(name) or {}).get("available") is True for name in ("current", "catboost", "tabpfn"))
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "generated_at": _parse_dt(now).isoformat() if _parse_dt(now) else None,
        "status": "SHADOW_ACTIVE",
        "population_contract": "ALL_SUPPORTED_PRE_SELECTION",
        "rows": rows,
        "summary": {
            "rows": len(rows), "captured_this_run": added,
            "population_counts": {"ALL": len(rows), "PLAYABLE": None, "SELECTED": None},
            "model_available_counts": available_counts,
            "common_current_catboost_tabpfn": common_count,
        },
        "production_influence": False,
        "learning_consumer_enabled": False,
        "telemetry_consumer_enabled": False,
        "auto_promote": False,
    }
