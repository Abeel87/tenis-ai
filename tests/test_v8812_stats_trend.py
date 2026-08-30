from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_stats_trend_is_promoted_to_main_view():
    js = read("frontend/stats-ranking-v886.js")
    assert "VERSION='v8.8.16'" in js
    assert "promoteMainTrend" in js
    assert "pc12-summary" in js
    assert "pc12-pro .pc12-pro-body" in js
    assert "Trend skuteczności" in js
    assert "insertAdjacentElement('afterend',trendCard)" in js


def test_stats_ranking_is_event_driven_without_observer():
    js = read("frontend/stats-ranking-v886.js")
    assert "DASHBOARD_READY_EVENT='tenis-ai:stats-dashboard-ready'" in js
    assert "tenis-ai:stats-ready" in js
    assert "document.addEventListener(DASHBOARD_READY_EVENT" in js
    assert "new MutationObserver(" not in js
    assert "WATCH_MAX_MS" not in js
    assert "stopStatsObserver" not in js
