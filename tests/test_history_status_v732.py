from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from live_history_settle import final_from_match, settle_entry
from datetime import datetime, timezone

def entry(): return {'p1':'A','p2':'B','status':'pending','live_status':'Interrupted','signals':[]}
def test_interrupted_not_final(): assert final_from_match({'event_status':'Interrupted','winner':None},entry()) is None
def test_postponed_not_final(): assert final_from_match({'event_status':'Postponed','winner':None},entry()) is None
def test_settled_clears_live_status():
    x=settle_entry(entry(),{'status':'completed','winner':'A','sets':[[6,4],[6,3]],'p1':'A','p2':'B'},datetime.now(timezone.utc))
    assert x['status']=='settled' and 'live_status' not in x
