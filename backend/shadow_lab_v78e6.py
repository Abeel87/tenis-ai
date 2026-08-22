from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from history_tracker import GREEN_THRESHOLD, MODEL_VERSION, load_history, match_key, save_history

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
RESULTS_PATH = OUT / "results.json"
HISTORY_PATH = OUT / "history.json"
META_PATH = OUT / "meta.json"
SHADOW_CURRENT_PATH = OUT / "shadow_current.json"
SHADOW_STATS_PATH = OUT / "shadow_stats.json"

SHADOW_MIN_THRESHOLD = 55.0
SHADOW_MAX_THRESHOLD = float(GREEN_THRESHOLD)
SHADOW_VERSION = "v7.8E6-shadow-lab"


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


def _signal(market, label, pick, score, **extra):
    return {
        "id": "|".join([market, str(extra.get("line", "")), str(extra.get("checkpoint", "")), str(pick)]),
        "market": market,
        "label": label,
        "pick": str(pick),
        "score": round(float(score), 1),
        "result": "pending",
        "shadow": True,
        "shadow_reason": "below_green_threshold",
        **extra,
    }


def _shadow_score(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if SHADOW_MIN_THRESHOLD <= v < SHADOW_MAX_THRESHOLD else None


def extract_shadow_signals(match: dict) -> list[dict]:
    out = []

    def add_binary(field, market, label, source_model="adaptive", **extra):
        for pick, value in (match.get(field) or {}).items():
            v = _shadow_score(value)
            if v is not None:
                out.append(_signal(market, label, pick, v, source_model=source_model, **extra))

    add_binary("match_win", "match_winner", "Zwycięzca meczu")
    add_binary("first_set_win", "set1_winner", "Zwycięzca 1. seta")
    add_binary("second_set_win", "set2_winner", "Zwycięzca 2. seta")
    add_binary("third_set_win", "set3_winner", "Zwycięzca 3. seta · jeśli będzie")
    add_binary("total_sets", "total_sets", "Liczba setów")
    add_binary("exact_match_score", "exact_match", "Dokładny wynik meczu")

    for line, sides in (match.get("over_under") or {}).items():
        for side in ("over", "under"):
            v = _shadow_score((sides or {}).get(side))
            if v is not None:
                out.append(_signal("set1_total", f"1. set · {side.upper()} {line}", side, v,
                                   line=float(line), source_model="adaptive"))

    for line, sides in (match.get("match_over_under") or {}).items():
        for side in ("over", "under"):
            v = _shadow_score((sides or {}).get(side))
            if v is not None:
                out.append(_signal("match_total", f"Mecz · {side.upper()} {line}", side, v,
                                   line=float(line), source_model="adaptive"))

    for pick, value in (match.get("exact_first_set") or {}).items():
        v = _shadow_score(value)
        if v is not None:
            out.append(_signal("exact_set1", "Dokładny wynik 1. seta", pick, v, source_model="adaptive"))

    return sorted(out, key=lambda s: (-s["score"], s["label"], s["pick"]))


def build_shadow_current(results: list[dict]) -> list[dict]:
    rows = []
    for match in results or []:
        if not isinstance(match, dict):
            continue
        ready = bool(match.get("model_ready"))
        signals = extract_shadow_signals(match) if ready else []
        if ready and not signals:
            continue
        p1s, p2s = match.get("p1_stats") or {}, match.get("p2_stats") or {}
        rows.append({
            "match_key": match_key(match),
            "match_id": match.get("id"),
            "scheduled_time": match.get("scheduled_time"),
            "tour": match.get("tour") or "",
            "tournament": match.get("tournament") or "",
            "surface": match.get("surface") or "",
            "p1": match.get("p1") or "",
            "p2": match.get("p2") or "",
            "quality": match.get("quality"),
            "model_confidence": match.get("model_confidence"),
            "model_ready": ready,
            "rejection_code": "below_green_threshold" if ready else "insufficient_data",
            "rejection_reason": (
                f"Sygnał {int(SHADOW_MIN_THRESHOLD)}–{int(SHADOW_MAX_THRESHOLD - 1)} / 100 — poniżej progu zielonego."
                if ready else
                "Za mała lub zbyt słaba próbka danych — obserwujemy, ale nie uczymy skuteczności."
            ),
            "p1_matches": p1s.get("matches"),
            "p2_matches": p2s.get("matches"),
            "p1_quality": p1s.get("quality"),
            "p2_quality": p2s.get("quality"),
            "signals": signals,
        })
    rows.sort(key=lambda x: x.get("scheduled_time") or "")
    return rows


def capture_shadow_history(entries: list[dict], results: list[dict], now: datetime | None = None,
                           cutoff_minutes: int = 5) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    by_key = {e.get("match_key"): e for e in entries if e.get("match_key")}

    for match in results or []:
        if not isinstance(match, dict) or not match.get("model_ready"):
            continue
        scheduled = _dt(match.get("scheduled_time"))
        if scheduled is None or scheduled <= now + timedelta(minutes=cutoff_minutes):
            continue
        key = match_key(match)
        current = by_key.get(key)
        if not current or current.get("status") not in ("pending", "upcoming"):
            continue

        x = dict(current)
        x["shadow_signals"] = extract_shadow_signals(match)
        x["shadow_version"] = SHADOW_VERSION
        x["shadow_captured_at"] = now.isoformat()
        x["shadow_first_captured_at"] = x.get("shadow_first_captured_at") or now.isoformat()
        by_key[key] = x

    return list(by_key.values())


def _summary(items):
    hits = sum(1 for _, s in items if s.get("result") == "hit")
    total = len(items)
    return {
        "settled": total,
        "hits": hits,
        "misses": total - hits,
        "accuracy": round(hits * 100 / total, 1) if total else None,
    }


def _band(score):
    try:
        v = float(score)
    except (TypeError, ValueError):
        return "N/D"
    if v >= 68:
        return "68–71"
    if v >= 65:
        return "65–67"
    if v >= 60:
        return "60–64"
    return "55–59"


def _grouped(items, key_fn):
    groups = {}
    for pair in items:
        groups.setdefault(key_fn(*pair), []).append(pair)
    return {k: _summary(v) for k, v in sorted(groups.items())}


def build_shadow_stats(entries: list[dict]) -> dict:
    current_entries = [e for e in entries or [] if e.get("model_version") == MODEL_VERSION]
    settled = []
    excluded = 0
    for e in current_entries:
        for s in e.get("shadow_signals") or []:
            if s.get("result") in ("hit", "miss"):
                settled.append((e, s))
            elif s.get("result") in ("void", "unverifiable"):
                excluded += 1

    pending = sum(
        1 for e in current_entries
        if e.get("status") in ("pending", "upcoming") and (e.get("shadow_signals") or [])
    )
    tracked = sum(1 for e in current_entries if e.get("shadow_signals"))
    overall = _summary(settled)
    return {
        "version": SHADOW_VERSION,
        "model_version": MODEL_VERSION,
        "green_threshold": SHADOW_MAX_THRESHOLD,
        "shadow_min_threshold": SHADOW_MIN_THRESHOLD,
        "overall": overall,
        "matches_tracked": tracked,
        "matches_pending": pending,
        "excluded_signals": excluded,
        "discarded_but_hit": overall["hits"],
        "discarded_and_missed": overall["misses"],
        "by_market": _grouped(settled, lambda e, s: s.get("label") or s.get("market") or "Inne"),
        "by_score_band": _grouped(settled, lambda e, s: _band(s.get("score"))),
        "learning_ready": overall["settled"] >= 300,
        "learning_target_sample": 300,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "shadow_only_never_mix_with_official_accuracy",
    }


def run(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    results = _read(RESULTS_PATH, [])
    if not isinstance(results, list):
        results = []
    entries = load_history(HISTORY_PATH)
    entries = capture_shadow_history(entries, results, now=now)
    entries = sorted(entries, key=lambda e: e.get("scheduled_time") or "", reverse=True)[:2500]
    save_history(HISTORY_PATH, entries)

    current = build_shadow_current(results)
    stats = build_shadow_stats(entries)
    _write(SHADOW_CURRENT_PATH, current)
    _write(SHADOW_STATS_PATH, stats)

    meta = _read(META_PATH, {})
    if not isinstance(meta, dict):
        meta = {}
    meta.update({
        "shadow_lab_version": SHADOW_VERSION,
        "shadow_current_rows": len(current),
        "shadow_matches_tracked": stats["matches_tracked"],
        "shadow_matches_pending": stats["matches_pending"],
        "shadow_settled_signals": stats["overall"]["settled"],
        "shadow_learning_ready": stats["learning_ready"],
        "shadow_updated_at": now.isoformat(),
    })
    _write(META_PATH, meta)
    return {
        "current_rows": len(current),
        "tracked": stats["matches_tracked"],
        "pending": stats["matches_pending"],
        "settled": stats["overall"]["settled"],
        "learning_ready": stats["learning_ready"],
    }


def main():
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
