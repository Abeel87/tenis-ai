from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"(?<![A-Za-z0-9_])model_ready(?![A-Za-z0-9_])")
EXPECTED_EXACT_TOKEN_FILES = {
    "backend/autolearn_v84.py",
    "backend/context_engine_shadow.py",
    "backend/history_coverage_audit.py",
    "backend/history_freshness_counterfactual.py",
    "backend/history_tracker.py",
    "backend/market_lab_v741.py",
    "backend/model.py",
    "backend/model_core.py",
    "backend/pbp_cache_recovery.py",
    "backend/pbp_enrich.py",
    "backend/player_dna_player_state_shadow.py",
    "backend/population_priors_audit.py",
    "backend/prediction_integrity_v78a.py",
    "backend/ranking_provenance_audit.py",
    "backend/readiness_engine_shadow.py",
    "backend/shadow_lab_v78e6.py",
    "backend/specialist_learning_v79b.py",
    "backend/tml_2024_integration_readiness_audit.py",
    "backend/tml_2024_runtime_equivalence_audit.py",
    "backend/update.py",
    "frontend/app.js",
}


def _source_files():
    for root_name in ("backend", "frontend"):
        for path in (ROOT / root_name).rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".js", ".mjs"}:
                continue
            if "__pycache__" in path.parts or "data" in path.parts:
                continue
            yield path


def test_legacy_model_ready_exact_token_inventory_is_frozen():
    found = {
        path.relative_to(ROOT).as_posix()
        for path in _source_files()
        if TOKEN.search(path.read_text(encoding="utf-8"))
    }
    assert found == EXPECTED_EXACT_TOKEN_FILES


def test_consumer_map_covers_every_exact_token_file():
    mapping = (ROOT / "TENIS_AI_READINESS_CONSUMER_MAP.md").read_text(encoding="utf-8")
    missing = [path for path in sorted(EXPECTED_EXACT_TOKEN_FILES) if f"`{path}`" not in mapping]
    assert not missing, f"Consumer map missing exact-token files: {missing}"
    assert "Audited exact-token source count: **21 files**" in mapping


def test_consumer_audit_does_not_wire_shadow_readiness_into_runtime_consumers():
    runtime_consumers = (
        "backend/history_tracker.py",
        "backend/market_lab_v741.py",
        "backend/pbp_cache_recovery.py",
        "backend/pbp_enrich.py",
        "backend/autolearn_v84.py",
        "backend/specialist_learning_v79b.py",
        "backend/shadow_lab_v78e6.py",
        "backend/update.py",
        "frontend/app.js",
    )
    for name in runtime_consumers:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "readiness_engine_shadow" not in text
        assert "readiness_engine_shadow.json" not in text


def test_similarly_named_readiness_contracts_remain_distinct():
    assert "market_ready" in (ROOT / "backend/pbp_market_evidence.py").read_text(encoding="utf-8")
    assert "learning_model_ready" in (ROOT / "backend/symphony2_engine.py").read_text(encoding="utf-8")
    superbet = (ROOT / "backend/superbet_direct.py").read_text(encoding="utf-8")
    assert "has_operator_market_evidence" in superbet
    readiness = (ROOT / "backend/readiness_engine_shadow.py").read_text(encoding="utf-8")
    assert '"legacy_model_ready_observational_only": True' in readiness
    assert '"runtime_gating_enabled": False' in readiness
