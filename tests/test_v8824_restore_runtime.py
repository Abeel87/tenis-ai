from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_navigation_controls_are_render_driven_without_app_observer():
    js = read("frontend/navigation-tools.js")
    assert "RUNTIME_FIX='v8.8.24'" in js
    assert "wrapRenderMatches" in js
    assert "tenis-ai:stats-ready" in js
    assert "tenis-ai:stats-dashboard-ready" in js
    assert "new MutationObserver(" not in js
    assert "obs.observe(app" not in js
    assert "setTimeout(()=>{\n      $$" not in js


def test_navigation_keeps_controls_and_player_links():
    js = read("frontend/navigation-tools.js")
    for token in ["Zwiń wszystko","Rozwiń wszystko","Statystyki / skuteczność",".p751-group",".p751-names > b, .p751-matchup > b","openPlayer"]:
        assert token in js


def test_index_uses_only_canonical_navigation_assets():
    html = read("frontend/index.html")
    assert 'href="navigation-tools.css"' in html
    assert 'src="navigation-tools.js"' in html
    assert "restore-v762.js" not in html
    assert "restore-v762.css" not in html
