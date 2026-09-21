from datetime import datetime, timezone

from backend import ineed_scoped_runner as runner

NOW = datetime(2026, 9, 21, 14, 31, tzinfo=timezone.utc)


def _config():
    return {
        "currency": "PLN", "minimum_stake": 2.0, "stake_rounding": 0.01,
        "stake_tax_rate": 0.12, "high_win_tax_rate": 0.10,
        "high_win_tax_threshold_pln": 2280.0, "high_win_tax_trigger": "above",
        "fractional_kelly": 0.25, "max_single_bet_pct": 0.03,
        "max_match_exposure_pct": 0.03, "max_player_exposure_pct": 0.03,
        "max_market_exposure_pct": 0.15, "max_total_exposure_pct": 0.15,
        "minimum_net_ev": 0.05, "minimum_edge_pp": 4.0,
        "minimum_confidence": None, "minimum_odds": 1.01,
        "maximum_odds": None, "odds_max_age_minutes": 108,
        "drawdown": {"caution": 0.10, "defensive": 0.20, "halted": 0.30},
        "risk_profiles": {
            "NORMAL": {"stake_multiplier": 1.0, "exposure_multiplier": 1.0, "minimum_net_ev": 0.05, "minimum_edge_pp": 4.0},
            "CAUTION": {"stake_multiplier": 0.67, "exposure_multiplier": 0.67, "minimum_net_ev": 0.07, "minimum_edge_pp": 5.0},
            "DEFENSIVE": {"stake_multiplier": 0.33, "exposure_multiplier": 0.33, "minimum_net_ev": 0.10, "minimum_edge_pp": 6.0},
            "HALTED": {"stake_multiplier": 0.0, "exposure_multiplier": 0.0, "minimum_net_ev": 1.0, "minimum_edge_pp": 100.0},
        },
    }


def _result():
    return {
        "match_id": "m-1", "p1": "Alice", "p2": "Betty",
        "symphony2_playable": {
            "playable": True, "final_playable_authority": True,
            "authority": "SYMPHONY2_FINAL_PLAYABLE", "operator": "superbet.pl",
            "recommended_leg_count": 2, "joint_probability": 90.0, "joint_status": "EXACT_STATE",
            "signals": [
                {"market": "set1_total", "pick": "over", "line": 8.5,
                 "operator_market_id": "10", "operator_outcome_id": "11", "fixture_line_verified": True,
                 "learning_reliability": 0.9},
                {"market": "set1_winner", "pick": "Alice", "line": None,
                 "operator_market_id": "20", "operator_outcome_id": "21", "fixture_line_verified": True,
                 "learning_reliability": 0.8},
            ],
        },
    }


def _direct():
    return {
        "mode": "SHADOW_SUPERBET_DIRECT_SELECTED_MATCH_FEED",
        "status": "OK", "generated_at": "2026-09-21T14:29:00+00:00", "prices_used": False,
        "matches": [{
            "match_id": "m-1", "p1": "Alice", "p2": "Betty", "event_id": "15000001",
            "event_url": "https://superbet.pl/kursy/tenis/alice-vs-betty-15000001",
            "direct_match_verified": True, "prices_used": False,
            "canonical_selections": [
                {"market": "set1_total", "pick": "over", "line": 8.5,
                 "operator_available": True, "operator_price_verified": True, "operator_price": 1.5,
                 "operator_selection_status": "active", "operator_selection_id": "leg-a"},
                {"market": "set1_winner", "pick": "Alice", "line": None,
                 "operator_available": True, "operator_price_verified": True, "operator_price": 1.4,
                 "operator_selection_status": "active", "operator_selection_id": "leg-b"},
            ],
        }],
    }


def _artifact():
    return {
        "mode": "SHADOW_SUPERBET_EXACT_BUILDER_QUOTE_FEED", "status": "OK",
        "generated_at": "2026-09-21T14:30:00+00:00",
        "direct_generated_at": "2026-09-21T14:29:00+00:00",
        "operator": "superbet.pl", "prices_used": False, "synthetic_prices": False,
        "production_influence": False, "playable_influence": False,
        "symphony_influence": False, "ineed_runtime_influence": False,
        "automatic_real_betting": False,
        "matches": [{
            "match_id": "m-1", "p1": "Alice", "p2": "Betty", "event_id": "15000001",
            "event_url": "https://superbet.pl/kursy/tenis/alice-vs-betty-15000001",
            "direct_match_verified": True, "observed_at": "2026-09-21T14:30:00+00:00",
            "quotes": [{
                "operator": "superbet.pl", "quote_kind": "SUPERBETS_PREPRICED_COMBINATION",
                "source_event_id": "15000001", "operator_selection_id": "combo-1",
                "component_selection_ids": ["leg-b", "leg-a"], "combined_odds": 1.5,
                "operator_verified": True, "freshness_verified": True,
                "odds_timestamp": "2026-09-21T14:30:00+00:00",
                "source": "superbet_direct_public_event_json",
            }],
        }],
    }


def _state():
    return {
        "available_capital": 200.0, "bankroll_equity": 200.0, "peak_bankroll": 200.0,
        "open_bets": [], "risk_exposures": [],
        "experiment": {"id": "exp-1", "starting_bankroll": 200.0, "config": _config()},
    }


def _patch_reads(monkeypatch, *, artifact=None, direct=None):
    values = {
        runner.RESULTS: [_result()],
        runner.DIRECT: direct if direct is not None else _direct(),
        runner.BUILDER_QUOTES: artifact if artifact is not None else _artifact(),
        runner.CONFIG: _config(),
        runner.HISTORY: [],
    }
    monkeypatch.setattr(runner, "read", lambda path, fallback: values.get(path, fallback))


def test_scoped_runner_produces_phase4_and_phase5_shadow_without_persistence(monkeypatch):
    _patch_reads(monkeypatch)
    out = runner.build_builder_shadow_runtime(_state(), now=NOW)
    assert out["compositions_count"] == 1
    assert out["evaluations_count"] == 1
    assert out["qualified_count"] == 1
    assert out["tickets_count"] == 1
    assert out["compositions"][0]["combined_price_status"] == "VERIFIED"
    assert out["evaluations"][0]["status"] == "SHADOW_QUALIFIED"
    assert out["tickets"][0]["status"] == "SHADOW_TICKET_PROPOSED"
    assert out["tickets"][0]["runtime_publishable"] is False
    assert out["tickets"][0]["persistence_ready"] is False
    assert out["edge_sync_enabled"] is False
    assert out["reservation_writes_enabled"] is False
    assert out["settlement_enabled"] is False
    assert out["automatic_real_betting"] is False


def test_artifact_snapshot_mismatch_fails_closed_without_ticket(monkeypatch):
    artifact = _artifact()
    artifact["direct_generated_at"] = "2026-09-21T14:28:00+00:00"
    _patch_reads(monkeypatch, artifact=artifact)
    out = runner.build_builder_shadow_runtime(_state(), now=NOW)
    assert out["compositions_count"] == 1
    assert out["compositions"][0]["combined_price_status"] == "NOT_AVAILABLE"
    assert out["evaluations"][0]["status"] == "SHADOW_REJECTED"
    assert out["evaluations"][0]["reason_code"] == "NO_EXACT_OPERATOR_BUILDER_QUOTE"
    assert out["tickets"] == []


def test_foreign_event_identity_fails_closed_without_ticket(monkeypatch):
    artifact = _artifact()
    artifact["matches"][0]["event_id"] = "15000002"
    _patch_reads(monkeypatch, artifact=artifact)
    out = runner.build_builder_shadow_runtime(_state(), now=NOW)
    assert out["tickets_count"] == 0
    assert out["evaluations"][0]["reason_code"] == "NO_EXACT_OPERATOR_BUILDER_QUOTE"


def test_v1_sync_payload_remains_separate_from_builder_shadow(monkeypatch):
    _patch_reads(monkeypatch)
    monkeypatch.setattr(runner, "refresh_direct_for_ineed", lambda rows, feed: (feed, {"status": "TEST"}))
    monkeypatch.setattr(runner, "evaluate", lambda *args, **kwargs: [{"fingerprint": "v1-only", "status": "REJECTED"}])
    monkeypatch.setattr(runner, "build_settlements", lambda *args, **kwargs: [])
    payload = runner.build_payload(_state())
    assert payload["evaluations"] == [{"fingerprint": "v1-only", "status": "REJECTED"}]
    assert "builder_shadow" not in payload
    assert "tickets" not in payload
    assert payload["health"]["automatic_real_betting"] is False
