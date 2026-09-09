from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def test_navigation_is_render_driven_without_legacy_bridge():
    assert not (ROOT/"frontend/navigation-tools.js").exists()
    js=read("frontend/project-ui.js")
    assert "function navActive" in js
    assert "function bindHome" in js
    assert "new MutationObserver(" not in js
    assert "setInterval(" not in js

def test_navigation_keeps_controls_and_player_links():
    html=read("frontend/index.html")
    js=read("frontend/project-ui.js")
    assert 'id="tour-nav"' in html
    assert 'class="main-tabs"' in html
    assert "v762-player-link" in js
    assert "openMatch" in js
    assert "closeMatch" in js

def test_index_uses_only_canonical_navigation_assets():
    html=read("frontend/index.html")
    assert 'href="style.css"' in html
    assert "navigation-tools.css" not in html
    assert "navigation-tools.js" not in html
    assert "restore-v762.js" not in html
    assert "restore-v762.css" not in html
