import io
import json
from urllib.error import HTTPError

import pytest

from backend import superbet_market_core as core


def _http_error(path: str, status: int, payload: dict) -> HTTPError:
    body = io.BytesIO(json.dumps(payload).encode("utf-8"))
    return HTTPError(f"https://example.invalid/{path}", status, "error", {}, body)


def test_fixture_not_found_means_valid_empty_fixture_catalogue(monkeypatch):
    def fake_urlopen(*args, **kwargs):
        raise _http_error(
            "fixtures",
            404,
            {"error": {"code": "FIXTURE_NOT_FOUND", "message": "No fixtures found for the specified criteria"}},
        )

    monkeypatch.setattr(core, "urlopen", fake_urlopen)
    quota = {"requests_used_by_v91": 0, "monthly_cap": 150}

    assert core._request("fixtures", "secret", quota, sportId=12) == []
    assert quota["requests_used_by_v91"] == 1


@pytest.mark.parametrize(
    ("path", "status", "payload"),
    [
        ("markets", 404, {"error": {"code": "FIXTURE_NOT_FOUND", "message": "No fixtures found"}}),
        ("fixtures", 404, {"error": {"code": "OTHER_NOT_FOUND", "message": "not found"}}),
        ("fixtures", 404, {"code": "FIXTURE_NOT_FOUND", "message": "wrong shape"}),
        ("fixtures", 401, {"error": {"code": "UNAUTHORIZED"}}),
        ("fixtures", 429, {"error": {"code": "RATE_LIMITED"}}),
        ("fixtures", 500, {"error": {"code": "SERVER_ERROR"}}),
    ],
)
def test_other_http_errors_remain_hard_failures(monkeypatch, path, status, payload):
    def fake_urlopen(*args, **kwargs):
        raise _http_error(path, status, payload)

    monkeypatch.setattr(core, "urlopen", fake_urlopen)
    quota = {"requests_used_by_v91": 0, "monthly_cap": 150}

    with pytest.raises(RuntimeError, match=rf"OddsPapi {path}: HTTP {status}"):
        core._request(path, "secret", quota)
