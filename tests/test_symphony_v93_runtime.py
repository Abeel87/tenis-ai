from backend import symphony_bo5_compact_v93c as compact
from backend import symphony_scenario_lattice_v93 as deep
from backend import symphony_scenario_runtime_v93 as runtime


def test_bo5_runtime_uses_compact_builder_while_bo3_keeps_deep_paths(monkeypatch):
    seen = []

    def fake_deep(match):
        seen.append(("deep", match.get("best_of")))
        return [{"prob": 1.0, "kind": "deep"}]

    def fake_compact(match):
        seen.append(("compact", match.get("best_of")))
        return [{"prob": 1.0, "kind": "compact", "bo5_compact_scope": compact.SCOPE}]

    def fake_run(legs=4):
        bo5 = deep._build_deep_outcomes({"best_of": 5})
        bo3 = deep._build_deep_outcomes({"best_of": 3})
        assert bo5[0]["kind"] == "compact"
        assert bo3[0]["kind"] == "deep"
        return {"status": "OK", "matches": 2}

    monkeypatch.setattr(deep, "_build_deep_outcomes", fake_deep)
    monkeypatch.setattr(compact, "build_bo5_compact_outcomes", fake_compact)
    monkeypatch.setattr(deep, "run", fake_run)
    result = runtime.run()

    assert seen == [("compact", 5), ("deep", 3)]
    assert result["runtime_guard_version"] == "v9.3C-runtime-compact-bo5"
    assert result["bo3_exact_scope"] == "SET1+SET2+MATCH"
    assert result["bo5_scope"] == compact.SCOPE
    assert result["bo5_checkpoint_fabrication"] is False
