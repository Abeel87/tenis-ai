from __future__ import annotations

import json
from datetime import datetime, timezone

from backend import market_lab_v741 as lab
from backend.superbet_market_context_v91 import (
    _sanitize_fixture,
    canonical_market,
    finalize_results,
    prepare_results,
)


def test_canonical_superbet_market_mapping():
    assert canonical_market("Total Games Over Under") == ("match_total", None, None)
    assert canonical_market("Correct Score First Set After Six Games") == ("game_state", 6, None)
    assert canonical_market("Participant 1 Total Games") == ("player_total_games", None, "p1")
    assert canonical_market("Total Aces") == ("match_total_aces", None, None)


def test_sanitize_fixture_keeps_lines_but_discards_prices():
    meta = {
        "1229": {
            "marketName": "Total Games Over Under",
            "outcomes": {
                "o": {"outcomeName": "Over"},
                "u": {"outcomeName": "Under"},
            },
        }
    }
    row = {
        "fixtureId": "f1",
        "participant1Name": "Alpha",
        "participant2Name": "Beta",
        "startTime": "2026-08-28T15:00:00Z",
        "tournamentName": "US Open",
        "tournamentId": 1,
        "bookmakerOdds": {
            "superbet.pl": {
                "markets": {
                    "1229": {
                        "marketActive": True,
                        "outcomes": {
                            "o": {"players": {"0": {"active": True, "bookmakerOutcomeId": "20.5/over", "price": 1.8}}},
                            "u": {"players": {"0": {"active": True, "bookmakerOutcomeId": "20.5/under", "price": 2.0}}},
                        },
                    }
                }
            }
        },
    }
    out = _sanitize_fixture(row, meta)
    assert out is not None
    assert {x["line"] for x in out["canonical_selections"]} == {20.5}
    assert {x["pick"] for x in out["canonical_selections"]} == {"over", "under"}
    assert "price" not in json.dumps(out).casefold()


def test_prepare_matches_names_independent_of_order_and_punctuation():
    results = [{"p1": "O'Connell, Christopher", "p2": "Piros, Zsombor", "scheduled_time": "2026-08-28T15:00:00Z"}]
    availability = {
        "generated_at": "2026-08-28T14:00:00Z",
        "fixtures": [{
            "fixture_id": "f2",
            "p1": "Piros Zsombor",
            "p2": "Christopher O Connell",
            "start_time": "2026-08-28T15:00:00Z",
            "suspended": False,
            "canonical_selections": [{
                "market": "match_total", "pick": "over", "line": 22.5,
                "operator_available": True, "operator_line_verified": True,
            }],
        }],
    }
    prepared, matched = prepare_results(results, availability, now=datetime(2026, 8, 28, 15, tzinfo=timezone.utc))
    assert matched == 1
    ctx = prepared[0]["superbet_market_v91"]
    assert ctx["status"] == "VERIFIED"
    assert ctx["operator_verified"] is True
    assert ctx["canonical_markets"]["match_total"]["lines"] == [22.5]


def _simple_match_with_operator_lines():
    return {
        "p1": "Alpha",
        "p2": "Beta",
        "model_ready": True,
        "best_of": 3,
        "service_model": {"p1_hold": 78.0, "p2_hold": 74.0},
        "exact_first_set": {
            "6:3": 25.0, "6:4": 25.0, "7:5": 15.0, "7:6": 10.0,
            "3:6": 10.0, "4:6": 8.0, "5:7": 4.0, "6:7": 3.0,
        },
        "second_set_win": {"Alpha": 55.0, "Beta": 45.0},
        "third_set_win": {"Alpha": 56.0, "Beta": 44.0},
        "superbet_market_v91": {
            "status": "VERIFIED",
            "operator_verified": True,
            "canonical_selections": [
                {"market": "set1_total", "pick": "over", "line": 9.5, "operator_available": True},
                {"market": "set1_total", "pick": "under", "line": 9.5, "operator_available": True},
                {"market": "match_total", "pick": "over", "line": 21.5, "operator_available": True},
                {"market": "match_total", "pick": "under", "line": 21.5, "operator_available": True},
            ],
        },
    }


def test_market_lab_uses_real_operator_lines():
    out = lab.enrich(_simple_match_with_operator_lines())
    block = out["market_lab_v741"]
    assert set(block["set1_total"]) == {"9.5"}
    assert set(block["match_total"]) == {"21.5"}
    assert block["operator_market_context"]["used"] is True
    assert block["operator_market_context"]["prices_used"] is False


def test_finalize_builds_verified_model_signal_from_real_line():
    match = _simple_match_with_operator_lines()
    match["match_win"] = {"Alpha": 61.0, "Beta": 39.0}
    match["superbet_market_v91"]["canonical_selections"].append({
        "market": "match_winner", "pick": "Alpha", "line": None,
        "operator_available": True, "operator_line_verified": True,
        "market_id": "121", "outcome_id": "1",
    })
    match = lab.enrich(match)
    rows, ready, signals = finalize_results([match])
    assert ready == 1
    assert signals > 0
    winner = next(x for x in rows[0]["superbet_market_v91"]["model_signals"] if x["market"] == "match_winner" and x["pick"] == "Alpha")
    assert winner["score"] == 61.0
    assert winner["operator_line_verified"] is True


def test_prepare_expiry_metadata_and_future_timestamp_fail_closed(monkeypatch):
    from backend import superbet_market_context_v91 as market
    from datetime import timedelta

    monkeypatch.setattr(market, 'REFRESH_HOURS', 1)
    start = datetime(2026, 8, 28, 11, tzinfo=timezone.utc)
    matches = [{'p1': 'Alpha', 'p2': 'Beta', 'scheduled_time': '2026-08-28T15:00:00Z'}]
    availability = {'generated_at': start.isoformat(), 'fixtures': [{
        'fixture_id': 'test', 'p1': 'Alpha', 'p2': 'Beta',
        'start_time': matches[0]['scheduled_time'], 'canonical_selections': []
    }]}
    for minutes, expected in [(-1, False), (0, True), (108, True), (109, False)]:
        prepared, _ = market.prepare_results(matches, availability, start + timedelta(minutes=minutes))
        ctx = prepared[0]['superbet_market_v91']
        assert ctx['operator_verified'] is expected
        assert ctx['source_max_age_hours'] == 1.8
    assert 'superbet_market_v91' not in matches[0]
