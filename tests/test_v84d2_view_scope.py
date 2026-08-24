from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(p):
    return (ROOT/p).read_text(encoding="utf-8")

def test_scope_uses_scenario_draft_not_pool_as_current_view():
    js=read("frontend/dynamic-weights-v84d1.js")
    assert "TENIS_AI_SCENARIOS" in js
    assert "currentScenarioRows" in js
    assert "Aktualny scenariusz" in js
    assert "Cała pula" in js

def test_scope_tracks_match_and_signal_counts():
    js=read("frontend/dynamic-weights-v84d1.js")
    assert "signalCount" in js
    assert "matchCount" in js
    assert "draft.items.length" in js

def test_protected_pins_stay_intact():
    h=read("frontend/index.html")
    assert "autolearn-v84.css?v=84a1&hf=84a3" in h
    assert "scenario-studio-v82a.js?v=82a6&hf=84a1" in h
    assert any(x in h for x in (
        "dynamic-weights-v84d1.js?v=84d2",
        "dynamic-weights-v84d1.js?v=84e0",
    ))
