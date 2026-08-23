from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
RESULTS_PATH = OUT / "results.json"
HISTORY_PATH = OUT / "history.json"
META_PATH = OUT / "meta.json"

VERSION = "v7.9B-specialist-tracker"
CAPTURE_CUTOFF_MINUTES = 5
DISPLAY_THRESHOLD = 68.0
MODEL_IDS = ("adaptive", "early", "serve", "form", "surface")
TRACKED_SPECIALISTS = ("early", "serve", "form", "surface", "consensus")


def _read(path: Path, fallback):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _write(path: Path, value):
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


def clamp(x, lo=0.0, hi=100.0):
    v = _num(x, 50.0)
    return max(lo, min(hi, v))


def avg(*xs):
    vals = [float(x) for x in xs if _num(x) is not None]
    return sum(vals) / len(vals) if vals else 0.5


def pc(x):
    return _num(x, 0.5)


def conf01(x):
    return clamp(_num(x, 50.0), 0, 100) / 100.0


def pair_score(a, b, scale=100.0, confidence=1.0):
    return clamp(50.0 + (a - b) * scale * confidence, 8, 92)


def key_safe(s):
    return re.sub(r"[^a-z0-9.:-]+", "_", str(s or "").lower())


def mk(key, label, v, market, pick, **extra):
    return {
        "key": key,
        "label": label,
        "score": round(clamp(v), 1),
        "market": market,
        "pick": str(pick),
        **extra,
    }


def best_entry(obj):
    rows = [(str(k), _num(v)) for k, v in (obj or {}).items() if _num(v) is not None]
    return max(rows, key=lambda x: x[1]) if rows else None


def player_stats(m, p):
    return (m.get("p1_stats") or {}) if p == 1 else (m.get("p2_stats") or {})


def player_name(m, p):
    return m.get("p1") if p == 1 else m.get("p2")


def adaptive_signals(m):
    out = []

    def bin_sig(key_market, market, prefix, obj):
        e = best_entry(obj)
        if e:
            out.append(mk(f"{key_market}|{key_safe(e[0])}", f"{prefix}: {e[0]}", e[1], market, e[0]))

    # Keep JS consensus keys exactly, but use backend-settleable market names.
    bin_sig("match_win", "match_winner", "Mecz", m.get("match_win"))
    bin_sig("set1_win", "set1_winner", "1. set", m.get("first_set_win"))
    bin_sig("set2_win", "set2_winner", "2. set", m.get("second_set_win"))
    bin_sig("set3_win", "set3_winner", "3. set*", m.get("third_set_win"))
    bin_sig("total_sets", "total_sets", "Sety", m.get("total_sets"))

    for line, sides in (m.get("over_under") or {}).items():
        over, under = _num((sides or {}).get("over")), _num((sides or {}).get("under"))
        if over is None or under is None:
            continue
        pick = "over" if over >= under else "under"
        out.append(mk(f"set1_total|{line}|{pick}", f"1S {'O' if pick == 'over' else 'U'}{line}",
                      over if pick == "over" else under, "set1_total", pick, line=float(line)))

    for line, sides in (m.get("match_over_under") or {}).items():
        over, under = _num((sides or {}).get("over")), _num((sides or {}).get("under"))
        if over is None or under is None:
            continue
        pick = "over" if over >= under else "under"
        out.append(mk(f"match_total|{line}|{pick}", f"M {'O' if pick == 'over' else 'U'}{line}",
                      over if pick == "over" else under, "match_total", pick, line=float(line)))
    return out


def strength_serve(s):
    return (.34 * pc(s.get("hold_rate")) + .22 * pc(s.get("break_rate"))
            + .18 * pc(s.get("serve_points_won")) + .16 * pc(s.get("return_points_won"))
            + .10 * pc(s.get("won")))


def strength_set1(s):
    return (.30 * pc(s.get("first_set_won")) + .25 * pc(s.get("hold_rate"))
            + .18 * pc(s.get("break_rate")) + .14 * pc(s.get("serve_points_won"))
            + .13 * pc(s.get("return_points_won")))


def strength_form(s):
    fatigue = clamp(_num(s.get("fatigue_load"), 0), 0, 6) / 6
    inactivity = clamp((_num(s.get("days_since_last"), 0) - 35) / 140, 0, 1)
    return (.40 * pc(s.get("won")) + .30 * pc(s.get("first_set_won"))
            + .16 * pc(s.get("second_set_won")) + .08 * pc(s.get("third_set_won"))
            + .06 * (1 - fatigue) - .05 * inactivity)


def sample_confidence(s, kind="all"):
    n = _num(s.get("surface_matches") if kind == "surface" else s.get("matches"), 0)
    data = conf01(s.get("data_confidence") or 60)
    return clamp((n / (n + 5)) * .70 + data * .30, .22, 1)


def over_hist(s, line):
    mp = {
        "8.5": "first_set_over85", "9.5": "first_set_over95",
        "10.5": "first_set_over105", "11.5": "first_set_over115",
        "12.5": "first_set_over125",
    }
    return _num(s.get(mp.get(str(line), "")))


def expected_over(s1, s2, line):
    vals = [x for x in (over_hist(s1, line), over_hist(s2, line)) if x is not None]
    if vals:
        return avg(*vals)
    games = avg(s1.get("first_set_games"), s2.get("first_set_games"))
    return clamp(.5 + (games - float(line)) * .09, .08, .92)


def hold_balance(m):
    sm = m.get("service_model") or {}
    h1 = _num(sm.get("p1_hold"))
    h2 = _num(sm.get("p2_hold"))
    if h1 is None:
        h1 = pc((m.get("p1_stats") or {}).get("hold_rate")) * 100
    if h2 is None:
        h2 = pc((m.get("p2_stats") or {}).get("hold_rate")) * 100
    h1, h2 = clamp(h1), clamp(h2)
    return {"h1": h1, "h2": h2, "avg": (h1 + h2) / 2, "diff": abs(h1 - h2)}


def winner_signals(m, mode):
    s1, s2 = player_stats(m, 1), player_stats(m, 2)
    if mode == "serve":
        a, b = strength_serve(s1), strength_serve(s2)
        conf = avg(sample_confidence(s1), sample_confidence(s2))
    elif mode == "form":
        a, b = strength_form(s1), strength_form(s2)
        conf = avg(sample_confidence(s1), sample_confidence(s2))
    else:
        a = .30*pc(s1.get("won")) + .25*pc(s1.get("first_set_won")) + .20*pc(s1.get("hold_rate")) + .15*pc(s1.get("break_rate")) + .10*pc(s1.get("return_points_won"))
        b = .30*pc(s2.get("won")) + .25*pc(s2.get("first_set_won")) + .20*pc(s2.get("hold_rate")) + .15*pc(s2.get("break_rate")) + .10*pc(s2.get("return_points_won"))
        conf = avg(sample_confidence(s1, "surface"), sample_confidence(s2, "surface"))

    p1 = pair_score(a, b, 145, conf)
    p2 = 100 - p1
    match_p = 1 if p1 >= p2 else 2
    match_v = max(p1, p2)

    if mode == "serve":
        a1, b1 = strength_set1(s1), strength_set1(s2)
    elif mode == "form":
        a1 = .55*pc(s1.get("first_set_won")) + .30*pc(s1.get("won")) + .15*pc(s1.get("hold_rate"))
        b1 = .55*pc(s2.get("first_set_won")) + .30*pc(s2.get("won")) + .15*pc(s2.get("hold_rate"))
    else:
        a1 = .50*pc(s1.get("first_set_won")) + .22*pc(s1.get("hold_rate")) + .16*pc(s1.get("break_rate")) + .12*pc(s1.get("won"))
        b1 = .50*pc(s2.get("first_set_won")) + .22*pc(s2.get("hold_rate")) + .16*pc(s2.get("break_rate")) + .12*pc(s2.get("won"))

    f1 = pair_score(a1, b1, 155, conf)
    f2 = 100 - f1
    set_p = 1 if f1 >= f2 else 2
    return [
        mk(f"match_win|{key_safe(player_name(m, match_p))}", f"Mecz: {player_name(m, match_p)}",
           match_v, "match_winner", player_name(m, match_p)),
        mk(f"set1_win|{key_safe(player_name(m, set_p))}", f"1. set: {player_name(m, set_p)}",
           max(f1, f2), "set1_winner", player_name(m, set_p)),
    ]


def total_signals(m, mode):
    s1, s2, out = m.get("p1_stats") or {}, m.get("p2_stats") or {}, []
    hb = hold_balance(m)
    for line in (m.get("over_under") or {}).keys():
        over = expected_over(s1, s2, line)
        if mode == "serve":
            over = .62*over + .38*clamp((hb["avg"] - 58)/30, 0, 1)
        elif mode == "form":
            over = .78*over + .22*avg(pc(s1.get("first_set_over85")), pc(s2.get("first_set_over85")))
        elif mode == "surface":
            cf = avg(sample_confidence(s1, "surface"), sample_confidence(s2, "surface"))
            over = .5 + (over - .5)*cf
        elif mode == "early":
            over = .55*over + .45*clamp((hb["avg"] - 56)/34, 0, 1)
        over = clamp(over*100, 7, 93)
        under = 100 - over
        pick = "over" if over >= under else "under"
        out.append(mk(f"set1_total|{line}|{pick}", f"1S {'O' if pick=='over' else 'U'}{line}",
                      max(over, under), "set1_total", pick, line=float(line)))

    if mode != "early":
        for line, v in (m.get("match_over_under") or {}).items():
            base = _num((v or {}).get("over"))
            if base is None:
                continue
            over = base
            if mode == "serve":
                over = .70*base + .30*clamp(50 + (hb["avg"] - 68)*1.3, 15, 85)
            elif mode == "form":
                over = .82*base + .18*clamp(50 + (avg(s1.get("first_set_games"), s2.get("first_set_games")) - 9.5)*5, 25, 75)
            elif mode == "surface":
                cf = avg(sample_confidence(s1, "surface"), sample_confidence(s2, "surface"))
                over = 50 + (base - 50)*cf
            under = 100 - over
            pick = "over" if over >= under else "under"
            out.append(mk(f"match_total|{line}|{pick}", f"M {'O' if pick=='over' else 'U'}{line}",
                          max(over, under), "match_total", pick, line=float(line)))
    return out


def early_winner(m):
    s1, s2 = m.get("p1_stats") or {}, m.get("p2_stats") or {}
    a = .48*pc(s1.get("first_set_won")) + .26*pc(s1.get("hold_rate")) + .16*pc(s1.get("break_rate")) + .10*pc(s1.get("serve_points_won"))
    b = .48*pc(s2.get("first_set_won")) + .26*pc(s2.get("hold_rate")) + .16*pc(s2.get("break_rate")) + .10*pc(s2.get("serve_points_won"))
    conf = avg(sample_confidence(s1), sample_confidence(s2))
    p1 = pair_score(a, b, 145, conf)
    p2 = 100 - p1
    p = 1 if p1 >= p2 else 2
    return mk(f"set1_win|{key_safe(player_name(m,p))}", f"1. set: {player_name(m,p)}",
              max(p1,p2), "set1_winner", player_name(m,p))


def model_signals(model_id, m):
    if model_id == "adaptive":
        return adaptive_signals(m)
    if model_id == "early":
        return [early_winner(m), *total_signals(m, "early")]
    if model_id == "serve":
        return [*winner_signals(m, "serve"), *total_signals(m, "serve")]
    if model_id == "form":
        return [*winner_signals(m, "form"), *total_signals(m, "form")]
    if model_id == "surface":
        return [*winner_signals(m, "surface"), *total_signals(m, "surface")]
    return []


def consensus_signals(m):
    maps = {mid: {x["key"]: x for x in model_signals(mid, m)} for mid in MODEL_IDS}
    keys = set().union(*(mp.keys() for mp in maps.values()))
    out = []
    for key in keys:
        vals = [maps[mid].get(key) for mid in MODEL_IDS if maps[mid].get(key)]
        if len(vals) < 2:
            continue
        supporters = [x for x in vals if x["score"] >= 68]
        if len(supporters) < 2:
            continue
        strong = sum(1 for x in supporters if x["score"] >= 72)
        mean = sum(x["score"] for x in supporters) / len(supporters)
        sc = clamp(mean + (len(supporters)-1)*1.7 + (1.5 if strong >= 3 else 0), 0, 98)
        x = max(supporters, key=lambda r: r["score"])
        out.append({
            **x,
            "score": round(sc, 1),
            "votes": len(supporters),
            "strong_votes": strong,
            "model_scores": {mid: (maps[mid].get(key) or {}).get("score") for mid in MODEL_IDS},
        })
    return sorted(out, key=lambda r: (-r["votes"], -r["strong_votes"], -r["score"]))


def specialist_signals(m):
    out = []
    for model_id in ("early", "serve", "form", "surface"):
        for s in model_signals(model_id, m):
            if s["score"] < DISPLAY_THRESHOLD:
                continue
            out.append({
                **s,
                "source_model": model_id,
                "result": "pending",
                "learning_only": True,
                "tracker_version": VERSION,
            })
    for s in consensus_signals(m):
        if s["score"] < DISPLAY_THRESHOLD:
            continue
        out.append({
            **s,
            "source_model": "consensus",
            "result": "pending",
            "learning_only": True,
            "tracker_version": VERSION,
        })
    # De-duplicate per source/key.
    uniq = {}
    for s in out:
        uniq[(s["source_model"], s["key"])] = s
    return sorted(uniq.values(), key=lambda x: (x["source_model"], -x["score"], x["key"]))


def _dt(value):
    try:
        d = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _match_key(m):
    mid = m.get("id")
    if mid is not None and str(mid) != "":
        return f"id:{mid}"
    def norm(x):
        return " ".join(re.sub(r"[^a-z0-9]+", " ", str(x or "").lower()).split())
    return "|".join([norm(m.get("p1")), norm(m.get("p2")), str(m.get("scheduled_time") or "")[:10], norm(m.get("tournament"))])


def capture(entries, results, now=None, cutoff_minutes=CAPTURE_CUTOFF_MINUTES):
    now = now or datetime.now(timezone.utc)
    by_key = {e.get("match_key"): dict(e) for e in entries or [] if e.get("match_key")}
    captured_matches = 0
    captured_signals = 0

    for m in results or []:
        if not isinstance(m, dict) or not m.get("model_ready"):
            continue
        scheduled = _dt(m.get("scheduled_time"))
        if scheduled is None or scheduled <= now + timedelta(minutes=cutoff_minutes):
            continue
        key = _match_key(m)
        e = by_key.get(key)
        if not e or e.get("status") not in ("pending", "upcoming"):
            continue

        sigs = specialist_signals(m)
        e["learning_signals_v79b"] = sigs
        e["specialist_learning_version"] = VERSION
        e["specialist_learning_captured_at"] = now.isoformat()
        e["specialist_learning_first_captured_at"] = e.get("specialist_learning_first_captured_at") or now.isoformat()
        by_key[key] = e
        captured_matches += 1
        captured_signals += len(sigs)

    return list(by_key.values()), captured_matches, captured_signals


def run(now=None):
    now = now or datetime.now(timezone.utc)
    results = _read(RESULTS_PATH, [])
    history = _read(HISTORY_PATH, [])
    meta = _read(META_PATH, {})
    if not isinstance(results, list): results = []
    if not isinstance(history, list): history = []
    if not isinstance(meta, dict): meta = {}

    history, matches, signals = capture(history, results, now=now)
    history = sorted(history, key=lambda e: e.get("scheduled_time") or "", reverse=True)[:2500]
    _write(HISTORY_PATH, history)

    pending_signals = sum(
        1 for e in history for s in (e.get("learning_signals_v79b") or [])
        if s.get("result") == "pending"
    )
    tracked_models = sorted({
        s.get("source_model") for e in history for s in (e.get("learning_signals_v79b") or [])
        if s.get("source_model")
    })
    meta.update({
        "specialist_learning_version": VERSION,
        "specialist_learning_captured_matches": matches,
        "specialist_learning_captured_signals": signals,
        "specialist_learning_pending_signals": pending_signals,
        "specialist_learning_models": tracked_models,
        "specialist_learning_updated_at": now.isoformat(),
    })
    _write(META_PATH, meta)
    return {
        "version": VERSION,
        "captured_matches": matches,
        "captured_signals": signals,
        "pending_signals": pending_signals,
        "models": tracked_models,
    }


def main():
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
