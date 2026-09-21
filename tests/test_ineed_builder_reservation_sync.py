from pathlib import Path

import backend.ineed_scoped_runner as scoped

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "logic12-builder-reservation-shadow-v1"


def _state(config=None):
    return {"experiment": {"id": "exp-1", "config": {} if config is None else config}}


def test_disabled_gate_makes_zero_edge_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(scoped, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or {})
    out = scoped.sync_builder_ticket_reservations(
        "https://edge.invalid", "token", _state(), {"status": "OK", "tickets": [{"ticket_key": "builder-ticket:x"}]}
    )
    assert out["status"] == "DISABLED"
    assert out["reason_code"] == "BUILDER_RESERVATION_DISABLED"
    assert out["attempted_count"] == 0
    assert out["reservation_writes_enabled"] is False
    assert calls == []


def test_contract_mismatch_makes_zero_edge_calls(monkeypatch):
    calls = []
    cfg = {"builder_reservation": {"enabled": True, "contract_version": "wrong"}}
    monkeypatch.setattr(scoped, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or {})
    out = scoped.sync_builder_ticket_reservations("edge", "token", _state(cfg), {"status": "OK", "tickets": []})
    assert out["status"] == "DISABLED"
    assert out["reason_code"] == "BUILDER_RESERVATION_CONTRACT_MISMATCH"
    assert calls == []


def test_enabled_gate_with_no_tickets_is_noop(monkeypatch):
    calls = []
    cfg = {"builder_reservation": {"enabled": True, "contract_version": CONTRACT}}
    monkeypatch.setattr(scoped, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or {})
    out = scoped.sync_builder_ticket_reservations("edge", "token", _state(cfg), {"status": "OK", "tickets": []})
    assert out["status"] == "NO_TICKETS"
    assert out["reservation_writes_enabled"] is True
    assert out["attempted_count"] == 0
    assert calls == []


def test_enabled_gate_posts_only_separate_builder_action(monkeypatch):
    cfg = {"builder_reservation": {"enabled": True, "contract_version": CONTRACT}}
    tickets = [
        {"ticket_key": "builder-ticket:a", "automatic_real_betting": False},
        {"ticket_key": "builder-ticket:b", "automatic_real_betting": False},
    ]
    seen = {}

    def fake_post(url, token, body):
        seen.update({"url": url, "token": token, "body": body})
        return {"ok": True, "reservations": [{"status": "RESERVED"}, {"status": "IDEMPOTENT"}]}

    monkeypatch.setattr(scoped, "post", fake_post)
    out = scoped.sync_builder_ticket_reservations("edge", "token", _state(cfg), {"status": "OK", "tickets": tickets})
    assert seen["body"]["action"] == "reserve_builder_tickets"
    payload = seen["body"]["payload"]
    assert payload["experiment_id"] == "exp-1"
    assert payload["contract_version"] == CONTRACT
    assert payload["automatic_real_betting"] is False
    assert payload["tickets"] == tickets
    assert "evaluations" not in payload and "settlements" not in payload
    assert out["status"] == "OK"
    assert out["attempted_count"] == 2
    assert out["reserved_count"] == 1
    assert out["idempotent_count"] == 1


def test_edge_builder_action_is_isolated_from_v1_email_and_settlement():
    edge = (ROOT / "supabase/functions/ineed-sync/index.ts").read_text(encoding="utf-8")
    segment = edge.split("async function reserveBuilderTickets", 1)[1].split("async function settle", 1)[0]
    assert 'supabase.rpc("ineed_system_reserve_builder_ticket"' in segment
    assert "ineed_system_place_bet" not in segment
    assert "ineed_system_settle_bet" not in segment
    assert "flushEmails" not in segment
    assert "BUILDER_RESERVATION_DISABLED" in edge
    assert "REAL_BETTING_MUST_REMAIN_DISABLED" in edge
    assert edge.count("flushEmails(supabase)") == 1
