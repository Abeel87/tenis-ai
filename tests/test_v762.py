from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_navigation_controls_are_structural_and_no_legacy_bridge_remains():
    index=(ROOT/"frontend/index.html").read_text(encoding="utf-8")
    ui=(ROOT/"frontend/project-ui.js").read_text(encoding="utf-8")
    assert 'id="tour-nav"' in index
    assert 'class="main-tabs"' in index
    assert 'data-view="matches"' in index
    assert 'data-view="stats"' in index
    assert 'function navActive' in ui
    assert not (ROOT/"frontend/navigation-tools.js").exists()

def test_project_ui_keeps_clickable_players_and_back_navigation():
    ui=(ROOT/"frontend/project-ui.js").read_text(encoding="utf-8")
    assert "v762-player-link" in ui
    assert "openMatch" in ui
    assert "closeMatch" in ui
    assert "returnScroll" in ui

def test_retired_restore_runtime_stays_deleted():
    assert not (ROOT/"frontend/restore-v762.js").exists()
    assert not (ROOT/"frontend/restore-v762.css").exists()
