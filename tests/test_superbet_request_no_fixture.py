from __future__ import annotations

import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from backend import superbet_market_core as market


def _provider_404(error_code: str) -> HTTPError:
    body = json.dumps({
        "error": {
            "message": "No fixtures found for the specified lookup.",
            "code": error_code,
        }
    }).encode("utf-8")
    return HTTPError(
        url="https://api.oddspapi.io/v4/test",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=BytesIO(body),
    )


@pytest.mark.parametrize("path", ["fixtures", "odds-by-tournaments"])
def test_fixture_not_found_is_an_empty_lookup(monkeypatch, path):
    def no_fixtures(*_args, **_kwargs):
        raise _provider_404("FIXTURE_NOT_FOUND")

    monkeypatch.setattr(market, "urlopen", no_fixtures)
    quota = {"requests_used_by_v91": 0, "monthly_cap": 4000}

    assert market._request(path, "test-key", quota, tournamentIds="123") == []
    assert quota["requests_used_by_v91"] == 1


def test_other_provider_404_still_fails_closed(monkeypatch):
    def provider_error(*_args, **_kwargs):
        raise _provider_404("BOOKMAKER_NOT_FOUND")

    monkeypatch.setattr(market, "urlopen", provider_error)
    quota = {"requests_used_by_v91": 0, "monthly_cap": 4000}

    with pytest.raises(RuntimeError, match=r"OddsPapi odds-by-tournaments: HTTP 404"):
        market._request(
            "odds-by-tournaments",
            "test-key",
            quota,
            tournamentIds="123",
            bookmakers="superbet.pl",
        )
