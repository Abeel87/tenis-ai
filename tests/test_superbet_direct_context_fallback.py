from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend import superbet_market_context as context
from backend import superbet_market_core as core


def _direct_sidecar(now: datetime, *, prices_used: bool = False) -> dict:
    return {
        "mode": "SHADOW_SUPERBET_DIRECT_SELECTED_MATCH_FEED",
        "status": "OK",
        "generated_at": now.isoformat(),
        "operator": "superbet.pl",
        "contains_prices": True,
        "operator_prices_metadata_only": True,
        "prices_used": prices_used,
        "writes_canonical_context": False,
        "production_influence": False,
        "playable_influence": False,
        "matches": [
            {
                "match_id": "paul-bublik",
                "p1": "Tommy Paul",
                "p2": "Alexander Bublik",
                "scheduled_time": "2026-09-04T16:30:00Z",
                "event_id": "14809301",
                "event_url": "https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301",
                "operator_start_time": "2026-09-04T16:30:00Z",
                "direct_match_verified": True,
                "prices_used": False,
                "market_counts": {"match_total": 2},
                "canonical_selections": [
                    {
                        "market": "match_total",
                        "pick": "over",
                        "line": 38.5,
                        "player": None,
                        "set_no": None,
                        "operator_available": True,
                        "operator_line_verified": True,
                        "fixture_line_verified": True,
                        "operator_price": 1.95,
                        "operator_price_verified": True,
                        "operator_price_source": "superbet_direct_public_event_json",
                        "operator_market_id": 1001,
                        "operator_outcome_id": 2001,
                        "operator_market_name": "Liczba gemów",
                        "raw_label": "Powyżej 38.5",
                        "direct_source": True,
                        "prices_used": False,
                    },
                    {
                        "market": "match_total",
                        "pick": "under",
                        "line": 38.5,
                        "player": None,
                        "set_no": None,
                        "operator_available": True,
                        "operator_line_verified": True,
                        "fixture_line_verified": True,
                        "operator_price": 1.85,
                        "operator_price_verified": True,
                        "operator_price_source": "superbet_direct_public_event_json",
                        "operator_market_id": 1001,
                        "operator_outcome_id": 2002,
                        "operator_market_name": "Liczba gemów",
                        "raw_label": "Poniżej 38.5",
                        "direct_source": True,
                        "prices_used": False,
                    },
                ],
            }
        ],
    }


def _write_sidecar(monkeypatch, tmp_path: Path, payload: dict) -> None:
    path = tmp_path / "superbet_direct_current.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(context, "DIRECT_SIDECAR", path)


def _app_match() -> dict:
    return {
        "match_id": "paul-bublik",
        "p1": "Tommy Paul",
        "p2": "Alexander Bublik",
        "scheduled_time": "2026-09-04T16:30:00Z",
    }


def _assert_no_operator_price_fields(value) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            assert not str(key).startswith("operator_price")
            _assert_no_operator_price_fields(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_operator_price_fields(child)


def test_direct_fallback_adds_price_free_fixture_only_when_current_provider_missing(monkeypatch, tmp_path):
    now = datetime(2026, 9, 4, 16, 30, tzinfo=timezone.utc)
    _write_sidecar(monkeypatch, tmp_path, _direct_sidecar(now))
    availability = {
        "generated_at": now.isoformat(),
        "refresh_status": "OK",
        "fixtures": [],
        "contains_prices": False,
        "prices_used": False,
    }

    merged = context._overlay_direct_fallback([_app_match()], availability, now=now)

    assert len(merged["fixtures"]) == 1
    fixture = merged["fixtures"][0]
    assert fixture["fixture_id"] == "14809301"
    assert fixture["p1"] == "Tommy Paul"
    assert fixture["p2"] == "Alexander Bublik"
    assert fixture["operator_offer_source"] == context.DIRECT_SOURCE
    assert fixture["direct_source"] is True
    assert fixture["prices_used"] is False
    assert len(fixture["canonical_selections"]) == 2
    assert {row["line"] for row in fixture["canonical_selections"]} == {38.5}
    assert {row["pick"] for row in fixture["canonical_selections"]} == {"over", "under"}
    assert all(row["operator_line_source"] == context.DIRECT_SOURCE for row in fixture["canonical_selections"])
    _assert_no_operator_price_fields(fixture)

    diag = merged["direct_fallback"]
    assert diag["fallback_fixtures_added"] == 1
    assert diag["existing_provider_preferred"] == 0
    assert diag["unsafe_sidecar_matches_rejected"] == 0
    assert diag["prices_in_canonical_availability"] is False
    assert diag["prices_used"] is False
    assert diag["canonical_context_activation"] is True
    assert diag["downstream_playable_eligibility"] is True
    assert diag["model_math_unchanged"] is True
    assert merged["contains_prices"] is False
    assert merged["prices_used"] is False


def test_existing_current_provider_fixture_wins_over_direct(monkeypatch, tmp_path):
    now = datetime(2026, 9, 4, 16, 30, tzinfo=timezone.utc)
    _write_sidecar(monkeypatch, tmp_path, _direct_sidecar(now))
    existing = {
        "fixture_id": "oddspapi-current",
        "p1": "Alexander Bublik",
        "p2": "Tommy Paul",
        "start_time": "2026-09-04T16:30:00Z",
        "suspended": False,
        "canonical_selections": [
            {
                "market": "match_total",
                "pick": "over",
                "line": 39.5,
                "operator_available": True,
                "operator_line_verified": True,
                "fixture_line_verified": True,
            }
        ],
    }
    availability = {
        "generated_at": now.isoformat(),
        "refresh_status": "OK",
        "fixtures": [existing],
        "contains_prices": False,
        "prices_used": False,
    }

    merged = context._overlay_direct_fallback([_app_match()], availability, now=now)

    assert len(merged["fixtures"]) == 1
    assert merged["fixtures"][0]["fixture_id"] == "oddspapi-current"
    assert merged["direct_fallback"]["fallback_fixtures_added"] == 0
    assert merged["direct_fallback"]["existing_provider_preferred"] == 1
    assert merged["direct_fallback"]["canonical_context_activation"] is False
    assert merged["direct_fallback"]["downstream_playable_eligibility"] is False


def test_stale_or_unsafe_direct_sidecar_never_enters_canonical_availability(monkeypatch, tmp_path):
    now = datetime(2026, 9, 4, 16, 30, tzinfo=timezone.utc)

    stale = _direct_sidecar(now - timedelta(hours=context.DIRECT_MAX_AGE_HOURS + 0.1))
    _write_sidecar(monkeypatch, tmp_path, stale)
    merged = context._overlay_direct_fallback(
        [_app_match()],
        {"generated_at": now.isoformat(), "fixtures": [], "prices_used": False},
        now=now,
    )
    assert merged["fixtures"] == []
    assert merged["direct_fallback"]["fallback_fixtures_added"] == 0

    unsafe = _direct_sidecar(now, prices_used=True)
    _write_sidecar(monkeypatch, tmp_path, unsafe)
    merged = context._overlay_direct_fallback(
        [_app_match()],
        {"generated_at": now.isoformat(), "fixtures": [], "prices_used": False},
        now=now,
    )
    assert merged["fixtures"] == []
    assert merged["direct_fallback"]["fallback_fixtures_added"] == 0


def test_direct_fallback_flows_through_existing_prepare_and_playable_contract(monkeypatch, tmp_path):
    now = datetime(2026, 9, 4, 16, 30, tzinfo=timezone.utc)
    _write_sidecar(monkeypatch, tmp_path, _direct_sidecar(now))
    availability = context._overlay_direct_fallback(
        [_app_match()],
        {
            "generated_at": now.isoformat(),
            "refresh_status": "OK",
            "fixtures": [],
            "contains_prices": False,
            "prices_used": False,
        },
        now=now,
    )

    prepared, matched = core.prepare_results([_app_match()], availability, now=now)
    assert matched == 1
    ctx = prepared[0]["superbet_market_v91"]
    assert ctx["status"] == "VERIFIED"
    assert ctx["operator_verified"] is True
    assert ctx["fixture_id"] == "14809301"
    assert ctx["operator_offer_source"] == context.DIRECT_SOURCE
    assert ctx["prices_used"] is False
    assert len(ctx["canonical_selections"]) == 2
    assert all(row["operator_line_source"] == context.DIRECT_SOURCE for row in ctx["canonical_selections"])
    _assert_no_operator_price_fields(ctx)

    original = core._model_probability
    core._model_probability = lambda match, selection: (0.72, "test_probability")
    try:
        finalized, ready, signals = core.finalize_results(prepared)
    finally:
        core._model_probability = original
    assert ready == 1
    assert signals == 2
    model_signals = finalized[0]["superbet_market_v91"]["model_signals"]
    assert all(row["operator_line_source"] == context.DIRECT_SOURCE for row in model_signals)
    assert all(row["operator_offer_source"] == context.DIRECT_SOURCE for row in model_signals)
    assert finalized[0]["superbet_market_v91"]["prices_used"] is False


def test_main_workflow_refreshes_direct_before_superbet_prepare():
    workflow = Path(".github/workflows/update-and-pages.yml").read_text(encoding="utf-8")
    direct_pos = workflow.index("Superbet Direct selected-match SHADOW sidecar")
    prepare_pos = workflow.index("Superbet Market Availability PREPARE")
    finalize_pos = workflow.index("Superbet Market Context FINALIZE")
    assert direct_pos < prepare_pos < finalize_pos
    assert workflow.count("Superbet Direct selected-match SHADOW sidecar") == 1



def test_hourly_workflow_guards_direct_fallback_activation():
    workflow = Path(".github/workflows/superbet-market-refresh.yml").read_text(encoding="utf-8")
    assert "SUPERBET_DIRECT_FALLBACK_DIAGNOSTIC" in workflow
    assert "prices_in_canonical_availability" in workflow
    assert "canonical_context_activation" in workflow
    assert "downstream_playable_eligibility" in workflow
    assert "model_math_unchanged" in workflow
    direct_refresh = workflow.index("Refresh Superbet Direct selected-match sidecar")
    canonical_refresh = workflow.index("Refresh real Superbet catalogue + map audited families")
    assert direct_refresh < canonical_refresh
    assert "backend/superbet_direct.py" in workflow
    assert "tests/test_superbet_direct.py" in workflow



def test_malformed_direct_handicap_variant_is_suppressed_before_canonical_context():
    now = datetime(2026, 9, 4, 16, 30, tzinfo=timezone.utc)
    sidecar = _direct_sidecar(now)
    match = sidecar["matches"][0]
    match["canonical_selections"].extend([
        {
            "market": "match_game_handicap",
            "pick": "Tommy Paul",
            "player": "Tommy Paul",
            "line": 7.5,
            "set_no": None,
            "operator_available": True,
            "operator_line_verified": True,
            "fixture_line_verified": True,
            "operator_market_id": 520,
            "operator_outcome_id": 1327,
            "operator_special_bet_value": "7.5",
            "operator_specifiers": {"hcp": "7.5"},
            "prices_used": False,
        },
        {
            "market": "match_game_handicap",
            "pick": "Alexander Bublik",
            "player": "Alexander Bublik",
            "line": 7.5,
            "set_no": None,
            "operator_available": True,
            "operator_line_verified": True,
            "fixture_line_verified": True,
            "operator_market_id": 520,
            "operator_outcome_id": 1328,
            "operator_special_bet_value": "7.5",
            "operator_specifiers": {"hcp": "7.5"},
            "prices_used": False,
        },
    ])

    fixture = context._direct_fixture_from_sidecar(match)

    assert fixture is not None
    assert fixture["direct_handicap_semantics_guard"] is True
    assert fixture["suppressed_direct_handicap_variants"] == 1
    assert all(
        row["market"] != "match_game_handicap"
        for row in fixture["canonical_selections"]
    )
    assert {row["market"] for row in fixture["canonical_selections"]} == {"match_total"}
