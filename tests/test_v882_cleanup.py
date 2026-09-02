from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def t(path):
    return (ROOT/path).read_text(encoding="utf-8")


def test_v882_generator_is_retired_for_symphony2_ranking():
    index=t("frontend/index.html")
    engine=t("backend/symphony2_engine.py")
    assert not (ROOT/"frontend/scenario-studio-v82a.js").exists()
    assert "scenario-studio-v82a.js" not in index
    assert "symphony2.js?v=210" in index
    assert "MIN_ACTIONABLE_P = 0.55" in engine
    assert "from itertools import combinations" in engine
    assert "joint_probability" in engine


def test_performance_dashboard_feed_selection_only():
    s=t("frontend/performance-dashboard.js")
    assert "TENIS_AI_PERFORMANCE_V882" in s
    assert "priorFor" in s
    assert "Nie zmieniają oceny FINAL" in s


def test_performance_dashboard_tabs_and_charts():
    s=t("frontend/performance-dashboard.js")
    for token in ["Przegląd","Wykresy","pc882-trend-monitor","Rynki","Modele","Adaptive","trend(","calibration(","heatmap(","segments("]:
        assert token in s


def test_performance_dashboard_runtime_refresh_is_targeted():
    s=t("frontend/performance-dashboard.js")
    assert "RUNTIME_FIX='v8.8.13'" in s
    assert "tenis-ai:stats-dashboard-ready" in s
    assert "relevantPolishClick" in s
    assert "[250,700,1500,2600]" not in s
    assert "document.addEventListener('click',()=>setTimeout(polish,60),true)" not in s
    assert "setTimeout(()=>{\n    wrapStats();\n    polish();" in s


def test_performance_dashboard_adaptive_compact():
    css=t("frontend/performance-dashboard.css")
    assert "#v79-health:not(.expanded)" in css


def test_performance_dashboard_assets_use_stable_paths():
    h=t("frontend/index.html")
    assert "performance-dashboard.css" in h
    assert "performance-dashboard.js" in h
    assert h.index("adaptive-prod-bridge.js") < h.index("performance-dashboard.js")
    assert "v882-cleanup.js" not in h
    assert "v882-cleanup.css" not in h
