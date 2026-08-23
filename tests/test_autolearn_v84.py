from datetime import datetime, timedelta, timezone

from backend.autolearn_v84 import (
    _candidate_key,
    _optimize_weights,
    _prob_from_score,
    build_training_rows,
    chronological_split,
)


def _entry(i, result="hit"):
    t=(datetime(2026,8,1,tzinfo=timezone.utc)+timedelta(hours=i)).isoformat()
    return {
        "match_key":f"id:{i}","match_id":i,"scheduled_time":t,"tour":"ATP","surface":"hard",
        "quality":"good","model_confidence":78,"status":"settled",
        "signals":[{"market":"set1_total","pick":"over","line":8.5,"score":74,"result":result,"source_model":"adaptive"}],
        "learning_signals_v79b":[
            {"key":"set1_total|8.5|over","market":"set1_total","pick":"over","line":8.5,"score":77,"result":result,"source_model":"serve"},
            {"key":"set1_total|8.5|over","market":"set1_total","pick":"over","line":8.5,"score":79,"result":result,"source_model":"consensus","votes":4,"strong_votes":3},
        ],
    }


def test_candidate_key_matches_scenario_total_key():
    assert _candidate_key({"market":"set1_total","pick":"over","line":8.5}) == "set1_total|8.5|over"


def test_training_row_joins_models_on_same_concrete_signal():
    rows=build_training_rows([_entry(1,"hit")])
    assert len(rows)==1
    r=rows[0]
    assert r["adaptive"]==74
    assert r["serve"]==77
    assert r["consensus"]==79
    assert r["support"]==3
    assert r["target"]==1


def test_chronological_split_keeps_entire_matches_apart():
    rows=build_training_rows([_entry(i,"hit" if i%3 else "miss") for i in range(40)])
    train,cal,val=chronological_split(rows)
    a={x["match_key"] for x in train};b={x["match_key"] for x in cal};c={x["match_key"] for x in val}
    assert a.isdisjoint(b) and a.isdisjoint(c) and b.isdisjoint(c)
    assert len(train)+len(cal)+len(val)==len(rows)


def test_weight_search_is_data_driven_and_normalized():
    rows=[]
    for i in range(20):
        rows.append({"target":1 if i<12 else 0,"base_score":70})
    current=[_prob_from_score(r) for r in rows]
    cat=[.9 if r["target"] else .1 for r in rows]
    w=_optimize_weights(rows,{"current":current,"catboost":cat})
    assert abs(sum(w.values())-1.0)<1e-9
    assert w["catboost"]>w["current"]
