from backend import symphony_bo5_compact_v93c as compact
from backend import symphony_deep_progress_v93m as progress
from backend import symphony_scenario_lattice_v93 as deep
from backend import symphony_scenario_runtime_v93 as runtime


def test_bo5_runtime_uses_compact_builder_while_bo3_keeps_deep_paths(monkeypatch):
    seen = []
    progress_rows = []

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

    def fake_write(path, value):
        if str(path).endswith(progress.FILENAME):
            progress_rows.append(dict(value))

    monkeypatch.setattr(deep, "_build_deep_outcomes", fake_deep)
    monkeypatch.setattr(compact, "build_bo5_compact_outcomes", fake_compact)
    monkeypatch.setattr(deep, "run", fake_run)
    monkeypatch.setattr(runtime.core, "_read", lambda path, fallback: {})
    monkeypatch.setattr(runtime.core, "_write", fake_write)
    result = runtime.run()

    assert seen == [("compact", 5), ("deep", 3)]
    assert result["runtime_guard_version"] == "v9.3C-runtime-compact-bo5"
    assert result["bo3_exact_scope"] == "SET1+SET2+MATCH"
    assert result["bo5_scope"] == compact.SCOPE
    assert result["bo5_checkpoint_fabrication"] is False
    assert result["progress_telemetry_version"] == progress.VERSION

    stages = [row["stage"] for row in progress_rows]
    assert stages[0] == "RUN_START"
    assert stages.count("BUILD_OUTCOME_LATTICE") == 2
    assert stages.count("OUTCOME_LATTICE_DONE") == 2
    assert stages[-1] == "RUN_DONE"
    assert all(row["production_influence"] is False for row in progress_rows)
    assert all(row["playable_influence"] is False for row in progress_rows)
    assert all(row["prices_used"] is False for row in progress_rows)
    assert all(row["external_requests"] == 0 for row in progress_rows)


def test_progress_adapter_restores_all_wrapped_functions(monkeypatch):
    monkeypatch.setattr(runtime.core, "_read", lambda path, fallback: [])
    monkeypatch.setattr(runtime.core, "_write", lambda path, value: None)

    build_match = deep.build_match_model_scenario
    augment = deep._augment_model_raw
    outcomes = deep._build_deep_outcomes
    compositions = runtime.fast._fast_one_pass_compositions

    installed = progress.install(deep, runtime.fast, runtime.core)
    assert deep.build_match_model_scenario is not build_match
    assert deep._augment_model_raw is not augment
    assert deep._build_deep_outcomes is not outcomes
    assert runtime.fast._fast_one_pass_compositions is not compositions

    installed.uninstall()
    assert deep.build_match_model_scenario is build_match
    assert deep._augment_model_raw is augment
    assert deep._build_deep_outcomes is outcomes
    assert runtime.fast._fast_one_pass_compositions is compositions
