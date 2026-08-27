from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def t(path):
    return (ROOT/path).read_text(encoding="utf-8")

def test_v883_assets_and_brand_are_wired():
    h=t("frontend/index.html")
    assert "Tenis AI v8.8.7" in h
    assert "v883-final.css?v=883" in h
    assert "v883-final.js?v=883" in h
    assert h.index("v882-cleanup.js?v=882") < h.index("v883-final.js?v=883")

def test_v886_stats_ranking_hotfix_is_wired_after_stats_owners():
    h=t("frontend/index.html")
    js=t("frontend/stats-ranking-v886.js")
    assert "stats-ranking-v886.js?v=886" in h
    assert h.index("v883-final.js?v=883") < h.index("stats-ranking-v886.js?v=886")
    assert "Porównanie modeli i komponentów" in js
    assert "nie bierze udziału w rankingu" in js
    assert "selector\\s+proxy" in js

def test_v887_v888_market_quality_layer_is_scoped_to_core():
    h=t("frontend/index.html")
    js=t("frontend/checkpoint-quality-v887.js")
    assert "checkpoint-quality-v887.js?v=887" in h
    assert h.index("stats-ranking-v886.js?v=886") < h.index("checkpoint-quality-v887.js?v=887")

    for token in [
        "CP_MIN_SETTLED=30",
        "CP_MIN_ACCURACY=65",
        "CP_MIN_WILSON=45",
        "WIN_MIN_SETTLED=30",
        "WIN_MIN_ACCURACY=65",
        "WIN_MIN_WILSON=45",
        "early_hold_v7?.ready!==true",
        "segments_30d?.market",
        "window.TENIS_AI_WINNER_QUALITY_V888",
        "return state.coreEventDepth>0?filteredSignals(rows,match):rows",
        "activeScenarioProfile()!=='experimental'",
        "Manual i Model Test/SHADOW zachowują pełne rynki",
    ]:
        assert token in js

    assert "match_winner','set1_winner','set2_winner','set3_winner" in js
    assert "new MutationObserver(" not in js
    assert "setInterval(" not in js

def test_v883_pair_reasoning_is_visible():
    js=t("frontend/v883-final.js")
    for token in ["PAIR SCORE","DLACZEGO TEN MECZ","HISTORIA","selector_match_score","selector_pair","selector_reason"]:
        assert token in js

def test_v883_has_single_stats_owner():
    old=t("frontend/v88-upgrade.js")
    final=t("frontend/v883-final.js")
    css=t("frontend/v883-final.css")
    assert "function wrapStats(){\n  return false;" in old
    assert "v882-cleanup.js" in old
    assert "pc88-dashboard" in final
    assert "#pc88-dashboard{display:none!important}" in css

def test_v883_pwa_name_is_clean():
    m=json.loads(t("frontend/manifest.webmanifest"))
    assert m["name"]=="Tenis AI"
    assert m["short_name"]=="Tenis AI"

def test_v883_shadow_boundary_copy_remains():
    js=t("frontend/v883-final.js")
    assert "Player Intelligence i Accuracy Lab pozostają SHADOW" in js
