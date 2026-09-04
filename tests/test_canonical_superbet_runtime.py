from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "superbet-market-refresh.yml"
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

CANONICAL_ENTRYPOINTS = {
    "superbet_market_context.py",
    "superbet_line_coverage.py",
    "superbet_playable.py",
}
STABLE_RUNTIME_MODULES = CANONICAL_ENTRYPOINTS | {
    "superbet_market_core.py",
    "superbet_market_mapping.py",
    "superbet_market_audit.py",
    "superbet_fixture_matching.py",
}
RETIRED_COMPATIBILITY_SHIMS = {
    "superbet_market_context_v91.py",
    "superbet_market_context_v913.py",
    "superbet_market_context_v923.py",
    "superbet_market_context_v924.py",
    "superbet_line_coverage_v922.py",
    "superbet_line_coverage_v924.py",
    "superbet_playable_v912.py",
    "superbet_fixture_matching_v927.py",
}
STABLE_FRONTEND_RUNTIME = {
    "playable-ui.js", "playable-freshness.js", "match-browser.js", "match-visibility.js",
    "superbet-model-coverage.js", "market-segregation.js", "match-detail.js",
    "player-intelligence-human.js", "player-intelligence-ui.js", "clarity-labels.js",
    "app-coherence.js", "symphony2-live-ui.js",
    "runtime-fetch.js", "match-loading.js", "data-runtime.js", "fixture-history-freshness.js",
    "registration-handler.js", "registration-ux.js", "registration-ux.css",
    "history-ui.js", "history-ui.css", "project-ui.js", "project-ui.css", "project-readability.css",
    "navigation-tools.js", "navigation-tools.css", "adaptive-prod-bridge.js", "adaptive-prod-bridge.css",
    "performance-dashboard.js", "performance-dashboard.css", "performance-center.js", "performance-center.css",
    "ui-cleanup.js", "ui-cleanup.css", "ui-organizer.js", "ui-organizer.css",
    "superbet-playable-stats.js", "superbet-playable-stats.css",
    "stats-ranking.js", "market-quality.js", "project-ui-quality.js",
    "integrity-status.js", "integrity-status.css", "model-trends.js", "model-trends.css",
    "match-time.js", "match-time.css", "pbp-validation.js", "pbp-validation.css", "market-lab.js", "market-lab.css",
    "project-analysis.css", "calibration-status.css", "early-hold-paths.js", "early-hold-paths.css",
    "player-trends.js", "player-trends.css", "player-analytics.js", "player-analytics.css",
    "match-tendencies.js", "match-tendencies.css", "community-admin.js", "community-admin.css",
    "admin-delete.js", "admin-delete.css",
}
RETIRED_FRONTEND_RUNTIME = {
    "playable-ui-coherence-v917.js", "playable-line-freshness-v925.js", "match-browser-v945.js",
    "match-list-visibility-v916.js", "superbet-model-coverage-v922.js", "market-segregation-v93g.js",
    "match-detail-architecture-v950.js", "player-intelligence-v888-human.js",
    "player-intelligence-v851b-ui.js", "clarity-labels-v711.js", "app-coherence-v892.js",
    "symphony2-live-ui-v201.js", "runtime-fetch-v853.js", "loading-fix-v889.js",
    "runtime-health-v84e0.js", "hotfix-v84e01.js", "restore-v762.js", "restore-v762.css",
    "ui-v75.js", "ui-v75.css", "ui-v751.js", "ui-v751.css",
    "registration-fix-v741.js", "registration-ux-v752.js", "registration-ux-v752.css",
    "readability-v753.js", "readability-v753.css", "community-admin-v75.js", "community-admin-v75.css",
    "admin-delete-v754.js", "admin-delete-v754.css", "performance-center-v77.js", "performance-center-v77.css",
    "early-hold-paths-v771.js", "early-hold-paths-v771.css",
    "player-trends-v71.js", "player-trends-v71.css", "player-analytics-v76.js", "player-analytics-v76.css",
    "match-tendencies-v712.js", "match-tendencies-v712.css",
    "v88-upgrade.js", "v88-upgrade.css", "v882-cleanup.js", "v882-cleanup.css",
    "v883-final.js", "v883-final.css", "ui-organizer-v853.js", "ui-organizer-v853.css",
    "superbet-playable-v912.js", "superbet-playable-v912.css", "stats-ranking-v886.js",
    "checkpoint-quality-v887.js", "project-ui-quality-v8815.js",
    "integrity-v78a.js", "integrity-v78a.css", "model-trends-v84e2.js", "model-trends-v84e2.css",
    "match-time-v84e11.js", "match-time-v84e11.css", "pbp-validation-v73.js", "pbp-validation-v73.css",
    "market-lab-v741.js", "market-lab-v741.css", "logic-audit-v772.css", "calibration-v78d.css",
}


def test_canonical_superbet_entrypoints_exist():
    missing = sorted(name for name in STABLE_RUNTIME_MODULES if not (BACKEND / name).is_file())
    assert not missing, f"Missing stable Superbet runtime modules: {missing}"


def test_retired_superbet_compatibility_shims_stay_deleted():
    present = sorted(name for name in RETIRED_COMPATIBILITY_SHIMS if (BACKEND / name).exists())
    assert not present, f"Retired Superbet compatibility shims returned: {present}"


def test_canonical_playable_frontend_runtime_exists():
    missing = sorted(name for name in STABLE_FRONTEND_RUNTIME if not (FRONTEND / name).is_file())
    assert not missing, f"Missing stable PLAYABLE frontend runtime: {missing}"


def test_retired_playable_frontend_runtime_stays_deleted():
    present = sorted(name for name in RETIRED_FRONTEND_RUNTIME if (FRONTEND / name).exists())
    assert not present, f"Retired PLAYABLE frontend runtime returned: {present}"


def test_active_frontend_does_not_boot_retired_runtime_filenames():
    offenders = []
    active_texts = [(FRONTEND / "index.html").read_text(encoding="utf-8")]
    active_texts.extend(path.read_text(encoding="utf-8") for path in FRONTEND.glob("*.js"))
    for idx, text in enumerate(active_texts):
        for retired in RETIRED_FRONTEND_RUNTIME:
            if retired in text:
                offenders.append(f"source-{idx}:{retired}")
    assert not offenders, f"Active frontend still boots retired runtime paths: {offenders}"


def test_app_meta_owns_single_canonical_playable_bootstrap():
    text = (FRONTEND / "app-meta.js").read_text(encoding="utf-8")
    assert "load('playable-ui.js','tenis-ai-playable-ui',freshness)" in text
    assert "load('playable-freshness.js','tenis-ai-playable-freshness')" in text
    visibility = (FRONTEND / "match-visibility.js").read_text(encoding="utf-8")
    assert "playable-ui.js" not in visibility
    assert "playable-freshness.js" not in visibility


def test_match_visibility_owns_stable_detail_chain_only():
    text = (FRONTEND / "match-visibility.js").read_text(encoding="utf-8")
    assert "superbet-model-coverage.js" in text
    assert "market-segregation.js" in text
    assert "match-detail.js" in text
    for retired in ("superbet-model-coverage-v922.js", "market-segregation-v93g.js", "match-detail-architecture-v950.js"):
        assert retired not in text


def test_project_ui_has_single_match_list_owner():
    project = (FRONTEND / "project-ui.js").read_text(encoding="utf-8")
    history = (FRONTEND / "history-ui.js").read_text(encoding="utf-8")
    assert "renderMatches=function" in project
    assert "window.TENIS_AI_PROJECT_UI" in project
    assert "renderMatches=function" not in history
    assert "filteredReady" not in history
    assert "window.renderHistory=render" in history


def test_index_boots_stable_production_runtime_chain():
    text = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for name in (
        "runtime-fetch.js", "match-loading.js", "data-runtime.js", "fixture-history-freshness.js",
        "registration-handler.js", "registration-ux.js", "clarity-labels.js", "history-ui.js", "project-ui.js",
        "navigation-tools.js", "ui-organizer.js", "adaptive-prod-bridge.js", "performance-dashboard.js",
        "performance-center.js", "player-intelligence-ui.js", "ui-cleanup.js", "stats-ranking.js", "market-quality.js",
        "project-ui-quality.js", "integrity-status.js", "match-time.js", "model-trends.js",
        "pbp-validation.js", "market-lab.js", "early-hold-paths.js", "player-trends.js", "player-analytics.js",
        "match-tendencies.js", "community-admin.js", "admin-delete.js", "match-visibility.js",
    ):
        assert f'src="{name}"' in text
    for name in (
        "registration-ux.css", "history-ui.css", "project-ui.css", "project-readability.css",
        "navigation-tools.css", "ui-organizer.css", "adaptive-prod-bridge.css", "performance-dashboard.css",
        "performance-center.css", "ui-cleanup.css", "integrity-status.css", "match-time.css", "model-trends.css",
        "pbp-validation.css", "market-lab.css", "project-analysis.css", "calibration-status.css",
        "early-hold-paths.css", "player-trends.css", "player-analytics.css", "match-tendencies.css",
        "community-admin.css", "admin-delete.css",
    ):
        assert f'href="{name}"' in text
    assert text.index('src="history-ui.js"') < text.index('src="project-ui.js"')
    assert text.index('src="registration-handler.js"') < text.index('src="registration-ux.js"')
    for retired in RETIRED_FRONTEND_RUNTIME:
        assert retired not in text


def test_model_trend_monitor_stays_read_only():
    text = (FRONTEND / "model-trends.js").read_text(encoding="utf-8")
    assert "Read-only monitoring" in text
    assert "never changes production weights" in text
    assert "window.TENIS_AI_MODEL_TRENDS_V84E2" in text


def test_integrity_status_preserves_shadow_experiment_boundary():
    text = (FRONTEND / "integrity-status.js").read_text(encoding="utf-8")
    assert "integrity_report_v78a.json" in text
    assert "shadow-lab-v78e6.js" in text
    assert "shadow-lab-v78e6.css" in text


def test_match_time_runtime_preserves_single_formatter_contract():
    text = (FRONTEND / "match-time.js").read_text(encoding="utf-8")
    assert "One formatter + one lightweight clock" in text
    assert "TENIS_AI_MATCH_TIME" in text
    assert "A passed scheduled time never implies LIVE" in text


def test_market_lab_stays_lab_only():
    text = (FRONTEND / "market-lab.js").read_text(encoding="utf-8")
    assert "Market Lab v7.4.1" in text
    assert "Na razie nie podbijają wyniku 72/80+" in text


def test_pbp_validation_stays_reporting_only():
    text = (FRONTEND / "pbp-validation.js").read_text(encoding="utf-8")
    assert "PBP Result Tracker + walk-forward validation" in text
    assert "diagnostyka stabilności tendencji" in text


def test_production_workflow_does_not_execute_versioned_superbet_entrypoints():
    text = WORKFLOW.read_text(encoding="utf-8")
    offenders = sorted(set(re.findall(r"python\s+backend/(superbet_[A-Za-z0-9_]+_v\d+[A-Za-z0-9_]*\.py)", text)))
    assert not offenders, (
        "Production workflow must execute stable canonical Superbet entrypoints, "
        f"not version-suffixed patch modules: {offenders}"
    )


def test_playable_is_real_canonical_implementation():
    text = (BACKEND / "superbet_playable.py").read_text(encoding="utf-8")
    assert "def inject(" in text
    assert "def project(" in text
    assert "LEGACY_IMPLEMENTATION =" not in text


def test_line_coverage_is_fully_canonical_implementation():
    text = (BACKEND / "superbet_line_coverage.py").read_text(encoding="utf-8")
    assert "def enrich_match(" in text
    assert "def enrich_results(" in text
    import_pattern = re.compile(r"(?:from\s+\.?|import\s+)(superbet_line_coverage_v\d+[A-Za-z0-9_]*)")
    assert not import_pattern.search(text)
    assert "LEGACY_IMPLEMENTATION =" not in text


def test_market_context_is_composed_from_stable_modules_only():
    text = (BACKEND / "superbet_market_context.py").read_text(encoding="utf-8")
    assert "def prepare(" in text
    assert "def finalize(" in text
    assert "superbet_market_core" in text
    assert "superbet_market_mapping" in text
    assert "superbet_market_audit" in text
    assert "superbet_fixture_matching" in text
    assert "LEGACY_IMPLEMENTATION =" not in text


def test_stable_runtime_has_no_versioned_superbet_imports_or_wildcards():
    import_pattern = re.compile(r"(?:from\s+\.?|import\s+)(superbet_[A-Za-z0-9_]*_v\d+[A-Za-z0-9_]*)")
    versioned = []
    wildcards = []
    for name in STABLE_RUNTIME_MODULES:
        text = (BACKEND / name).read_text(encoding="utf-8")
        if import_pattern.search(text):
            versioned.append(name)
        if re.search(r"\bimport\s+\*", text):
            wildcards.append(name)
    assert not versioned, f"Stable Superbet runtime imports legacy versioned modules: {versioned}"
    assert not wildcards, f"Stable Superbet runtime leaks namespaces through import *: {wildcards}"



def test_superbet_core_owns_refresh_and_quota_constants():
    from backend import superbet_market_core as core
    from backend import superbet_market_mapping as mapping

    assert core.REFRESH_HOURS == 1
    assert core.MONTHLY_REQUEST_CAP == 4000
    assert core.DIRECT_FIXTURE_MONTHLY_CAP == 1700
    assert mapping.REFRESH_HOURS == core.REFRESH_HOURS
    assert mapping.MONTHLY_REQUEST_CAP == core.MONTHLY_REQUEST_CAP

    source = (BACKEND / "superbet_market_mapping.py").read_text(encoding="utf-8")
    compact = source.replace(" ", "")
    assert "base.REFRESH_HOURS=" not in compact
    assert "base.MONTHLY_REQUEST_CAP=" not in compact
