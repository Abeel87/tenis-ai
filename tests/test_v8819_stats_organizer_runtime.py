from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_stats_organizer_is_event_driven_without_delayed_layout_passes():
    js = read("frontend/ui-organizer.js")
    assert "RUNTIME_FIX = 'v8.8.19'" in js
    assert "tenis-ai:stats-ready" in js
    assert "tenis-ai:stats-dashboard-ready" in js
    assert "setTimeout(organize, 300)" not in js
    assert "setTimeout(organize, 900)" not in js
    assert "setTimeout(organize, 500)" not in js
    assert "setTimeout(organize, 1400)" not in js
    assert "setTimeout(visualPolish" not in js
    assert "setTimeout(ensureReadabilityControls" not in js
    assert "new MutationObserver(" not in js
    assert "setInterval(" not in js


def test_stats_organizer_does_one_complete_pass():
    js = read("frontend/ui-organizer.js")
    assert "visualPolish();\n    ensureReadabilityControls();" in js
    assert "timer = setTimeout(organize, delay)" in js
    assert "runtimeFix: RUNTIME_FIX" in js


def test_canonical_organizer_does_not_overwrite_app_version_branding():
    js = read("frontend/ui-organizer.js")
    index = read("frontend/index.html")
    assert "brand.textContent='Tenis AI v8.5.3" not in js
    assert "ui-organizer.js" in index
    assert "ui-organizer-v853.js" not in index
    assert "ui-organizer-v853.css" not in index
