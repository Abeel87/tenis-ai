from datetime import datetime, timezone

from backend import superbet_market_context as context
from backend import superbet_market_core as core


def test_fixture_discovery_is_bookmaker_neutral_and_operator_query_is_filtered(monkeypatch):
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    previous = {
        "generated_at": "2026-09-03T00:00:00+00:00",
        "market_meta_generated_at": "2026-09-04T11:00:00+00:00",
        "market_meta_cache": {"1": {"marketName": "Winner", "outcomes": {}}},
        "quota_guard": {
            "month": "2026-09",
            "monthly_cap": core.MONTHLY_REQUEST_CAP,
            "requests_used_by_v91": 0,
        },
        "fixtures": [],
    }
    calls = []
    writes = []

    def fake_request(path, api_key, quota, **params):
        calls.append((path, params))
        if path == "fixtures":
            return [{
                "fixtureId": "neutral-fixture-1",
                "participant1Name": "Player A",
                "participant2Name": "Player B",
                "startTime": "2026-09-04T12:00:00+00:00",
                "tournamentId": "tournament-1",
            }]
        if path == "odds-by-tournaments":
            return [{
                "fixtureId": "operator-fixture-99",
                "participant1Name": "Player A",
                "participant2Name": "Player B",
                "startTime": "2026-09-04T12:00:00+00:00",
                "tournamentId": "tournament-1",
                "bookmakerOdds": {"superbet.pl": {"markets": {}}},
            }]
        raise AssertionError(f"unexpected request path: {path}")

    monkeypatch.setenv("ODDSPAPI_API_KEY", "test-key")
    monkeypatch.setattr(core, "_read", lambda path, fallback: previous)
    monkeypatch.setattr(core, "_write", lambda path, value: writes.append((path, value)))
    monkeypatch.setattr(core, "_request", fake_request)
    monkeypatch.setattr(core, "_sanitize_fixture", lambda row, meta: {
        "fixture_id": row.get("fixtureId"),
        "p1": row.get("participant1Name"),
        "p2": row.get("participant2Name"),
        "canonical_selections": [],
    })
    monkeypatch.setattr(core.time, "sleep", lambda *_: None)

    report = core.refresh_availability([{
        "p1": "Player A",
        "p2": "Player B",
        "scheduled_time": "2026-09-04T12:00:00+00:00",
    }], now=now)

    fixture_path, fixture_params = calls[0]
    assert fixture_path == "fixtures"
    assert fixture_params["sportId"] == core.SPORT_ID_TENNIS
    assert fixture_params["statusId"] == 0
    assert fixture_params["language"] == "en"
    assert "hasOdds" not in fixture_params
    assert "bookmakers" not in fixture_params

    odds_path, odds_params = calls[1]
    assert odds_path == "odds-by-tournaments"
    assert odds_params["bookmakers"] == core.BOOKMAKER
    assert odds_params["tournamentIds"] == "tournament-1"
    assert report["refresh_status"] == "OK"
    assert report["operator_odds_rows_seen"] == 1
    assert report["operator_fixture_candidates"] == 1
    assert report["operator_fixture_id_matches"] == 0
    assert report["operator_pair_time_matches"] == 1
    assert report["operator_fixture_ids_in_neutral_catalogue"] == 0
    assert report["operator_rows_with_requested_bookmaker"] == 1
    assert report["operator_rows_in_horizon"] == 1
    assert report["operator_rows_in_horizon_with_requested_bookmaker"] == 1
    assert report["operator_bookmakers_seen"] == ["superbet.pl"]
    assert report["operator_start_min"] == "2026-09-04T12:00:00+00:00"
    assert report["operator_start_max"] == "2026-09-04T12:00:00+00:00"
    assert len(report["fixtures"]) == 1
    assert report["fixtures"][0]["fixture_id"] == "operator-fixture-99"
    assert writes


def test_context_runtime_does_not_patch_core_request():
    original_request = context.base._request
    with context._patched_runtime():
        assert context.base._request is original_request
    assert context.base._request is original_request




def test_stale_operator_row_is_rejected_before_fixture_join(monkeypatch):
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    previous = {
        "generated_at": "2026-09-03T00:00:00+00:00",
        "market_meta_generated_at": "2026-09-04T11:00:00+00:00",
        "market_meta_cache": {"1": {"marketName": "Winner", "outcomes": {}}},
        "quota_guard": {
            "month": "2026-09",
            "monthly_cap": core.MONTHLY_REQUEST_CAP,
            "requests_used_by_v91": 0,
        },
        "fixtures": [],
    }

    def fake_request(path, api_key, quota, **params):
        if path == "fixtures":
            return [{
                "fixtureId": "shared-fixture-id",
                "participant1Name": "Player A",
                "participant2Name": "Player B",
                "startTime": "2026-09-04T12:00:00+00:00",
                "tournamentId": "tournament-1",
            }]
        if path == "odds-by-tournaments":
            # Same provider fixture ID, but historical tournament row.
            # It must be rejected before fixture identity matching.
            return [{
                "fixtureId": "shared-fixture-id",
                "participant1Name": "Player A",
                "participant2Name": "Player B",
                "startTime": "2026-08-31T12:00:00+00:00",
                "tournamentId": "tournament-1",
                "bookmakerOdds": {"superbet.pl": {"markets": {}}},
            }]
        if path == "odds":
            # Direct current-fixture lookup is allowed to find no Superbet offer;
            # the stale tournament row must still stay rejected.
            assert params["fixtureId"] == "shared-fixture-id"
            assert params["bookmakers"] == core.BOOKMAKER
            return []
        raise AssertionError(path)

    monkeypatch.setenv("ODDSPAPI_API_KEY", "test-key")
    monkeypatch.setattr(core, "_read", lambda path, fallback: previous)
    monkeypatch.setattr(core, "_write", lambda path, value: None)
    monkeypatch.setattr(core, "_request", fake_request)
    monkeypatch.setattr(core.time, "sleep", lambda *_: None)

    report = core.refresh_availability([{
        "p1": "Player A",
        "p2": "Player B",
        "scheduled_time": "2026-09-04T12:00:00+00:00",
    }], now=now)

    assert report["operator_odds_rows_seen"] == 1
    assert report["operator_rows_with_requested_bookmaker"] == 1
    assert report["operator_rows_in_horizon"] == 0
    assert report["operator_rows_in_horizon_with_requested_bookmaker"] == 0
    assert report["operator_fixture_candidates"] == 0
    assert report["operator_fixture_id_matches"] == 0
    assert report["direct_fixture_requests_this_refresh"] == 1
    assert report["direct_fixture_rows_seen"] == 0
    assert report["direct_fixture_matches"] == 0
    assert report["fixtures"] == []
    assert report["contract"]["current_operator_horizon_required"] is True
    assert report["contract"]["requested_bookmaker_required_before_join"] is True



def test_direct_fixture_odds_recovers_current_superbet_when_bulk_is_stale(monkeypatch):
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    previous = {
        "generated_at": "2026-09-03T00:00:00+00:00",
        "market_meta_generated_at": "2026-09-04T11:00:00+00:00",
        "market_meta_cache": {"1": {"marketName": "Winner", "outcomes": {}}},
        "quota_guard": {
            "month": "2026-09",
            "monthly_cap": core.MONTHLY_REQUEST_CAP,
            "requests_used_by_v91": 0,
            "direct_fixture_request_cap": core.DIRECT_FIXTURE_MONTHLY_CAP,
            "direct_fixture_requests_used": 0,
        },
        "fixtures": [],
        "direct_fixture_cache": {},
    }
    calls = []

    current_fixture = {
        "fixtureId": "fixture-current",
        "participant1Name": "Player A",
        "participant2Name": "Player B",
        "startTime": "2026-09-04T14:00:00+00:00",
        "tournamentId": "tournament-1",
    }

    def fake_request(path, api_key, quota, **params):
        calls.append((path, dict(params)))
        if path == "fixtures":
            return [current_fixture]
        if path == "odds-by-tournaments":
            return [{
                "fixtureId": "fixture-current",
                "participant1Name": "Player A",
                "participant2Name": "Player B",
                "startTime": "2026-08-31T14:00:00+00:00",
                "tournamentId": "tournament-1",
                "bookmakerOdds": {"superbet.pl": {"markets": {}}},
            }]
        if path == "odds":
            assert params["fixtureId"] == "fixture-current"
            assert params["bookmakers"] == core.BOOKMAKER
            return {
                **current_fixture,
                "bookmakerOdds": {
                    "superbet.pl": {
                        "bookmakerIsActive": True,
                        "suspended": False,
                        "markets": {"1": {}},
                    }
                },
            }
        raise AssertionError(path)

    monkeypatch.setenv("ODDSPAPI_API_KEY", "test-key")
    monkeypatch.setattr(core, "_read", lambda path, fallback: previous)
    monkeypatch.setattr(core, "_write", lambda path, value: None)
    monkeypatch.setattr(core, "_request", fake_request)
    monkeypatch.setattr(core, "_sanitize_fixture", lambda row, meta: {
        "fixture_id": row.get("fixtureId"),
        "p1": row.get("participant1Name"),
        "p2": row.get("participant2Name"),
        "start_time": row.get("startTime"),
        "canonical_selections": [{"market": "match_winner", "pick": "Player A"}],
    })
    monkeypatch.setattr(core.time, "sleep", lambda *_: None)

    report = core.refresh_availability([{
        "p1": "Player A",
        "p2": "Player B",
        "scheduled_time": "2026-09-04T14:00:00+00:00",
    }], now=now)

    assert [path for path, _ in calls] == ["fixtures", "odds-by-tournaments", "odds"]
    assert report["bulk_operator_odds_rows_seen"] == 1
    assert report["operator_rows_in_horizon"] == 1
    assert report["operator_rows_in_horizon_with_requested_bookmaker"] == 1
    assert report["direct_fixture_requests_this_refresh"] == 1
    assert report["direct_fixture_rows_seen"] == 1
    assert report["direct_fixture_rows_with_superbet"] == 1
    assert report["direct_fixture_matches"] == 1
    assert len(report["fixtures"]) == 1
    assert report["fixtures"][0]["fixture_id"] == "fixture-current"
    assert report["fixtures"][0]["operator_offer_source"] == "odds_by_fixture"
    assert report["contract"]["current_offer_primary_recovery"] == "odds_by_fixture"
    assert report["contract"]["tournament_bulk_is_not_current_offer_authority"] is True
    assert report["quota_guard"]["direct_fixture_requests_used"] == 1


def test_direct_fixture_cache_avoids_repeating_same_milestone(monkeypatch):
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    cached_offer = {
        "fixture_id": "fixture-cache",
        "p1": "Player A",
        "p2": "Player B",
        "start_time": "2026-09-04T18:00:00+00:00",
        "canonical_selections": [{"market": "match_winner", "pick": "Player A"}],
    }
    previous = {
        "generated_at": "2026-09-03T00:00:00+00:00",
        "market_meta_generated_at": "2026-09-04T11:00:00+00:00",
        "market_meta_cache": {"1": {"marketName": "Winner", "outcomes": {}}},
        "quota_guard": {
            "month": "2026-09",
            "monthly_cap": core.MONTHLY_REQUEST_CAP,
            "requests_used_by_v91": 10,
            "direct_fixture_request_cap": core.DIRECT_FIXTURE_MONTHLY_CAP,
            "direct_fixture_requests_used": 3,
        },
        "fixtures": [],
        "direct_fixture_cache": {
            "fixture-cache": {
                "stage": "within_12h",
                "last_checked_at": "2026-09-04T11:00:00+00:00",
                "offer": cached_offer,
                "last_error": None,
            }
        },
    }
    calls = []

    def fake_request(path, api_key, quota, **params):
        calls.append(path)
        if path == "fixtures":
            return [{
                "fixtureId": "fixture-cache",
                "participant1Name": "Player A",
                "participant2Name": "Player B",
                "startTime": "2026-09-04T18:00:00+00:00",
                "tournamentId": "tournament-1",
            }]
        if path == "odds-by-tournaments":
            return []
        if path == "odds":
            raise AssertionError("same direct milestone must reuse sanitized cache")
        raise AssertionError(path)

    monkeypatch.setenv("ODDSPAPI_API_KEY", "test-key")
    monkeypatch.setattr(core, "_read", lambda path, fallback: previous)
    monkeypatch.setattr(core, "_write", lambda path, value: None)
    monkeypatch.setattr(core, "_request", fake_request)
    monkeypatch.setattr(core.time, "sleep", lambda *_: None)

    report = core.refresh_availability([{
        "p1": "Player A",
        "p2": "Player B",
        "scheduled_time": "2026-09-04T18:00:00+00:00",
    }], now=now)

    assert calls == ["fixtures", "odds-by-tournaments"]
    assert report["direct_fixture_requests_this_refresh"] == 0
    assert report["direct_fixture_cache_offers_used"] == 1
    assert report["fixtures"][0]["operator_offer_source"] == "odds_by_fixture_cache"
    assert report["quota_guard"]["direct_fixture_requests_used"] == 3
