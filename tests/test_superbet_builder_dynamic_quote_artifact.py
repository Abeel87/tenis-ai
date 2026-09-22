from datetime import datetime, timezone
import json

import pytest

from backend import superbet_builder_dynamic_quotes as dyn
from backend import superbet_direct as direct

NOW = datetime(2026, 9, 21, 14, 31, tzinfo=timezone.utc)


def _result(match_id="m-1", p1="Alice", p2="Betty"):
    return {
        "match_id": match_id,
        "p1": p1,
        "p2": p2,
        "symphony2_playable": {
            "playable": True,
            "final_playable_authority": True,
            "authority": "SYMPHONY2_FINAL_PLAYABLE",
            "operator": "superbet.pl",
            "recommended_leg_count": 2,
            "joint_probability": 61.5,
            "joint_status": "EXACT_STATE",
            "signals": [
                {"market": "set1_total", "pick": "over", "line": 8.5,
                 "operator_market_id": "10", "operator_outcome_id": "11",
                 "fixture_line_verified": True},
                {"market": "set1_winner", "pick": p1, "line": None,
                 "operator_market_id": "20", "operator_outcome_id": "21",
                 "fixture_line_verified": True},
            ],
        },
    }


def _direct(match_id="m-1", p1="Alice", p2="Betty", event_id="15000001",
            leg_a="leg-a", leg_b="leg-b"):
    return {
        "mode": "SHADOW_SUPERBET_DIRECT_SELECTED_MATCH_FEED",
        "status": "OK",
        "generated_at": "2026-09-21T14:29:00+00:00",
        "prices_used": False,
        "matches": [{
            "match_id": match_id,
            "p1": p1,
            "p2": p2,
            "event_id": event_id,
            "direct_match_verified": True,
            "prices_used": False,
            "canonical_selections": [
                {"market": "set1_total", "pick": "over", "line": 8.5,
                 "operator_available": True, "operator_price_verified": True,
                 "operator_price": 1.5, "operator_selection_status": "active",
                 "operator_selection_id": leg_a, "prices_used": False},
                {"market": "set1_winner", "pick": p1, "line": None,
                 "operator_available": True, "operator_price_verified": True,
                 "operator_price": 1.4, "operator_selection_status": "active",
                 "operator_selection_id": leg_b, "prices_used": False},
            ],
        }],
    }


def _payload(leg_a="leg-a", leg_b="leg-b"):
    return {
        "price": 1.65,
        "sgaUuid": "sga-1",
        "status": "ACTIVE",
        "combinationBettingStatus": "ACTIVE",
        "marketId": 238733,
        "outcomeId": 16603,
        "legs": [
            {"oddUuid": leg_a, "status": "ACTIVE"},
            {"oddUuid": leg_b, "status": "ACTIVE"},
        ],
    }


def test_exact_dynamic_quote_is_frozen_without_runtime_influence():
    calls = []

    def fetcher(event_id, component_ids):
        calls.append((event_id, list(component_ids)))
        return _payload()

    out = dyn.build_artifact([_result()], _direct(), fetcher=fetcher, now=NOW)
    assert out["status"] == "OK"
    assert out["candidate_count"] == 1
    assert out["external_requests"] == 1
    assert out["quotes_count"] == 1
    assert calls == [("15000001", ["leg-a", "leg-b"])]
    row = out["matches"][0]
    quote = row["quote"]
    assert quote["combined_odds"] == 1.65
    assert quote["operator_combination_selection_id"] == "sga-1"
    assert quote["source_quote_kind"] == "BET_BUILDER_DYNAMIC_SGA"
    assert quote["operator_verified"] is True
    assert out["ineed_runtime_influence"] is False
    assert out["settlement_enabled"] is False
    assert out["automatic_real_betting"] is False
    dyn.validate_artifact(out)


def test_missing_component_identity_makes_zero_requests():
    feed = _direct()
    feed["matches"][0]["canonical_selections"][1]["operator_selection_id"] = None
    calls = []
    out = dyn.build_artifact(
        [_result()],
        feed,
        fetcher=lambda *args: calls.append(args),
        now=NOW,
    )
    assert out["status"] == "NO_ELIGIBLE_COMPOSITIONS"
    assert out["candidate_count"] == 0
    assert out["external_requests"] == 0
    assert calls == []
    assert out["rejected"][0]["status"] == "DIRECT_COMPONENT_IDENTITY_UNAVAILABLE"


def test_foreign_dynamic_payload_is_not_accepted():
    out = dyn.build_artifact(
        [_result()],
        _direct(),
        fetcher=lambda *_: _payload(leg_b="foreign-leg"),
        now=NOW,
    )
    assert out["status"] == "NO_EXACT_DYNAMIC_QUOTES"
    assert out["external_requests"] == 1
    assert out["matches"] == []
    assert out["rejected"][0]["status"] == "NO_EXACT_DYNAMIC_QUOTE"


def test_stale_direct_snapshot_fails_before_network():
    feed = _direct()
    feed["generated_at"] = "2026-09-21T10:00:00+00:00"
    calls = []
    out = dyn.build_artifact(
        [_result()], feed, fetcher=lambda *args: calls.append(args), now=NOW
    )
    assert out["status"] == "DIRECT_INPUT_STALE"
    assert out["external_requests"] == 0
    assert calls == []


def test_more_than_request_cap_fails_closed_without_partial_polling():
    results = []
    matches = []
    for index in range(dyn.MAX_DYNAMIC_REQUESTS + 1):
        match_id = f"m-{index}"
        p1, p2 = f"A{index}", f"B{index}"
        results.append(_result(match_id, p1, p2))
        matches.extend(_direct(
            match_id, p1, p2, str(15000000 + index),
            f"leg-a-{index}", f"leg-b-{index}",
        )["matches"])
    feed = _direct()
    feed["matches"] = matches
    calls = []
    out = dyn.build_artifact(results, feed, fetcher=lambda *args: calls.append(args), now=NOW)
    assert out["status"] == "CANDIDATE_LIMIT_EXCEEDED"
    assert out["candidate_count"] == dyn.MAX_DYNAMIC_REQUESTS + 1
    assert out["external_requests"] == 0
    assert calls == []


def test_validation_rejects_any_runtime_or_betting_influence():
    out = dyn.build_artifact(
        [_result()], _direct(), fetcher=lambda *_: _payload(), now=NOW
    )
    out["automatic_real_betting"] = True
    with pytest.raises(ValueError, match="automatic_real_betting"):
        dyn.validate_artifact(out)


def test_atomic_writer_round_trip(tmp_path):
    out = dyn.build_artifact(
        [_result()], _direct(), fetcher=lambda *_: _payload(), now=NOW
    )
    target = tmp_path / "dynamic.json"
    dyn.write_artifact(out, target)
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved == out
    dyn.validate_artifact(saved)


class _Headers:
    def get(self, key, default=None):
        return "application/json; charset=utf-8" if key == "Content-Type" else default

    def get_content_charset(self):
        return "utf-8"


class _Response:
    headers = _Headers()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, _limit):
        return json.dumps(_payload()).encode("utf-8")


def test_public_dynamic_fetcher_uses_exact_canonical_url(monkeypatch):
    seen = []

    def fake_urlopen(request, timeout=20):
        seen.append((request.full_url, timeout))
        return _Response()

    monkeypatch.setattr(direct, "urlopen", fake_urlopen)
    payload = direct.fetch_dynamic_sga_payload_public("15000001", ["leg-b", "leg-a"], timeout=7)
    expected = direct.build_dynamic_sga_quote_url("15000001", ["leg-a", "leg-b"])
    assert seen == [(expected, 7)]
    assert payload["sgaUuid"] == "sga-1"
    assert payload["status"] == "ACTIVE"
