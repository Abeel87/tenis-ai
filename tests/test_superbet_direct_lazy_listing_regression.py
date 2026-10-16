from backend import superbet_direct as direct


def test_browser_scanner_collects_network_catalogue_and_incremental_dom(monkeypatch):
    class Driver:
        def execute_script(self, script):
            assert "scrollBy" in script
            return [1000, 1000, 1000]
    calls = []
    url = "https://superbet.pl/kursy/tenis/one-player-vs-two-player-12345678"
    monkeypatch.setattr(direct, "_collect_dom_urls", lambda d: [])
    monkeypatch.setattr(direct, "_drain_public_listing_json", lambda d: calls.append(1) or [url])
    monkeypatch.setattr(direct.time, "sleep", lambda _: None)
    urls, diag = direct._collect_listing_urls(Driver())
    assert urls == [url]
    assert len(calls) > 1
    assert diag["network_event_urls_found"] == 1


def test_selected_feed_reports_all_eligible_matches_beyond_legacy_64(monkeypatch):
    monkeypatch.setattr(direct, "candidate_event_urls", lambda *a, **k: [1])
    monkeypatch.setattr(direct, "resolve_selected_match_offer", lambda *a, **k: {
        "status": "NO_SAFE_DIRECT_MATCH", "reason": "EVENT_FETCH_FAILED"})
    rows = [{"id": str(i), "p1": "One Player", "p2": "Two Player", "scheduled_time": "2026-10-16T10:00:00Z"} for i in range(75)]
    feed = direct.build_selected_direct_feed(rows, [])
    assert feed["candidate_app_matches"] == 75
    assert len(feed["match_diagnostics"]) == 75
    assert feed["coverage"]["event_request_budget"] == 512
