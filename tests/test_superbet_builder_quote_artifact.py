from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from backend import superbet_builder_quotes as bq
from backend import superbet_direct as direct

NOW = datetime(2026, 9, 21, 14, 30, tzinfo=timezone.utc)


def direct_feed(status="OK"):
    return {
        "mode": "SHADOW_SUPERBET_DIRECT_SELECTED_MATCH_FEED",
        "status": status,
        "generated_at": "2026-09-21T14:29:00+00:00",
        "matches": [] if status != "OK" else [{
            "match_id": "m-1",
            "p1": "Alice",
            "p2": "Betty",
            "scheduled_time": "2026-09-21T16:00:00Z",
            "event_id": "15000001",
            "event_url": "https://superbet.pl/kursy/tenis/alice-vs-betty-15000001",
            "direct_match_verified": True,
        }],
        "prices_used": False,
    }


def combo(uuid="combo-1", price=2.75, components=None):
    components = components or [
        {"UUID": "leg-a", "universalMarketID": 521, "universalOutcomeID": 1329},
        {"UUID": "leg-b", "universalMarketID": 1002, "universalOutcomeID": 4263},
    ]
    return {
        "uuid": uuid,
        "marketId": direct.COMBINATION_MARKET_ID,
        "outcomeId": 16603,
        "price": price,
        "status": "active",
        "marketName": "A; B",
        "name": "A; B",
        "extra": {"tag": "superbets"},
        "oddComponents": components,
    }


def payload(rows):
    return {
        "data": [{
            "eventId": 15000001,
            "matchName": "Alice·Betty",
            "utcDate": "2026-09-21T16:00:00Z",
            "odds": rows,
        }]
    }


def test_artifact_extracts_only_exact_operator_combination_quotes():
    calls = []

    def fetcher(event_id):
        calls.append(event_id)
        return payload([combo()])

    out = bq.build_artifact(direct_feed(), fetcher=fetcher, now=NOW)

    assert calls == ["15000001"]
    assert out["status"] == "OK"
    assert out["mode"] == bq.MODE
    assert out["quote_policy"] == "EXACT_PREPRICED_OPERATOR_ONLY"
    assert out["quotes_count"] == 1
    assert out["external_requests"] == 1
    assert out["dynamic_sga_requests"] == 0
    assert out["prices_used"] is False
    assert out["synthetic_prices"] is False
    assert out["ineed_runtime_influence"] is False
    assert out["automatic_real_betting"] is False

    match = out["matches"][0]
    quote = match["quotes"][0]
    assert match["direct_match_verified"] is True
    assert quote["combined_odds"] == 2.75
    assert quote["operator_selection_id"] == "combo-1"
    assert quote["component_selection_ids"] == ["leg-a", "leg-b"]
    assert quote["source_event_id"] == "15000001"
    assert direct.exact_combination_quote(match["quotes"], ["leg-b", "leg-a"], event_id="15000001") == quote


def test_no_exact_quote_is_safe_explicit_state_not_synthetic_price():
    out = bq.build_artifact(direct_feed(), fetcher=lambda event_id: payload([]), now=NOW)

    assert out["status"] == "NO_EXACT_BUILDER_QUOTES"
    assert out["matches"][0]["quotes"] == []
    assert out["quotes_count"] == 0
    assert out["contains_prices"] is False
    encoded = json.dumps(out, sort_keys=True)
    for forbidden in ("joint_probability", "model_probability", "expected_value_net", "final_stake", "reservation_proposal"):
        assert forbidden not in encoded


def test_no_current_overlap_makes_zero_requests_and_clears_stale_state():
    called = []

    def fetcher(event_id):
        called.append(event_id)
        raise AssertionError("must not fetch")

    out = bq.build_artifact(direct_feed("NO_CURRENT_OVERLAP"), fetcher=fetcher, now=NOW)

    assert out["status"] == "NO_CURRENT_OVERLAP"
    assert out["matches"] == []
    assert out["quotes_count"] == 0
    assert out["external_requests"] == 0
    assert called == []


def test_event_fetch_failure_is_fail_closed_and_not_persistable(tmp_path):
    def fetcher(event_id):
        raise RuntimeError("offline")

    out = bq.build_artifact(direct_feed(), fetcher=fetcher, now=NOW)
    assert out["status"] == "EVENT_FETCH_FAILED"
    assert out["external_requests"] == 1

    try:
        bq.write_artifact(out, tmp_path / "quotes.json")
    except ValueError as exc:
        assert "unsafe builder quote status" in str(exc)
    else:
        raise AssertionError("unsafe artifact must not persist")


def test_atomic_writer_preserves_metadata_only_contract(tmp_path):
    out = bq.build_artifact(direct_feed(), fetcher=lambda event_id: payload([combo()]), now=NOW)
    target = tmp_path / "superbet_builder_quotes_current.json"

    written = bq.write_artifact(out, target)
    loaded = json.loads(written.read_text(encoding="utf-8"))

    assert written == target
    assert not target.with_name(target.name + ".tmp").exists()
    assert loaded["status"] == "OK"
    assert loaded["prices_used"] is False
    assert loaded["production_influence"] is False
    assert loaded["playable_influence"] is False
    assert loaded["symphony_influence"] is False
    assert loaded["ineed_runtime_influence"] is False


def test_validation_rejects_influence_or_synthetic_price(tmp_path):
    safe = bq.build_artifact(direct_feed(), fetcher=lambda event_id: payload([combo()]), now=NOW)
    for key, value in (("synthetic_prices", True), ("ineed_runtime_influence", True), ("production_influence", True)):
        bad = json.loads(json.dumps(safe))
        bad[key] = value
        try:
            bq.write_artifact(bad, tmp_path / f"{key}.json")
        except ValueError:
            pass
        else:
            raise AssertionError(f"{key} must fail closed")


def test_refresh_current_writes_safe_empty_artifact_for_no_overlap(tmp_path):
    source = tmp_path / "direct.json"
    target = tmp_path / "builder.json"
    source.write_text(json.dumps(direct_feed("NO_CURRENT_OVERLAP")), encoding="utf-8")

    result = bq.refresh_current(direct_path=source, output_path=target, fetcher=lambda event_id: None)

    assert result["status"] == "NO_CURRENT_OVERLAP"
    assert result["written"] is True
    assert result["external_requests"] == 0
    assert json.loads(target.read_text(encoding="utf-8"))["status"] == "NO_CURRENT_OVERLAP"
