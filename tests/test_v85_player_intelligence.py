from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path

import pandas as pd

MODULE = Path(__file__).resolve().parents[1] / "backend" / "player_intelligence_v85.py"
spec = importlib.util.spec_from_file_location("player_intelligence_v85", MODULE)
pi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pi)


def _df():
    rows=[]
    base=pd.Timestamp("2026-08-20")
    for i in range(12):
        rows.append({
            "date": base-pd.Timedelta(days=i*10), "surface":"hard", "player":"A", "player_key":"a",
            "opponent":"X", "opponent_rank":50+i*10, "rank":20, "won":1.0 if i<8 else 0.0,
            "hold_rate":.82, "break_rate":.31, "serve_points_won":.64, "return_points_won":.41,
            "first_serve_won":.72, "second_serve_won":.53, "first_set_won":.7, "second_set_won":.65,
            "second_after_first_win":.7, "second_after_first_loss":.55, "third_set_won":.6,
            "first_set_over85":.8, "first_set_over95":.55, "first_set_over105":.3, "sets_played":3,
        })
    for i in range(20):
        rows.append({
            "date": base-pd.Timedelta(days=i*8), "surface":"clay", "player":"A", "player_key":"a",
            "opponent":"Y", "opponent_rank":200, "rank":20, "won":0.0,
            "hold_rate":.60, "break_rate":.20, "serve_points_won":.55, "return_points_won":.34,
            "first_serve_won":.62, "second_serve_won":.42, "first_set_won":.2, "second_set_won":.2,
            "second_after_first_win":.2, "second_after_first_loss":.2, "third_set_won":.2,
            "first_set_over85":.4, "first_set_over95":.25, "first_set_over105":.1, "sets_played":2,
        })
    for i in range(12):
        rows.append({
            "date": base-pd.Timedelta(days=i*10), "surface":"hard", "player":"B", "player_key":"b",
            "opponent":"Z", "opponent_rank":300+i*5, "rank":90, "won":1.0 if i<5 else 0.0,
            "hold_rate":.72, "break_rate":.24, "serve_points_won":.58, "return_points_won":.37,
            "first_serve_won":.66, "second_serve_won":.45, "first_set_won":.45, "second_set_won":.45,
            "second_after_first_win":.5, "second_after_first_loss":.4, "third_set_won":.45,
            "first_set_over85":.72, "first_set_over95":.48, "first_set_over105":.25, "sets_played":2,
        })
    return pd.DataFrame(rows)


def test_profile_uses_same_surface_only():
    p=pi.build_profile(_df(),"A","hard","2026-08-24T12:00:00Z",80)
    assert p["surface"]=="hard"
    assert p["sample_matches"]==12
    hold=p["windows"]["10"]["metrics"]["hold_rate"]["raw"]
    assert hold > .80


def test_windows_are_5_10_20_and_quality():
    p=pi.build_profile(_df(),"A","hard","2026-08-24T12:00:00Z",80)
    assert set(p["windows"])=={"5","10","20"}
    assert p["windows"]["5"]["sample_matches"]==5
    assert p["windows"]["10"]["sample_matches"]==10
    assert p["quality"] in {"HIGH","MEDIUM"}


def test_shadow_is_bounded():
    s,shift=pi._shadow(.70,.95,"HIGH")
    assert round(shift,6) <= .04
    assert s <= .74
    s2,shift2=pi._shadow(.70,.20,"MEDIUM")
    assert shift2 >= -.02
    assert s2 >= .6799


def test_winner_probability_favors_stronger_profile():
    df=_df()
    a=pi.build_profile(df,"A","hard","2026-08-24T12:00:00Z",80)
    b=pi.build_profile(df,"B","hard","2026-08-24T12:00:00Z",55)
    p=pi._winner_probability(a,b,1)
    assert p is not None and p > .5


def test_over_probability_available_for_first_set_lines():
    df=_df()
    a=pi.build_profile(df,"A","hard","2026-08-24T12:00:00Z",80)
    b=pi.build_profile(df,"B","hard","2026-08-24T12:00:00Z",55)
    p=pi._over_probability(a,b,8.5)
    assert p is not None and .2 <= p <= .9


def test_no_cross_surface_fallback():
    df=_df()
    p=pi.build_profile(df,"A","grass","2026-08-24T12:00:00Z",None)
    assert p["sample_matches"]==0
    assert p["quality"]=="N/D"


def test_parse_up_to_five_sets():
    assert pi._set_pairs('6-4 3-6 7-6 2-6 6-3') == [(6,4),(3,6),(7,6),(2,6),(6,3)]


def test_undated_history_is_excluded_from_player_profile_and_priors():
    df = _df()
    poisoned = df.iloc[[0]].copy()
    poisoned["date"] = pd.NaT
    poisoned["hold_rate"] = 0.01
    poisoned["won"] = 0.0
    combined = pd.concat([df, poisoned], ignore_index=True)

    clean = pi.build_profile(df, "A", "hard", "2026-08-24T12:00:00Z", 80)
    guarded = pi.build_profile(combined, "A", "hard", "2026-08-24T12:00:00Z", 80)

    assert guarded["sample_matches"] == clean["sample_matches"]
    assert guarded["windows"]["10"]["metrics"]["hold_rate"] == clean["windows"]["10"]["metrics"]["hold_rate"]
    priors_clean = pi._surface_priors(df, "hard", pd.Timestamp("2026-08-24"))
    priors_guarded = pi._surface_priors(combined, "hard", pd.Timestamp("2026-08-24"))
    assert priors_guarded.get("hold_rate") == priors_clean.get("hold_rate")
