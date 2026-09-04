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
