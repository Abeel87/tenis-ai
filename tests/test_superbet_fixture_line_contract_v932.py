from backend import superbet_market_context_v924 as ctx


def _meta(catalogue_line=15.5):
    return {
        "13000": {
            "marketName": "Total Games Over Under",
            "marketType": "total-games",
            "handicap": catalogue_line,
            "outcomes": {
                "13000": {"outcomeName": "Over"},
                "13001": {"outcomeName": "Under"},
            },
        }
    }


def _row(bookmaker_market_id="fixture-total-18.5", over_id="sb-over-18.5", under_id="sb-under-18.5"):
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
                            "13000": {"players": {"0": {"active": True, "bookmakerOutcomeId": over_id, "mainLine": True}}},
                            "13001": {"players": {"0": {"active": True, "bookmakerOutcomeId": under_id, "mainLine": True}}},
                        },
                    }
                },
            }
        },
    }


def test_current_fixture_line_overrides_stale_catalogue_line():
    out = ctx.mapped_sanitize(_row(), _meta(15.5))
    assert out is not None
    selections = out["canonical_selections"]
    assert {(x["pick"], x["line"]) for x in selections} == {("over", 18.5), ("under", 18.5)}
    assert {x["operator_line_source"] for x in selections} == {"oddspapi_fixture_text_line"}
    assert all(x["fixture_line_verified"] is True for x in selections)


def test_opaque_fixture_does_not_fall_back_to_catalogue_line():
    out = ctx.mapped_sanitize(
        _row(bookmaker_market_id="opaque", over_id="opaque-over", under_id="opaque-under"),
        _meta(22.5),
    )
    assert out is not None
    assert out["canonical_selections"] == []
    assert out["suppressed_line_selections_without_fixture_evidence"] == 2


def test_structured_current_fixture_line_is_authoritative():
    row = _row(bookmaker_market_id="fixture-total-18.5")
    row["bookmakerOdds"]["superbet.pl"]["markets"]["13000"]["line"] = 20.5
    out = ctx.mapped_sanitize(row, _meta(15.5))
    assert out is not None
    selections = out["canonical_selections"]
    assert {(x["pick"], x["line"]) for x in selections} == {("over", 20.5), ("under", 20.5)}
    assert {x["operator_line_source"] for x in selections} == {"oddspapi_fixture_market_line"}


def test_strict_contract_forbids_non_fixture_fallbacks():
    assert ctx.STRICT_FIXTURE_LINE_VERSION == "v9.3.2-core"
    source = open(ctx.__file__, encoding="utf-8").read()
    assert '"catalogue_fallback_allowed": False' in source
    assert '"model_line_fallback_allowed": False' in source
    assert '"nearest_line_fallback_allowed": False' in source
