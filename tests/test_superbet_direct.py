from backend import superbet_direct as direct


def test_discover_match_urls_is_tennis_only_and_deduplicated():
    html = """
    <html><body>
      <a href="/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301">match</a>
      <a href="https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301?x=1">dup</a>
      <a href="/kursy/pilka-nozna/a-vs-b-123">football</a>
      <a href="https://example.com/kursy/tenis/a-vs-b-123">external</a>
    </body></html>
    """
    assert direct.discover_match_urls(html) == [
        "https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301"
    ]

    hydrated = r'''
    <html><body><script>
      {"route":"\\/kursy\\/tenis\\/jiri-lehecka-vs-stefanos-tsitsipas-14809302"}
    </script></body></html>
    '''
    assert direct.discover_match_urls(hydrated) == [
        "https://superbet.pl/kursy/tenis/jiri-lehecka-vs-stefanos-tsitsipas-14809302"
    ]


def test_match_page_summary_requires_real_market_shape():
    market_block = """
      Zwycięzca Alexander Bublik wygra 2.75 Tommy Paul wygra 1.46
      Liczba gemów Poniżej 36.5 2.12 Powyżej 36.5 1.65
      Handicap Alexander Bublik -1.5 2.87 Tommy Paul +1.5 1.37
      Dokładny wynik 3:0 7.00 3:1 6.20 3:2 6.50
      Liczba setów 3.5 1.80 Tiebreak Nie 1.72
    """
    html = "<html><body>" + (f"<div>{market_block}</div>" * 30) + "</body></html>"
    summary = direct.summarize_match_page(
        html,
        "https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301",
    )
    assert summary["has_operator_market_evidence"] is True
    assert summary["market_marker_count"] >= 5
    assert summary["decimal_token_count"] >= 4


def test_probe_is_read_only_and_isolated(monkeypatch):
    listing = """
      <html><body>
        <a href="/kursy/tenis/a-vs-b-14809301">A vs B</a>
      </body></html>
    """
    market_block = """
      Zwycięzca A 1.55 B 2.30
      Liczba gemów Poniżej 22.5 1.90 Powyżej 22.5 1.90
      Handicap A -1.5 1.85 B +1.5 1.95
      Dokładny wynik 2:0 2.10 2:1 3.20 0:2 4.40
    """
    match = "<html><body>" + (f"<section>{market_block}</section>" * 40) + "</body></html>"

    def fake_fetch(url, timeout=25):
        if url == direct.TENNIS_LISTING_URL:
            return listing
        return match

    monkeypatch.setattr(direct, "fetch_html", fake_fetch)
    result = direct.probe()

    assert result["status"] == "OK"
    assert result["production_influence"] is False
    assert result["playable_influence"] is False
    assert result["player_dna_influence"] is False
    assert result["symphony_influence"] is False
    assert result["match_urls_found"] == 1


def test_fetch_rejects_non_superbet_url():
    try:
        direct.fetch_html("https://example.com/kursy/tenis/a-vs-b-123")
    except ValueError as exc:
        assert "Superbet PL tennis URLs" in str(exc)
    else:
        raise AssertionError("external URL was not rejected")



def test_parse_visible_offer_text_normalizes_unambiguous_core_markets():
    text = """
    Alexander Bublik wygra
    1
    2.75
    Tommy Paul wygra
    2
    1.46
    Poniżej 36.5 gemów w meczu
    Poniżej 36.5
    2.12
    Powyżej 36.5 gemów w meczu
    Powyżej 36.5
    1.65
    Poniżej 8.5 gemów w 1. secie
    Poniżej 8.5
    4.10
    Powyżej 8.5 gemów w 1. secie
    Powyżej 8.5
    1.20
    Mecz zakończy się wynikiem 3:0
    3:0
    7.00
    Alexander Bublik wygra 2.set przy uwzględnieniu podanego Handicapu gemów (-1.5)
    Alexander Bublik (-1.5)
    2.87
    Tommy Paul wygra 2.set przy uwzględnieniu podanego Handicapu gemów (1.5)
    Tommy Paul (1.5)
    1.37
    Alexander Bublik zdobędzie poniżej 4.5 gemów w 2.secie
    Poniżej 4.5
    2.07
    Alexander Bublik zdobędzie powyżej 4.5 gemów w 2.secie
    Powyżej 4.5
    1.69
    Alexander Bublik wygra mecz i poniżej 36.5 gemów w meczu
    1 & poniżej 36.5
    6.60
    """
    result = direct.parse_visible_offer_text(
        text,
        url="https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301",
        title="Alexander Bublik vs Tommy Paul: Kursy i Zakłady | Superbet",
    )

    assert result["event_id"] == "14809301"
    assert result["p1"] == "Alexander Bublik"
    assert result["p2"] == "Tommy Paul"
    assert result["prices_used"] is False
    assert result["production_influence"] is False
    assert result["playable_influence"] is False
    assert result["canonical_selections_count"] == 11

    rows = {
        (
            row["market"],
            row["pick"],
            row.get("line"),
            row.get("player"),
            row.get("set_no"),
        ): row
        for row in result["canonical_selections"]
    }
    assert rows[("match_winner", "Alexander Bublik", None, None, None)]["operator_price"] == 2.75
    assert rows[("match_winner", "Tommy Paul", None, None, None)]["operator_price"] == 1.46
    assert rows[("match_total", "under", 36.5, None, None)]["operator_price"] == 2.12
    assert rows[("match_total", "over", 36.5, None, None)]["operator_price"] == 1.65
    assert rows[("set1_total", "under", 8.5, None, 1)]["operator_price"] == 4.10
    assert rows[("set1_total", "over", 8.5, None, 1)]["operator_price"] == 1.20
    assert rows[("exact_match_score", "3:0", None, None, None)]["operator_price"] == 7.00
    assert rows[("set2_game_handicap", "Alexander Bublik", -1.5, "Alexander Bublik", 2)]["operator_price"] == 2.87
    assert rows[("set2_game_handicap", "Tommy Paul", 1.5, "Tommy Paul", 2)]["operator_price"] == 1.37
    assert rows[("player_total_games", "under", 4.5, "Alexander Bublik", 2)]["operator_price"] == 2.07
    assert rows[("player_total_games", "over", 4.5, "Alexander Bublik", 2)]["operator_price"] == 1.69

    assert rows[("match_total", "under", 36.5, None, None)]["operator_line_verified"] is True
    assert rows[("match_total", "under", 36.5, None, None)]["fixture_line_verified"] is True
    assert rows[("match_total", "under", 36.5, None, None)]["operator_price_verified"] is True
    assert "operator_line_verified" not in rows[("exact_match_score", "3:0", None, None, None)]


def test_parse_visible_offer_text_deduplicates_repeated_rendered_rows():
    block = """
    Poniżej 9.5 gemów w 1. secie
    Poniżej 9.5
    2.07
    Powyżej 9.5 gemów w 1. secie
    Powyżej 9.5
    1.69
    """
    result = direct.parse_visible_offer_text(
        block + block,
        url="https://superbet.pl/kursy/tenis/a-vs-b-12345678",
        title="A vs B: Kursy i Zakłady | Superbet",
    )
    assert result["canonical_selections_count"] == 2
    assert result["market_counts"] == {"set1_total": 2}


def test_browser_offer_rejects_listing_and_external_urls():
    bad = [
        "https://superbet.pl/zaklady-bukmacherskie/tenis",
        "https://example.com/kursy/tenis/a-vs-b-12345678",
    ]
    for url in bad:
        try:
            direct.browser_offer(url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"URL should be rejected: {url}")



def test_parse_visible_offer_text_reads_explicit_superbet_match_total_table():
    text = """
    Liczba gemów
    Gemy
    PONIŻEJ
    POWYŻEJ
    38.5
    2.10
    1.67
    39.5
    1.97
    1.76
    40.5
    1.83
    1.91
    Dokładny wynik
    """
    result = direct.parse_visible_offer_text(
        text,
        url="https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301",
        title="Alexander Bublik vs Tommy Paul: Kursy i Zakłady | Superbet",
    )
    rows = {
        (row["market"], row["pick"], row.get("line")): row
        for row in result["canonical_selections"]
    }
    assert result["canonical_selections_count"] == 6
    assert rows[("match_total", "under", 38.5)]["operator_price"] == 2.10
    assert rows[("match_total", "over", 38.5)]["operator_price"] == 1.67
    assert rows[("match_total", "under", 39.5)]["operator_price"] == 1.97
    assert rows[("match_total", "over", 40.5)]["operator_price"] == 1.91
    assert all(row["operator_line_verified"] is True for row in rows.values())
    assert all(row["prices_used"] is False for row in rows.values())


def test_parse_visible_offer_text_reads_self_describing_total_sets_card():
    text = """
    150+ postawiło ten zakład
    Liczba setów - Powyżej 3.5
    1.47
    przejdź na początek
    """
    result = direct.parse_visible_offer_text(
        text,
        url="https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301",
        title="Alexander Bublik vs Tommy Paul: Kursy i Zakłady | Superbet",
    )
    assert result["canonical_selections_count"] == 1
    row = result["canonical_selections"][0]
    assert row["market"] == "total_sets"
    assert row["pick"] == "over"
    assert row["line"] == 3.5
    assert row["operator_price"] == 1.47
    assert row["prices_used"] is False



def test_parse_event_payload_uses_active_single_market_json_contract():
    payload = {
        "dataIn": {"eventId": 14809301, "lang": "pl-PL"},
        "data": [{
            "eventId": 14809301,
            "matchName": "Alexander Bublik·Tommy Paul",
            "utcDate": "2026-09-04T16:10:00Z",
            "marketCount": 83,
            "odds": [
                {
                    "uuid": "winner-p1", "marketId": 521, "outcomeId": 1329,
                    "price": 2.37, "status": "active", "code": "1",
                    "name": "1", "marketName": "Zwycięzca",
                    "info": "Alexander Bublik wygra",
                },
                {
                    "uuid": "winner-p2", "marketId": 521, "outcomeId": 1330,
                    "price": 1.60, "status": "active", "code": "2",
                    "name": "2", "marketName": "Zwycięzca",
                    "info": "Tommy Paul wygra",
                },
                {
                    "uuid": "set1-p1", "marketId": 523, "outcomeId": 1333,
                    "price": 2.15, "specialBetValue": "1", "status": "active",
                    "code": "1", "name": "1. set - Alexander Bublik",
                    "marketName": "X. set - zwycięzca", "info": "Wygra 1. seta",
                    "specifiers": {"setnr": "1"},
                },
                {
                    "uuid": "total-under", "marketId": 1002, "outcomeId": 4262,
                    "price": 2.37, "specialBetValue": "36.5", "status": "active",
                    "code": "-", "name": "Poniżej 36.5",
                    "marketName": "Liczba gemów",
                    "info": "Poniżej 36.5 gemów w meczu",
                    "specifiers": {"total": "36.5"},
                },
                {
                    "uuid": "total-over", "marketId": 1002, "outcomeId": 4263,
                    "price": 1.55, "specialBetValue": "36.5", "status": "active",
                    "code": "+", "name": "Powyżej 36.5",
                    "marketName": "Liczba gemów",
                    "info": "Powyżej 36.5 gemów w meczu",
                    "specifiers": {"total": "36.5"},
                },
                {
                    "uuid": "sets-over", "marketId": 2001, "outcomeId": 5001,
                    "price": 1.47, "specialBetValue": "3.5", "status": "active",
                    "name": "Powyżej 3.5", "marketName": "Liczba setów",
                    "info": "Liczba setów - Powyżej 3.5",
                    "specifiers": {"total": "3.5"},
                },
                {
                    "uuid": "score-30", "marketId": 3001, "outcomeId": 6001,
                    "price": 7.00, "status": "active", "name": "3:0",
                    "marketName": "Dokładny wynik",
                    "info": "Mecz zakończy się wynikiem 3:0",
                },
                {
                    "uuid": "set1-total-under", "marketId": 4001, "outcomeId": 7001,
                    "price": 4.10, "specialBetValue": "8.5", "status": "active",
                    "name": "Poniżej 8.5", "marketName": "X. set - liczba gemów",
                    "info": "Poniżej 8.5 gemów w 1. secie",
                    "specifiers": {"setnr": "1", "total": "8.5"},
                },
                {
                    "uuid": "player-set2-over", "marketId": 4002, "outcomeId": 7002,
                    "price": 1.69, "specialBetValue": "4.5", "status": "active",
                    "name": "Powyżej 4.5",
                    "marketName": "X. set - liczba gemów zawodnika",
                    "info": "Alexander Bublik zdobędzie powyżej 4.5 gemów w 2. secie",
                    "specifiers": {"setnr": "2", "total": "4.5"},
                },
                {
                    "uuid": "set2-hcp", "marketId": 4003, "outcomeId": 7003,
                    "price": 2.87, "specialBetValue": "-1.5", "status": "active",
                    "name": "Alexander Bublik (-1.5)",
                    "marketName": "X. set - handicap gemów",
                    "info": "Alexander Bublik wygra 2. set przy uwzględnieniu podanego Handicapu gemów (-1.5)",
                    "specifiers": {"setnr": "2", "handicap": "-1.5"},
                },
                {
                    "uuid": "combo", "marketId": direct.COMBINATION_MARKET_ID,
                    "outcomeId": 16603, "price": 1.80, "status": "active",
                    "marketName": "Liczba gemów: powyżej 39.5; 1. set - powyżej 7.5 gemów",
                    "name": "Liczba gemów: powyżej 39.5; 1. set - powyżej 7.5 gemów",
                    "info": "",
                },
                {
                    "uuid": "inactive", "marketId": 1002, "outcomeId": 9999,
                    "price": 9.99, "specialBetValue": "99.5", "status": "inactive",
                    "name": "Powyżej 99.5", "marketName": "Liczba gemów",
                    "info": "Powyżej 99.5 gemów w meczu",
                },
            ],
        }],
        "error": None,
    }

    result = direct.parse_event_payload(
        payload,
        event_id="14809301",
        url="https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301",
    )

    assert result["status"] == "OK"
    assert result["source"] == "PUBLIC_EVENT_JSON"
    assert result["event_id"] == "14809301"
    assert result["p1"] == "Alexander Bublik"
    assert result["p2"] == "Tommy Paul"
    assert result["start_time"] == "2026-09-04T16:10:00Z"
    assert result["odds_rows_seen"] == 12
    assert result["active_odds_rows_seen"] == 11
    assert result["combination_rows_skipped"] == 1
    assert result["canonical_selections_count"] == 10
    assert result["prices_used"] is False
    assert result["production_influence"] is False
    assert result["playable_influence"] is False

    rows = {
        (
            row["market"],
            row["pick"],
            row.get("line"),
            row.get("player"),
            row.get("set_no"),
        ): row
        for row in result["canonical_selections"]
    }
    assert rows[("match_winner", "Alexander Bublik", None, None, None)]["operator_price"] == 2.37
    assert rows[("set1_winner", "Alexander Bublik", None, None, 1)]["operator_price"] == 2.15
    assert rows[("match_total", "under", 36.5, None, None)]["operator_price"] == 2.37
    assert rows[("match_total", "over", 36.5, None, None)]["operator_price"] == 1.55
    assert rows[("total_sets", "over", 3.5, None, None)]["operator_price"] == 1.47
    assert rows[("exact_match_score", "3:0", None, None, None)]["operator_price"] == 7.0
    assert rows[("set1_total", "under", 8.5, None, 1)]["operator_price"] == 4.10
    assert rows[("player_total_games", "over", 4.5, "Alexander Bublik", 2)]["operator_price"] == 1.69
    assert rows[("set2_game_handicap", "Alexander Bublik", -1.5, "Alexander Bublik", 2)]["operator_price"] == 2.87

    line_row = rows[("match_total", "under", 36.5, None, None)]
    assert line_row["operator_line_verified"] is True
    assert line_row["fixture_line_verified"] is True
    assert line_row["operator_line_source"] == direct.EVENT_JSON_SOURCE
    assert line_row["operator_price_source"] == direct.EVENT_JSON_SOURCE
    assert line_row["operator_market_id"] == 1002
    assert line_row["operator_selection_status"] == "active"


def test_parse_event_payload_fails_closed_for_wrong_event():
    payload = {"data": [{"eventId": 123, "matchName": "A·B", "odds": []}]}
    result = direct.parse_event_payload(payload, event_id="999")
    assert result["status"] == "EVENT_NOT_FOUND"
    assert result["canonical_selections"] == []
    assert result["prices_used"] is False



def _direct_event_payload(event_id, p1, p2, start_time, score="2:0"):
    return {
        "data": [{
            "eventId": int(event_id),
            "matchName": f"{p1}·{p2}",
            "utcDate": start_time,
            "marketCount": 2,
            "odds": [
                {
                    "uuid": f"{event_id}-w1",
                    "marketId": 521,
                    "outcomeId": 1329,
                    "price": 1.80,
                    "status": "active",
                    "code": "1",
                    "name": "1",
                    "marketName": "Zwycięzca",
                    "info": f"{p1} wygra",
                },
                {
                    "uuid": f"{event_id}-w2",
                    "marketId": 521,
                    "outcomeId": 1330,
                    "price": 2.00,
                    "status": "active",
                    "code": "2",
                    "name": "2",
                    "marketName": "Zwycięzca",
                    "info": f"{p2} wygra",
                },
                {
                    "uuid": f"{event_id}-score",
                    "marketId": 3001,
                    "outcomeId": 6001,
                    "price": 4.20,
                    "status": "active",
                    "name": score,
                    "marketName": "Dokładny wynik",
                    "info": f"Mecz zakończy się wynikiem {score}",
                },
            ],
        }]
    }


def test_candidate_event_urls_shortlists_by_canonical_player_matcher():
    urls = [
        "https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301",
        "https://superbet.pl/kursy/tenis/jiri-lehecka-vs-stefanos-tsitsipas-14809302",
        "https://superbet.pl/kursy/tenis/tommy-paul-vs-alexander-bublik-14809303",
    ]
    match = {
        "p1": "A. Bublik",
        "p2": "Tommy Paul",
        "scheduled_time": "2026-09-04T16:10:00Z",
    }
    candidates = direct.candidate_event_urls(match, urls)
    assert [row["event_id"] for row in candidates] == ["14809301", "14809303"]


def test_resolve_selected_match_offer_requires_names_and_time_and_orients_scores():
    urls = [
        "https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301",
        "https://superbet.pl/kursy/tenis/jiri-lehecka-vs-stefanos-tsitsipas-14809302",
    ]
    payloads = {
        "14809301": _direct_event_payload(
            "14809301",
            "Alexander Bublik",
            "Tommy Paul",
            "2026-09-04T16:10:00Z",
            score="3:1",
        ),
    }

    match = {
        "match_id": 777,
        "p1": "Tommy Paul",
        "p2": "Alexander Bublik",
        "scheduled_time": "2026-09-04T16:10:00Z",
    }
    result = direct.resolve_selected_match_offer(
        match,
        urls,
        fetcher=lambda event_id: payloads[event_id],
    )

    assert result["status"] == "OK"
    assert result["direct_match_verified"] is True
    assert result["event_id"] == "14809301"
    assert result["p1"] == "Tommy Paul"
    assert result["p2"] == "Alexander Bublik"
    assert result["participant_order_reoriented"] is True
    assert result["prices_used"] is False
    assert result["production_influence"] is False
    assert result["playable_influence"] is False

    score_rows = [
        row for row in result["canonical_selections"]
        if row["market"] == "exact_match_score"
    ]
    assert len(score_rows) == 1
    assert score_rows[0]["pick"] == "1:3"


def test_resolve_selected_match_offer_rejects_ambiguous_nearby_events():
    urls = [
        "https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301",
        "https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809309",
    ]
    payloads = {
        "14809301": _direct_event_payload(
            "14809301", "Alexander Bublik", "Tommy Paul", "2026-09-04T16:10:00Z"
        ),
        "14809309": _direct_event_payload(
            "14809309", "Alexander Bublik", "Tommy Paul", "2026-09-04T16:15:00Z"
        ),
    }
    match = {
        "match_id": 778,
        "p1": "Alexander Bublik",
        "p2": "Tommy Paul",
        "scheduled_time": "2026-09-04T16:12:00Z",
    }
    result = direct.resolve_selected_match_offer(
        match,
        urls,
        fetcher=lambda event_id: payloads[event_id],
    )
    assert result["status"] == "NO_SAFE_DIRECT_MATCH"
    assert result["direct_match_verified"] is False
    assert result["canonical_selections"] == []
    assert result["event_payloads_ok"] == 2


def test_resolve_selected_match_offer_rejects_wrong_time():
    urls = [
        "https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301",
    ]
    payload = _direct_event_payload(
        "14809301", "Alexander Bublik", "Tommy Paul", "2026-09-05T16:10:00Z"
    )
    match = {
        "p1": "Alexander Bublik",
        "p2": "Tommy Paul",
        "scheduled_time": "2026-09-04T16:10:00Z",
    }
    result = direct.resolve_selected_match_offer(
        match,
        urls,
        fetcher=lambda event_id: payload,
    )
    assert result["status"] == "NO_SAFE_DIRECT_MATCH"
    assert result["direct_match_verified"] is False


def test_pure_direct_matching_does_not_mutate_fixture_matching_telemetry():
    import copy

    before = copy.deepcopy(direct.fixture_matching._TELEMETRY)
    row = {
        "fixture_id": "14809301",
        "p1": "Alexander Bublik",
        "p2": "Tommy Paul",
        "start_time": "2026-09-04T16:10:00Z",
        "canonical_selections": [],
    }
    selected = direct.fixture_matching.select_cached_fixture(
        {
            "p1": "Alexander Bublik",
            "p2": "Tommy Paul",
            "scheduled_time": "2026-09-04T16:10:00Z",
        },
        [row],
    )
    assert selected["fixture_id"] == "14809301"
    assert direct.fixture_matching._TELEMETRY == before


def test_fetch_event_payload_public_rejects_non_numeric_event_id():
    try:
        direct.fetch_event_payload_public("../secret")
    except ValueError as exc:
        assert "numeric" in str(exc)
    else:
        raise AssertionError("non-numeric event id was not rejected")
