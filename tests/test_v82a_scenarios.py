from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p): return (ROOT/p).read_text(encoding="utf-8")

def test_scenario_core_has_no_global_observers_or_intervals():
    s=read("frontend/scenario-studio-v82a.js")
    assert "new MutationObserver(" not in s
    assert "setInterval(" not in s
    assert "TENIS_AI_SCENARIOS" in s

def test_scenario_limits_and_modes():
    s=read("frontend/scenario-studio-v82a.js")
    assert "MAX_MATCHES=8" in s
    assert "MAX_PER_MATCH=4" in s
    for mode in ["stable","balanced","strong","experimental"]:
        assert mode in s

def test_scenario_uses_existing_model_api_not_backend_recalculation():
    s=read("frontend/scenario-studio-v82a.js")
    assert "TENIS_AI_MODEL_API" in s
    assert "allSignals" in s

def test_manual_builder_has_categories_and_dock():
    s=read("frontend/scenario-studio-v82a.js")
    assert "Start seta" in s
    assert "Gemy" in s
    assert "Kierunek" in s
    assert "AI Top" in s
    assert "scenario-v82a-dock" in s

def test_scenario_persistence_targets_own_profile_table():
    s=read("frontend/scenario-studio-v82a.js")
    assert ".from('ai_scenarios')" in s
    assert "user_id:user.id" in s

def test_index_loads_scenario_assets_last():
    h=read("frontend/index.html")
    assert 'scenario-studio-v82a.css?v=82a' in h
    assert 'scenario-studio-v82a.js?v=82a' in h
    assert h.index('clean-core-v80.js?v=801') < h.index('scenario-studio-v82a.js?v=82a')


def test_v82a1_uses_canonical_visible_bottom_nav():
    ui=read("frontend/ui-v751.js")
    sc=read("frontend/scenario-studio-v82a.js")
    css=read("frontend/scenario-studio-v82a.css")
    assert 'data-p751-nav="scenarios"' in ui
    assert "TENIS_AI_SCENARIOS?.open?.('home')" in ui
    assert "navActive('scenarios')" in ui
    assert "$('#p751-bottom-nav [data-p751-nav=\"scenarios\"]')" in sc
    assert "nav.appendChild(navButton)" not in sc
    assert "repeat(7,minmax(0,1fr))" in css
