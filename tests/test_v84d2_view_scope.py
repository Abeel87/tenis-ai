from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(p):
    return (ROOT/p).read_text(encoding="utf-8")

def test_dynamic_weights_audit_is_pool_only_after_scenario_retirement():
    js=read("frontend/dynamic-weights-v84d1.js")
    assert "TENIS_AI_SCENARIOS" not in js
    assert "currentScenarioRows" not in js
    assert "scenario" not in js.lower()
    assert "poolRows" in js
    assert "Wszystkie sygnały" in js


def test_scope_tracks_pool_dynamic_and_global_counts():
    js=read("frontend/dynamic-weights-v84d1.js")
    assert "activePool" in js
    assert "globalPool" in js
    assert "poolRows.length" in js


def test_protected_pins_stay_intact():
    h=read("frontend/index.html")
    assert "autolearn-v84.css?v=84a1&hf=84a3" in h
    assert "symphony2.js?v=220" in h
    assert "scenario-studio-v82a.js" not in h
    assert any(x in h for x in (
        "dynamic-weights-v84d1.js?v=84d2",
        "dynamic-weights-v84d1.js?v=84e0",
    ))
