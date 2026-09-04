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



def test_requested_bookmaker_payload_is_exact_superbet_pl_only():
    generic = {"markets": {"x": {}}}
    exact = {"markets": {"y": {}}}
    assert core._requested_bookmaker_payload({
        "bookmakerOdds": {"superbet": generic}
    }) is None
    assert core._requested_bookmaker_payload({
        "bookmakerOdds": {"superbet": generic, "superbet.pl": exact}
    }) == exact


def test_direct_offer_cache_without_exact_bookmaker_identity_is_rechecked():
    now = core.datetime(2026, 9, 4, 12, 0, tzinfo=core.timezone.utc)
    legacy = {
        "stage": "within_4h",
        "last_checked_at": now.isoformat(),
        "offer": {"fixture_id": "f1", "bookmaker": "superbet.pl"},
        "last_error": None,
    }
    assert core._direct_offer_due(legacy, "within_4h", now) is True

    exact = dict(legacy, bookmaker_key="superbet.pl")
    assert core._direct_offer_due(exact, "within_4h", now) is False
