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
