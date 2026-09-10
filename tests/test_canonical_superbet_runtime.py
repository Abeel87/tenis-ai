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
STABLE_FRONTEND_RUNTIME = {'adaptive-prod-bridge.js', 'supabase-config.js', 'style.css', 'match-tendencies.js', 'player-analytics.js', 'serve-props-v72.js', 'signal-mapping-v84d4.js', 'market-quality.js', 'player-avatars.js', 'presentation-data.js', 'performance-center.js', 'early-hold-paths.js', 'sw.js', 'autolearn-v84.js', 'clean-core-v80.js', 'app.js', 'playable-ui.js', 'account.js', 'multi-model.js', 'model-guide.js', 'match-time.js'}
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
    "clarity-labels.js", "navigation-tools.js", "project-ui-quality.js", "ui-cleanup.js", "ui-organizer.js",
    "project-ui.css", "project-readability.css", "neon.css",
    "clean-core-v80.css", "symphony2.css",
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
