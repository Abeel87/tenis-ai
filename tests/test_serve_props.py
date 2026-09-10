from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))

from serve_props import normalize_serve_props, poisson_over, _history_windows, _profile, _side_model


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


def _ace_profile(*, ace_rate, allow_rate, ready=True):
    return {
        "ace_per_service_game": ace_rate,
        "aces_allowed_per_return_game": allow_rate,
        "df_per_service_game": 0.20,
        "ready_aces": ready,
        "ready_df": True,
        "ace_matches": 12,
        "df_matches": 12,
        "allow_matches": 12,
        "match_games": 22.0,
    }


def test_master_plan_high_ace_server_scores_higher_vs_weak_returner():
    match = {"expected_match_games": 22.0}
    server = _ace_profile(ace_rate=0.80, allow_rate=0.30)
    weak_returner = _ace_profile(ace_rate=0.40, allow_rate=0.70)
    strong_returner = _ace_profile(ace_rate=0.40, allow_rate=0.20)

    weak = _side_model(match, server, weak_returner, "p1", None)
    strong = _side_model(match, server, strong_returner, "p1", None)

    assert weak["aces"]["ready"] is True
    assert strong["aces"]["ready"] is True
    assert weak["aces"]["mean"] > strong["aces"]["mean"]


def test_ace_mean_is_monotone_in_server_ace_rate_for_fixed_returner():
    match = {"expected_match_games": 22.0}
    returner = _ace_profile(ace_rate=0.40, allow_rate=0.45)

    means = []
    for rate in (0.40, 0.60, 0.80):
        server = _ace_profile(ace_rate=rate, allow_rate=0.30)
        result = _side_model(match, server, returner, "p1", None)
        means.append(result["aces"]["mean"])

    assert means[0] < means[1] < means[2]
