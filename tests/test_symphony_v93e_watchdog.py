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
    assert written[-1][0] == engine.DEEP_RUNTIME_STATUS
    assert written[-1][1]["execution_version"] == engine.DEEP_EXECUTION_VERSION


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
