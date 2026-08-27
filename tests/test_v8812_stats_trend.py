from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_stats_trend_is_promoted_to_main_view():
    js = read("frontend/stats-ranking-v886.js")
    assert "VERSION='v8.8.12'" in js
    assert "promoteMainTrend" in js
    assert "pc12-summary" in js
    assert "pc12-pro .pc12-pro-body" in js
    assert "Trend skuteczności" in js
    assert "insertAdjacentElement('afterend',trendCard)" in js


def test_stats_observer_is_bounded_and_disconnects():
    js = read("frontend/stats-ranking-v886.js")
    assert "WATCH_MAX_MS=2500" in js
    assert "stopStatsObserver" in js
    assert "setTimeout(stopStatsObserver,WATCH_MAX_MS)" in js
    assert "card.dataset.v886Ranking='1';\n  stopStatsObserver();" in js
    assert "tenis-ai:stats-ready" in js
