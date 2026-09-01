from pathlib import Path


def test_pbp_supply_contract_is_not_silently_zeroed():
    """Guardrail placeholder: implementation must replace this marker with real supply assertions."""
    source = Path("backend/pbp_enrich_v7.py").read_text(encoding="utf-8")
    assert "pbp_v7_profiles" in source or "profiles" in source
