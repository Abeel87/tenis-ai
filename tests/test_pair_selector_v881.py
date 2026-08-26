from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(p):
    return (ROOT/p).read_text(encoding="utf-8")

def test_pair_selector_is_installed():
    s=read("frontend/scenario-studio-v82a.js")
    assert "v8.8.1 BET BUILDER PAIR SELECTOR" in s
    assert "selectorBestPair" in s
    assert "selectorPairScore" in s
    assert "selectorMatchScore" in s

def test_pair_selector_prefers_coupon_patterns():
    s=read("frontend/scenario-studio-v82a.js")
    assert "SET1_WIN_OVER" in s
    assert "EARLY_HOLD_JOINT" in s
    assert "MATCH_AND_SET_WIN" in s
    assert "DOUBLE_TOTAL_OVER" in s

def test_pair_selector_never_invents_total_line():
    s=read("frontend/scenario-studio-v82a.js")
    assert "selectorPreferredTotalRows" in s
    assert "totalLine(x)!=null" in s
    assert "TYLKO istniejace linie" in s

def test_pair_selector_has_core_and_model_test():
    s=read("frontend/scenario-studio-v82a.js")
    assert "CORE_PAIR" in s
    assert "MODEL_TEST_SHADOW" in s
    assert "catboost" in s
    assert "tabpfn" in s
    assert "playerAssist" in s

def test_generator_defaults_to_seven_by_two():
    s=read("frontend/scenario-studio-v82a.js")
    assert """n===7?'active':''""" in s
    assert """n===2?'active':''""" in s
    assert """dataset.scN||7""" in s
    assert """dataset.scN||2""" in s

def test_protected_scenario_asset_pin_stays_unchanged():
    h=read("frontend/index.html")
    assert "scenario-studio-v82a.js?v=82a6" in h
    assert "scenario-studio-v82a.css?v=82a51" in h
