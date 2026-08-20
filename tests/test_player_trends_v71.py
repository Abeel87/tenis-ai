from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))

from player_trends import build_player_tendencies
from pbp_enrich import _pbp_tendency_windows


def test_general_windows_and_surface():
    rows=[]
    for i in range(20):
        rows.append({
            "date":pd.Timestamp("2026-08-20")-pd.Timedelta(days=i+1),
            "player":"A","player_key":"a","opponent":"B","opponent_key":f"b{i}",
            "surface":"hard" if i<12 else "clay",
            "won":1.0 if i<8 else 0.0,
            "first_set_won":1.0 if i<7 else 0.0,
            "first_set_over85":1.0,
            "first_set_over95":1.0 if i%2==0 else 0.0,
            "first_set_over105":0.0,"first_set_over115":0.0,"first_set_over125":0.0,
            "sets_played":2.0 if i%3 else 3.0,
            "hold_rate":.8,"break_rate":.25,"serve_points_won":.64,"return_points_won":.38,
            "first_set_games":9.6,
        })
    df=pd.DataFrame(rows)
    x=build_player_tendencies(df,"A","hard","2026-08-21T10:00:00Z")
    assert x["all"]["5"]["sample_matches"]==5
    assert x["all"]["20"]["sample_matches"]==20
    assert x["surface"]["20"]["sample_matches"]==12
    assert x["all"]["10"]["metrics"]["match_win"]["hits"]==8
    assert x["all"]["5"]["metrics"]["set1_over_8.5"]["pct"]==100.0


def test_pbp_windows_keep_counts():
    samples=[]
    for i in range(12):
        samples.append({
            "surface":"hard" if i<9 else "clay",
            "hold1":1.0,"hold2":1.0 if i<8 else 0.0,"hold3":1.0,
            "after2":"1:1","after4":"2:2" if i<7 else "3:1","after6":"3:3" if i<6 else "4:2",
            "set1_win":1.0 if i<7 else 0.0,"over85":1.0,"over95":1.0 if i<6 else 0.0,
        })
    x=_pbp_tendency_windows(samples,"hard")
    assert x["all"]["10"]["sample_matches"]==10
    assert x["all"]["20"]["sample_matches"]==12
    assert x["surface"]["20"]["sample_matches"]==9
    assert x["all"]["5"]["metrics"]["hold1"]["pct"]==100.0
    assert x["all"]["10"]["metrics"]["after4_22"]["hits"]==7
