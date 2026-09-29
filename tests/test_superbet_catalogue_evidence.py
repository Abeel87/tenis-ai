import importlib.util
from pathlib import Path

def _core():
    spec = importlib.util.spec_from_file_location("catalogue_core", Path(__file__).resolve().parents[1] / "backend/superbet_market_core.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_catalogue_evidence_distinguishes_missing_names_from_no_overlap():
    core = _core()
    row = {"fixtureId": "f1", "startTime": "2026-09-29T10:00:00Z",
           "sportId": 12, "statusId": 0, "bookmakerOdds": {"secret": 1.5}}
    evidence = core._fixture_catalogue_evidence([row], "2026-09-29", "2026-10-01")
    assert evidence["missing_fields"]["participant1Name"] == 1
    assert evidence["missing_fields"]["participant2Name"] == 1
    assert evidence["sport_ids"] == {"12": 1}
    assert evidence["start_days"] == {"2026-09-29": 1}
    assert "bookmakerOdds" not in evidence["identity_samples"][0]
    row.update(participant1Name="Alpha Player", participant2Name="Beta Player")
    evidence = core._fixture_catalogue_evidence([row] * 70, "2026-09-29", "2026-10-01")
    assert evidence["missing_fields"] == {key: 0 for key in ("fixtureId", "participant1Name", "participant2Name", "startTime")}
    assert len(evidence["identity_samples"]) == 64
    assert evidence["identity_samples"][0]["participant1Name"] == "Alpha Player"

def test_evidence_is_saved_even_when_no_fixture_matches():
    text = (Path(__file__).resolve().parents[1] / "backend/superbet_market_core.py").read_text()
    assert text.count('"fixture_catalogue_evidence": discovery_evidence') == 2
