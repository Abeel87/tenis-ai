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
    assert 'scenario-studio-v82a.css?v=82a51' in h
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
    assert 'scenario-studio-v82a.js?v=82a51' in h


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
    assert 'scenario-studio-v82a.js?v=82a51' in h


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
    assert 'scenario-studio-v82a.js?v=82a51' in h

def test_v82a5_market_line_guard_direction():
    s=read("frontend/scenario-studio-v82a.js")
    assert "v8.2A.5 Market Line Guard" in s
    assert "side==='over'" in s
    assert "totalLine(b)-totalLine(a)" in s
    assert "totalLine(a)-totalLine(b)" in s
    assert "const sig=marketLineGuard(" in s

def test_v82a5_manual_line_change_recalculates_score():
    s=read("frontend/scenario-studio-v82a.js")
    assert "function changeDraftLine(" in s
    assert "composer_score:composerSignalScore" in s
    assert "suggested_line:original" in s
    assert "selected_line:selected" in s
    assert "data-sc-line-open" in s
    assert "data-sc-line-pick" in s

def test_v82a5_snapshot_tracks_suggested_and_selected_line():
    s=read("frontend/scenario-studio-v82a.js")
    assert "suggested_line:totalLine(s)" in s
    assert "selected_line:totalLine(s)" in s

def test_v82a5_no_observer_or_interval_added():
    s=read("frontend/scenario-studio-v82a.js")
    assert "new MutationObserver(" not in s
    assert "setInterval(" not in s

def test_v82a5_cache_bust_is_pinned():
    h=read("frontend/index.html")
    assert 'scenario-studio-v82a.js?v=82a51' in h

def test_v82a51_line_picker_layout():
    s=read("frontend/scenario-studio-v82a.js")
    c=read("frontend/scenario-studio-v82a.css")
    assert 'class="sc82-line-tools"' in s
    assert 'class="sc82-line-toggle"' in s
    assert 'class="sc82-line-options"' in s
    assert 'sc82-line-option' in s
    assert ".sc82-draft-row>button[data-sc-remove]" in c
    assert ".sc82-draft-row .sc82-line-toggle" in c

def test_v82a51_line_picker_not_forced_to_square():
    c=read("frontend/scenario-studio-v82a.css")
    assert "width:auto!important" in c
    assert "height:auto!important" in c
    assert "position:static!important" in c

def test_v82a51_manual_builder_mentions_exact_lines():
    s=read("frontend/scenario-studio-v82a.js")
    assert "Przy gemach wybierasz konkretną linię" in s

def test_v82a51_asset_cache_bust():
    h=read("frontend/index.html")
    assert 'scenario-studio-v82a.js?v=82a51' in h
    assert 'scenario-studio-v82a.css?v=82a51' in h
