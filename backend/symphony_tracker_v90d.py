from __future__ import annotations

"""Tenis AI v9.0D — settlement + learning tracker for Tennis Symphony.

The tracker freezes the latest pre-match Symphony snapshot and later settles
ALL main compositions (2, 3, 4, 5 and 6 legs) against the canonical scenario
settlement feed.  This gives a fair counterfactual comparison of leg counts:
the same match teaches us how 2-leg, 3-leg, ... 6-leg versions performed.

Hard rules:
- never mutates PROD / Adaptive / SHADOW model output;
- never captures a new snapshot after the freeze cutoff;
- unknown actual data stays UNKNOWN, never guessed;
- full-hit statistics require every leg in that composition to be resolved;
- void/retired matches do not enter performance statistics.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
import unicodedata
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
REPORT_PATH = OUT / "symphony_v90.json"
SETTLEMENT_PATH = OUT / "scenario_results_v83c.json"
HISTORY_PATH = OUT / "symphony_history_v90d.json"
STATS_PATH = OUT / "symphony_stats_v90d.json"
META_PATH = OUT / "meta.json"

VERSION = "v9.0D"
KEEP_DAYS = 180
FREEZE_MINUTES_BEFORE_START = 5
LEG_COUNTS = (2, 3, 4, 5, 6)


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
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


def _dt(value):
    try:
        d = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _ascii(value: Any) -> str:
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold().strip()


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", _ascii(value))


def _same_name(a, b) -> bool:
    return bool(_compact(a)) and _compact(a) == _compact(b)


def _score_pair(value):
    m = re.search(r"(\d+)\s*[:\-]\s*(\d+)", str(value or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _canonical_market(value: Any) -> str:
    x = _ascii(value).replace("-", "_").replace(" ", "_")
    aliases = {
        "match_win": "match_winner",
        "winner": "match_winner",
        "set1_win": "set1_winner",
        "first_set_win": "set1_winner",
        "set2_win": "set2_winner",
        "second_set_win": "set2_winner",
        "set3_win": "set3_winner",
        "third_set_win": "set3_winner",
        "state": "game_state",
        "gamestate": "game_state",
        "sets_total": "total_sets",
        "correct_score": "exact_match_score",
        "match_score": "exact_match_score",
        "set1_score": "set1_exact_score",
        "first_set_score": "set1_exact_score",
        "tiebreak": "set1_tiebreak",
        "tie_break": "set1_tiebreak",
    }
    return aliases.get(x, x)


def _match_key(row: dict) -> str:
    key = str(row.get("match_key") or "").strip()
    if key:
        return key
    mid = row.get("match_id") if row.get("match_id") is not None else row.get("id")
    if mid is not None and str(mid) != "":
        return f"id:{mid}"
    return "|".join([
        _ascii(row.get("p1")),
        _ascii(row.get("p2")),
        str(row.get("scheduled_time") or "")[:16],
        _ascii(row.get("tournament")),
    ])


def _leg_snapshot(leg: dict) -> dict:
    keep = (
        "key", "label", "market", "pick", "line", "checkpoint",
        "evidence_score", "prod_score", "path_probability",
        "market_source", "raw_market_probability", "score_kind", "approximation",
    )
    return {k: leg.get(k) for k in keep if leg.get(k) is not None}


def _composition_snapshot(comp: dict) -> dict:
    frag = (comp.get("fragility") or [None])[0] or {}
    return {
        "story_type": comp.get("story_type"),
        "symphony_score": comp.get("symphony_score"),
        "joint_probability": comp.get("joint_probability"),
        "path_coverage": comp.get("path_coverage"),
        "prod_shadow_agreement": comp.get("prod_shadow_agreement"),
        "model_conflict": comp.get("model_conflict"),
        "fragility": {
            "key": frag.get("key"),
            "label": frag.get("label"),
            "value": frag.get("fragility"),
        } if frag else None,
        "selection": [_leg_snapshot(x) for x in (comp.get("selection") or []) if isinstance(x, dict)],
    }


def _report_record(match: dict, report: dict, now: datetime) -> dict | None:
    scheduled = _dt(match.get("scheduled_time"))
    if scheduled is None:
        return None
    freeze_at = scheduled - timedelta(minutes=FREEZE_MINUTES_BEFORE_START)
    if now >= freeze_at:
        return None

    comps = {}
    for n in LEG_COUNTS:
        comp = (match.get("compositions") or {}).get(str(n))
        if isinstance(comp, dict) and len(comp.get("selection") or []) == n:
            comps[str(n)] = _composition_snapshot(comp)
    if not comps:
        return None

    return {
        "match_key": _match_key(match),
        "match_id": match.get("id") if match.get("id") is not None else match.get("match_id"),
        "p1": match.get("p1"),
        "p2": match.get("p2"),
        "scheduled_time": match.get("scheduled_time"),
        "tour": match.get("tour"),
        "tournament": match.get("tournament"),
        "surface": match.get("surface"),
        "best_of": match.get("best_of"),
        "captured_at": now.isoformat(),
        "freeze_at": freeze_at.isoformat(),
        "report_version": report.get("version"),
        "engine_version": report.get("engine_version"),
        "recommended_leg_count": match.get("recommended_leg_count"),
        "leg_count_intelligence": match.get("leg_count_intelligence") or {},
        "compositions": comps,
        "status": "pending",
        "settlement": None,
    }


def capture(report: dict, history: dict, now: datetime) -> tuple[dict, int, int]:
    rows = history.get("matches") if isinstance(history, dict) else []
    rows = [dict(x) for x in (rows or []) if isinstance(x, dict)]
    by_key = {_match_key(x): x for x in rows if _match_key(x)}
    added = updated = 0

    for match in report.get("matches") or []:
        if not isinstance(match, dict):
            continue
        fresh = _report_record(match, report, now)
        if not fresh:
            continue
        key = fresh["match_key"]
        old = by_key.get(key)
        if old and str(old.get("status")) in {"settled", "void"}:
            continue
        if old:
            # Latest strictly pre-match snapshot wins. This never happens after
            # freeze_at because _report_record rejects it above.
            by_key[key] = fresh
            updated += 1
        else:
            by_key[key] = fresh
            added += 1

    cutoff = now - timedelta(days=KEEP_DAYS)
    kept = []
    for row in by_key.values():
        scheduled = _dt(row.get("scheduled_time"))
        if scheduled is not None and scheduled < cutoff:
            continue
        kept.append(row)
    kept.sort(key=lambda x: x.get("scheduled_time") or "", reverse=True)
    return {
        "version": VERSION,
        "updated_at": now.isoformat(),
        "keep_days": KEEP_DAYS,
        "freeze_minutes_before_start": FREEZE_MINUTES_BEFORE_START,
        "matches": kept,
    }, added, updated


def _settlement_index(feed: dict):
    by_key, by_id = {}, {}
    for row in feed.get("matches") or []:
        if not isinstance(row, dict):
            continue
        key = _match_key(row)
        if key:
            by_key[key] = row
        mid = row.get("match_id")
        if mid is not None:
            by_id[str(mid)] = row
    return by_key, by_id


def _set_pair(actual: dict, set_no: int):
    sets = actual.get("sets") or []
    if len(sets) >= set_no and isinstance(sets[set_no - 1], (list, tuple)) and len(sets[set_no - 1]) >= 2:
        a = _num(sets[set_no - 1][0])
        b = _num(sets[set_no - 1][1])
        if a is not None and b is not None:
            return int(a), int(b)
    if set_no == 1:
        return _score_pair(actual.get("first_set_score") or ((actual.get("pbp") or {}).get("first_set_score")))
    return None


def _set_winner(actual: dict, set_no: int, p1: str, p2: str):
    if set_no == 1:
        pbp_winner = ((actual.get("pbp") or {}).get("first_set_winner"))
        if pbp_winner:
            return pbp_winner
    pair = _set_pair(actual, set_no)
    if not pair or pair[0] == pair[1]:
        return None
    return p1 if pair[0] > pair[1] else p2


def _ou_result(value, pick: str, line):
    value = _num(value)
    line = _num(line)
    if value is None or line is None:
        return None
    side = _ascii(pick)
    if side in {"over", "o", "powyzej", "above"}:
        return value > line
    if side in {"under", "u", "ponizej", "below"}:
        return value < line
    return None


def _serve_actual(actual: dict, side: str, field: str):
    # Forward-compatible hook. scenario_results_v83c does not always carry
    # final serve stats yet, so absence is intentionally UNKNOWN.
    stats = actual.get("serve_stats") or actual.get("stats") or {}
    if not isinstance(stats, dict):
        return None
    block = stats.get(side) or {}
    if not isinstance(block, dict):
        return None
    aliases = {
        "aces": ("aces", "ace"),
        "double_faults": ("double_faults", "df", "doubleFaults"),
    }
    for key in aliases.get(field, (field,)):
        x = _num(block.get(key))
        if x is not None:
            return x
    return None


def evaluate_leg(leg: dict, actual: dict, p1: str, p2: str):
    market = _canonical_market(leg.get("market"))
    pick = str(leg.get("pick") or "")
    line = leg.get("line")

    if market == "game_state":
        cp = str(int(_num(leg.get("checkpoint"), 0) or 0))
        state = (((actual.get("pbp") or {}).get("states") or {}).get(cp))
        if state is None:
            return None
        return _score_pair(state) == _score_pair(pick)

    if market == "match_winner":
        winner = actual.get("winner")
        return None if not winner else _same_name(winner, pick)

    if market in {"set1_winner", "set2_winner", "set3_winner"}:
        set_no = int(market[3])
        winner = _set_winner(actual, set_no, p1, p2)
        return None if not winner else _same_name(winner, pick)

    if market == "set1_total":
        pair = _set_pair(actual, 1)
        return None if not pair else _ou_result(pair[0] + pair[1], pick, line)

    if market == "match_total":
        return _ou_result(actual.get("total_games"), pick, line)

    if market == "total_sets":
        return _ou_result(actual.get("number_of_sets"), pick, line)

    if market == "exact_match_score":
        pair = _score_pair(actual.get("match_score"))
        return None if pair is None else pair == _score_pair(pick)

    if market == "set1_exact_score":
        pair = _set_pair(actual, 1)
        return None if pair is None else pair == _score_pair(pick)

    if market == "set1_tiebreak":
        pair = _set_pair(actual, 1)
        if pair is None:
            return None
        happened = pair in {(7, 6), (6, 7)}
        yes = _ascii(pick) in {"yes", "tak", "true", "1"}
        no = _ascii(pick) in {"no", "nie", "false", "0"}
        return happened if yes else ((not happened) if no else None)

    if market in {"player_aces", "player_double_faults"}:
        key = str(leg.get("key") or "")
        side = "p1" if "|p1|" in key else ("p2" if "|p2|" in key else None)
        if side is None:
            if _same_name(pick, p1):
                side = "p1"
            elif _same_name(pick, p2):
                side = "p2"
        if side is None:
            return None
        field = "aces" if market == "player_aces" else "double_faults"
        value = _serve_actual(actual, side, field)
        return _ou_result(value, pick, line) if value is not None else None

    if market in {"most_aces", "most_double_faults", "most_aces_plus_df"}:
        if market == "most_aces":
            a = _serve_actual(actual, "p1", "aces")
            b = _serve_actual(actual, "p2", "aces")
        elif market == "most_double_faults":
            a = _serve_actual(actual, "p1", "double_faults")
            b = _serve_actual(actual, "p2", "double_faults")
        else:
            aa = _serve_actual(actual, "p1", "aces")
            ad = _serve_actual(actual, "p1", "double_faults")
            ba = _serve_actual(actual, "p2", "aces")
            bd = _serve_actual(actual, "p2", "double_faults")
            if None in (aa, ad, ba, bd):
                return None
            a, b = aa + ad, ba + bd
        if a is None or b is None:
            return None
        if a == b:
            winner = "draw"
        else:
            winner = p1 if a > b else p2
        return _ascii(pick) in {"draw", "remis"} if winner == "draw" else _same_name(winner, pick)

    return None


def _settle_composition(comp: dict, actual: dict, p1: str, p2: str) -> dict:
    leg_rows = []
    hits = misses = unknown = 0
    for leg in comp.get("selection") or []:
        value = evaluate_leg(leg, actual, p1, p2)
        if value is True:
            result = "hit"
            hits += 1
        elif value is False:
            result = "miss"
            misses += 1
        else:
            result = "unknown"
            unknown += 1
        leg_rows.append({
            "key": leg.get("key"),
            "label": leg.get("label"),
            "market": leg.get("market"),
            "result": result,
        })

    total = len(leg_rows)
    fully_resolved = total > 0 and unknown == 0
    if fully_resolved:
        full_result = "hit" if misses == 0 else "miss"
    elif misses > 0:
        full_result = "definite_miss_partial_data"
    else:
        full_result = "partial"

    return {
        "legs": total,
        "resolved_legs": hits + misses,
        "hit_legs": hits,
        "miss_legs": misses,
        "unknown_legs": unknown,
        "leg_accuracy": round(100.0 * hits / (hits + misses), 3) if hits + misses else None,
        "fully_resolved": fully_resolved,
        "full_result": full_result,
        "legs_detail": leg_rows,
    }


def settle(history: dict, feed: dict, now: datetime) -> tuple[dict, int, int]:
    by_key, by_id = _settlement_index(feed)
    settled = voided = 0
    rows = []
    for original in history.get("matches") or []:
        if not isinstance(original, dict):
            continue
        row = dict(original)
        if str(row.get("status")) in {"settled", "void"}:
            rows.append(row)
            continue
        actual = by_key.get(_match_key(row))
        if actual is None and row.get("match_id") is not None:
            actual = by_id.get(str(row.get("match_id")))
        if not actual:
            rows.append(row)
            continue
        status = str(actual.get("status") or "").lower()
        if status in {"void", "retired"}:
            row["status"] = "void"
            row["settled_at"] = now.isoformat()
            row["settlement"] = {"status": status, "reason": actual.get("reason")}
            voided += 1
            rows.append(row)
            continue
        if status != "completed":
            rows.append(row)
            continue

        comp_results = {}
        for n in LEG_COUNTS:
            comp = (row.get("compositions") or {}).get(str(n))
            if isinstance(comp, dict):
                comp_results[str(n)] = _settle_composition(comp, actual, str(row.get("p1") or ""), str(row.get("p2") or ""))
        row["status"] = "settled"
        row["settled_at"] = now.isoformat()
        row["settlement"] = {
            "status": "completed",
            "winner": actual.get("winner"),
            "match_score": actual.get("match_score"),
            "first_set_score": actual.get("first_set_score"),
            "total_games": actual.get("total_games"),
            "number_of_sets": actual.get("number_of_sets"),
            "compositions": comp_results,
        }
        settled += 1
        rows.append(row)

    history = dict(history)
    history["matches"] = rows
    history["updated_at"] = now.isoformat()
    return history, settled, voided


def _avg(values):
    xs = [float(x) for x in values if _num(x) is not None]
    return (sum(xs) / len(xs)) if xs else None


def _pct(h, n):
    return (100.0 * h / n) if n else None


def _sample_label(n):
    if n >= 50:
        return "strong"
    if n >= 20:
        return "medium"
    if n >= 10:
        return "small"
    return "tiny"


def aggregate(history: dict, now: datetime) -> dict:
    buckets = {str(n): {
        "full_n": 0, "full_hits": 0,
        "resolved_legs": 0, "leg_hits": 0,
        "scores": [], "coverage": [], "joint": [], "fragility": [],
    } for n in LEG_COUNTS}
    auto = {
        "full_n": 0, "full_hits": 0,
        "resolved_legs": 0, "leg_hits": 0,
        "recommended_distribution": defaultdict(int),
    }
    stories = defaultdict(lambda: {"full_n": 0, "full_hits": 0, "resolved_legs": 0, "leg_hits": 0})
    daily = defaultdict(lambda: {str(n): {"n": 0, "hits": 0} for n in LEG_COUNTS})
    settled_matches = pending_matches = void_matches = 0

    for row in history.get("matches") or []:
        status = str(row.get("status") or "")
        if status == "pending":
            pending_matches += 1
            continue
        if status == "void":
            void_matches += 1
            continue
        if status != "settled":
            continue
        settled_matches += 1
        rec = int(_num(row.get("recommended_leg_count"), 0) or 0)
        if rec in LEG_COUNTS:
            auto["recommended_distribution"][str(rec)] += 1
        day = str(row.get("scheduled_time") or "")[:10]
        results = ((row.get("settlement") or {}).get("compositions") or {})

        for n in LEG_COUNTS:
            key = str(n)
            comp = (row.get("compositions") or {}).get(key)
            result = results.get(key)
            if not isinstance(comp, dict) or not isinstance(result, dict):
                continue
            b = buckets[key]
            b["scores"].append(comp.get("symphony_score"))
            b["coverage"].append(comp.get("path_coverage"))
            b["joint"].append(comp.get("joint_probability"))
            b["fragility"].append(((comp.get("fragility") or {}).get("value")))
            b["resolved_legs"] += int(result.get("resolved_legs") or 0)
            b["leg_hits"] += int(result.get("hit_legs") or 0)

            story = str(comp.get("story_type") or "UNKNOWN")
            s = stories[story]
            s["resolved_legs"] += int(result.get("resolved_legs") or 0)
            s["leg_hits"] += int(result.get("hit_legs") or 0)

            if result.get("fully_resolved"):
                b["full_n"] += 1
                hit = result.get("full_result") == "hit"
                b["full_hits"] += int(hit)
                daily[day][key]["n"] += 1
                daily[day][key]["hits"] += int(hit)
                s["full_n"] += 1
                s["full_hits"] += int(hit)

                if n == rec:
                    auto["full_n"] += 1
                    auto["full_hits"] += int(hit)
            if n == rec:
                auto["resolved_legs"] += int(result.get("resolved_legs") or 0)
                auto["leg_hits"] += int(result.get("hit_legs") or 0)

    leg_counts = {}
    for n in LEG_COUNTS:
        key = str(n)
        b = buckets[key]
        full_rate = _pct(b["full_hits"], b["full_n"])
        leg_rate = _pct(b["leg_hits"], b["resolved_legs"])
        survival = (full_rate / 100.0) ** (1.0 / n) * 100.0 if full_rate is not None and full_rate > 0 else (0.0 if full_rate == 0 else None)
        # Normalized quality prevents history from mechanically preferring 2 legs.
        normalized = None
        if leg_rate is not None and survival is not None:
            normalized = 0.60 * leg_rate + 0.40 * survival
        elif leg_rate is not None:
            normalized = leg_rate
        leg_counts[key] = {
            "legs": n,
            "full_settled": b["full_n"],
            "full_hits": b["full_hits"],
            "full_hit_rate": round(full_rate, 3) if full_rate is not None else None,
            "per_leg_survival": round(survival, 3) if survival is not None else None,
            "resolved_legs": b["resolved_legs"],
            "leg_hits": b["leg_hits"],
            "leg_accuracy": round(leg_rate, 3) if leg_rate is not None else None,
            "normalized_quality": round(normalized, 3) if normalized is not None else None,
            "avg_symphony_score": round(_avg(b["scores"]), 3) if _avg(b["scores"]) is not None else None,
            "avg_path_coverage": round(_avg(b["coverage"]), 4) if _avg(b["coverage"]) is not None else None,
            "avg_joint_probability": round(_avg(b["joint"]), 3) if _avg(b["joint"]) is not None else None,
            "avg_fragility": round(_avg(b["fragility"]), 3) if _avg(b["fragility"]) is not None else None,
            "sample": _sample_label(b["full_n"]),
            "history_weight_ready": bool(b["full_n"] >= 20 and b["resolved_legs"] >= 50),
        }

    story_rows = []
    for name, b in stories.items():
        story_rows.append({
            "story_type": name,
            "full_settled": b["full_n"],
            "full_hit_rate": round(_pct(b["full_hits"], b["full_n"]), 3) if b["full_n"] else None,
            "resolved_legs": b["resolved_legs"],
            "leg_accuracy": round(_pct(b["leg_hits"], b["resolved_legs"]), 3) if b["resolved_legs"] else None,
        })
    story_rows.sort(key=lambda x: (x.get("full_settled") or 0, x.get("leg_accuracy") or 0), reverse=True)

    trend = []
    for day in sorted(daily):
        trend.append({
            "date": day,
            "leg_counts": {
                key: {
                    "n": daily[day][key]["n"],
                    "hits": daily[day][key]["hits"],
                    "full_hit_rate": round(_pct(daily[day][key]["hits"], daily[day][key]["n"]), 3) if daily[day][key]["n"] else None,
                }
                for key in map(str, LEG_COUNTS)
            },
        })

    return {
        "version": VERSION,
        "generated_at": now.isoformat(),
        "settled_matches": settled_matches,
        "pending_matches": pending_matches,
        "void_matches": void_matches,
        "leg_counts": leg_counts,
        "auto": {
            "full_settled": auto["full_n"],
            "full_hits": auto["full_hits"],
            "full_hit_rate": round(_pct(auto["full_hits"], auto["full_n"]), 3) if auto["full_n"] else None,
            "resolved_legs": auto["resolved_legs"],
            "leg_hits": auto["leg_hits"],
            "leg_accuracy": round(_pct(auto["leg_hits"], auto["resolved_legs"]), 3) if auto["resolved_legs"] else None,
            "recommended_distribution": dict(sorted(auto["recommended_distribution"].items())),
        },
        "story_types": story_rows,
        "trend": trend[-90:],
        "learning_contract": {
            "all_leg_counts_snapshotted": True,
            "latest_pre_match_snapshot": True,
            "freeze_minutes_before_start": FREEZE_MINUTES_BEFORE_START,
            "unknown_is_not_miss": True,
            "full_hit_requires_all_legs_resolved": True,
            "historical_weight_min_full_settled": 20,
            "historical_weight_min_resolved_legs": 50,
            "normalized_quality_not_raw_full_hit": True,
        },
    }


def run(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    report = _read(REPORT_PATH, {})
    feed = _read(SETTLEMENT_PATH, {})
    history = _read(HISTORY_PATH, {})
    if not isinstance(report, dict):
        report = {}
    if not isinstance(feed, dict):
        feed = {}
    if not isinstance(history, dict):
        history = {}

    history, added, updated = capture(report, history, now)
    history, newly_settled, newly_void = settle(history, feed, now)
    stats = aggregate(history, now)
    _write(HISTORY_PATH, history)
    _write(STATS_PATH, stats)

    meta = _read(META_PATH, {})
    if not isinstance(meta, dict):
        meta = {}
    meta.update({
        "symphony_tracker_version": VERSION,
        "symphony_tracker_updated_at": now.isoformat(),
        "symphony_tracker_snapshots": len(history.get("matches") or []),
        "symphony_tracker_settled": stats.get("settled_matches", 0),
        "symphony_tracker_pending": stats.get("pending_matches", 0),
    })
    _write(META_PATH, meta)

    return {
        "status": "OK",
        "version": VERSION,
        "captured_new": added,
        "captured_updated": updated,
        "newly_settled": newly_settled,
        "newly_void": newly_void,
        "settled_total": stats.get("settled_matches", 0),
        "pending_total": stats.get("pending_matches", 0),
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
