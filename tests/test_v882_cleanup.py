from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def t(path):
    return (ROOT/path).read_text(encoding="utf-8")

def test_v882_generator_relative_ranking():
    s=t("frontend/scenario-studio-v82a.js")
    assert "v8.8.2 GENERATOR RELATIVE RANKING" in s
    assert "softPairFloor" in s
    assert "signalFloor" in s
    assert "runPairFloor" in s
    assert "pair_preserved:true" in s

def test_v882_stats_feed_selection_only():
    s=t("frontend/v882-cleanup.js")
    assert "TENIS_AI_PERFORMANCE_V882" in s
    assert "priorFor" in s
    assert "Nie zmieniają oceny FINAL" in s

def test_v882_stats_tabs_and_charts():
    s=t("frontend/v882-cleanup.js")
    for token in ["Przegląd","Wykresy","pc882-trend-monitor","Rynki","Modele","Adaptive","trend(","calibration(","heatmap(","segments("]:
        assert token in s

def test_v882_runtime_refresh_is_targeted():
    s=t("frontend/v882-cleanup.js")
    assert "RUNTIME_FIX='v8.8.13'" in s
    assert "tenis-ai:stats-dashboard-ready" in s
    assert "relevantPolishClick" in s
    assert "[250,700,1500,2600]" not in s
    assert "document.addEventListener('click',()=>setTimeout(polish,60),true)" not in s
    assert "setTimeout(()=>{\n    wrapStats();\n    polish();" in s

def test_v882_adaptive_compact():
    css=t("frontend/v882-cleanup.css")
    assert "#v79-health:not(.expanded)" in css

def test_v882_assets_loaded_after_v88():
    h=t("frontend/index.html")
    assert "v882-cleanup.css?v=882" in h
    assert "v882-cleanup.js?v=882" in h
    assert h.index("v88-upgrade.js?v=88") < h.index("v882-cleanup.js?v=882")
