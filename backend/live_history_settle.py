from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from history_tracker import history_stats, settle_signal
from shadow_lab_v78e6 import SHADOW_STATS_PATH, build_shadow_stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
CACHE = ROOT / "data" / "cache"
HISTORY_PATH = OUT / "history.json"
STATS_PATH = OUT / "history_stats.json"
META_PATH = OUT / "meta.json"
STATE_PATH = CACHE / "live_result_settle_v731.json"

BASE_URL = "https://api.livetennisapi.com/api/public/v1"
UA = "TenisAI-v7.8E5-RetirementSettlement/1.0"
MIN_AGE_MINUTES = 75
RETRY_HOURS = 2
MAX_CALLS_PER_RUN = 40
DAILY_RESERVE = 150
SETTLEMENT_VERSION = "v7.8E5-retirement-partial"


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _write(path: Path, value):
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


def _obj(payload):
    if not isinstance(payload, dict):
        return {}
    d = payload.get("data")
    return d if isinstance(d, dict) else payload


def _usage_remaining(key: str):
    try:
        r = requests.get(
            BASE_URL + "/usage",
            headers={"Authorization": f"Bearer {key}", "User-Agent": UA},
            timeout=(7, 18),
        )
        r.raise_for_status()
        u = r.json() or {}
        today = u.get("today") or {}
        limits = u.get("limits") or {}
        rem = today.get("remaining_day")
        if rem is None and isinstance(limits.get("per_day"), (int, float)) and isinstance(today.get("calls"), (int, float)):
            rem = int(limits["per_day"]) - int(today["calls"])
        return int(rem) if isinstance(rem, (int, float)) else None
    except Exception:
        return None


def _score_sets(match: dict):
    score = match.get("score") or {}
    games = score.get("games") or []
    try:
        p1 = list(games[0] or [])
        p2 = list(games[1] or [])
    except Exception:
        return []
    n = min(len(p1), len(p2))
    out = []
    for i in range(n):
        try:
            a, b = int(p1[i]), int(p2[i])
        except (TypeError, ValueError):
            continue
        if a == 0 and b == 0 and i == n - 1:
            continue
        out.append([a, b])
    return out


def _set_complete(a: int, b: int) -> bool:
    hi, lo = max(a, b), min(a, b)
    return (hi >= 6 and hi - lo >= 2) or (hi == 7 and lo == 6)


def _winner_index(match: dict):
    winner = match.get("winner")
    try:
        winner = int(winner) if winner is not None else None
    except (TypeError, ValueError):
        winner = None
    return winner if winner in (1, 2) else None


def final_from_match(match: dict, entry: dict):
    status = str(match.get("event_status") or "").strip()
    low = status.casefold()

    if low in ("postponed", "interrupted", "suspended"):
        return None

    sets = _score_sets(match)
    winner_idx = _winner_index(match)
    p1, p2 = entry.get("p1"), entry.get("p2")
    actual_winner = p1 if winner_idx == 1 else p2 if winner_idx == 2 else None

    if low in ("cancelled", "canceled", "walk over", "walkover", "abandoned"):
        return {
            "status": "void",
            "winner": actual_winner,
            "score_text": status or "Cancelled",
            "reason": status or "cancelled/walkover",
            "p1": p1,
            "p2": p2,
        }

    if low in ("retired", "retirement", "defaulted", "default"):
        complete = [_set_complete(a, b) for a, b in sets]
        score = " · ".join(f"{a}:{b}" for a, b in sets)
        return {
            "status": "retired",
            "winner": actual_winner,
            "score_text": f"{score} · {status}".strip(" ·"),
            "reason": status or "Retired",
            "sets": sets,
            "completed_sets": complete,
            "first_set_score": f"{sets[0][0]}:{sets[0][1]}" if sets else None,
            "p1": p1,
            "p2": p2,
        }

    if winner_idx not in (1, 2):
        return None
    if not sets:
        return None

    set_wins_p1 = sum(1 for a, b in sets if a > b)
    set_wins_p2 = sum(1 for a, b in sets if b > a)
    if set_wins_p1 == set_wins_p2:
        return None

    score_text = " ".join(f"{a}-{b}" for a, b in sets)
    return {
        "status": "completed",
        "winner": actual_winner,
        "score_text": score_text,
        "sets": sets,
        "completed_sets": [_set_complete(a, b) for a, b in sets],
        "match_score": f"{set_wins_p1}:{set_wins_p2}",
        "number_of_sets": len(sets),
        "total_games": sum(a + b for a, b in sets),
        "first_set_score": f"{sets[0][0]}:{sets[0][1]}",
        "p1": p1,
        "p2": p2,
    }


def settle_signal_live(signal: dict, final: dict) -> str:
    status = final.get("status")
    if status == "completed":
        return settle_signal(signal, final)
    if status == "void":
        return "void"
    if status != "retired":
        return "unverifiable"

    market = signal.get("market")
    pick = str(signal.get("pick") or "")
    sets = final.get("sets") or []
    complete = final.get("completed_sets") or []
    p1, p2 = final.get("p1"), final.get("p2")

    if market == "game_state":
        return "unverifiable"
    if market in ("match_winner", "total_sets", "exact_match", "match_total"):
        return "void"

    if market in ("set1_winner", "set2_winner", "set3_winner"):
        idx = {"set1_winner": 0, "set2_winner": 1, "set3_winner": 2}[market]
        if len(sets) <= idx or len(complete) <= idx or not complete[idx] or not p1 or not p2:
            return "void"
        a, b = sets[idx]
        if a == b:
            return "void"
        actual = p1 if a > b else p2
        from history_tracker import _key
        return "hit" if _key(pick) == _key(actual) else "miss"

    if market == "set1_total":
        if not sets or not complete or not complete[0]:
            return "void"
        total = sum(sets[0])
        try:
            line = float(signal.get("line"))
        except (TypeError, ValueError):
            return "void"
        ok = total > line if pick == "over" else total < line
        return "hit" if ok else "miss"

    if market == "exact_set1":
        if not sets or not complete or not complete[0]:
            return "void"
        actual = f"{sets[0][0]}:{sets[0][1]}"
        return "hit" if pick == actual else "miss"

    return "unverifiable"


def _settle_signal_list(rows, final):
    out = []
    for s in rows or []:
        s = dict(s)
        s["result"] = settle_signal_live(s, final)
        s["settlement_source"] = "Live Tennis API"
        out.append(s)
    return out


def settle_entry(entry: dict, final: dict, now: datetime):
    x = dict(entry)
    x["result"] = final
    x["settled_at"] = now.isoformat()
    x["settlement_source"] = "Live Tennis API /matches/{id}"
    x["settlement_version"] = SETTLEMENT_VERSION
    x["status"] = "void" if final.get("status") == "void" else "settled"
    x.pop("live_status", None)
    x.pop("live_status_updated_at", None)
    x["signals"] = _settle_signal_list(x.get("signals"), final)
    if "shadow_signals" in x:
        x["shadow_signals"] = _settle_signal_list(x.get("shadow_signals"), final)
    return x


def _needs_retirement_migration(entry: dict) -> bool:
    if entry.get("status") != "void":
        return False
    if entry.get("settlement_version") == SETTLEMENT_VERSION:
        return False
    text = " ".join([
        str((entry.get("result") or {}).get("reason") or ""),
        str((entry.get("result") or {}).get("score_text") or ""),
    ]).casefold()
    return "retir" in text


def main():
    now = datetime.now(timezone.utc)
    key = os.getenv("LIVE_TENNIS_API_KEY", "").strip()
    hist = _read(HISTORY_PATH, [])
    state = _read(STATE_PATH, {"matches": {}})
    meta = _read(META_PATH, {})
    if not isinstance(hist, list):
        hist = []
    if not isinstance(state, dict):
        state = {"matches": {}}
    state.setdefault("matches", {})
    if not isinstance(meta, dict):
        meta = {}

    candidates = []
    for i, e in enumerate(hist):
        migration = _needs_retirement_migration(e)
        normal_pending = e.get("status") in ("pending", "upcoming")
        if not (normal_pending or migration) or e.get("match_id") is None:
            continue
        if not migration and not (e.get("signals") or e.get("shadow_signals")):
            continue
        scheduled = _dt(e.get("scheduled_time"))
        if scheduled is None or scheduled > now - timedelta(minutes=MIN_AGE_MINUTES):
            continue
        rec = state["matches"].get(str(e["match_id"])) or {}
        last = _dt(rec.get("last_checked_at"))
        if not migration and last and now - last < timedelta(hours=RETRY_HOURS):
            continue
        candidates.append((scheduled, i, e, migration))
    candidates.sort(key=lambda x: x[0])

    remaining = _usage_remaining(key) if key and candidates else None
    budget = min(MAX_CALLS_PER_RUN, max(0, (remaining or 0) - DAILY_RESERVE)) if remaining is not None else 0
    calls = settled = voided = retired = not_ready = errors = migrated = 0

    for _, idx, e, migration in candidates[:budget]:
        mid = e.get("match_id")
        rec = state["matches"].setdefault(str(mid), {})
        rec["last_checked_at"] = now.isoformat()
        rec["checks"] = int(rec.get("checks") or 0) + 1
        try:
            r = requests.get(
                BASE_URL + f"/matches/{mid}",
                headers={"Authorization": f"Bearer {key}", "User-Agent": UA},
                timeout=(7, 22),
            )
            calls += 1
            rec["last_status_code"] = r.status_code
            if r.status_code != 200:
                errors += 1
                continue
            match = _obj(r.json())
            final = final_from_match(match, e)
            if final is None:
                not_ready += 1
                feed_status = str(match.get("event_status") or match.get("status") or "").strip()
                rec["last_feed_status"] = feed_status
                pending = dict(e)
                if feed_status:
                    pending["live_status"] = feed_status
                    pending["live_status_updated_at"] = now.isoformat()
                hist[idx] = pending
                continue

            hist[idx] = settle_entry(e, final, now)
            rec["settled_at"] = now.isoformat()
            rec["settled_status"] = final.get("status")
            rec["settlement_version"] = SETTLEMENT_VERSION
            if migration:
                migrated += 1
            if final.get("status") == "void":
                voided += 1
            elif final.get("status") == "retired":
                retired += 1
            else:
                settled += 1
        except Exception as ex:
            errors += 1
            rec["last_error"] = type(ex).__name__

    if len(state["matches"]) > 3000:
        keys = list(state["matches"].keys())[-3000:]
        state["matches"] = {k: state["matches"][k] for k in keys}
    state["updated_at"] = now.isoformat()
    _write(STATE_PATH, state)
    _write(HISTORY_PATH, hist)
    _write(STATS_PATH, history_stats(hist))
    _write(SHADOW_STATS_PATH, build_shadow_stats(hist))

    meta.update({
        "history_live_settle_updated_at": now.isoformat(),
        "history_live_settle_candidates": len(candidates),
        "history_live_settle_calls": calls,
        "history_live_settle_settled": settled,
        "history_live_settle_retired": retired,
        "history_live_settle_voided": voided,
        "history_live_settle_retirement_migrated": migrated,
        "history_live_settle_not_ready": not_ready,
        "history_live_settle_errors": errors,
        "history_live_settle_remaining_before": remaining,
        "history_settlement_version": SETTLEMENT_VERSION,
    })
    _write(META_PATH, meta)
    print(json.dumps(
        {k: v for k, v in meta.items() if k.startswith("history_live_settle_") or k == "history_settlement_version"},
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
