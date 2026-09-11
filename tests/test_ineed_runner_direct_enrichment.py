from backend import ineed_runner as runner


def test_event_urls_from_public_listing_payload_extracts_hidden_match():
    payload = {
        "data": {
            "groups": [
                {
                    "events": [
                        {
                            "eventId": 14999999,
                            "matchName": "Ilia Simakin · Max Purcell",
                            "utcDate": "2026-09-12T05:00:00Z",
                        }
                    ]
                }
            ]
        }
    }

    urls = runner.event_urls_from_payload(payload)

    assert urls == [
        "https://superbet.pl/kursy/tenis/ilia-simakin-vs-max-purcell-14999999"
    ]


def test_event_urls_prefers_concrete_superbet_tennis_url_and_deduplicates():
    event = {
        "eventId": "14999999",
        "matchName": "Ilia Simakin · Max Purcell",
        "eventUrl": "/kursy/tenis/ilia-simakin-vs-max-purcell-14999999",
    }
    payload = {"data": [event, {"nested": event}]}

    urls = runner.event_urls_from_payload(payload)

    assert urls == [
        "https://superbet.pl/kursy/tenis/ilia-simakin-vs-max-purcell-14999999"
    ]


def test_collect_dom_urls_uses_atomic_js_snapshot():
    class FakeDriver:
        page_source = ""

        def execute_script(self, script):
            assert "querySelectorAll" in script
            return [
                "https://superbet.pl/kursy/tenis/ilia-simakin-vs-max-purcell-14999999",
                "/kursy/tenis/ilia-simakin-vs-max-purcell-14999999",
                "https://example.com/kursy/tenis/not-allowed-12345",
            ]

        def find_elements(self, *_args, **_kwargs):
            raise AssertionError("WebElement fallback should not be used when JS snapshot succeeds")

    assert runner._collect_dom_urls(FakeDriver()) == [
        "https://superbet.pl/kursy/tenis/ilia-simakin-vs-max-purcell-14999999"
    ]


def test_refresh_direct_reuses_known_event_urls_and_adds_public_discovery(monkeypatch):
    old = {
        "status": "OK",
        "matches": [
            {
                "match_id": 189069,
                "event_url": "https://superbet.pl/kursy/tenis/alexander-zverev-vs-karen-khachanov-14917583",
            }
        ],
    }
    results = [
        {
            "match_id": 189069,
            "symphony2_playable": {
                "playable": True,
                "final_playable_authority": True,
                "authority": "SYMPHONY2_FINAL_PLAYABLE",
                "operator": "superbet.pl",
            },
        },
        {
            "match_id": 189354,
            "symphony2_playable": {
                "playable": True,
                "final_playable_authority": True,
                "authority": "SYMPHONY2_FINAL_PLAYABLE",
                "operator": "superbet.pl",
            },
        },
    ]
    discovered = [
        "https://superbet.pl/kursy/tenis/ilia-simakin-vs-max-purcell-14999999"
    ]
    captured = {}
    fresh = {
        "status": "OK",
        "candidate_app_matches": 2,
        "resolved_app_matches": 2,
        "matches": [{"match_id": 189069}, {"match_id": 189354}],
    }

    def fake_build(rows, urls, max_matches=64):
        captured["rows"] = rows
        captured["urls"] = urls
        captured["max_matches"] = max_matches
        return fresh

    monkeypatch.setattr(runner.superbet_direct, "build_selected_direct_feed", fake_build)

    feed, diag = runner.refresh_direct_for_ineed(
        results,
        old,
        discoverer=lambda: (discovered, {"status": "OK", "network_event_urls_found": 1}),
    )

    assert feed is fresh
    assert captured["urls"] == [
        "https://superbet.pl/kursy/tenis/alexander-zverev-vs-karen-khachanov-14917583",
        "https://superbet.pl/kursy/tenis/ilia-simakin-vs-max-purcell-14999999",
    ]
    assert captured["max_matches"] == 64
    assert diag["used_fresh_direct"] is True
    assert diag["fresh_resolved_matches"] == 2
    assert diag["status"] == "OK"


def test_refresh_direct_falls_back_to_fresh_seed_quotes_when_discovery_breaks(monkeypatch):
    old = {
        "status": "OK",
        "matches": [
            {
                "match_id": 189069,
                "event_url": "https://superbet.pl/kursy/tenis/alexander-zverev-vs-karen-khachanov-14917583",
            }
        ],
    }
    results = [
        {
            "match_id": 189069,
            "symphony2_playable": {
                "playable": True,
                "final_playable_authority": True,
                "authority": "SYMPHONY2_FINAL_PLAYABLE",
                "operator": "superbet.pl",
            },
        }
    ]
    fresh = {
        "status": "OK",
        "candidate_app_matches": 1,
        "resolved_app_matches": 1,
        "matches": [{"match_id": 189069}],
    }
    captured = {}

    def broken():
        raise RuntimeError("browser unavailable")

    def fake_build(rows, urls, max_matches=64):
        captured["urls"] = urls
        return fresh

    monkeypatch.setattr(runner.superbet_direct, "build_selected_direct_feed", fake_build)

    feed, diag = runner.refresh_direct_for_ineed(results, old, discoverer=broken)

    assert feed is fresh
    assert captured["urls"] == [
        "https://superbet.pl/kursy/tenis/alexander-zverev-vs-karen-khachanov-14917583"
    ]
    assert diag["status"] == "DEGRADED_SEED_REFRESH"
    assert diag["live_discovery_error"] == "RuntimeError"
    assert diag["used_fresh_direct"] is True


def test_refresh_direct_fails_closed_when_discovery_breaks_without_seed_urls():
    old = {"status": "OK", "matches": []}

    def broken():
        raise RuntimeError("browser unavailable")

    feed, diag = runner.refresh_direct_for_ineed(
        [
            {
                "match_id": 1,
                "symphony2_playable": {
                    "playable": True,
                    "final_playable_authority": True,
                    "authority": "SYMPHONY2_FINAL_PLAYABLE",
                    "operator": "superbet.pl",
                },
            }
        ],
        old,
        discoverer=broken,
    )

    assert feed is old
    assert diag["status"] == "LIVE_DISCOVERY_FAILED"
    assert diag["used_fresh_direct"] is False
