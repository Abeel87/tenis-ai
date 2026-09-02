from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
RETIRED = "superbet_candidate_settlement_v925"
RETIRED_IMPORTS = (
    "from .superbet_candidate_settlement_v925 import",
    "from superbet_candidate_settlement_v925 import",
    "import superbet_candidate_settlement_v925",
)


def test_candidate_settlement_has_one_canonical_module_path():
    assert (BACKEND / "superbet_candidate_settlement.py").is_file()
    assert not (BACKEND / "superbet_candidate_settlement_v925.py").exists()


def test_active_python_imports_do_not_reference_retired_settlement_module():
    offenders = []
    for folder in (BACKEND, ROOT / "tests"):
        for path in folder.glob("*.py"):
            if path.name == Path(__file__).name:
                continue
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in RETIRED_IMPORTS):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, f"Retired settlement module still imported by: {offenders}"


def test_versioned_settlement_data_contract_is_preserved():
    module = (BACKEND / "superbet_candidate_settlement.py").read_text(encoding="utf-8")
    degraded = (BACKEND / "degraded_history.py").read_text(encoding="utf-8")
    reports = (BACKEND / "refresh_settlement_reports.py").read_text(encoding="utf-8")
    assert 'LAYER = "superbet_candidate_signals_v925"' in module
    assert '"superbet_candidate_stats_v925.json"' in degraded
    assert "'superbet_candidate_stats_v925.json'" in reports
    assert '"superbet_candidate_settlement_v925"' in degraded
    assert "'superbet_candidate_settlement_v925'" in reports
    assert "from superbet_candidate_settlement import" in degraded
    assert "from superbet_candidate_settlement import" in reports
