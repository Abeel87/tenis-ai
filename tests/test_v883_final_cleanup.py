from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def t(path):
    return (ROOT/path).read_text(encoding="utf-8")

def test_v883_assets_and_brand_are_wired():
    h=t("frontend/index.html")
    assert "Tenis AI v8.8.6" in h
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
