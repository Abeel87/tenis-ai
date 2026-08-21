import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import pandas as pd

from history_hygiene_v78a import score_is_complete, clean_history
from prediction_integrity_v78a import validate, apply_pre_output_guards


def test_history_hygiene_void_and_partial():
    assert score_is_complete("6-4 6-4")
    assert score_is_complete("6-4 4-6 6-3")
    assert score_is_complete("6-4 6-4 6-4", best_of=5)
    for score in ("6-4", "6-4 2-1 RET", "W/O", "DEF", "", None):
        assert not score_is_complete(score)
    assert not score_is_complete("6-4 6-4", best_of=5)


def test_clean_history_reports_removed():
    df=pd.DataFrame([
        {"score":"6-4 6-4","best_of":3},
        {"score":"6-4 2-1 RET","best_of":3},
        {"score":"6-4 6-4","best_of":5},
        {"score":"6-4 6-4 6-4","best_of":5},
    ])
    clean,meta=clean_history(df)
    assert len(clean)==2
    assert meta["raw_rows"]==4
    assert meta["kept_rows"]==2
    assert meta["removed_rows"]==2


def test_integrity_valid_market_passes():
    m={
        "id":1,"p1":"A","p2":"B","best_of":3,
        "match_win":{"A":60.0,"B":40.0},
        "first_set_win":{"A":55.0,"B":45.0},
        "over_under":{
            "8.5":{"over":80.0,"under":20.0},
            "9.5":{"over":65.0,"under":35.0},
            "10.5":{"over":40.0,"under":60.0},
        },
        "match_over_under":{
            "18.5":{"over":75.0,"under":25.0},
            "19.5":{"over":68.0,"under":32.0},
        },
        "game_states":{"2":{"2:0":20.0,"1:1":65.0,"0:2":15.0}},
        "early_hold_v7":{"checkpoint_breakdown":{
            "2":{"total":65.0,"clean_holds":60.0,"with_breaks":5.0}
        }},
    }
    assert validate([m])["status"]=="PASS"


def test_integrity_rejects_non_monotonic_over():
    m={
        "id":2,"p1":"A","p2":"B","best_of":3,
        "match_over_under":{
            "18.5":{"over":40.0,"under":60.0},
            "19.5":{"over":60.0,"under":40.0},
        }
    }
    r=validate([m])
    assert r["status"]=="FAIL"
    assert any("niemonotoniczne" in x for x in r["errors"])


def test_integrity_rejects_bad_probability_sum():
    m={"id":3,"p1":"A","p2":"B","best_of":3,"match_win":{"A":80.0,"B":30.0}}
    r=validate([m])
    assert r["status"]=="FAIL"
    assert any("suma=" in x for x in r["errors"])


def test_bo5_guard_keeps_first_set_hides_full_match():
    m={
        "id":4,"p1":"A","p2":"B","best_of":5,
        "first_set_win":{"A":55.0,"B":45.0},
        "over_under":{"8.5":{"over":70.0,"under":30.0}},
        "match_win":{"A":70.0,"B":30.0},
        "match_over_under":{"18.5":{"over":70.0,"under":30.0}},
        "expected_match_games":22.0,
        "total_sets":{"2 sety":60.0,"3 sety":40.0},
        "exact_match_score":{"2:0":40.0,"2:1":30.0,"1:2":20.0,"0:2":10.0},
    }
    g=apply_pre_output_guards(m)
    assert g["first_set_win"] is not None
    assert g["over_under"] is not None
    assert g["match_win"] is None
    assert g["match_over_under"] is None
    assert g["expected_match_games"] is None
    assert g["total_sets"] is None
    assert g["exact_match_score"] is None
    assert validate([g])["status"]=="PASS"


def test_joint_future_invariant_reference():
    # Reguła dla v7.8B: P(A∩B∩C) nigdy nie może być większe niż najmniejsza składowa.
    marginals=[0.84,0.79,0.83]
    joint=0.54
    assert joint <= min(marginals)
