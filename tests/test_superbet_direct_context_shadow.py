from datetime import datetime, timedelta, timezone

from backend import superbet_market_context as context


def _feed(now, *, status="OK"):
    return {
        "mode": "SHADOW_SUPERBET_DIRECT_SELECTED_MATCH_FEED",
        "status": status,
        "generated_at": now.isoformat(),
        "operator": "superbet.pl",
        "prices_used": False,
        "production_influence": False,
        "playable_influence": False,
        "matches": [
            {
                "event_id": "14809301",
                "p1": "Alexander Bublik",
                "p2": "Tommy Paul",
                "scheduled_time": "2026-09-04T16:30:00Z",
                "operator_start_time": "2026-09-04T16:30:00Z",
                "direct_match_verified": True,
                "canonical_selections": [
                    {
                        "market": "match_total",
                        "pick": "over",
                        "line": 38.5,
                        "player": None,
                        "set_no": None,
                        "operator": "superbet.pl",
                        "operator_available": True,
                        "operator_line_verified": True,
                        "fixture_line_verified": True,
                        "operator_line_source": "superbet_direct_public_event_json",
                        "operator_price": 1.91,
                        "operator_price_verified": True,
                        "operator_price_source": "superbet_direct_public_event_json",
                        "prices_used": False,
                    },
                    {
                        "market": "exact_match_score",
                        "pick": "3:1",
                        "line": None,
                        "player": None,
                        "set_no": None,
                        "operator": "superbet.pl",
                        "operator_available": True,
                        "operator_price": 6.2,
                        "operator_price_verified": True,
                        "operator_price_source": "superbet_direct_public_event_json",
                        "prices_used": False,
                    },
                ],
            }
        ],
    }


def _app_match(*, existing_status="NOT_FOUND", operator_verified=False):
    return {
        "id": "app-paul-bublik",
        "p1": "Tommy Paul",
        "p2": "Alexander Bublik",
        "scheduled_time": "2026-09-04T16:30:00Z",
        "superbet_market_v91": {
            "status": existing_status,
            "operator_verified": operator_verified,
            "suspended": False,
            "canonical_selections": [],
        },
    }


def test_direct_context_candidate_strips_all_price_fields_and_keeps_exact_line():
    now = datetime(2026, 9, 4, 16, 45, tzinfo=timezone.utc)
    candidate = context.direct_context_candidate(_app_match(), _feed(now), now=now)

    assert candidate is not None
    assert candidate["status"] == context.DIRECT_SHADOW_STATUS
    assert candidate["operator_verified"] is True
    assert candidate["candidate_only"] is True
    assert candidate["prices_used"] is False
    assert candidate["production_influence"] is False
    assert candidate["playable_influence"] is False
    assert candidate["contract"]["operator_prices_removed_before_context"] is True
    assert candidate["contract"]["not_applied_to_superbet_market_v91"] is True

    rows = candidate["canonical_selections"]
    assert len(rows) == 2
    assert all(
        not any(str(key).startswith("operator_price") for key in row)
        for row in rows
    )
    total = next(row for row in rows if row["market"] == "match_total")
    assert total["line"] == 38.5
    assert total["pick"] == "over"
    assert total["fixture_line_verified"] is True
    assert total["operator_line_verified"] is True
    assert total["operator_line_source"] == "superbet_direct_public_event_json"


def test_direct_context_candidate_reorients_score_to_app_player_order():
    now = datetime(2026, 9, 4, 16, 45, tzinfo=timezone.utc)
    candidate = context.direct_context_candidate(_app_match(), _feed(now), now=now)

    scores = [
        row for row in candidate["canonical_selections"]
        if row["market"] == "exact_match_score"
    ]
    assert len(scores) == 1
    assert scores[0]["pick"] == "1:3"


def test_direct_context_candidate_rejects_stale_feed():
    now = datetime(2026, 9, 4, 20, 0, tzinfo=timezone.utc)
    stale = _feed(now - timedelta(hours=context.DIRECT_FEED_MAX_AGE_HOURS + 0.1))

    assert context.direct_context_candidate(_app_match(), stale, now=now) is None


def test_direct_shadow_audit_counts_missing_context_recovery_without_mutation():
    now = datetime(2026, 9, 4, 16, 45, tzinfo=timezone.utc)
    match = _app_match()
    original = {
        "status": match["superbet_market_v91"]["status"],
        "operator_verified": match["superbet_market_v91"]["operator_verified"],
    }

    report = context.direct_shadow_audit([match], _feed(now), now=now)

    assert report["status"] == "OK"
    assert report["app_matches_seen"] == 1
    assert report["direct_context_candidates"] == 1
    assert report["would_recover_missing_context"] == 1
    assert report["existing_verified_overlap"] == 0
    assert report["operator_price_fields_after_adapter"] == 0
    assert report["unverified_line_rows_after_adapter"] == 0
    assert report["writes_results"] is False
    assert report["writes_canonical_context"] is False
    assert report["prices_used"] is False
    assert report["production_influence"] is False
    assert report["playable_influence"] is False
    assert match["superbet_market_v91"]["status"] == original["status"]
    assert match["superbet_market_v91"]["operator_verified"] == original["operator_verified"]

    row = report["matches"][0]
    assert row["p1"] == "Tommy Paul"
    assert row["p2"] == "Alexander Bublik"
    assert row["existing_context_status"] == "NOT_FOUND"
    assert row["direct_fixture_id"] == "14809301"
    assert row["direct_context_status"] == context.DIRECT_SHADOW_STATUS
    assert row["direct_selections_count"] == 2
    assert row["would_recover_missing_context"] is True


def test_direct_shadow_audit_distinguishes_existing_verified_overlap():
    now = datetime(2026, 9, 4, 16, 45, tzinfo=timezone.utc)
    match = _app_match(existing_status="VERIFIED", operator_verified=True)

    report = context.direct_shadow_audit([match], _feed(now), now=now)

    assert report["status"] == "OK"
    assert report["direct_context_candidates"] == 1
    assert report["would_recover_missing_context"] == 0
    assert report["existing_verified_overlap"] == 1
    assert report["matches"][0]["would_recover_missing_context"] is False
