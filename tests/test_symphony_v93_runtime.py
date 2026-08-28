from backend import symphony_scenario_lattice_v93 as deep
from backend import symphony_scenario_runtime_v93 as runtime


def test_bo5_runtime_is_evidence_only_without_deep_state_explosion(monkeypatch):
    seen = []

    def fake_build(match):
        seen.append(match.get("best_of"))
        return [{"prob": 1.0}]

    def fake_run(legs=4):
        # Runtime wrapper must replace deep builder while this function runs.
        assert deep._build_deep_outcomes({"best_of": 5}) == []
        assert deep._build_deep_outcomes({"best_of": 3}) == [{"prob": 1.0}]
        return {"status": "OK", "matches": 2}

    monkeypatch.setattr(deep, "_build_deep_outcomes", fake_build)
    monkeypatch.setattr(deep, "run", fake_run)
    result = runtime.run()

    assert seen == [3]
    assert result["runtime_guard_version"] == "v9.3A-runtime-bounded"
    assert result["bo3_exact_scope"] == "SET1+SET2+MATCH"
    assert result["bo5_scope"] == "EVIDENCE_ONLY_PENDING_COMPACT_DEEP_STATE"
