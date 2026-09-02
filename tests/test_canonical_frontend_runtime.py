from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

CANONICAL = {
    "runtime-fetch.js", "loading-runtime.js", "runtime-health.js", "runtime-compat.js",
    "restore-ui.js", "restore-ui.css", "ui-base.js", "ui-base.css", "ui-detail.js", "ui-detail.css",
    "clean-core.js", "clean-core.css", "match-time.js", "match-time.css", "ui-organizer.js", "ui-organizer.css",
    "adaptive-prod-bridge.js", "adaptive-prod-bridge.css", "performance-dashboard.js", "performance-dashboard.css",
    "performance-cleanup.js", "performance-cleanup.css", "match-list-visibility.js", "match-browser.js",
    "stats-ranking.js", "checkpoint-quality.js", "project-ui-quality.js", "app-coherence.js",
    "market-segregation.js", "playable-ui.js", "playable-freshness.js", "superbet-playable.js",
    "superbet-playable.css", "superbet-model-coverage.js", "match-detail-architecture.js", "symphony2-live-ui.js",
}

LEGACY_PRODUCTION = {
    "runtime-fetch-v853.js", "loading-fix-v889.js", "runtime-health-v84e0.js", "hotfix-v84e01.js",
    "restore-v762.js", "restore-v762.css", "ui-v75.js", "ui-v75.css", "ui-v751.js", "ui-v751.css",
    "clean-core-v80.js", "clean-core-v80.css", "match-time-v84e11.js", "match-time-v84e11.css",
    "ui-organizer-v853.js", "ui-organizer-v853.css", "v88-upgrade.js", "v88-upgrade.css",
    "v882-cleanup.js", "v882-cleanup.css", "v883-final.js", "v883-final.css",
    "match-list-visibility-v916.js", "stats-ranking-v886.js", "checkpoint-quality-v887.js",
    "project-ui-quality-v8815.js", "app-coherence-v892.js", "market-segregation-v93g.js",
    "playable-ui-coherence-v917.js", "playable-line-freshness-v925.js", "superbet-playable-v912.js",
    "superbet-playable-v912.css", "superbet-model-coverage-v922.js", "match-detail-architecture-v950.js",
    "symphony2-live-ui-v201.js",
}


def read(name):
    return (FRONTEND / name).read_text(encoding="utf-8")


def test_canonical_production_assets_exist_and_legacy_paths_are_gone():
    for name in CANONICAL:
        assert (FRONTEND / name).exists(), name
    for name in LEGACY_PRODUCTION:
        assert not (FRONTEND / name).exists(), name


def test_entrypoint_never_references_deleted_production_assets():
    index = read("index.html")
    for name in LEGACY_PRODUCTION:
        assert name not in index, name


def test_dynamic_bootstrap_uses_canonical_paths():
    meta = read("app-meta.js")
    for name in ("app-coherence.js", "symphony2-live-ui.js", "playable-ui.js", "playable-freshness.js"):
        assert name in meta
    for name in ("app-coherence-v892.js", "symphony2-live-ui-v201.js", "playable-ui-coherence-v917.js", "playable-line-freshness-v925.js"):
        assert name not in meta


def test_match_browser_has_one_strict_loader_owner():
    visibility = read("match-list-visibility.js")
    freshness = read("playable-freshness.js")
    assert "script.src='match-browser.js'" not in visibility
    assert "match-browser-v945.js" not in visibility
    assert "script.src='match-browser.js'" in freshness
    assert freshness.index("window.TENIS_AI_PLAYABLE_UI_V917=wrapped") < freshness.index("script.src='match-browser.js'")


def test_match_ui_loader_chain_uses_stable_paths_without_touching_data_contracts():
    visibility = read("match-list-visibility.js")
    for name in ("playable-ui.js", "superbet-model-coverage.js", "market-segregation.js", "match-detail-architecture.js"):
        assert name in visibility
    assert "superbet_market_v91" in read("playable-ui.js")
    assert "MODEL/RAW" in read("playable-freshness.js")
