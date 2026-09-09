from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend import superbet_market_core as core
from backend import superbet_market_mapping as mapping
from backend import superbet_market_context as context


ROOT = Path(__file__).resolve().parents[1]


def _market_meta():
    return {
        "1": {
            "marketName": "Winner",
            "outcomes": {
                "1": {"outcomeName": "1"},
                "2": {"outcomeName": "2"},
            },
        }
    }


def _book(markets=None):
    return {
        "bookmakerIsActive": True,
        "suspended": False,
        "markets": markets or {},
    }


def _winner_markets():
    return {
        "1": {
            "marketActive": True,
            "outcomes": {
                "1": {
                    "players": {
                        "a": {
                            "active": True,
                            "bookmakerOutcomeId": "1",
                            "mainLine": True,
                        }
                    }
                },
                "2": {
                    "players": {
                        "b": {
                            "active": True,
                            "bookmakerOutcomeId": "2",
                            "mainLine": True,
                        }
                    }
                },
            },
        }
    }


def test_requested_bookmaker_identity_is_exact_superbet_pl_only():
    generic = _book(_winner_markets())
    foreign = _book(_winner_markets())
    exact = _book(_winner_markets())

    assert core._requested_bookmaker_payload({
        "bookmakerOdds": {"superbet": generic, "superbet.ro": foreign}
    }) is None
    assert core._requested_bookmaker_payload({
        "bookmakerOdds": {
            "superbet": generic,
            "superbet.ro": foreign,
            "superbet.pl": exact,
        }
    }) is exact

    assert mapping._sanitize_fixture({
        "fixtureId": "f1",
        "participant1Name": "A",
        "participant2Name": "B",
        "startTime": "2026-09-08T12:00:00Z",
        "bookmakerOdds": {"superbet": generic},
    }, _market_meta()) is None






def test_canonical_provider_selection_requires_explicit_price_level_active_true():
    base_row = {
        "fixtureId": "f-active",
        "participant1Name": "A",
        "participant2Name": "B",
        "startTime": "2026-09-08T12:00:00Z",
    }

    active = _winner_markets()
    active_row = {**base_row, "bookmakerOdds": {"superbet.pl": _book(active)}}
    sanitized = mapping._sanitize_fixture(active_row, _market_meta())
    assert sanitized is not None
    assert len(sanitized["canonical_selections"]) == 2

    for availability_case in ("false", "missing"):
        markets = _winner_markets()
        for outcome in markets["1"]["outcomes"].values():
            for player_data in outcome["players"].values():
                if availability_case == "false":
                    player_data["active"] = False
                else:
                    player_data.pop("active", None)
        row = {**base_row, "bookmakerOdds": {"superbet.pl": _book(markets)}}
        out = mapping._sanitize_fixture(row, _market_meta())
        assert out is not None
        assert out["canonical_selections"] == []


def test_canonical_context_sanitizer_cannot_reintroduce_generic_superbet():
    generic = _book(_winner_markets())
    exact = _book(_winner_markets())
    row = {
        "fixtureId": "f-context",
        "participant1Name": "A",
        "participant2Name": "B",
        "startTime": "2026-09-08T12:00:00Z",
        "bookmakerOdds": {"superbet": generic},
    }
    assert context.mapped_sanitize(row, _market_meta()) is None

    row["bookmakerOdds"]["superbet.pl"] = exact
    sanitized = context.mapped_sanitize(row, _market_meta())
    assert sanitized is not None
    assert sanitized["bookmaker"] == "superbet.pl"
    assert {s["market"] for s in sanitized["canonical_selections"]} == {"match_winner"}

def test_legacy_direct_cache_is_rechecked_under_exact_bookmaker_contract():
    now = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    legacy = {
        "stage": "within_4h",
        "last_checked_at": now.isoformat(),
        "offer": {"fixture_id": "f1", "bookmaker": "superbet.pl"},
        "last_error": None,
    }
    assert core._direct_offer_due(legacy, "within_4h", now) is True

    exact = dict(legacy, bookmaker_key="superbet.pl")
    assert core._direct_offer_due(exact, "within_4h", now) is False
    assert core._direct_offer_due(exact, "within_1h_retry", now) is True


def test_direct_fixture_recovers_current_offer_when_tournament_bulk_is_stale(monkeypatch):
    now = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    start = now + timedelta(hours=2)
    start_iso = start.isoformat().replace("+00:00", "Z")
    previous = {
        "generated_at": (now - timedelta(hours=2)).isoformat(),
        "market_meta_generated_at": (now - timedelta(hours=1)).isoformat(),
        "market_meta_cache": _market_meta(),
        "fixtures": [],
        "quota_guard": {
            "month": "2026-09",
            "requests_used_by_v91": 0,
            "direct_fixture_requests_used": 0,
        },
        "direct_fixture_cache": {},
    }
    written = {}
    calls = []

    discovered = {
        "fixtureId": "f1",
        "participant1Name": "A",
        "participant2Name": "B",
        "startTime": start_iso,
        "tournamentId": "t1",
        "tournamentName": "ATP Test",
        "hasOdds": True,
    }
    stale_bulk = {
        "fixtureId": "old-f1",
        "participant1Name": "A",
        "participant2Name": "B",
        "startTime": (now - timedelta(days=3)).isoformat().replace("+00:00", "Z"),
        "tournamentId": "t1",
        "tournamentName": "ATP Test",
        "bookmakerOdds": {"superbet": _book(_winner_markets())},
    }
    direct = {
        "fixtureId": "f1",
        "participant1Name": "A",
        "participant2Name": "B",
        "startTime": start_iso,
        "tournamentId": "t1",
        "tournamentName": "ATP Test",
        "bookmakerOdds": {"superbet.pl": _book(_winner_markets())},
    }

    def fake_request(path, api_key, quota, **params):
        calls.append((path, dict(params)))
        if path == "fixtures":
            return [discovered]
        if path == "odds-by-tournaments":
            return [stale_bulk]
        if path == "odds":
            assert params.get("fixtureId") == "f1"
            assert params.get("bookmakers") == "superbet.pl"
            return [direct]
        raise AssertionError(f"unexpected OddsPapi path: {path}")

    monkeypatch.setenv("ODDSPAPI_API_KEY", "test-key")
    monkeypatch.setattr(core, "_read", lambda path, fallback: previous)
    monkeypatch.setattr(core, "_write", lambda path, value: written.update({"value": value}))
    monkeypatch.setattr(core, "_request", fake_request)
    monkeypatch.setattr(core.time, "sleep", lambda *_: None)

    report = core.refresh_availability([
        {"id": "m1", "p1": "A", "p2": "B", "scheduled_time": start_iso}
    ], now=now)

    assert report["refresh_status"] == "OK"
    assert report["bookmaker"] == "superbet.pl"
    assert report["direct_fixture_requests_this_refresh"] == 1
    assert report["direct_fixture_matches"] == 1
    assert report["contract"]["requested_bookmaker_identity"] == "EXACT_KEY_ONLY"
    assert report["contract"]["tournament_bulk_is_not_current_offer_authority"] is True
    assert len(report["fixtures"]) == 1
    fixture = report["fixtures"][0]
    assert fixture["fixture_id"] == "f1"
    assert fixture["operator_offer_source"] == "odds_by_fixture"
    assert fixture["bookmaker"] == "superbet.pl"
    assert {s["market"] for s in fixture["canonical_selections"]} == {"match_winner"}
    assert any(path == "odds" for path, _ in calls)
    assert written["value"]["fixtures"][0]["fixture_id"] == "f1"


def test_mapping_cannot_override_core_offer_policy_owner():
    text = (ROOT / "backend" / "superbet_market_mapping.py").read_text(encoding="utf-8")
    assert mapping.REFRESH_HOURS == core.REFRESH_HOURS
    assert mapping.MONTHLY_REQUEST_CAP == core.MONTHLY_REQUEST_CAP
    assert "REFRESH_HOURS = base.REFRESH_HOURS" in text
    assert "MONTHLY_REQUEST_CAP = base.MONTHLY_REQUEST_CAP" in text
    assert "base.REFRESH_HOURS=" not in text
    assert "base.MONTHLY_REQUEST_CAP=" not in text
    assert "base._requested_bookmaker_payload(row)" in text



def test_direct_cache_freshness_uses_actual_offer_check_time_not_hourly_report_time():
    now = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    checked = now - timedelta(hours=3)
    availability = {
        "generated_at": now.isoformat(),
        "fixtures": [{
            "fixture_id": "f1",
            "p1": "A",
            "p2": "B",
            "start_time": (now + timedelta(hours=2)).isoformat(),
            "bookmaker": "superbet.pl",
            "suspended": False,
            "offer_checked_at": checked.isoformat(),
            "operator_offer_source": "odds_by_fixture_cache",
            "canonical_selections": [{
                "market": "match_winner",
                "pick": "A",
                "line": None,
                "operator_available": True,
                "operator_line_verified": True,
            }],
        }],
    }

    rows, matched = core.prepare_results([{
        "id": "m1",
        "p1": "A",
        "p2": "B",
        "scheduled_time": (now + timedelta(hours=2)).isoformat(),
    }], availability, now=now)

    assert matched == 1
    operator = rows[0]["superbet_market_v91"]
    assert operator["source_generated_at"] == checked.isoformat()
    assert operator["source_age_hours"] == 3.0
    assert operator["status"] == "CACHE_STALE"
    assert operator["operator_verified"] is False



def test_all_active_superbet_provider_layers_reject_generic_bookmaker_fallback():
    backend = ROOT / "backend"
    active = (
        "superbet_market_core.py",
        "superbet_market_mapping.py",
        "superbet_market_context.py",
        "superbet_market_audit.py",
        "superbet_fixture_matching.py",
        "superbet_line_coverage.py",
        "superbet_playable.py",
    )
    forbidden = (
        '"superbet" in str(',
        "'superbet' in str(",
        "bookmaker_odds.items() if \"superbet\"",
    )
    offenders = []
    for name in active:
        text = (backend / name).read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                offenders.append(f"{name}:{token}")
    assert not offenders, f"generic/foreign Superbet fallback returned: {offenders}"



def test_context_keeps_strict_parser_version_as_cache_invalidation_owner():
    text = (ROOT / "backend" / "superbet_market_context.py").read_text(encoding="utf-8")
    assert 'availability["runtime_adapter_version"]=STRICT_FIXTURE_LINE_VERSION' in text
    assert 'availability["runtime_adapter_version"]=VERSION' not in text
    assert context.STRICT_FIXTURE_LINE_VERSION != context.VERSION
