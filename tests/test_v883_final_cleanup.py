from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def t(path):
    return (ROOT/path).read_text(encoding="utf-8")

def test_v883_assets_and_brand_are_wired():
    h=t("frontend/index.html")
    assert "Tenis AI v8.8.7" in h
    assert "performance-cleanup.css?v=883" in h
    assert "performance-cleanup.js?v=883" in h
    assert h.index("performance-dashboard.js?v=882") < h.index("performance-cleanup.js?v=883")

def test_v886_stats_ranking_hotfix_is_wired_after_stats_owners():
    h=t("frontend/index.html")
    js=t("frontend/stats-ranking.js")
    assert "stats-ranking.js?v=886" in h
    assert h.index("performance-cleanup.js?v=883") < h.index("stats-ranking.js?v=886")
    assert "Porównanie modeli i komponentów" in js
    assert "nie bierze udziału w rankingu" in js
    assert "selector\\s+proxy" in js

def test_v887_v8810_market_quality_layer_is_scoped_to_core_and_cross_view():
    h=t("frontend/index.html")
    js=t("frontend/checkpoint-quality.js")
    assert "checkpoint-quality.js?v=887" in h
    assert h.index("stats-ranking.js?v=886") < h.index("checkpoint-quality.js?v=887")

    for token in [
        "CP_MIN_SETTLED=30",
        "CP_MIN_ACCURACY=65",
        "CP_MIN_WILSON=45",
        "RESULT_MIN_SETTLED=30",
        "RESULT_MIN_ACCURACY=65",
        "RESULT_MIN_WILSON=45",
        "RESULT_MARKETS=new Set([...WINNER_MARKETS,'total_sets'])",
        "early_hold_v7?.ready!==true",
        "segments_30d?.market",
        "window.TENIS_AI_WINNER_QUALITY_V888",
        "window.TENIS_AI_RESULT_QUALITY_V889",
        "window.TENIS_AI_CROSS_VIEW_QUALITY_V8810",
        "return state.coreEventDepth>0?filteredSignals(rows,match):rows",
        "activeScenarioProfile()!=='experimental'",
        "finalSelectedSignals(match,limit=3)",
        "window.bestSignalsData=(match,limit=3)=>finalSelectedSignals",
        "window.bestSignals=match=>",
        "window.compactSignals=match=>",
        "FINAL Adaptive PROD · Quality Lock",
        "Karty meczu, Top i Generator korzystają z jednego źródła FINAL",
        "Manual i Model Test/SHADOW zachowują pełne rynki",
    ]:
        assert token in js

    assert "match_winner','set1_winner','set2_winner','set3_winner" in js
    assert "'set1_total'" not in js.split("RESULT_MARKETS=new Set",1)[1].split(";",1)[0]
    assert "'match_total'" not in js.split("RESULT_MARKETS=new Set",1)[1].split(";",1)[0]
    assert "new MutationObserver(" not in js
    assert "setInterval(" not in js

def test_v883_no_longer_contains_retired_generator_pair_ui():
    js=t("frontend/performance-cleanup.js")
    for token in [
        "PAIR SELECTOR · RANKING",
        "DLACZEGO TEN MECZ",
        "selector_match_score",
        "selector_pair",
        "selector_reason",
        "decorateGeneratorCards",
        "wrapScenarioOpen",
        "TENIS_AI_SCENARIOS",
    ]:
        assert token not in js

def test_v883_no_longer_decorates_retired_scenario_scores():
    js=t("frontend/performance-cleanup.js")
    for token in [
        "function clarifyScenarioScores()",
        "Ocena scenariusza · Composer",
        "sc883-saved-label",
        "scenario-v82a-panel",
    ]:
        assert token not in js
    assert "new MutationObserver(" not in js
    assert "setInterval(" not in js

def test_v883_has_single_stats_owner_and_hides_legacy_ui_before_cleanup():
    old=t("frontend/adaptive-prod-bridge.js")
    final=t("frontend/performance-cleanup.js")
    css=t("frontend/performance-cleanup.css")
    assert "function wrapStats(){\n  return false;" in old
    assert "v882-cleanup.js" in old
    assert "pc88-dashboard" in final
    assert "#pc88-dashboard," in css
    assert "#model-switcher," in css
    assert "[data-p751-models]{display:none!important}" in css

def test_v883_pwa_name_is_clean():
    m=json.loads(t("frontend/manifest.webmanifest"))
    assert m["name"]=="Tenis AI"
    assert m["short_name"]=="Tenis AI"

def test_v883_shadow_boundary_copy_remains():
    js=t("frontend/performance-cleanup.js")
    assert "window.TENIS_AI_APPLY_META?.()" in js
    meta=t("frontend/app-meta.js")
    assert "Player Intelligence i Player Learning działają w SHADOW" in meta
    assert "Modele nie gwarantują wygranej ani zysku" in meta
