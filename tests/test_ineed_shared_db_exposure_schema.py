from pathlib import Path
import random
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import ineed_money as money


MIGRATIONS = ROOT / "supabase" / "migrations"
MIGRATION_PATHS = sorted(MIGRATIONS.glob("*_ineed_builder_shared_exposure_dormant.sql"))
assert len(MIGRATION_PATHS) == 1
MIGRATION = MIGRATION_PATHS[0].read_text(encoding="utf-8")
MIGRATION_LOWER = MIGRATION.lower()
EDGE = (ROOT / "supabase/functions/ineed-sync/index.ts").read_text(encoding="utf-8")
PLACE = (MIGRATIONS / "20260910222554_ineed_v1_risk_guards.sql").read_text(encoding="utf-8")
READER_PATHS = sorted(MIGRATIONS.glob("*_ineed_shared_exposure_readers.sql"))
assert len(READER_PATHS) == 1
READER = READER_PATHS[0].read_text(encoding="utf-8")


def _view_v1_rows(open_bets):
    rows = []
    for bet in open_bets:
        if bet.get("status") not in money.OPEN:
            continue
        snap = bet.get("placement_snapshot") or {}
        p1 = str(snap.get("p1") or "").strip()
        p2 = str(snap.get("p2") or "").strip()
        players = []
        for player in (p1, p2):
            if player and player not in players:
                players.append(player)
        market = str(bet.get("market") or "").strip()
        rows.append({
            "economic_unit": money.RISK_UNIT_V1,
            "status": str(bet.get("status") or ""),
            "stake": float(bet.get("stake") or 0.0),
            "match_id": str(bet.get("match_id") or ""),
            "players": players,
            "markets": [market] if market else [],
            "source_id": str(bet.get("id") or "") or None,
            "composition_id": None,
        })
    return rows


def test_schema_is_dormant_and_has_no_writer_or_rpc():
    assert "create table public.ineed_builder_tickets" in MIGRATION_LOWER
    assert "create view public.ineed_open_risk_exposures" in MIGRATION_LOWER
    for forbidden in (
        "create function",
        "create or replace function",
        "ineed_system_reserve_builder_ticket",
        "insert into public.ineed_builder_tickets",
        "grant insert",
        "grant update",
        "grant delete",
    ):
        assert forbidden not in MIGRATION_LOWER


def test_builder_owner_is_database_derived_and_read_only():
    assert "create extension if not exists pgcrypto with schema extensions" in MIGRATION_LOWER
    assert "ticket_key text generated always as" in MIGRATION_LOWER
    assert "reservation_key text generated always as" in MIGRATION_LOWER
    assert "ticket_digest text generated always as" in MIGRATION_LOWER
    assert "extensions.digest(ticket_snapshot::text, 'sha256')" in MIGRATION_LOWER
    assert "status = 'shadow_reserved'" in MIGRATION_LOWER
    assert "enable row level security" in MIGRATION_LOWER
    assert "from public, anon, authenticated, service_role" in MIGRATION_LOWER
    assert "grant select on table public.ineed_builder_tickets to service_role" in MIGRATION_LOWER


def test_ticket_snapshot_contract_remains_phase5_shadow_only():
    required = (
        '"status":"shadow_ticket_proposed"',
        '"economic_unit":"bet_builder_composition"',
        '"mode":"shadow"',
        '"operator":"superbet.pl"',
        '"runtime_publishable":false',
        '"persistence_ready":false',
        '"settlement_ready":false',
        '"settlement_contract_status":"not_implemented"',
        '"automatic_real_betting":false',
        "reservation_proposal,reservation_key",
        "economics,final_stake",
    )
    for fragment in required:
        assert fragment in MIGRATION_LOWER


def test_ledger_has_one_owner_and_one_builder_reservation_barrier():
    assert "add column builder_ticket_id uuid" in MIGRATION_LOWER
    assert "num_nonnulls(bet_id, builder_ticket_id) = 1" in MIGRATION_LOWER
    assert "source = 'ineed_builder_ticket'" in MIGRATION_LOWER
    assert "source_key like 'reserve:builder:%'" in MIGRATION_LOWER
    assert "ineed_ledger_builder_reservation_unique" in MIGRATION_LOWER
    assert "where entry_type = 'stake_reserved' and builder_ticket_id is not null" in MIGRATION_LOWER


def test_shared_view_has_security_invoker_and_both_economic_units():
    assert "with (security_invoker = true)" in MIGRATION_LOWER
    assert "'v1_single_bet'::text as economic_unit" in MIGRATION_LOWER
    assert "where b.status in ('shadow_placed', 'pending')" in MIGRATION_LOWER
    assert "'bet_builder_composition'::text as economic_unit" in MIGRATION_LOWER
    assert "where t.status = 'shadow_reserved'" in MIGRATION_LOWER
    assert "grant select on table public.ineed_open_risk_exposures to service_role" in MIGRATION_LOWER


def test_reader_migration_uses_shared_source_without_changing_v1_open_bets():
    assert "from public.ineed_shadow_bets" in PLACE.lower()
    assert "ineed_open_risk_exposures" not in PLACE
    assert "from public.ineed_open_risk_exposures r" in READER.lower()
    assert 'from("ineed_open_risk_exposures").select("*")' in EDGE
    assert 'from("ineed_shadow_bets").select("*")' in EDGE
    assert 'open_bets: openBets || []' in EDGE
    assert 'risk_exposures: normalizedRiskExposures' in EDGE


def test_v1_view_projection_matches_backend_normalization_exactly():
    rng = random.Random(12084010)
    statuses = ["PENDING", "SHADOW_PLACED", "WIN", "LOSS", "VOID", "CANCELLED"]
    markets = ["match_winner", "set1_total", "game_state"]
    players = ["Alice", "Betty", "  Carol  ", "Dora"]

    for case in range(250):
        bets = []
        for index in range(rng.randint(0, 8)):
            p1 = rng.choice(players)
            p2 = rng.choice(players)
            market = rng.choice(markets)
            bets.append({
                "id": f"bet-{case}-{index}",
                "signal_id": f"signal-{case}-{index}",
                "status": rng.choice(statuses),
                "stake": round(rng.uniform(2.0, 20.0), 2),
                "match_id": f"match-{rng.randint(1, 4)}",
                "market": f"  {market}  ",
                "placement_snapshot": {"p1": p1, "p2": p2},
            })
        state = {"open_bets": bets}
        assert _view_v1_rows(bets) == money.normalize_risk_exposures(state)
