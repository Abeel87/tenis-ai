from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))

from serve_props import normalize_serve_props, poisson_over, _history_windows, _profile


def raw_rows():
    rows=[]
    base=pd.Timestamp("2026-08-01")
    for i in range(12):
        rows.append({
            "tourney_date":int((base-pd.Timedelta(days=i)).strftime("%Y%m%d")),
            "surface":"Hard" if i<8 else "Clay",
            "winner_name":"A","loser_name":"B",
            "score":"6-4 6-4",
            "w_ace":6+i%3,"l_ace":3,
            "w_df":2,"l_df":4,
            "w_SvGms":10,"l_SvGms":10,
        })
    return pd.DataFrame(rows)


def test_normalize_aces_df():
    x=normalize_serve_props(raw_rows())
    a=x[x.player=="A"].iloc[0]
    assert a.aces in (6,7,8)
    assert a.double_faults==2
    assert abs(a.ace_per_service_game-a.aces/10)<1e-9
    assert abs(a.aces_allowed_per_return_game-0.3)<1e-9


def test_poisson_line():
    p=poisson_over(5.0,3.5)
    assert 0.70 < p < 0.75
    q=poisson_over(2.0,3.5)
    assert 0.10 < q < 0.20


def test_windows():
    x=normalize_serve_props(raw_rows())
    h=_history_windows(x,"A","hard","2026-08-20T12:00:00Z")
    assert h["all"]["5"]["aces"]["sample"]==5
    assert h["all"]["10"]["double_faults"]["avg"]==2.0
    assert h["surface"]["20"]["sample_matches"]==8


def test_profile_ready():
    x=normalize_serve_props(raw_rows())
    p=_profile(x,"A","hard","2026-08-20T12:00:00Z")
    assert p["ready_aces"] is True
    assert p["ready_df"] is True
    assert p["ace_matches"]>=5


def test_serve_props_ui_has_no_body_wide_observer():
    js=(ROOT/"frontend"/"serve-props-v72.js").read_text(encoding="utf-8")
    assert "new MutationObserver(" not in js
    assert "obs.observe(document.body" not in js
    assert "scheduleRefresh(document)" in js
    assert "requestAnimationFrame" in js
    assert "data-sp-line" in js
