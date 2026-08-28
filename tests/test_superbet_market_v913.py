from __future__ import annotations

from backend.superbet_market_context_v913 import (
    MAX_TOURNAMENT_IDS_PER_REQUEST,
    MONTHLY_REQUEST_CAP,
    REFRESH_HOURS,
    _sanitize_fixture,
    _tournament_ids,
    batched_request,
)


def test_paid_plan_refresh_policy_keeps_headroom():
    assert REFRESH_HOURS == 1
    assert MONTHLY_REQUEST_CAP == 4000
    assert MONTHLY_REQUEST_CAP < 5000


def test_tournament_id_normalization_dedupes_and_preserves_order():
    assert _tournament_ids("9,1,9, 3 ,") == ["9", "1", "3"]


def test_odds_by_tournaments_is_split_into_max_five_ids(monkeypatch):
    calls = []

    def fake_request(path, api_key, quota, **params):
        calls.append((path, params.get("tournamentIds")))
        ids = str(params.get("tournamentIds") or "").split(",")
        return [{"fixtureId": f"fixture-{x}"} for x in ids if x]

    monkeypatch.setattr("backend.superbet_market_context_v913.time.sleep", lambda _seconds: None)
    quota = {"requests_used_by_v91": 0, "monthly_cap": MONTHLY_REQUEST_CAP}
    out = batched_request(
        fake_request,
        "odds-by-tournaments",
        "key",
        quota,
        tournamentIds=",".join(str(x) for x in range(1, 13)),
        bookmakers="superbet.pl",
    )
    assert [batch for _path, batch in calls] == [
        "1,2,3,4,5",
        "6,7,8,9,10",
        "11,12",
    ]
    assert all(len(batch.split(",")) <= MAX_TOURNAMENT_IDS_PER_REQUEST for _path, batch in calls)
    assert len(out) == 12


def test_small_tournament_request_stays_single_call():
    calls = []

    def fake_request(path, api_key, quota, **params):
        calls.append(params.get("tournamentIds"))
        return {"fixtureId": "one"}

    result = batched_request(
        fake_request,
        "odds-by-tournaments",
        "key",
        {"requests_used_by_v91": 0, "monthly_cap": MONTHLY_REQUEST_CAP},
        tournamentIds="1,2,3,4,5",
    )
    assert calls == ["1,2,3,4,5"]
    assert result == {"fixtureId": "one"}


def test_sanitize_uses_market_catalogue_handicap_when_superbet_outcome_id_is_opaque():
    meta = {
        "13000": {
            "marketName": "Total Games Over Under",
            "marketType": "total-games",
            "handicap": 22.5,
            "outcomes": {
                "13000": {"outcomeName": "Over"},
                "13001": {"outcomeName": "Under"},
            },
        }
    }
    row = {
        "fixtureId": "f-total",
        "participant1Name": "Alpha",
        "participant2Name": "Beta",
        "startTime": "2026-08-28T18:00:00Z",
        "bookmakerOdds": {
            "superbet.pl": {
                "bookmakerIsActive": True,
                "suspended": False,
                "markets": {
                    "13000": {
                        "bookmakerMarketId": "opaque-market-id",
                        "marketActive": True,
                        "outcomes": {
                            "13000": {"players": {"0": {"active": True, "bookmakerOutcomeId": "opaque-over", "mainLine": True}}},
                            "13001": {"players": {"0": {"active": True, "bookmakerOutcomeId": "opaque-under", "mainLine": True}}},
                        },
                    }
                },
            }
        },
    }

    out = _sanitize_fixture(row, meta)
    assert out is not None
    selections = out["canonical_selections"]
    assert {(x["pick"], x["line"]) for x in selections} == {("over", 22.5), ("under", 22.5)}
    assert {x["operator_line_source"] for x in selections} == {"oddspapi_market_handicap"}


def test_sanitize_maps_catalogue_one_two_to_real_player_names_even_with_opaque_ids():
    meta = {
        "121": {
            "marketName": "Winner",
            "marketType": "twoway",
            "handicap": 0.0,
            "outcomes": {
                "121": {"outcomeName": "1"},
                "122": {"outcomeName": "2"},
            },
        }
    }
    row = {
        "fixtureId": "f-winner",
        "participant1Name": "Alpha",
        "participant2Name": "Beta",
        "startTime": "2026-08-28T18:00:00Z",
        "bookmakerOdds": {
            "superbet.pl": {
                "markets": {
                    "121": {
                        "marketActive": True,
                        "outcomes": {
                            "121": {"players": {"0": {"active": True, "bookmakerOutcomeId": "sb-928381", "mainLine": True}}},
                            "122": {"players": {"0": {"active": True, "bookmakerOutcomeId": "sb-928382", "mainLine": True}}},
                        },
                    }
                }
            }
        },
    }

    out = _sanitize_fixture(row, meta)
    assert out is not None
    selections = out["canonical_selections"]
    assert {(x["market"], x["pick"]) for x in selections} == {
        ("match_winner", "Alpha"),
        ("match_winner", "Beta"),
    }


def test_handicap_catalogue_line_is_p1_perspective_and_p2_gets_opposite_sign():
    meta = {
        "12175": {
            "marketName": "Game Handicap",
            "marketType": "handicap",
            "handicap": -3.5,
            "outcomes": {
                "12175": {"outcomeName": "1"},
                "12176": {"outcomeName": "2"},
            },
        },
        "12378": {
            "marketName": "Game Handicap First Set",
            "marketType": "handicap",
            "handicap": 1.5,
            "outcomes": {
                "12378": {"outcomeName": "1"},
                "12379": {"outcomeName": "2"},
            },
        },
        "12471": {
            "marketName": "Game Handicap Second Set",
            "marketType": "handicap",
            "handicap": -2.5,
            "outcomes": {
                "12471": {"outcomeName": "1"},
                "12472": {"outcomeName": "2"},
            },
        },
    }

    markets = {}
    for market_id, market_meta in meta.items():
        outcome_ids = list(market_meta["outcomes"])
        markets[market_id] = {
            "marketActive": True,
            "outcomes": {
                outcome_ids[0]: {"players": {"0": {"active": True, "bookmakerOutcomeId": f"opaque-{market_id}-1", "mainLine": True}}},
                outcome_ids[1]: {"players": {"0": {"active": True, "bookmakerOutcomeId": f"opaque-{market_id}-2", "mainLine": True}}},
            },
        }

    row = {
        "fixtureId": "f-handicap",
        "participant1Name": "Alpha",
        "participant2Name": "Beta",
        "startTime": "2026-08-28T18:00:00Z",
        "bookmakerOdds": {"superbet.pl": {"markets": markets}},
    }

    out = _sanitize_fixture(row, meta)
    assert out is not None
    got = {
        (selection["market"], selection["pick"]): selection["line"]
        for selection in out["canonical_selections"]
    }
    assert got[("match_game_handicap", "Alpha")] == -3.5
    assert got[("match_game_handicap", "Beta")] == 3.5
    assert got[("set1_game_handicap", "Alpha")] == 1.5
    assert got[("set1_game_handicap", "Beta")] == -1.5
    assert got[("set2_game_handicap", "Alpha")] == -2.5
    assert got[("set2_game_handicap", "Beta")] == 2.5
