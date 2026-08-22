from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from history_tracker import MODEL_VERSION
from shadow_lab_v78e6 import build_shadow_current,build_shadow_stats,capture_shadow_history,extract_shadow_signals

def sample_match():
    return {
        "id":987,"tour":"ATP","tournament":"Test","surface":"hard","scheduled_time":"2026-08-23T12:00:00Z",
        "p1":"A","p2":"B","model_ready":True,"quality":"MEDIUM","model_confidence":70,
        "p1_stats":{"matches":10,"quality":"HIGH"},"p2_stats":{"matches":8,"quality":"MEDIUM"},
        "match_win":{"A":69.0,"B":31.0},"first_set_win":{"A":74.0,"B":26.0},
        "second_set_win":{"A":63.0,"B":37.0},"total_sets":{"2 sety":58.0,"3 sety":42.0},
        "over_under":{"8.5":{"over":66.0,"under":34.0}},"match_over_under":{"22.5":{"over":44.0,"under":56.0}},
        "exact_match_score":{},"exact_first_set":{}
    }

def test_shadow_extracts_only_55_to_below_72():
    rows=extract_shadow_signals(sample_match());got={(x["market"],x["pick"],x["score"]) for x in rows}
    assert ("match_winner","A",69.0) in got
    assert ("set2_winner","A",63.0) in got
    assert ("set1_total","over",66.0) in got
    assert ("match_total","under",56.0) in got
    assert not any(x["market"]=="set1_winner" for x in rows)

def test_shadow_current_includes_no_data_without_learning_signal():
    m=sample_match();m["model_ready"]=False;m["p1_stats"]={"matches":2,"quality":"LOW"}
    current=build_shadow_current([m])
    assert len(current)==1
    assert current[0]["rejection_code"]=="insufficient_data"
    assert current[0]["signals"]==[]

def test_shadow_history_and_stats_are_separate():
    m=sample_match()
    entry={"match_key":"id:987","match_id":987,"scheduled_time":m["scheduled_time"],"p1":"A","p2":"B","status":"pending","model_version":MODEL_VERSION,"signals":[{"label":"green","score":80,"result":"pending"}]}
    out=capture_shadow_history([entry],[m],now=datetime(2026,8,22,8,0,tzinfo=timezone.utc))
    assert out[0]["shadow_signals"]
    out[0]["shadow_signals"][0]["result"]="hit";out[0]["shadow_signals"][1]["result"]="miss"
    stats=build_shadow_stats(out)
    assert stats["overall"]["settled"]==2
    assert stats["overall"]["hits"]==1
    assert stats["overall"]["accuracy"]==50.0
    assert stats["policy"]=="shadow_only_never_mix_with_official_accuracy"
