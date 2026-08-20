from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from live_history_settle import final_from_match, settle_entry
from datetime import datetime, timezone

def entry(): return {'p1':'A','p2':'B','status':'pending','signals':[]}
def test_completed_score():
    m={'winner':1,'event_status':None,'score':{'sets':[2,0],'games':[[6,6],[4,3]]}}
    f=final_from_match(m,entry());assert f['winner']=='A';assert f['match_score']=='2:0';assert f['first_set_score']=='6:4';assert f['total_games']==19

def test_live_not_final():
    m={'winner':None,'score':{'sets':[1,0],'games':[[6,2],[4,1]]}}
    assert final_from_match(m,entry()) is None

def test_walkover_void():
    f=final_from_match({'event_status':'Walk Over','winner':1,'score':None},entry());assert f['status']=='void'
