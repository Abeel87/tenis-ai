from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
HISTORY_PATH = OUT / "history.json"
PBP_HISTORY_PATH = OUT / "pbp_history.json"
OUTPUT_PATH = OUT / "scenario_results_v83c.json"
META_PATH = OUT / "meta.json"
VERSION = "v8.3C"
KEEP_DAYS = 120


def _read_json(path: Path, fallback):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _dt(value):
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _match_id(entry):
    value = entry.get("match_id")
    if value is None:
        key = str(entry.get("match_key") or "")
        if key.startswith("id:"):
            value = key[3:]
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _base_outcome(entry: dict) -> dict | None:
    result = entry.get("result") or {}
    status = str(entry.get("status") or "").lower()
    result_status = str(result.get("status") or "").lower()
    if status not in ("settled", "void", "retired") and result_status not in ("completed", "void", "retired"):
        return None

    out = {
        "match_id": _match_id(entry),
        "match_key": entry.get("match_key"),
        "scheduled_time": entry.get("scheduled_time"),
        "p1": entry.get("p1"),
        "p2": entry.get("p2"),
        "tournament": entry.get("tournament"),
        "surface": entry.get("surface"),
        "status": result_status or ("void" if status in ("void", "retired") else "completed"),
        "settled_at": entry.get("settled_at"),
        "winner": result.get("winner"),
        "score_text": result.get("score_text"),
        "sets": result.get("sets") or [],
        "match_score": result.get("match_score"),
        "number_of_sets": result.get("number_of_sets"),
        "total_games": result.get("total_games"),
        "first_set_score": result.get("first_set_score"),
        "reason": result.get("reason"),
        "pbp": None,
    }
    return out


def _merge_pbp(out: dict, pbp: dict) -> dict:
    actual = pbp.get("actual") or {}
    if not actual:
        return out
    out = dict(out)
    out["pbp"] = {
        "first_set_score": actual.get("first_set_score"),
        "first_set_winner": actual.get("first_set_winner"),
        "first_set_games": actual.get("first_set_games"),
        "over85": actual.get("over85"),
        "states": actual.get("states") or {},
        "source": actual.get("source"),
        "settled_at": pbp.get("settled_at"),
    }
    if not out.get("first_set_score"):
        out["first_set_score"] = actual.get("first_set_score")
    return out


def build_feed(history: list[dict], pbp_history: list[dict], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=KEEP_DAYS)
    by_id: dict[int, dict] = {}
    by_key: dict[str, dict] = {}

    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        scheduled = _dt(entry.get("scheduled_time"))
        if scheduled and scheduled < cutoff:
            continue
        outcome = _base_outcome(entry)
        if not outcome:
            continue
        mid = outcome.get("match_id")
        if mid is not None:
            by_id[mid] = outcome
        key = str(outcome.get("match_key") or "")
        if key:
            by_key[key] = outcome

    for pbp in pbp_history or []:
        if not isinstance(pbp, dict) or str(pbp.get("status") or "").lower() != "settled":
            continue
        mid = _match_id(pbp)
        if mid is None:
            continue
        existing = by_id.get(mid)
        if existing is None:
            scheduled = _dt(pbp.get("scheduled_time"))
            if scheduled and scheduled < cutoff:
                continue
            existing = {
                "match_id": mid,
                "match_key": f"id:{mid}",
                "scheduled_time": pbp.get("scheduled_time"),
                "p1": pbp.get("p1"),
                "p2": pbp.get("p2"),
                "tournament": pbp.get("tournament"),
                "surface": pbp.get("surface"),
                "status": "partial",
                "settled_at": pbp.get("settled_at"),
                "winner": None,
                "score_text": None,
                "sets": [],
                "match_score": None,
                "number_of_sets": None,
                "total_games": None,
                "first_set_score": None,
                "reason": None,
                "pbp": None,
            }
        merged = _merge_pbp(existing, pbp)
        by_id[mid] = merged
        by_key[str(merged.get("match_key") or f"id:{mid}")] = merged

    rows = sorted(
        by_id.values(),
        key=lambda x: x.get("scheduled_time") or "",
        reverse=True,
    )
    return {
        "version": VERSION,
        "generated_at": now.isoformat(),
        "keep_days": KEEP_DAYS,
        "matches": rows,
        "count": len(rows),
    }


def main() -> None:
    now = datetime.now(timezone.utc)
    history = _read_json(HISTORY_PATH, [])
    pbp_history = _read_json(PBP_HISTORY_PATH, [])
    feed = build_feed(history if isinstance(history, list) else [], pbp_history if isinstance(pbp_history, list) else [], now=now)
    _write_json(OUTPUT_PATH, feed)

    meta = _read_json(META_PATH, {})
    if not isinstance(meta, dict):
        meta = {}
    meta.update({
        "scenario_settlement_v83c_version": VERSION,
        "scenario_settlement_v83c_updated_at": now.isoformat(),
        "scenario_settlement_v83c_results": feed.get("count", 0),
    })
    _write_json(META_PATH, meta)
    print(json.dumps({
        "version": VERSION,
        "results": feed.get("count", 0),
        "output": str(OUTPUT_PATH.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
