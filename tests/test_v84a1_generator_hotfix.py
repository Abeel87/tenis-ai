from pathlib import Path

from backend.autolearn_v84 import (
    _bounded_tabpfn_weights,
    _choose_weights,
)

ROOT=Path(__file__).resolve().parents[1]
def read(p): return (ROOT/p).read_text(encoding="utf-8")


def test_tabpfn_gets_bounded_real_vote_after_previous_validation_pass():
    prev={
        "current":{"n":40,"selected_n":35,"brier":0.220,"log_loss":0.640},
        "tabpfn":{"n":40,"selected_n":35,"brier":0.205,"log_loss":0.605},
    }
    w,policy=_bounded_tabpfn_weights(
        {"current":0.30,"catboost":0.70,"tabpfn":0.0},
        prev,{},True
    )
    assert policy["allowed"] is True
    assert 0.10 <= w["tabpfn"] <= 0.25
    assert abs(sum(w.values())-1.0) < 1e-9


def test_tabpfn_weight_is_not_silently_zeroed_on_non_retrain_run():
    rows=[{"target":1} for _ in range(20)]
    probs={"current":[0.7]*20,"catboost":[0.72]*20}
    w,policy=_choose_weights(
        rows,probs,
        {"current":0.27,"catboost":0.63,"tabpfn":0.10},
        {},{},False
    )
    assert abs(w.get("tabpfn",0)-0.10) < 1e-9
    assert policy["status"]=="preserved"



def test_previous_validation_can_reenable_bounded_tabpfn_without_retraining():
    rows=[{"target":1} for _ in range(24)]
    probs={"current":[0.69]*24,"catboost":[0.72]*24}
    prev={
        "current":{"n":40,"selected_n":35,"brier":0.220,"log_loss":0.640},
        "tabpfn":{"n":40,"selected_n":35,"brier":0.205,"log_loss":0.605},
    }
    w,policy=_choose_weights(
        rows,probs,
        {"current":0.30,"catboost":0.70,"tabpfn":0.0},
        prev,{},False,tab_cached_available=True
    )
    assert policy["allowed"] is True
    assert policy["mode"]=="cached_challenger_reenabled"
    assert 0.10 <= w.get("tabpfn",0) <= 0.25

def test_bad_previous_tabpfn_validation_can_hold_challenger_at_zero():
    prev={
        "current":{"n":40,"selected_n":35,"brier":0.200,"log_loss":0.590},
        "tabpfn":{"n":40,"selected_n":35,"brier":0.270,"log_loss":0.720},
    }
    w,policy=_bounded_tabpfn_weights(
        {"current":0.30,"catboost":0.50,"tabpfn":0.20},
        prev,{},True
    )
    assert policy["allowed"] is False
    assert w.get("tabpfn",0)==0


def test_generator_has_profile_soft_fill_without_forced_junk():
    s=read("frontend/scenario-studio-v82a.js")
    assert "function generatorProfilePolicy" in s
    assert "function repairGeneratorCandidate" in s
    assert ".map(x=>repairGeneratorCandidate(x,spm,profile)).filter(x=>x.picked.length===spm)" in s
    assert "minAverage" in s
    assert "generatorTotalMarketable" in s
    assert "Nie dokładam słabszych na siłę" in s
    assert "floor:72" in s
    assert "floor:74" in s
    assert "floor:80" in s
    assert "floor:62" in s
    assert "floor:57" not in s
    assert "floor:58" not in s
    assert "floor:63" not in s
    assert "b.avgScore" in s


def test_generated_signal_exposes_model_votes_readably():
    s=read("frontend/scenario-studio-v82a.js")
    assert "function autoLearnSourceLabel" in s
    assert "raw_ensemble_score" in s
    assert "base_source_model" in s


def test_hotfix_assets_cache_bust_without_removing_v82a6_pin():
    h=read("frontend/index.html")
    assert any(x in h for x in ("autolearn-v84.js?v=84a1&hf=84a3", "autolearn-v84.js?v=84a1&hf=84b1"))
    assert "autolearn-v84.css?v=84a1&hf=84a3" in h
    assert "scenario-studio-v82a.js?v=82a6&hf=84a1" in h
    assert "scenario-studio-v82a.js?v=82a6" in h
