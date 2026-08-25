from datetime import datetime, timedelta, timezone

from backend.autolearn_v84 import (
    _apply_tracking_governor,
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


def test_tracking_governor_limits_weaker_catboost():
    tracking = {
        "catboost": {"selected_n": 120, "accuracy": 65.0, "brier": 0.220},
        "current": {"selected_n": 150, "accuracy": 67.5, "brier": 0.200},
    }
    initial_weights = {"catboost": 0.80, "current": 0.20}
    w, policy = _apply_tracking_governor(initial_weights, tracking)
    assert policy["active"] is True
    assert policy["catboost_capped"] is True
    assert w["catboost"] <= 0.40
    assert w["current"] >= 0.25
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_tracking_governor_can_raise_stronger_tabpfn():
    tracking = {
        "catboost": {"selected_n": 120, "accuracy": 65.0, "brier": 0.210},
        "current": {"selected_n": 150, "accuracy": 67.0, "brier": 0.200},
        "tabpfn": {"selected_n": 110, "accuracy": 70.0, "brier": 0.180},
    }
    initial_weights = {"catboost": 0.60, "current": 0.30, "tabpfn": 0.10}
    w, policy = _apply_tracking_governor(initial_weights, tracking, tabpfn_cap=0.25)
    assert policy["active"] is True
    assert policy["tabpfn_boosted"] is True
    assert w["tabpfn"] >= 0.20
    assert w["tabpfn"] <= 0.25
    assert w["current"] >= 0.25
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_tracking_governor_inactive_below_sample_size_100():
    tracking = {
        "catboost": {"selected_n": 80, "accuracy": 60.0, "brier": 0.250},
        "current": {"selected_n": 80, "accuracy": 68.0, "brier": 0.200},
        "tabpfn": {"selected_n": 80, "accuracy": 72.0, "brier": 0.170},
    }
    initial_weights = {"catboost": 0.70, "current": 0.20, "tabpfn": 0.10}
    w, policy = _apply_tracking_governor(initial_weights, tracking)
    assert policy["active"] is False
    assert abs(w["catboost"] - 0.70) < 1e-9
    assert abs(w["current"] - 0.20) < 1e-9
    assert abs(w["tabpfn"] - 0.10) < 1e-9
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_tracking_governor_weights_sum_to_one():
    test_cases = [
        ({"catboost": 0.90, "current": 0.10}, {"catboost": {"selected_n": 150, "accuracy": 60.0, "brier": 0.250}, "current": {"selected_n": 150, "accuracy": 68.0, "brier": 0.190}}),
        ({"catboost": 0.50, "current": 0.40, "tabpfn": 0.10}, {"catboost": {"selected_n": 110, "accuracy": 65.0, "brier": 0.220}, "current": {"selected_n": 120, "accuracy": 67.0, "brier": 0.200}, "tabpfn": {"selected_n": 110, "accuracy": 71.0, "brier": 0.180}}),
        ({"catboost": 0.33, "current": 0.33, "tabpfn": 0.34}, {"catboost": {"selected_n": 50, "accuracy": 50.0, "brier": 0.300}, "current": {"selected_n": 50, "accuracy": 60.0, "brier": 0.200}}),
    ]
    for weights, tracking in test_cases:
        w, _ = _apply_tracking_governor(weights, tracking)
        assert abs(sum(w.values()) - 1.0) < 1e-9
