from pathlib import Path
from types import SimpleNamespace

from scripts import runtime_health


def test_chunked_history_manifest_is_exact_size_baseline(monkeypatch):
    calls = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        if args[1] == 'cat-file':
            return SimpleNamespace(returncode=1, stdout='')
        return SimpleNamespace(
            returncode=0,
            stdout='{"format":"exact-history-bytes-v1","bytes":111500000,"chunks":[]}',
        )

    monkeypatch.setattr(runtime_health.subprocess, 'run', fake_run)
    assert runtime_health._git_blob_size(Path('/tmp'), 'base', 'history.json') == 111500000
    assert calls[0][1] == 'show'


def test_unrelated_missing_blob_has_no_manifest_fallback(monkeypatch):
    calls = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1, stdout='')

    monkeypatch.setattr(runtime_health.subprocess, 'run', fake_run)
    assert runtime_health._git_blob_size(Path('/tmp'), 'base', 'results.json') is None
    assert len(calls) == 1


def test_chunked_history_precedes_tracked_empty_placeholder(monkeypatch):
    calls = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        if args[1] == 'cat-file':
            return SimpleNamespace(returncode=0, stdout='2')
        return SimpleNamespace(
            returncode=0,
            stdout='{"format":"exact-history-bytes-v1","bytes":112133661,"chunks":[]}',
        )

    monkeypatch.setattr(runtime_health.subprocess, 'run', fake_run)
    assert runtime_health._git_blob_size(Path('/tmp'), 'base', 'history.json') == 112133661
    assert calls[0][1] == 'show'
