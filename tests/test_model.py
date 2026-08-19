import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import pandas as pd
from model import parse_first_set, normalize_matches, analyse_match

def test_parse_set():
    assert parse_first_set('7-6(5) 6-4')==(7,6)

def test_no_fake_lead_after6():
    rows=[]
    for i in range(10):
        rows.append({'tourney_date':20260801-i,'surface':'Hard','winner_name':'Alpha','loser_name':'Beta','score':'6-4 6-4','w_svpt':60,'w_1stIn':38,'w_1stWon':30,'w_2ndWon':12,'w_SvGms':10,'w_bpSaved':3,'w_bpFaced':4,'l_svpt':62,'l_1stIn':39,'l_1stWon':25,'l_2ndWon':10,'l_SvGms':10,'l_bpSaved':4,'l_bpFaced':6})
    long=normalize_matches(pd.DataFrame(rows))
    r=analyse_match(long,{'tour':'atp','tournament':'X','surface':'hard','p1':'Alpha','p2':'Beta','scheduled_time':''})
    assert r['score_lead_after6'] is None
    assert r['score_first_set'] is not None
