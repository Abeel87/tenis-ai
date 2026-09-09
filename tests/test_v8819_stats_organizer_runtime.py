from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_stats_runtime_is_event_driven_without_retired_organizer():
    ranking = read("frontend/stats-ranking.js")
    project = read("frontend/project-ui.js")
    assert "tenis-ai:stats-ready" in ranking
    assert "tenis-ai:stats-dashboard-ready" in ranking
    assert "tenis-ai:ui-ready" in project
    assert "tenis-ai:matches-rendered" in project
    assert "new MutationObserver(" not in ranking
    assert "setInterval(" not in ranking
    assert not (ROOT / "frontend/ui-organizer.js").exists()


def test_canonical_project_ui_owns_readability_mode():
    project = read("frontend/project-ui.js")
    index = read("frontend/index.html")
    assert "#tenis-ui-mode-toggle" in project
    assert "dataset.tenisUiMode" in project
    assert "tenis-ai-ui-mode-change" in project
    assert 'id="tenis-ui-mode-toggle"' in index
    assert "ui-organizer.js" not in index


def test_canonical_ui_does_not_restore_versioned_organizer_assets():
    index = read("frontend/index.html")
    for retired in (
        "ui-organizer.js",
        "ui-organizer.css",
        "ui-organizer-v853.js",
        "ui-organizer-v853.css",
    ):
        assert retired not in index
        assert not (ROOT / "frontend" / retired).exists()
