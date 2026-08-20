from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from history_tracker import history_stats, settle_signal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
CACHE = ROOT / "data" / "cache"
HISTORY_PATH = OUT / "history.json"
STATS_PATH = OUT / "history_stats.json"
META_PATH = OUT / "meta.json"
STATE_PATH = CACHE / "live_result_settle_v731.json"

BASE_URL = "https://api.livetennisapi.com/api/public/v1"
UA = "TenisAI-v7.3.1-HistorySettlement/1.0"
MIN_AGE_MINUTES = 75
RETRY_HOURS = 2
MAX_CALLS_PER_RUN = 40
DAILY_RESERVE = 150


def _read(path: Path, fallback):
    try:
        x=json.loads(path.read_text(encoding="utf-8"))
        return x
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(path)


def _dt(value):
    try:
        d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _obj(payload):
    if not isinstance(payload,dict): return {}
    d=payload.get("data")
    return d if isinstance(d,dict) else payload


def _usage_remaining(key: str):
    try:
        r=requests.get(BASE_URL+"/usage",headers={"Authorization":f"Bearer {key}","User-Agent":UA},timeout=(7,18))
        r.raise_for_status(); u=r.json() or {}; today=u.get("today") or {}; limits=u.get("limits") or {}
        rem=today.get("remaining_day")
        if rem is None and isinstance(limits.get("per_day"),(int,float)) and isinstance(today.get("calls"),(int,float)):
            rem=int(limits["per_day"])-int(today["calls"])
        return int(rem) if isinstance(rem,(int,float)) else None
    except Exception:
        return None


def _score_sets(match: dict):
    score=match.get("score") or {}
    games=score.get("games") or []
    try:
        p1=list(games[0] or []); p2=list(games[1] or [])
    except Exception:
        return []
    n=min(len(p1),len(p2))
    out=[]
    for i in range(n):
        try:
            a,b=int(p1[i]),int(p2[i])
        except (TypeError,ValueError):
            continue
        # Ignore an empty in-progress set, if any.
        if a==0 and b==0 and i==n-1:
            continue
        out.append([a,b])
    return out


def final_from_match(match: dict, entry: dict):
    status=str(match.get("event_status") or "").strip()
    if status in ("Cancelled","Walk Over","Retired"):
        return {"status":"void","winner":None,"score_text":status,"reason":status}
    if status in ("Postponed","Interrupted"):
        return None
    winner=match.get("winner")
    try: winner=int(winner) if winner is not None else None
    except (TypeError,ValueError): winner=None
    if winner not in (1,2):
        return None
    sets=_score_sets(match)
    if not sets:
        return None
    set_wins_p1=sum(1 for a,b in sets if a>b)
    set_wins_p2=sum(1 for a,b in sets if b>a)
    if set_wins_p1==set_wins_p2:
        # Winner field is authoritative, but a tied/partial score means detail is not final enough to settle totals.
        return None
    p1,p2=entry.get("p1"),entry.get("p2")
    actual_winner=p1 if winner==1 else p2
    score_text=" ".join(f"{a}-{b}" for a,b in sets)
    return {"status":"completed","winner":actual_winner,"score_text":score_text,"sets":sets,
            "match_score":f"{set_wins_p1}:{set_wins_p2}","number_of_sets":len(sets),
            "total_games":sum(a+b for a,b in sets),"first_set_score":f"{sets[0][0]}:{sets[0][1]}",
            "p1":p1,"p2":p2}


def settle_entry(entry: dict, final: dict, now: datetime):
    x=dict(entry); x["result"]=final; x["settled_at"]=now.isoformat(); x["settlement_source"]="Live Tennis API /matches/{id}"
    x["status"]="void" if final.get("status")=="void" else "settled"
    x.pop("live_status", None); x.pop("live_status_updated_at", None)
    signals=[]
    for s in x.get("signals") or []:
        s=dict(s)
        s["result"]=settle_signal(s,final)
        s["settlement_source"]="Live Tennis API"
        signals.append(s)
    x["signals"]=signals
    return x


def main():
    now=datetime.now(timezone.utc); key=os.getenv("LIVE_TENNIS_API_KEY","").strip()
    hist=_read(HISTORY_PATH,[]); state=_read(STATE_PATH,{"matches":{}}); meta=_read(META_PATH,{})
    if not isinstance(hist,list): hist=[]
    if not isinstance(state,dict): state={"matches":{}}
    state.setdefault("matches",{})
    if not isinstance(meta,dict): meta={}

    candidates=[]
    for i,e in enumerate(hist):
        if e.get("status") not in ("pending","upcoming") or e.get("match_id") is None: continue
        scheduled=_dt(e.get("scheduled_time"))
        if scheduled is None or scheduled > now-timedelta(minutes=MIN_AGE_MINUTES): continue
        rec=state["matches"].get(str(e["match_id"])) or {}
        last=_dt(rec.get("last_checked_at"))
        if last and now-last<timedelta(hours=RETRY_HOURS): continue
        candidates.append((scheduled,i,e))
    candidates.sort(key=lambda x:x[0])  # oldest first: clear backlog before newer matches

    remaining=_usage_remaining(key) if key and candidates else None
    budget=min(MAX_CALLS_PER_RUN,max(0,(remaining or 0)-DAILY_RESERVE)) if remaining is not None else 0
    calls=settled=voided=not_ready=errors=0

    for _,idx,e in candidates[:budget]:
        mid=e.get("match_id"); rec=state["matches"].setdefault(str(mid),{})
        rec["last_checked_at"]=now.isoformat(); rec["checks"]=int(rec.get("checks") or 0)+1
        try:
            r=requests.get(BASE_URL+f"/matches/{mid}",headers={"Authorization":f"Bearer {key}","User-Agent":UA},timeout=(7,22))
            calls+=1
            rec["last_status_code"]=r.status_code
            if r.status_code!=200:
                errors+=1; continue
            match=_obj(r.json()); final=final_from_match(match,e)
            if final is None:
                not_ready+=1
                feed_status=str(match.get("event_status") or match.get("status") or "").strip()
                rec["last_feed_status"]=feed_status
                pending=dict(e)
                if feed_status:
                    pending["live_status"]=feed_status
                    pending["live_status_updated_at"]=now.isoformat()
                hist[idx]=pending
                continue
            hist[idx]=settle_entry(e,final,now)
            rec["settled_at"]=now.isoformat(); rec["settled_status"]=final.get("status")
            if final.get("status")=="void": voided+=1
            else: settled+=1
        except Exception as ex:
            errors+=1; rec["last_error"]=type(ex).__name__

    # Keep state bounded; settled entries need no repeated checks.
    if len(state["matches"])>3000:
        keys=list(state["matches"].keys())[-3000:]; state["matches"]={k:state["matches"][k] for k in keys}
    state["updated_at"]=now.isoformat(); _write(STATE_PATH,state)
    _write(HISTORY_PATH,hist); _write(STATS_PATH,history_stats(hist))
    meta.update({"history_live_settle_updated_at":now.isoformat(),"history_live_settle_candidates":len(candidates),
                 "history_live_settle_calls":calls,"history_live_settle_settled":settled,"history_live_settle_voided":voided,
                 "history_live_settle_not_ready":not_ready,"history_live_settle_errors":errors,
                 "history_live_settle_remaining_before":remaining})
    _write(META_PATH,meta)
    print(json.dumps({k:v for k,v in meta.items() if k.startswith("history_live_settle_")},ensure_ascii=False,indent=2))


if __name__=="__main__": main()
