from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "superbet-market-refresh.yml"
BACKEND = ROOT / "backend"

CANONICAL_ENTRYPOINTS = {
    "superbet_market_context.py",
    "superbet_line_coverage.py",
    "superbet_playable.py",
}


def test_canonical_superbet_entrypoints_exist():
    missing = sorted(name for name in CANONICAL_ENTRYPOINTS if not (BACKEND / name).is_file())
    assert not missing, f"Missing canonical Superbet runtime entrypoints: {missing}"


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
    assert "superbet_playable_v912 import" not in text
    assert "LEGACY_IMPLEMENTATION =" not in text


def test_line_coverage_is_fully_canonical_implementation():
    text = (BACKEND / "superbet_line_coverage.py").read_text(encoding="utf-8")
    assert "def enrich_match(" in text
    assert "def enrich_results(" in text
    assert "superbet_line_coverage_v924" not in text
    assert "superbet_line_coverage_v922" not in text
    assert "LEGACY_IMPLEMENTATION =" not in text


def test_market_context_is_real_canonical_implementation():
    text = (BACKEND / "superbet_market_context.py").read_text(encoding="utf-8")
    assert "def prepare(" in text
    assert "def finalize(" in text
    assert "superbet_market_context_v924 import" not in text
    assert "LEGACY_IMPLEMENTATION =" not in text


def test_canonical_runtime_has_no_wildcard_imports():
    offenders = []
    for name in CANONICAL_ENTRYPOINTS:
        text = (BACKEND / name).read_text(encoding="utf-8")
        if re.search(r"\bimport\s+\*", text):
            offenders.append(name)
    assert not offenders, f"Canonical runtime must not leak legacy namespaces through import *: {offenders}"
