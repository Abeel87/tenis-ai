from __future__ import annotations

import gzip
import json
import math
import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from pbp_enrich import extract_first_set_games, _source_weight

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
CACHE = ROOT / "data" / "cache" / "pbp_v7"
MATCH_CACHE = CACHE / "matches"
INDEX_PATH = CACHE / "players.json"
RESULTS_PATH = OUT / "results.json"
PBP_HISTORY_PATH = OUT / "pbp_history.json"
PBP_STATS_PATH = OUT / "pbp_tracker_stats.json"
PBP_BACKTEST_PATH = OUT / "pbp_backtest.json"
GENERAL_HISTORY_PATH = OUT / "history.json"
GENERAL_STATS_PATH = OUT / "history_stats.json"
META_PATH = OUT / "meta.json"

BASE_URL = "https://api.livetennisapi.com/api/public/v1"
UA = "TenisAI-v7.3-PBP-Validation/1.0"
CAPTURE_CUTOFF_MINUTES = 5
MIN_SETTLE_AGE_MINUTES = 90
RETRY_HOURS = 6
MAX_REMOTE_SETTLES_PER_RUN = 18
DAILY_RESERVE = 120
GREEN = 0.72


def _read_json(path: Path, fallback):
    try:
        x = json.loads(path.read_text(encoding="utf-8"))
        return x
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _parse_dt(value):
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _key(value: Any) -> str:
    s = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def _match_cache_path(mid) -> Path:
    return MATCH_CACHE / f"{mid}.json.gz"


def _read_gz(path: Path):
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def _write_gz(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.gz")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as f:
        json.dump(value, f, ensure_ascii=False, separators=(",", ":"))
    tmp.replace(path)


def _p(x):
    try:
        y = float(x) / 100.0
        return max(0.0, min(1.0, y))
    except (TypeError, ValueError):
        return None


def _top_state(obj):
    rows = [(str(k), float(v)) for k, v in (obj or {}).items() if v is not None]
    if not rows:
        return None
    state, score = max(rows, key=lambda x: x[1])
    return {"state": state, "prob": round(score / 100.0, 4)}


def _prediction_snapshot(m: dict) -> dict:
    early = m.get("early_hold_v7") or {}
    over85 = (((m.get("early_over_under") or {}).get("8.5") or {}).get("over"))
    return {
        "first_set": {"pick": m.get("pick_first_set_early"), "prob": _p(m.get("score_first_set_early"))},
        "lead_after6": {"pick": m.get("pick_first_set_early"), "prob": _p(m.get("score_lead_after6"))},
        "over85": {"pick": "over", "prob": _p(over85)},
        "joint_builder": {"pick": m.get("pick_first_set_early"), "prob": _p(m.get("score_joint_builder"))},
        "balanced_after6": {"pick": "3:3", "prob": _p(early.get("balanced_after6"))},
        "state2": _top_state((m.get("game_states") or {}).get("2")),
        "state4": _top_state((m.get("game_states") or {}).get("4")),
        "state6": _top_state((m.get("game_states") or {}).get("6")),
    }


def capture(entries: list[dict], results: list[dict], now: datetime) -> tuple[list[dict], int]:
    by_id = {str(e.get("match_id")): e for e in entries if e.get("match_id") is not None}
    added = 0
    for m in results:
        eh = m.get("early_hold_v7") or {}
        if not eh.get("ready") or m.get("id") is None:
            continue
        scheduled = _parse_dt(m.get("scheduled_time"))
        if scheduled is None or scheduled <= now + timedelta(minutes=CAPTURE_CUTOFF_MINUTES):
            continue
        k = str(m["id"])
        old = by_id.get(k)
        if old and old.get("status") == "settled":
            continue
        snap = {
            "match_id": m.get("id"),
            "scheduled_time": m.get("scheduled_time"),
            "p1": m.get("p1"),
            "p2": m.get("p2"),
            "surface": m.get("surface") or "",
            "tour": m.get("tour") or "",
            "tournament": m.get("tournament") or "",
            "version": "v7.3-production-tracker",
            "model_version": eh.get("version") or "v7.1-pbp",
            "captured_at": now.isoformat(),
            "first_captured_at": (old or {}).get("first_captured_at") or now.isoformat(),
            "status": "pending",
            "prediction": _prediction_snapshot(m),
            "profile_snapshot": {
                "p1": {x: (eh.get("p1") or {}).get(x) for x in ("matches","surface_matches","ehs","quality","sample_ids")},
                "p2": {x: (eh.get("p2") or {}).get(x) for x in ("matches","surface_matches","ehs","quality","sample_ids")},
            },
            "actual": (old or {}).get("actual"),
            "last_attempt_at": (old or {}).get("last_attempt_at"),
            "settled_at": (old or {}).get("settled_at"),
        }
        if not old:
            added += 1
        by_id[k] = snap
    return sorted(by_id.values(), key=lambda e: e.get("scheduled_time") or "", reverse=True), added


def _tape_players(payload):
    match = payload.get("match") or {}
    players = match.get("players") or {}
    return (players.get("p1") or {}).get("name"), (players.get("p2") or {}).get("name")


def actual_from_tape(payload: dict, entry: dict) -> dict | None:
    parsed = extract_first_set_games(payload)
    if not parsed:
        return None
    tp1, tp2 = _tape_players(payload)
    same = _key(tp1) == _key(entry.get("p1")) and _key(tp2) == _key(entry.get("p2"))
    swapped = _key(tp1) == _key(entry.get("p2")) and _key(tp2) == _key(entry.get("p1"))
    if not same and not swapped:
        return None

    def orient_state(s):
        if not s:
            return None
        try:
            a, b = [int(v) for v in str(s).split(":", 1)]
            return f"{b}:{a}" if swapped else f"{a}:{b}"
        except Exception:
            return None

    states = {k: orient_state(v) for k, v in (parsed.get("checkpoints") or {}).items()}
    fs = orient_state(parsed.get("first_set_score"))
    if not fs:
        return None
    a, b = [int(v) for v in fs.split(":")]
    winner = entry.get("p1") if a > b else entry.get("p2")
    return {
        "first_set_score": fs,
        "first_set_winner": winner,
        "first_set_games": a + b,
        "over85": bool(a + b > 8.5),
        "states": states,
        "source": "BASIC PBP",
    }


def _result_signal(name: str, pred: dict | None, actual: dict, entry: dict):
    if not pred or pred.get("prob") is None:
        return None
    p = float(pred["prob"])
    pick = pred.get("pick")
    states = actual.get("states") or {}
    if name == "first_set":
        y = _key(pick) == _key(actual.get("first_set_winner"))
    elif name == "lead_after6":
        st = states.get("6")
        if not st: return None
        a, b = [int(x) for x in st.split(":")]
        y = (a > b and _key(pick) == _key(entry.get("p1"))) or (b > a and _key(pick) == _key(entry.get("p2")))
    elif name == "over85":
        y = bool(actual.get("over85"))
    elif name == "balanced_after6":
        y = states.get("6") == "3:3"
    elif name == "joint_builder":
        st = states.get("6")
        if not st: return None
        a, b = [int(x) for x in st.split(":")]
        lead = (a > b and _key(pick) == _key(entry.get("p1"))) or (b > a and _key(pick) == _key(entry.get("p2")))
        win = _key(pick) == _key(actual.get("first_set_winner"))
        y = lead and bool(actual.get("over85")) and win
    elif name in ("state2", "state4", "state6"):
        cp = name.replace("state", "")
        y = str(pick) == str(states.get(cp))
    else:
        return None
    return {
        "market": name, "pick": pick, "prob": round(p, 4), "actual": bool(y),
        "result": "hit" if y else "miss",
        "brier": round((p - (1.0 if y else 0.0)) ** 2, 6),
    }


def settle_one(entry: dict, payload: dict, now: datetime) -> dict | None:
    actual = actual_from_tape(payload, entry)
    if not actual:
        return None
    pred = entry.get("prediction") or {}
    signals = []
    for name in ("first_set","lead_after6","over85","joint_builder","balanced_after6","state2","state4","state6"):
        p = pred.get(name)
        if name.startswith("state") and p:
            p = {"pick": p.get("state"), "prob": p.get("prob")}
        s = _result_signal(name, p, actual, entry)
        if s: signals.append(s)
    out = dict(entry)
    out["actual"] = actual
    out["signals"] = signals
    out["status"] = "settled"
    out["settled_at"] = now.isoformat()
    return out


def _base_settled_ids(base_history):
    return {str(e.get("match_id")) for e in (base_history or [])
            if e.get("match_id") is not None and e.get("status") in ("settled", "void")}


def _usage_remaining(key: str):
    try:
        r = requests.get(BASE_URL + "/usage", headers={"Authorization": f"Bearer {key}", "User-Agent": UA}, timeout=(7,18))
        r.raise_for_status()
        u = r.json() or {}; today=u.get("today") or {}; limits=u.get("limits") or {}
        rem=today.get("remaining_day")
        if rem is None and isinstance(limits.get("per_day"),(int,float)) and isinstance(today.get("calls"),(int,float)):
            rem=int(limits["per_day"])-int(today["calls"])
        return int(rem) if isinstance(rem,(int,float)) else None
    except Exception:
        return None


def settle(entries: list[dict], base_history: list[dict], key: str, now: datetime):
    confirmed=_base_settled_ids(base_history)
    remote_budget=0; usage_checked=False; remote_calls=0; settled_n=0; out=[]
    for entry in entries:
        if entry.get("status")=="settled":
            out.append(entry); continue
        scheduled=_parse_dt(entry.get("scheduled_time"))
        if scheduled is None or scheduled > now-timedelta(minutes=MIN_SETTLE_AGE_MINUTES):
            out.append(entry); continue
        mid=entry.get("match_id"); path=_match_cache_path(mid); payload=_read_gz(path)
        if payload:
            got=settle_one(entry,payload,now)
            if got:
                settled_n+=1; out.append(got); continue
        last=_parse_dt(entry.get("last_attempt_at"))
        if last and now-last < timedelta(hours=RETRY_HOURS):
            out.append(entry); continue
        if not key or not (str(mid) in confirmed or now-scheduled >= timedelta(hours=6)):
            out.append(entry); continue
        if not usage_checked:
            remaining=_usage_remaining(key); usage_checked=True
            remote_budget=min(MAX_REMOTE_SETTLES_PER_RUN,max(0,(remaining or 0)-DAILY_RESERVE))
        if remote_calls>=remote_budget:
            out.append(entry); continue
        entry=dict(entry); entry["last_attempt_at"]=now.isoformat()
        try:
            r=requests.get(BASE_URL+f"/history/matches/{mid}",params={"sequence":"clean"},
                           headers={"Authorization":f"Bearer {key}","User-Agent":UA},timeout=(7,25))
            remote_calls+=1
            if r.status_code!=200:
                out.append(entry); continue
            payload=r.json(); got=settle_one(entry,payload,now)
            if got:
                _write_gz(path,payload); settled_n+=1; out.append(got)
            else: out.append(entry)
        except Exception:
            out.append(entry)
    return out,settled_n,remote_calls


def _summary(signals):
    n=len(signals)
    if not n:
        return {"settled":0,"hits":0,"misses":0,"accuracy":None,"avg_predicted":None,"brier":None}
    hits=sum(1 for s in signals if s.get("actual"))
    return {"settled":n,"hits":hits,"misses":n-hits,
            "accuracy":round(100*hits/n,1),
            "avg_predicted":round(100*sum(float(s["prob"]) for s in signals)/n,1),
            "brier":round(sum(float(s["brier"]) for s in signals)/n,4)}


def tracker_stats(entries):
    sig=[s for e in entries if e.get("status")=="settled" for s in (e.get("signals") or [])]
    by=defaultdict(list)
    for s in sig: by[s["market"]].append(s)
    buckets={}
    for lo,hi,label in ((0,.6,"<60"),(.6,.7,"60–69"),(.7,.8,"70–79"),(.8,.9,"80–89"),(.9,1.01,"90+")):
        rows=[s for s in sig if lo<=float(s.get("prob") or 0)<hi]
        if rows: buckets[label]=_summary(rows)
    green=[s for s in sig if float(s.get("prob") or 0)>=GREEN]
    return {"version":"v7.3","production_matches_captured":len(entries),
            "production_matches_settled":sum(1 for e in entries if e.get("status")=="settled"),
            "production_matches_pending":sum(1 for e in entries if e.get("status")!="settled"),
            "overall":_summary(sig),"green_72_plus":_summary(green),
            "markets":{k:_summary(v) for k,v in sorted(by.items())},
            "calibration_bands":buckets,
            "note":"Production tracker freezes the real pre-match Early Hold output and settles it from BASIC PBP."}


def _weighted(items):
    z=sum(w for _,w in items)
    return sum(v*w for v,w in items)/z if z else None


def _meta_by_match(index):
    out={}
    for entry in (index.get("players") or {}).values():
        for m in entry.get("matches") or []:
            if m.get("id") is not None: out[str(m["id"])]=m
    return out


def _sample_from_tape(mid,payload,meta):
    parsed=extract_first_set_games(payload)
    if not parsed: return []
    p1,p2=_tape_players(payload)
    if not p1 or not p2: return []
    date=(meta or {}).get("scheduled_time") or (payload.get("match") or {}).get("scheduled_time")
    surface=str((meta or {}).get("surface") or (payload.get("match") or {}).get("surface") or "").lower()
    try: a,b=[int(v) for v in parsed["first_set_score"].split(":")]
    except Exception: return []
    rows=[]
    for side,name in ((1,p1),(2,p2)):
        sg=parsed["service_games"].get(side) or {}
        rows.append({"mid":str(mid),"player":name,"date":date,"surface":surface,
                     "source_weight":float(_source_weight(payload)),
                     "hold1":sg.get("1"),"hold2":sg.get("2"),"hold3":sg.get("3"),
                     "after2_11":1.0 if parsed["checkpoints"].get("2")=="1:1" else 0.0,
                     "after4_22":1.0 if parsed["checkpoints"].get("4")=="2:2" else 0.0,
                     "after6_33":1.0 if parsed["checkpoints"].get("6")=="3:3" else 0.0,
                     "sequence":1.0 if parsed["checkpoints"].get("2")=="1:1" and parsed["checkpoints"].get("4")=="2:2" and parsed["checkpoints"].get("6")=="3:3" else 0.0,
                     "over85":1.0 if a+b>8.5 else 0.0,
                     "set1_win":1.0 if (side==1 and a>b) or (side==2 and b>a) else 0.0})
    return rows


def _walk_prob(prior,metric,surface):
    pairs=[]
    for i,s in enumerate(prior[:8]):
        v=s.get(metric)
        if v not in (0.0,1.0): continue
        recency=1.0 if i<5 else .55
        surf=1.35 if surface and s.get("surface")==surface else (.76 if surface else 1.0)
        pairs.append((float(v),recency*surf*float(s.get("source_weight") or 1.0)))
    return _weighted(pairs)


def backtest_cache():
    index=_read_json(INDEX_PATH,{"players":{}}); meta=_meta_by_match(index); samples=[]
    if MATCH_CACHE.exists():
        for path in MATCH_CACHE.glob("*.json.gz"):
            mid=path.stem.replace(".json",""); payload=_read_gz(path)
            if payload: samples.extend(_sample_from_tape(mid,payload,meta.get(str(mid)) or {}))
    by_player=defaultdict(list)
    for s in samples:
        d=_parse_dt(s.get("date"))
        if d: s["_dt"]=d; by_player[_key(s["player"])].append(s)
    obs=[]; metrics=("hold1","hold2","hold3","after2_11","after4_22","after6_33","sequence","over85","set1_win")
    for rows in by_player.values():
        rows.sort(key=lambda x:x["_dt"])
        for i,target in enumerate(rows):
            previous=[x for x in rows[:i] if x["_dt"]<target["_dt"]]
            if len(previous)<5: continue
            prior=list(reversed(previous))[:8]
            for metric in metrics:
                p=_walk_prob(prior,metric,target.get("surface")); y=target.get(metric)
                if p is None or y not in (0.0,1.0): continue
                confidence=max(p,1-p); chosen=p>=.5
                correct=(y==1.0) if chosen else (y==0.0)
                obs.append({"metric":metric,"confidence":confidence,"correct":bool(correct),
                            "brier":(p-y)**2,"green":confidence>=GREEN})
    def sm(rows):
        if not rows: return {"n":0,"accuracy":None,"green_n":0,"green_accuracy":None,"brier":None}
        green=[r for r in rows if r["green"]]
        return {"n":len(rows),"accuracy":round(100*sum(r["correct"] for r in rows)/len(rows),1),
                "green_n":len(green),
                "green_accuracy":round(100*sum(r["correct"] for r in green)/len(green),1) if green else None,
                "brier":round(sum(r["brier"] for r in rows)/len(rows),4)}
    grouped=defaultdict(list)
    for r in obs: grouped[r["metric"]].append(r)
    return {"version":"v7.3","type":"chronological-player-tendency-replay",
            "cached_tapes":len(list(MATCH_CACHE.glob("*.json.gz"))) if MATCH_CACHE.exists() else 0,
            "players":len(by_player),"overall":sm(obs),
            "metrics":{k:sm(v) for k,v in sorted(grouped.items())},
            "note":"Diagnostic walk-forward replay. Every target uses only earlier cached PBP matches for that player; it is not the full production match model."}


def _bucket(score):
    score=float(score or 72)
    return "90–100" if score>=90 else ("80–89" if score>=80 else "72–79")


def _general_history_stats(entries):
    settled=[(e,s) for e in entries for s in (e.get("signals") or []) if s.get("result") in ("hit","miss")]
    def summarize(items):
        hits=sum(1 for _,s in items if s.get("result")=="hit"); total=len(items)
        return {"settled":total,"hits":hits,"misses":total-hits,"accuracy":round(hits*100/total,1) if total else None}
    def grouped(fn):
        g={}
        for pair in settled: g.setdefault(fn(*pair),[]).append(pair)
        return {k:summarize(v) for k,v in sorted(g.items())}
    excluded=sum(1 for e in entries for s in (e.get("signals") or []) if s.get("result") in ("unverifiable","void"))
    return {"overall":summarize(settled),
            "matches_tracked":sum(1 for e in entries if e.get("signals")),
            "matches_pending":sum(1 for e in entries if e.get("status") in ("pending","upcoming") and e.get("signals")),
            "excluded_signals":excluded,
            "by_market":grouped(lambda e,s:s.get("label") or s.get("market") or "Inne"),
            "by_tour":grouped(lambda e,s:(e.get("tour") or "inne").upper()),
            "by_score_band":grouped(lambda e,s:_bucket(s.get("score"))),
            "generated_at":datetime.now(timezone.utc).isoformat(),"green_threshold":72.0}


def upgrade_general_game_states(base_history,now):
    changed=0
    for entry in base_history:
        mid=entry.get("match_id")
        if mid is None: continue
        candidates=[s for s in (entry.get("signals") or []) if s.get("market")=="game_state" and s.get("result")=="unverifiable"]
        if not candidates: continue
        payload=_read_gz(_match_cache_path(mid))
        if not payload: continue
        actual=actual_from_tape(payload,entry)
        if not actual: continue
        local=0; states=actual.get("states") or {}
        for s in candidates:
            observed=states.get(str(s.get("checkpoint") or ""))
            if observed:
                s["result"]="hit" if str(s.get("pick"))==observed else "miss"
                s["settlement_source"]="BASIC PBP v7.3"; changed+=1; local+=1
        if local: entry["pbp_game_state_checked_at"]=now.isoformat()
    return changed


def main():
    now=datetime.now(timezone.utc); key=os.getenv("LIVE_TENNIS_API_KEY","").strip()
    results=_read_json(RESULTS_PATH,[]); entries=_read_json(PBP_HISTORY_PATH,[]); base_history=_read_json(GENERAL_HISTORY_PATH,[])
    if not isinstance(results,list): results=[]
    if not isinstance(entries,list): entries=[]
    if not isinstance(base_history,list): base_history=[]
    entries,captured=capture(entries,results,now)
    entries,settled_n,remote_calls=settle(entries,base_history,key,now)
    entries=sorted(entries,key=lambda e:e.get("scheduled_time") or "",reverse=True)[:2500]
    _write_json(PBP_HISTORY_PATH,entries); _write_json(PBP_STATS_PATH,tracker_stats(entries))
    backtest=backtest_cache(); _write_json(PBP_BACKTEST_PATH,backtest)
    upgraded=upgrade_general_game_states(base_history,now)
    if upgraded:
        _write_json(GENERAL_HISTORY_PATH,base_history); _write_json(GENERAL_STATS_PATH,_general_history_stats(base_history))
    meta=_read_json(META_PATH,{})
    if not isinstance(meta,dict): meta={}
    meta.update({"pbp_v73_updated_at":now.isoformat(),"pbp_v73_captured_new":captured,
                 "pbp_v73_history_entries":len(entries),"pbp_v73_settled_this_run":settled_n,
                 "pbp_v73_settled_total":sum(1 for e in entries if e.get("status")=="settled"),
                 "pbp_v73_remote_calls":remote_calls,"pbp_v73_backtest_tapes":backtest.get("cached_tapes"),
                 "pbp_v73_backtest_observations":(backtest.get("overall") or {}).get("n"),
                 "pbp_v73_general_game_states_upgraded":upgraded})
    _write_json(META_PATH,meta)
    print(json.dumps({k:v for k,v in meta.items() if k.startswith("pbp_v73_")},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
