from __future__ import annotations

import subprocess
from types import SimpleNamespace

from backend import symphony_engine_v91 as engine


def test_deep_watchdog_returns_success_without_touching_model_math(monkeypatch):
    written = []
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        return SimpleNamespace(
            returncode=0,
            stdout='{"status":"OK","matches":7,"production_influence":false}\n',
            stderr="",
        )

    monkeypatch.setenv("SYMPHONY_DEEP_TIMEOUT_SECONDS", "42")
    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    monkeypatch.setattr(engine.base.core, "_write", lambda path, payload: written.append((path, payload)))

    result = engine._run_deep_bounded(legs=4)

    assert result["status"] == "OK"
    assert result["matches"] == 7
    assert result["timeout_seconds"] == 42
    assert result["preserved_previous_report"] is False
    assert result["execution_version"] == engine.DEEP_EXECUTION_VERSION
    assert seen["kwargs"]["timeout"] == 42
    assert seen["kwargs"]["check"] is False
    assert seen["command"][-2:] == ["--legs", "4"]
    assert written[-1][0] == engine.DEEP_RUNTIME_STATUS
    assert written[-1][1]["prices_used"] is False
    assert written[-1][1]["production_influence"] is False
    assert written[-1][1]["playable_influence"] is False


def test_deep_watchdog_timeout_preserves_previous_complete_report(monkeypatch):
    written = []

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setenv("SYMPHONY_DEEP_TIMEOUT_SECONDS", "31")
    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    monkeypatch.setattr(engine.base.core, "_write", lambda path, payload: written.append((path, payload)))

    result = engine._run_deep_bounded(legs=5)

    assert result == {
        "status": "TIMEOUT",
        "timeout_seconds": 31,
        "preserved_previous_report": True,
        "reason": "DEEP_MODEL_RAW_EXCEEDED_WALL_CLOCK_BOUND",
    }
    runtime_payload = next(payload for path, payload in written if path == engine.DEEP_RUNTIME_STATUS)
    assert runtime_payload["execution_version"] == engine.DEEP_EXECUTION_VERSION


def test_deep_watchdog_failure_is_nonfatal_and_diagnostic(monkeypatch):
    written = []

    monkeypatch.setattr(
        engine.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=9, stdout="", stderr="boom\ntrace"),
    )
    monkeypatch.setattr(engine.base.core, "_write", lambda path, payload: written.append((path, payload)))

    result = engine._run_deep_bounded()

    assert result["status"] == "ERROR"
    assert result["returncode"] == 9
    assert result["preserved_previous_report"] is True
    assert result["stderr_tail"].endswith("trace")
    assert written[-1][1]["prices_used"] is False


def test_terminal_telemetry_reconciles_stale_running_state(monkeypatch):
    writes = []
    payloads = {
        engine.DEEP_INCREMENTAL_STATUS: {"status": "RUNNING", "completed_this_run": 37, "pending_entries": 70},
        engine.DEEP_PROGRESS_STATUS: {"stage": "OUTCOME_LATTICE_DONE", "completed_matches": 37},
    }
    monkeypatch.setattr(engine.base.core, "_read", lambda path, default=None: dict(payloads.get(path, default or {})))
    monkeypatch.setattr(engine.base.core, "_write", lambda path, payload: writes.append((path, dict(payload))))
    engine._mark_deep_terminal("TIMEOUT", "DEEP_MODEL_RAW_EXCEEDED_WALL_CLOCK_BOUND")
    by_path = {path: payload for path, payload in writes}
    inc = by_path[engine.DEEP_INCREMENTAL_STATUS]
    progress = by_path[engine.DEEP_PROGRESS_STATUS]
    assert inc["status"] == "TIMEOUT"
    assert inc["child_status_at_termination"] == "RUNNING"
    assert inc["completed_this_run"] == 37 and inc["pending_entries"] == 70
    assert progress["stage"] == "OUTCOME_LATTICE_DONE"
    assert progress["terminal_status"] == "TIMEOUT"
    assert progress["completed_matches"] == 37
    assert inc["prices_used"] is False and progress["prices_used"] is False
