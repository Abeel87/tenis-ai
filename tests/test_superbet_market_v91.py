from __future__ import annotations

import json
from datetime import datetime, timezone

from backend import market_lab_v741 as lab
from backend.superbet_market_core import (
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
    assert canonical_market("Winner Second Set") == ("set2_winner", None, None)
    assert canonical_market("Winner Third Set") == ("set3_winner", None, None)
    assert canonical_market("Total Games Third Set") == ("set3_total", None, None)


def test_sanitize_fixture_keeps_lines_but_discards_prices():
    raw = {
        "id": 42,
        "participants": [
            {"name": "Player A", "id": 1},
            {"name": "Player B", "id": 2},
        ],
        "startTime": "2026-08-30T10:00:00Z",
        "tournamentId": 7,
        "markets": [
            {
                "name": "Total Games",
                "selections": [
                    {"name": "Over 22.5", "line": 22.5, "price": 1.8, "odds": 1.8},
                ],
            }
        ],
    }
    clean = _sanitize_fixture(raw)
    text = json.dumps(clean)
    assert "22.5" in text
    assert "price" not in text.lower()
    assert "odds" not in text.lower()


def test_prepare_results_marks_unverified_matches_without_overwriting_models():
    match = {
        "id": 1,
        "p1": "Player A",
        "p2": "Player B",
        "date": "2026-08-30T10:00:00Z",
        "over_under": {"8.5": {"over": 70.0, "under": 30.0}},
    }
    out, meta = prepare_results([match], {"fixtures": []})
    assert out[0]["over_under"] == match["over_under"]
    assert out[0]["superbet_market_v91"]["operator_verified"] is False
    assert meta["verified_matches"] == 0


def test_finalize_results_evaluates_verified_real_line_without_changing_raw_model_data():
    match = {
        "id": 1,
        "p1": "Player A",
        "p2": "Player B",
        "date": "2026-08-30T10:00:00Z",
        "match_over_under": {"22.5": {"over": 73.0, "under": 27.0}},
        "superbet_market_v91": {
            "operator_verified": True,
            "status": "VERIFIED",
            "canonical_selections": [
                {
                    "market": "match_total",
                    "pick": "over",
                    "line": 22.5,
                    "operator_available": True,
                    "operator_line_verified": True,
                }
            ],
        },
    }
    original = json.loads(json.dumps(match["match_over_under"]))
    out, meta = finalize_results([match])
    assert out[0]["match_over_under"] == original
    rows = out[0]["superbet_market_v91"]["model_signals"]
    assert rows
    assert rows[0]["market"] == "match_total"
    assert rows[0]["line"] == 22.5
    assert meta["evaluated_signals"] >= 1


def test_prepare_results_rejects_stale_fixture_as_current_offer():
    now = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    match = {
        "id": 1,
        "p1": "Player A",
        "p2": "Player B",
        "date": "2026-08-30T12:30:00Z",
    }
    availability = {
        "generated_at": "2026-08-30T10:00:00Z",
        "fixtures": [
            {
                "id": 99,
                "participants": [{"name": "Player A"}, {"name": "Player B"}],
                "startTime": "2026-08-30T12:30:00Z",
                "markets": [],
            }
        ],
    }
    out, _ = prepare_results([match], availability, now=now)
    assert out[0]["superbet_market_v91"]["operator_verified"] is False


def test_market_lab_raw_generation_is_independent_of_operator_context():
    match = {
        "p1": "A",
        "p2": "B",
        "service_model": {"p1_hold": 70.0, "p2_hold": 70.0},
    }
    before = lab.generate_market_signals(match)
    match["superbet_market_v91"] = {"operator_verified": False, "canonical_selections": []}
    after = lab.generate_market_signals(match)
    assert before == after
