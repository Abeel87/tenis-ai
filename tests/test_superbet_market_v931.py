from backend import superbet_market_context_v931 as v931


def _row(bookmaker_market_id="fixture-total-18.5", outcome_over="sb-over-18.5", outcome_under="sb-under-18.5"):
    return {
        "fixtureId": "fixture-1",
        "participant1Name": "Alpha",
        "participant2Name": "Beta",
        "startTime": "2026-08-30T18:00:00Z",
        "bookmakerOdds": {
            "superbet.pl": {
                "bookmakerIsActive": True,
                "suspended": False,
                "markets": {
                    "13000": {
                        "bookmakerMarketId": bookmaker_market_id,
                        "marketActive": True,
                        "outcomes": {
                            "13000": {"players": {"0": {"active": True, "bookmakerOutcomeId": outcome_over, "mainLine": True}}},
                            "13001": {"players": {"0": {"active": True, "bookmakerOutcomeId": outcome_under, "mainLine": True}}},
                        },
                    }
                },
            }
        },
    }


def _meta(catalogue_line=15.5, over_name="Over", under_name="Under"):
    return {
        "13000": {
            "marketName": "Total Games Over Under",
            "marketType": "total-games",
            "handicap": catalogue_line,
            "outcomes": {
                "13000": {"outcomeName": over_name},
                "13001": {"outcomeName": under_name},
            },
        }
    }


def test_fixture_total_line_overrides_stale_catalogue_handicap():
    out = v931._sanitize_fixture(_row(), _meta(15.5))
    assert out is not None
    selections = out["canonical_selections"]
    assert {(x["pick"], x["line"]) for x in selections} == {("over", 18.5), ("under", 18.5)}
    assert {x["operator_line_source"] for x in selections} == {"oddspapi_fixture_text_line"}


def test_opaque_fixture_ids_fall_back_to_catalogue_line():
    out = v931._sanitize_fixture(
        _row(bookmaker_market_id="opaque", outcome_over="opaque-over", outcome_under="opaque-under"),
        _meta(22.5),
    )
    assert out is not None
    selections = out["canonical_selections"]
    assert {(x["pick"], x["line"]) for x in selections} == {("over", 22.5), ("under", 22.5)}
    assert {x["operator_line_source"] for x in selections} == {"oddspapi_market_handicap_fallback"}


def test_structured_fixture_line_beats_both_text_and_catalogue():
    row = _row(bookmaker_market_id="fixture-total-18.5")
    market = row["bookmakerOdds"]["superbet.pl"]["markets"]["13000"]
    market["line"] = 20.5
    out = v931._sanitize_fixture(row, _meta(15.5))
    assert out is not None
    selections = out["canonical_selections"]
    assert {(x["pick"], x["line"]) for x in selections} == {("over", 20.5), ("under", 20.5)}
    assert {x["operator_line_source"] for x in selections} == {"oddspapi_fixture_line"}
