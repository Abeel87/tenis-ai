from __future__ import annotations
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"frontend"/"data"
RESULTS=DATA/"results.json"; HISTORY=DATA/"history.json"; OUT=DATA/"market_lab_history.json"; STATS=DATA/"market_lab_stats.json"; META=DATA/"meta.json"

def read(p,f):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except Exception:return f
def write(p,x):
    t=p.with_suffix(p.suffix+".tmp");t.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8");t.replace(p)
def dt(v):
    try:
        d=datetime.fromisoformat(str(v).replace("Z","+00:00"));return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:return None
def add(m,k,p):
    try:p=float(p)/100
    except Exception:return
    if 0<=p<=1:m[k]=round(p,4)

def flatten(x):
    l=x.get("market_lab_v741") or {};m={}
    for n,o in (l.get("set1_total") or {}).items():add(m,f"set1_over_{n}",o.get("over"))
    for n,o in (l.get("set2_total") or {}).items():add(m,f"set2_over_{n}",o.get("over"))
    add(m,"set1_exact_6_games",l.get("set1_exact_six_games"))
    add(m,"set1_tiebreak",(l.get("set1_tiebreak") or {}).get("yes"))
    add(m,"match_tiebreak",(l.get("match_tiebreak") or {}).get("yes"))
    add(m,"both_players_win_set",(l.get("both_players_win_set") or {}).get("yes"))
    for player,tag in ((x.get("p1"),"p1"),(x.get("p2"),"p2")):
        for n,o in ((l.get("player_total_games") or {}).get(player) or {}).items():add(m,f"{tag}_games_over_{n}",o.get("over"))
    return m

def outcomes(final):
    sets=[tuple(map(int,s[:2])) for s in (final.get("sets") or []) if isinstance(s,(list,tuple)) and len(s)>=2]
    if not sets:return {}
    o={}
    for i,s in enumerate(sets[:2],1):
        g=sum(s)
        for n in (6.5,7.5,8.5,9.5,10.5,11.5,12.5):o[f"set{i}_over_{n:.1f}"]=int(g>n)
    o["set1_exact_6_games"]=int(sum(sets[0])==6)
    o["set1_tiebreak"]=int(set(sets[0])=={6,7})
    o["match_tiebreak"]=int(any(set(s)=={6,7} for s in sets))
    o["both_players_win_set"]=int(len(sets)>=3)
    for tag,g in (("p1",sum(s[0] for s in sets)),("p2",sum(s[1] for s in sets))):
        for n in (6.5,7.5,8.5,9.5,10.5,11.5,12.5,13.5,14.5,15.5):o[f"{tag}_games_over_{n:.1f}"]=int(g>n)
    return o

def make_stats(rows):
    a={}
    for r in rows:
        ac=r.get("actual") or {}
        for k,p in (r.get("metrics") or {}).items():
            if k not in ac:continue
            y=ac[k];v=a.setdefault(k,{"n":0,"h":0,"g":0,"gh":0,"b":0.0})
            v["n"]+=1;v["h"]+=int((p>=.5)==bool(y));v["b"]+=(p-y)**2
            if max(p,1-p)>=.72:
                v["g"]+=1;v["gh"]+=int((p>=.5)==bool(y))
    markets={k:{"n":v["n"],"accuracy":round(100*v["h"]/v["n"],1),"green_n":v["g"],
                "green_accuracy":round(100*v["gh"]/v["g"],1) if v["g"] else None,
                "brier":round(v["b"]/v["n"],4)} for k,v in a.items()}
    n=sum(v["n"] for v in a.values());h=sum(v["h"] for v in a.values());g=sum(v["g"] for v in a.values());gh=sum(v["gh"] for v in a.values());b=sum(v["b"] for v in a.values())
    overall={"n":n,"accuracy":round(100*h/n,1) if n else None,"green_n":g,"green_accuracy":round(100*gh/g,1) if g else None,"brier":round(b/n,4) if n else None}
    return {"version":"v7.4.1","overall":overall,"markets":markets}

def main():
    now=datetime.now(timezone.utc);cur=read(RESULTS,[]);hist=read(HISTORY,[]);rows=read(OUT,[])
    if not isinstance(cur,list):cur=[]
    if not isinstance(hist,list):hist=[]
    if not isinstance(rows,list):rows=[]
    known={str(r.get("match_id")) for r in rows}
    by={str(h.get("match_id")):h for h in hist if h.get("match_id") is not None}
    cap=sett=0
    for x in cur:
        mid=x.get("id");sched=dt(x.get("scheduled_time"));metrics=flatten(x)
        if mid is None or str(mid) in known or not sched or sched<now+timedelta(minutes=2) or not metrics:continue
        rows.append({"match_id":mid,"scheduled_time":x.get("scheduled_time"),"p1":x.get("p1"),"p2":x.get("p2"),
                     "captured_at":now.isoformat(),"status":"pending","metrics":metrics,"actual":None})
        known.add(str(mid));cap+=1
    for r in rows:
        if r.get("status")=="settled":continue
        h=by.get(str(r.get("match_id")));final=(h or {}).get("result") or {}
        if (h or {}).get("status")=="settled" and final.get("sets"):
            r["actual"]=outcomes(final);r["status"]="settled";r["settled_at"]=now.isoformat();sett+=1
    rows=sorted(rows,key=lambda r:r.get("scheduled_time") or "",reverse=True)[:2500]
    write(OUT,rows);write(STATS,make_stats(rows))
    meta=read(META,{})
    if isinstance(meta,dict):
        meta.update({"market_lab_tracker_updated_at":now.isoformat(),"market_lab_tracker_captured_new":cap,
                     "market_lab_tracker_entries":len(rows),"market_lab_tracker_settled_new":sett,
                     "market_lab_tracker_settled_total":sum(r.get("status")=="settled" for r in rows)})
        write(META,meta)
    print(json.dumps({"captured":cap,"entries":len(rows),"settled_new":sett},ensure_ascii=False))
if __name__=="__main__":main()
