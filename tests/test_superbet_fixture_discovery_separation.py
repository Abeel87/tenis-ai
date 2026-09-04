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


def test_identity_debug_snapshot_excludes_odds_and_exposes_nested_identity_shape():
    snapshot = core._identity_debug_snapshot({
        "fixture": {
            "id": "fx-1",
            "startTime": "2026-09-04T12:00:00Z",
            "participant1Name": "Player A",
            "participant2Name": "Player B",
        },
        "eventName": "Player A - Player B",
        "bookmakerOdds": {"superbet.pl": {"markets": {"1": {"price": 1.91}}}},
        "markets": {"secret": "must-not-leak"},
    })
    assert snapshot["top_level_keys"] == ["bookmakerOdds", "eventName", "fixture", "markets"]
    assert snapshot["eventName"] == "Player A - Player B"
    assert snapshot["fixture"]["startTime"] == "2026-09-04T12:00:00Z"
    assert snapshot["fixture"]["participant1Name"] == "Player A"
    assert snapshot["fixture"]["participant2Name"] == "Player B"
    assert "bookmakerOdds" not in snapshot
    assert "markets" not in snapshot
