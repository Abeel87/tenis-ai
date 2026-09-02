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


def test_canonical_superbet_entrypoints_exist():
    missing = sorted(name for name in STABLE_RUNTIME_MODULES if not (BACKEND / name).is_file())
    assert not missing, f"Missing stable Superbet runtime modules: {missing}"


def test_retired_superbet_compatibility_shims_stay_deleted():
    present = sorted(name for name in RETIRED_COMPATIBILITY_SHIMS if (BACKEND / name).exists())
    assert not present, f"Retired Superbet compatibility shims returned: {present}"


def test_match_browser_uses_stable_production_filename():
    assert (FRONTEND / "match-browser.js").is_file()
    assert not (FRONTEND / "match-browser-v945.js").exists()


def test_active_frontend_does_not_boot_retired_match_browser_filename():
    offenders = []
    for path in FRONTEND.glob("*.js"):
        text = path.read_text(encoding="utf-8")
        if "match-browser-v945.js" in text:
            offenders.append(path.name)
    assert not offenders, f"Active frontend still boots retired Match Browser path: {offenders}"


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
    # Versioned JSON/meta keys are persisted data contracts and may remain during
    # code-path consolidation. What must disappear are imports/delegation to old
    # version-suffixed Python implementations.
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
