import importlib.util
import io
import urllib.error
from pathlib import Path

import pytest


def helper():
    spec = importlib.util.spec_from_file_location(
        "runtime_upload_test", Path(__file__).resolve().parents[1] / "scripts/publish_runtime_private.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Response:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def failure(code):
    return urllib.error.HTTPError(
        "https://storage.example/object?token=do-not-log", code, "failed", {},
        io.BytesIO(b"upstream may echo token=do-not-log"),
    )


@pytest.mark.parametrize("status", [500, 502, 503, 504, 520, 521, 522, 523, 524])
def test_transient_upload_retries_same_immutable_bytes(tmp_path, monkeypatch, status):
    module = helper()
    source = tmp_path / "snapshot.json"
    source.write_bytes(b'{"value":null}')
    requests, sleeps = [], []

    def send(request, **kwargs):
        requests.append(request)
        if len(requests) == 1:
            source.write_bytes(b'{"value":"changed during upload"}')
            raise failure(status)
        return Response()

    monkeypatch.setattr(module.urllib.request, "urlopen", send)
    monkeypatch.setattr(module.time, "sleep", sleeps.append)
    module.upload_signed("https://storage.example/object?token=do-not-log", source)
    assert len(requests) == 2
    assert sleeps == [1]
    assert all(r.data == b'{"value":null}' for r in requests)
    assert all(r.method == "PUT" and r.get_header("X-upsert") == "false" for r in requests)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 413, 429])
def test_permanent_upload_error_is_not_retried_or_leaked(tmp_path, monkeypatch, status):
    module = helper()
    source = tmp_path / "snapshot.json"
    source.write_text("{}")
    calls = []

    def send(*args, **kwargs):
        calls.append(1)
        raise failure(status)

    monkeypatch.setattr(module.urllib.request, "urlopen", send)
    monkeypatch.setattr(module.time, "sleep", lambda _: pytest.fail("must not retry"))
    with pytest.raises(module.PublishError, match=f"HTTP {status}") as error:
        module.upload_signed("https://storage.example/object?token=do-not-log", source)
    assert len(calls) == 1
    assert "do-not-log" not in str(error.value)


def test_exhausted_upload_never_activates_generation(tmp_path, monkeypatch):
    module = helper()
    source = tmp_path / "snapshot.json"
    source.write_text("{}")
    actions, calls, sleeps = [], [], []
    monkeypatch.setattr(module, "snapshot_files", lambda _: ([{"path": "data/x.json"}], {"digest": source}))

    def publisher(body):
        actions.append(body["action"])
        return 200, {"uploads": [{"sha256": "digest", "signed_url": "https://storage.example/object"}]}

    def send(*args, **kwargs):
        calls.append(1)
        raise failure(520)

    monkeypatch.setattr(module, "publisher_call", publisher)
    monkeypatch.setattr(module.urllib.request, "urlopen", send)
    monkeypatch.setattr(module.time, "sleep", sleeps.append)
    with pytest.raises(module.PublishError, match="HTTP 520"):
        module.publish("market")
    assert actions == ["prepare"]
    assert len(calls) == 3
    assert sleeps == [1, 3]


def test_conflict_after_transient_upload_keeps_activation_check(tmp_path, monkeypatch):
    module = helper()
    source = tmp_path / "snapshot.json"
    source.write_text("{}")
    statuses = iter([520, 409])
    actions = []
    monkeypatch.setattr(module, "snapshot_files", lambda _: ([{"path": "data/x.json"}], {"digest": source}))

    def publisher(body):
        actions.append(body["action"])
        if body["action"] == "prepare":
            return 200, {"generation": "new", "expected_generation": "old", "uploads": [
                {"sha256": "digest", "signed_url": "https://storage.example/object"}]}
        assert body == {"action": "activate", "layer": "market", "generation": "new", "expected_generation": "old"}
        return 200, {"ok": True, "generation": "new"}

    def send(*args, **kwargs):
        raise failure(next(statuses))

    monkeypatch.setattr(module, "publisher_call", publisher)
    monkeypatch.setattr(module.urllib.request, "urlopen", send)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    assert module.publish("market")["generation"] == "new"
    assert actions == ["prepare", "activate"]
