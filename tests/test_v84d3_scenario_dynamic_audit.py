from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(p):
    return (ROOT/p).read_text(encoding="utf-8")

def test_scenario_audit_is_additive():
    h=read("frontend/index.html")
    assert "scenario-dynamic-v84d3.css?v=84d3" in h
    assert any(x in h for x in (
        "scenario-dynamic-v84d3.js?v=84d3",
        "scenario-dynamic-v84d3.js?v=84d4",
    ))
    assert "scenario-studio-v82a.js?v=82a6&hf=84a1" in h

def test_scenario_audit_reads_existing_dynamic_metadata():
    s=read("frontend/scenario-dynamic-v84d3.js")
    assert "dynamic_weighting" in s
    assert "effective_weights" in s
    assert "local_weights" in s
    assert "TENIS_AI_SCENARIOS" in s
    assert "data-sc-remove" in s
    assert "data-sc-sig" in s

def test_scenario_audit_has_dynamic_global_and_summary():
    s=read("frontend/scenario-dynamic-v84d3.js")
    assert "DYNAMIC" in s
    assert "GLOBAL" in s
    assert "MAX SHIFT" in s
    assert "sc84d3-summary" in s

def test_scenario_audit_mobile():
    c=read("frontend/scenario-dynamic-v84d3.css")
    assert "@media(max-width:520px)" in c
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in c

def test_previous_dynamic_scope_pin_is_untouched():
    h=read("frontend/index.html")
    assert any(x in h for x in (
        "dynamic-weights-v84d1.js?v=84d2",
        "dynamic-weights-v84d1.js?v=84e0",
    ))
