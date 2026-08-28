from __future__ import annotations
import json, math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/"frontend"/"data"/"results.json"
META=ROOT/"frontend"/"data"/"meta.json"
SET_LINES=(6.5,7.5,8.5,9.5,10.5,11.5,12.5)
PLAYER_LINES=(6.5,7.5,8.5,9.5,10.5,11.5,12.5,13.5,14.5,15.5)

def clamp(x,a=0.0,b=1.0): return max(a,min(b,float(x)))
def read(path,fallback):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return fallback
def write(path,obj):
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8");tmp.replace(path)
def norm(d):
    z=sum(max(0.0,float(v)) for v in d.values())
    return {k:max(0.0,float(v))/z for k,v in d.items()} if z else {}
def pct(x): return round(100*clamp(x),1)

def _name_key(value):
    import re, unicodedata
    text=unicodedata.normalize("NFKD",str(value or ""))
    text="".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(sorted(re.sub(r"[^a-zA-Z0-9]+"," ",text).casefold().split()))

def _operator_lines(m,market,player=None):
    ctx=m.get("superbet_market_v91") or {}
    if not isinstance(ctx,dict) or ctx.get("status") not in {"VERIFIED","CACHE_STALE"}:
        return ()
    target=_name_key(player) if player else None
    lines=set()
    for row in ctx.get("canonical_selections") or []:
        if not isinstance(row,dict) or row.get("market")!=market:
            continue
        if target and _name_key(row.get("player"))!=target:
            continue
        try: lines.add(float(row.get("line")))
        except (TypeError,ValueError): pass
    return tuple(sorted(lines))

def parse_exact(exact):
    d={}
    for k,v in (exact or {}).items():
        try:
            a,b=map(int,str(k).split(":")[:2]);p=float(v)/100
        except Exception:continue
        if p>0:d[(a,b)]=p
    return norm(d)
def base_set(h1,h2):
    def one(first):
        live={(0,0):1.0};term={}
        strength=(h1+(1-h2))/2
        tb=clamp(1/(1+math.exp(-(strength-.5)*8)),.20,.80)
        while live:
            nxt={}
            for (a,b),pr in live.items():
                if a==6 and b==6:
                    term[(7,6)]=term.get((7,6),0)+pr*tb
                    term[(6,7)]=term.get((6,7),0)+pr*(1-tb);continue
                if (a>=6 or b>=6) and abs(a-b)>=2:
                    term[(a,b)]=term.get((a,b),0)+pr;continue
                g=a+b
                p1serves=first if g%2==0 else not first
                pg=h1 if p1serves else 1-h2
                nxt[(a+1,b)]=nxt.get((a+1,b),0)+pr*pg
                nxt[(a,b+1)]=nxt.get((a,b+1),0)+pr*(1-pg)
            live=nxt
        return term
    a,b=one(True),one(False)
    return norm({k:(a.get(k,0)+b.get(k,0))/2 for k in set(a)|set(b)})
def p1win(d):return sum(p for (a,b),p in d.items() if a>b)
def reweight(d,target):
    raw=p1win(d);target=clamp(target,.03,.97)
    if raw<=0 or raw>=1:return dict(d)
    return norm({s:p*(target/raw if s[0]>s[1] else (1-target)/(1-raw)) for s,p in d.items()})
def ou(dist,lines=SET_LINES):
    lines=tuple(lines or SET_LINES)
    return {f"{ln:.1f}":{"over":pct(sum(p for (a,b),p in dist.items() if a+b>ln)),
                         "under":pct(sum(p for (a,b),p in dist.items() if a+b<ln))}
            for ln in lines}
def build_match(first,second_if_win,second_if_loss,third):
    joint={};tb={0:0.0,1:0.0,2:0.0,3:0.0};exact={"2:0":0.0,"2:1":0.0,"1:2":0.0,"0:2":0.0}
    for s1,p1 in first.items():
        w1=s1[0]>s1[1];t1=int(set(s1)=={6,7});second=second_if_win if w1 else second_if_loss
        for s2,p2 in second.items():
            w2=s2[0]>s2[1];t2=int(set(s2)=={6,7});p12=p1*p2;a=s1[0]+s2[0];b=s1[1]+s2[1]
            if w1 and w2:joint[(a,b)]=joint.get((a,b),0)+p12;exact["2:0"]+=p12;tb[t1+t2]+=p12
            elif not w1 and not w2:joint[(a,b)]=joint.get((a,b),0)+p12;exact["0:2"]+=p12;tb[t1+t2]+=p12
            else:
                for s3,p3 in third.items():
                    pr=p12*p3;aa=a+s3[0];bb=b+s3[1];t3=int(set(s3)=={6,7});joint[(aa,bb)]=joint.get((aa,bb),0)+pr;exact["2:1" if s3[0]>s3[1] else "1:2"]+=pr
    return norm(joint),norm(tb),norm(exact)
def mix_dist(a,b,wa):
    wa=clamp(wa);keys=set(a)|set(b);return norm({k:wa*a.get(k,0)+(1-wa)*b.get(k,0) for k in keys})
def player_lines(joint,idx,lines=PLAYER_LINES):
    lines=tuple(lines or PLAYER_LINES)
    out={}
    for ln in lines:
        ov=sum(p for (a,b),p in joint.items() if (a if idx==0 else b)>ln)
        out[f"{ln:.1f}"]={"over":pct(ov),"under":pct(1-ov)}
    return out
def combo(dist,line=6.5):
    return {"p1":{"under":pct(sum(p for (a,b),p in dist.items() if a>b and a<line)),
                  "over":pct(sum(p for (a,b),p in dist.items() if a>b and a>line))},
            "p2":{"under":pct(sum(p for (a,b),p in dist.items() if b>a and b<line)),
                  "over":pct(sum(p for (a,b),p in dist.items() if b>a and b>line))}}

def enrich(m):
    if not m.get("model_ready") or not m.get("service_model") or not m.get("exact_first_set"):return m
    try:
        h1=float(m["service_model"]["p1_hold"])/100;h2=float(m["service_model"]["p2_hold"])/100
    except Exception:return m
    first=parse_exact(m.get("exact_first_set"))
    if not first:return m
    p1=m.get("p1");p2=m.get("p2")
    op_set1=_operator_lines(m,"set1_total")
    op_set2=_operator_lines(m,"set2_total")
    op_match=_operator_lines(m,"match_total")
    op_p1=_operator_lines(m,"player_total_games",p1)
    op_p2=_operator_lines(m,"player_total_games",p2)
    operator_used=bool(op_set1 or op_set2 or op_match or op_p1 or op_p2)
    try:
        best_of=5 if int(m.get("best_of") or 3)==5 else 3
    except (TypeError,ValueError):
        best_of=3
    if best_of==5:
        tb1=sum(p for s,p in first.items() if set(s)=={6,7})
        six=sum(p for s,p in first.items() if sum(s)==6)
        m["market_lab_v741"]={
          "status":"LAB_SET1_ONLY",
          "note":"BO5 guard: tylko 1. set; pełne rynki meczu N/D do czasu dedykowanego silnika BO5.",
          "set1_total":ou(first,op_set1 or SET_LINES),
          "set1_exact_six_games":pct(six),
          "set1_tiebreak":{"yes":pct(tb1),"no":pct(1-tb1)},
          "set1_winner_player_games_6_5":combo(first),
          "operator_market_context":{"version":"v9.1","used":bool(op_set1),"prices_used":False,"set1_total_lines":list(op_set1)},
        }
        return m
    raw=base_set(h1,h2)
    def target(obj,name,default):
        try:return float((obj or {}).get(name))/100
        except Exception:return default
    second_default=target(m.get("second_set_win"),p1,p1win(first))
    ctx=m.get("second_set_context") or {}
    second_if_win=reweight(raw,target(ctx,"p1_if_p1_wins_set1",second_default))
    second_if_loss=reweight(raw,target(ctx,"p1_if_p1_loses_set1",second_default))
    second=mix_dist(second_if_win,second_if_loss,p1win(first))
    third=reweight(raw,target(m.get("third_set_win"),p1,p1win(first)))
    joint,tb,exact=build_match(first,second_if_win,second_if_loss,third)
    tb1=sum(p for s,p in first.items() if set(s)=={6,7})
    six=sum(p for s,p in first.items() if sum(s)==6)
    anytb=1-tb.get(0,0);three=exact.get("2:1",0)+exact.get("1:2",0)
    block={
      "status":"LAB",
      "note":"LAB walidowany osobno; gdy dostępny jest katalog Superbet v9.1, model liczy dokładnie linie wystawione przez operatora; nie podnosi głównego score.",
      "set1_total":ou(first,op_set1 or SET_LINES),"set2_total":ou(second,op_set2 or SET_LINES),
      "set1_exact_six_games":pct(six),
      "set1_tiebreak":{"yes":pct(tb1),"no":pct(1-tb1)},
      "match_tiebreak":{"yes":pct(anytb),"no":pct(1-anytb)},
      "tiebreak_count":{str(k):pct(v) for k,v in sorted(tb.items())},
      "both_players_win_set":{"yes":pct(three),"no":pct(1-three)},
      "player_total_games":{p1:player_lines(joint,0,op_p1 or PLAYER_LINES),p2:player_lines(joint,1,op_p2 or PLAYER_LINES)},
      "set1_winner_player_games_6_5":combo(first),
      "set2_winner_player_games_6_5":combo(second),
      "operator_market_context":{
          "version":"v9.1","used":operator_used,"prices_used":False,
          "set1_total_lines":list(op_set1),"set2_total_lines":list(op_set2),"match_total_lines":list(op_match),
          "player_total_games":{str(p1):list(op_p1),str(p2):list(op_p2)},
      },
    }
    if op_match:
        block["match_total"]=ou(joint,op_match)
    m["market_lab_v741"]=block
    return m

def main():
    rows=read(RESULTS,[])
    if not isinstance(rows,list):rows=[]
    ready=0;operator_ready=0;out=[]
    for m in rows:
        x=enrich(dict(m))
        if x.get("market_lab_v741"):
            ready+=1
            if ((x.get("market_lab_v741") or {}).get("operator_market_context") or {}).get("used"):
                operator_ready+=1
        out.append(x)
    write(RESULTS,out)
    meta=read(META,{})
    if isinstance(meta,dict):
        meta["market_lab_v741_ready"]=ready
        meta["market_lab_v741_operator_context_ready"]=operator_ready
        meta["market_lab_v741_note"]="LAB: set/match totals, player games, tie-breaks; Superbet v9.1 supplies real available lines when present."
        write(META,meta)
    print(json.dumps({"market_lab_v741_ready":ready,"operator_context_ready":operator_ready},ensure_ascii=False))
if __name__=="__main__":main()
