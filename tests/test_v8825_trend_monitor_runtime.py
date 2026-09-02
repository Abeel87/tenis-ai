from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_trend_monitor_mount_is_event_driven():
    js = read("frontend/model-trends.js")
    assert "RUNTIME_FIX='v8.8.25'" in js
    assert "tenis-ai:stats-dashboard-ready" in js
    assert "setTimeout(" not in js
    assert "new MutationObserver(" not in js
    assert "setInterval(" not in js


def test_checkpoint_cards_use_same_quality_thresholds_as_core_lock():
    js = read("frontend/model-trends.js")
    for token in [
        "CP_MIN_SETTLED=30",
        "CP_MIN_ACCURACY=65",
        "CP_MIN_WILSON=45",
        "CP_MIN_RECENT_WHEN_FALLING=60",
        "checkpointCore",
        "wilsonLower",
        "CORE GOTOWY",
        "CORE BLOKADA",
    ]:
        assert token in js


def test_checkpoint_monitor_stays_read_only():
    js = read("frontend/model-trends.js")
    assert "Trend nie zmienia sam wag produkcyjnych" in js
    assert "status CORE checkpointu jest informacyjny" in js
