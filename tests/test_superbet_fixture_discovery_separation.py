from backend import superbet_market_context as context


def test_fixture_discovery_strips_offer_filters_only_from_fixtures():
    calls = []

    def fake_request(path, api_key, quota, **params):
        calls.append((path, params))
        return []

    quota = {"requests_used_by_v91": 0, "monthly_cap": 10}
    context._fixture_discovery_request(
        fake_request,
        "fixtures",
        "key",
        quota,
        sportId=12,
        statusId=0,
        hasOdds="true",
        bookmakers="superbet.pl",
        language="en",
    )
    path, params = calls[-1]
    assert path == "fixtures"
    assert params["sportId"] == 12
    assert params["statusId"] == 0
    assert params["language"] == "en"
    assert "hasOdds" not in params
    assert "bookmakers" not in params


def test_operator_odds_query_keeps_superbet_filter():
    calls = []

    def fake_request(path, api_key, quota, **params):
        calls.append((path, params))
        return []

    quota = {"requests_used_by_v91": 0, "monthly_cap": 10}
    context._fixture_discovery_request(
        fake_request,
        "odds-by-tournaments",
        "key",
        quota,
        tournamentIds="123,456",
        bookmakers="superbet.pl",
        language="en",
        verbosity=3,
        oddsFormat="decimal",
    )
    path, params = calls[-1]
    assert path == "odds-by-tournaments"
    assert params["bookmakers"] == "superbet.pl"
    assert params["tournamentIds"] == "123,456"


def test_patched_runtime_restores_original_request(monkeypatch):
    original = context.base._request
    observed = []

    def fake_request(path, api_key, quota, **params):
        observed.append((path, params))
        return []

    monkeypatch.setattr(context.base, "_request", fake_request)
    installed_original = context.base._request
    with context._patched_runtime():
        context.base._request(
            "fixtures",
            "key",
            {"requests_used_by_v91": 0, "monthly_cap": 10},
            sportId=12,
            hasOdds="true",
            bookmakers="superbet.pl",
        )
        assert observed[-1][0] == "fixtures"
        assert "hasOdds" not in observed[-1][1]
        assert "bookmakers" not in observed[-1][1]
    assert context.base._request is installed_original
    monkeypatch.setattr(context.base, "_request", original)
