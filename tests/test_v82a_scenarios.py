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


def test_v82a2_uses_main_match_source():
    s=read("frontend/scenario-studio-v82a.js")
    assert "typeof filteredReady==='function'" in s
    assert "typeof all!=='undefined'&&Array.isArray(all)" in s
    assert "Array.isArray(window.all)" in s

def test_v82a2_cache_bust_is_pinned():
    h=read("frontend/index.html")
    assert 'scenario-studio-v82a.js?v=82a4' in h


def test_v82a3_generator_exact_count_contract():
    s=read("frontend/scenario-studio-v82a.js")
    assert ".filter(x=>x.picked.length===spm)" in s
    assert "if(candidates.length<mc)" in s
    assert "const expected=mc*spm" in s
    assert "if(actual!==expected || actualMatches!==mc)" in s

def test_v82a3_generator_two_pass_fill():
    s=read("frontend/scenario-studio-v82a.js")
    assert "families.has(fam)||categories.has(cat)" in s
    assert "if(families.has(fam))continue" in s
    assert "picked.length>=spm" in s

def test_v82a3_cache_bust_is_pinned():
    h=read("frontend/index.html")
    assert 'scenario-studio-v82a.js?v=82a4' in h


def test_v82a4_generator_uses_distinct_market_families():
    s=read("frontend/scenario-studio-v82a.js")
    assert "const marketFamily=x=>" in s
    assert "return 'match_total'" in s
    assert "return 'set1_total'" in s
    assert "return 'early_state'" in s
    assert "if(families.has(fam))continue" in s

def test_v82a4_prefers_category_diversity_before_family_fallback():
    s=read("frontend/scenario-studio-v82a.js")
    assert "families.has(fam)||categories.has(cat)" in s
    assert "Przebieg 2: jeśli nadal brakuje" in s

def test_v82a4_cache_bust_is_pinned():
    h=read("frontend/index.html")
    assert 'scenario-studio-v82a.js?v=82a4' in h
