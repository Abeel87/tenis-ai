from pathlib import Path
import sys
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from pbp_tracker import capture, actual_from_tape, settle_one, tracker_stats

def row(a,b,server): return {"games":[[a],[b]],"points":["0","0"],"server":server,"sets":[0,0]}
def tape():
    scores=[(0,0),(1,0),(1,1),(2,1),(2,2),(3,2),(3,3),(4,3),(4,4),(5,4),(6,4)]; rows=[]
    for i in range(len(scores)-1):
        a,b=scores[i];na,nb=scores[i+1];server=1 if i%2==0 else 2
        rows += [row(a,b,server),row(a,b,server),row(na,nb,3-server)]
    return {"match":{"players":{"p1":{"name":"A"},"p2":{"name":"B"}}},"meta":{"coverage":"from_start","point_source":"observed"},"tape":rows}
def match():
    return {"id":77,"scheduled_time":"2026-08-21T12:00:00+00:00","p1":"A","p2":"B","surface":"hard","tour":"ATP",
      "early_hold_v7":{"ready":True,"version":"v7.1-pbp","balanced_after6":40.0,"p1":{"matches":8},"p2":{"matches":8}},
      "pick_first_set_early":"A","score_first_set_early":62.0,"score_lead_after6":38.0,"score_joint_builder":22.0,
      "early_over_under":{"8.5":{"over":76.0,"under":24.0}},
      "game_states":{"2":{"1:1":70.0},"4":{"2:2":55.0},"6":{"3:3":40.0}}}
def test_capture():
    x,n=capture([],[match()],datetime(2026,8,20,12,tzinfo=timezone.utc));assert n==1;assert x[0]["prediction"]["over85"]["prob"]==.76
def test_settle():
    e={"match_id":77,"p1":"A","p2":"B","status":"pending","prediction":{"first_set":{"pick":"A","prob":.62},"lead_after6":{"pick":"A","prob":.38},"over85":{"pick":"over","prob":.76},"joint_builder":{"pick":"A","prob":.22},"balanced_after6":{"pick":"3:3","prob":.4},"state2":{"state":"1:1","prob":.7},"state4":{"state":"2:2","prob":.55},"state6":{"state":"3:3","prob":.4}}}
    a=actual_from_tape(tape(),e);assert a["states"]["6"]=="3:3";assert a["first_set_winner"]=="A"
    s=settle_one(e,tape(),datetime.now(timezone.utc));assert s["status"]=="settled";by={x["market"]:x for x in s["signals"]};assert by["first_set"]["result"]=="hit";assert by["balanced_after6"]["result"]=="miss"
def test_stats():
    e={"status":"settled","signals":[{"market":"first_set","prob":.8,"actual":True,"brier":.04},{"market":"over85","prob":.75,"actual":False,"brier":.5625},{"market":"lead_after6","prob":.6,"actual":True,"brier":.16}]}
    s=tracker_stats([e]);assert s["overall"]["settled"]==3;assert s["green_72_plus"]["settled"]==2;assert s["green_72_plus"]["hits"]==1
