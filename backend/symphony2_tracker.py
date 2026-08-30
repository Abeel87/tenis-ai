from __future__ import annotations

"""Symfonia 2.0 history, settlement and performance statistics.

The new Symphony starts its own performance history from zero. Historical
Superbet PLAYABLE rows are used only as an exact settlement source (and by the
learning module as training data); legacy Symphony outcomes are never imported.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"
CURRENT = DATA / "symphony2_current.json"
BASE_HISTORY = DATA / "history.json"
HISTORY = DATA / "symphony2_history.json"
STATS = DATA / "symphony2_stats.json"
VERSION = "symphony2-tracker-1"


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _pick(value: Any) -> str:
    raw = _norm(value)
    aliases = {
        "o": "over", "powyzej": "over", "więcej": "over", "wiecej": "over",
        "u": "under", "ponizej": "under", "mniej": "under",
        "tak": "yes", "nie": "no",
    }
    return aliases.get(raw, raw)


def _match_id(row: dict) -> str:
    value = row.get("match_id") if row.get("match_id") is not None else row.get("id")
    if value is not None and str(value) != "":
        return str(value)
    return "|".join((_norm(row.get("p1")), _norm(row.get("p2")), str(row.get("scheduled_time") or "")[:16]))


def selection_signature(match_id: str, row: dict) -> tuple:
    return (
        str(match_id),
        _norm(row.get("market")).replace(" ", "_"),
        _pick(row.get("pick")),
        _num(row.get("line")),
        _num(row.get("checkpoint")),
        _norm(row.get("player")),
    )


def _settled_operator_index(base_history: list[dict]) -> dict[tuple, str]:
    out: dict[tuple, str] = {}
    for entry in base_history or []:
        if not isinstance(entry, dict):
            continue
        mid = _match_id(entry)
        # Rich AutoLearn freeze first, then PROD fallback. Exact signature wins.
        layers = (
            entry.get("playable_autolearn_signals_v912"),
            entry.get("playable_signals_v912"),
        )
        for rows in layers:
            if not isinstance(rows, list):
                continue
            for signal in rows:
                if not isinstance(signal, dict):
                    continue
                result = _norm(signal.get("result"))
                if result not in {"hit", "miss", "void"}:
                    continue
                sig = selection_signature(mid, signal)
                out.setdefault(sig, result)
    return out


def _composition_id(match_id: str, comp: dict) -> str:
    legs = sorted(
        "|".join(map(str, selection_signature(match_id, row)))
        for row in comp.get("selection") or [] if isinstance(row, dict)
    )
    raw = f"{match_id}::{int(comp.get('legs') or len(legs))}::" + "||".join(legs)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def capture(current: dict, history_doc: dict) -> tuple[dict, int]:
    doc = dict(history_doc) if isinstance(history_doc, dict) else {}
    rows = [dict(x) for x in (doc.get("entries") or []) if isinstance(x, dict)]
    seen = {str(x.get("prediction_id")) for x in rows if x.get("prediction_id")}
    captured = 0
    now = datetime.now(timezone.utc).isoformat()

    for match in current.get("matches") or []:
        if not isinstance(match, dict):
            continue
        n = match.get("recommended_leg_count")
        comp = (match.get("compositions") or {}).get(str(n)) if n is not None else None
        if not isinstance(comp, dict) or not comp.get("selection"):
            continue
        mid = _match_id(match)
        pid = _composition_id(mid, comp)
        if pid in seen:
            continue
        legs = []
        valid = True
        for raw in comp.get("selection") or []:
            if not isinstance(raw, dict):
                valid = False
                break
            # Capturing an actionable 2.0 prediction requires operator evidence.
            if raw.get("fixture_line_verified") is False:
                valid = False
                break
            legs.append({
                "selection_id": raw.get("selection_id"),
                "market": raw.get("market"),
                "pick": raw.get("pick"),
                "line": raw.get("line"),
                "checkpoint": raw.get("checkpoint"),
                "player": raw.get("player"),
                "label": raw.get("label"),
                "probability": raw.get("operator_model_probability"),
                "fixture_line_verified": raw.get("fixture_line_verified"),
                "result": "pending",
            })
        if not valid or len(legs) < 2:
            continue
        rows.append({
            "prediction_id": pid,
            "version": VERSION,
            "engine_version": current.get("version"),
            "captured_at": now,
            "match_id": mid,
            "p1": match.get("p1"),
            "p2": match.get("p2"),
            "scheduled_time": match.get("scheduled_time"),
            "legs": int(comp.get("legs") or len(legs)),
            "score": comp.get("score"),
            "joint_probability": comp.get("joint_probability"),
            "joint_status": comp.get("joint_status"),
            "selection": legs,
            "result": "pending",
        })
        seen.add(pid)
        captured += 1

    doc.update({
        "version": VERSION,
        "created_from_legacy_symphony": False,
        "legacy_symphony_results_imported": False,
        "entries": rows,
    })
    return doc, captured


def settle(history_doc: dict, base_history: list[dict]) -> tuple[dict, int]:
    doc = dict(history_doc) if isinstance(history_doc, dict) else {"entries": []}
    index = _settled_operator_index(base_history)
    settled = 0
    rows = []
    for raw in doc.get("entries") or []:
        if not isinstance(raw, dict):
            continue
        entry = dict(raw)
        if entry.get("result") in {"hit", "miss", "void"}:
            rows.append(entry)
            continue
        mid = str(entry.get("match_id") or "")
        legs = []
        statuses = []
        for leg_raw in entry.get("selection") or []:
            if not isinstance(leg_raw, dict):
                continue
            leg = dict(leg_raw)
            status = index.get(selection_signature(mid, leg))
            if status:
                leg["result"] = status
            statuses.append(str(leg.get("result") or "pending"))
            legs.append(leg)
        entry["selection"] = legs
        non_void = [x for x in statuses if x != "void"]
        if non_void and all(x == "hit" for x in non_void) and all(x in {"hit", "void"} for x in statuses):
            entry["result"] = "hit"
            entry["settled_at"] = datetime.now(timezone.utc).isoformat()
            settled += 1
        elif any(x == "miss" for x in statuses):
            entry["result"] = "miss"
            entry["settled_at"] = datetime.now(timezone.utc).isoformat()
            settled += 1
        elif statuses and all(x == "void" for x in statuses):
            entry["result"] = "void"
            entry["settled_at"] = datetime.now(timezone.utc).isoformat()
            settled += 1
        rows.append(entry)
    doc["entries"] = rows
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return doc, settled


def performance_stats(history_doc: dict) -> dict:
    entries = [x for x in (history_doc.get("entries") or []) if isinstance(x, dict)]
    settled = [x for x in entries if x.get("result") in {"hit", "miss"}]
    hits = sum(1 for x in settled if x.get("result") == "hit")
    legs = [
        leg for entry in entries for leg in (entry.get("selection") or [])
        if isinstance(leg, dict) and leg.get("result") in {"hit", "miss"}
    ]
    leg_hits = sum(1 for x in legs if x.get("result") == "hit")
    by_legs = {}
    for n in range(2, 7):
        subset = [x for x in settled if int(x.get("legs") or 0) == n]
        h = sum(1 for x in subset if x.get("result") == "hit")
        by_legs[str(n)] = {
            "settled": len(subset), "hits": h, "misses": len(subset) - h,
            "accuracy": round(100.0 * h / len(subset), 2) if subset else None,
        }
    return {
        "history_version": VERSION,
        "predictions_total": len(entries),
        "predictions_pending": sum(1 for x in entries if x.get("result") == "pending"),
        "compositions_settled": len(settled),
        "compositions_hits": hits,
        "compositions_misses": len(settled) - hits,
        "composition_accuracy": round(100.0 * hits / len(settled), 2) if settled else None,
        "legs_settled": len(legs),
        "legs_hits": leg_hits,
        "legs_misses": len(legs) - leg_hits,
        "leg_accuracy": round(100.0 * leg_hits / len(legs), 2) if legs else None,
        "by_leg_count": by_legs,
        "legacy_symphony_stats_used": False,
    }


def run() -> dict:
    current = _read(CURRENT, {})
    base_history = _read(BASE_HISTORY, [])
    old_history = _read(HISTORY, {})
    if not isinstance(current, dict):
        raise RuntimeError("symphony2_current.json invalid")
    if not isinstance(base_history, list):
        raise RuntimeError("history.json invalid")

    history_doc, captured = capture(current, old_history)
    history_doc, settled = settle(history_doc, base_history)
    _write(HISTORY, history_doc)

    stats = _read(STATS, {})
    if not isinstance(stats, dict):
        stats = {}
    stats["performance"] = performance_stats(history_doc)
    stats["tracker_version"] = VERSION
    stats["updated_at"] = datetime.now(timezone.utc).isoformat()
    stats["legacy_symphony_stats_used"] = False
    _write(STATS, stats)

    return {
        "status": "OK", "version": VERSION,
        "captured": captured, "settled": settled,
        **stats["performance"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
