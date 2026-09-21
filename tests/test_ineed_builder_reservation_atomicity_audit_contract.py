from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "TENIS_AI_LOGIC12_BUILDER_RESERVATION_ATOMICITY_AUDIT.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_atomicity_audit_freezes_single_owner_single_ledger_design():
    text = _text(AUDIT)
    required = (
        "AUDIT / DESIGN + READ-CONTRACT CORRECTION ONLY",
        "ineed_builder_tickets",
        "ineed_open_risk_exposures",
        "SHADOW_RESERVED",
        "same experiment-row lock",
        "exactly one `STAKE_RESERVED` ledger debit",
        "reserve:builder:<composition_id>",
        "IMMUTABLE_TICKET_CONFLICT",
        "IDEMPOTENT",
        "pgcrypto",
        "ticket_snapshot::text",
        "Builder settlement remains `NOT_IMPLEMENTED`",
    )
    for fragment in required:
        assert fragment in text


def test_post_audit_schema_stays_dormant_and_writer_has_separate_oidc_caller():
    paths = sorted((ROOT / "supabase/migrations").glob("*_ineed_builder_shared_exposure_dormant.sql"))
    assert len(paths) == 1
    migration = _text(paths[0]).lower()
    writer_paths = sorted((ROOT / "supabase/migrations").glob("*_ineed_builder_reservation_writer_shadow.sql"))
    assert len(writer_paths) == 1
    writer = _text(writer_paths[0]).lower()
    edge = _text(ROOT / "supabase/functions/ineed-sync/index.ts")
    config = _text(ROOT / "config/ineed_superbet_pl.json")
    assert "create table public.ineed_builder_tickets" in migration
    assert "create view public.ineed_open_risk_exposures" in migration
    assert "create function" not in migration
    assert "insert into public.ineed_builder_tickets" not in migration
    assert "create or replace function public.ineed_system_reserve_builder_ticket" in writer
    assert "{builder_reservation,enabled}" in writer
    assert "from public.ineed_open_risk_exposures r" in writer
    assert 'body.action === "reserve_builder_tickets"' in edge
    assert 'supabase.rpc("ineed_system_reserve_builder_ticket"' in edge
    assert 'from("ineed_builder_tickets")' not in edge
    assert '"builder_reservation"' not in config
    assert 'from("ineed_open_risk_exposures").select("*")' in edge
    assert 'open_bets: openBets || []' in edge


def test_current_v1_database_readers_use_shared_risk_source_but_keep_open_bets_v1_only():
    reader_paths = sorted((ROOT / "supabase/migrations").glob("*_ineed_shared_exposure_readers.sql"))
    assert len(reader_paths) == 1
    place = _text(reader_paths[0]).lower()
    edge = _text(ROOT / "supabase/functions/ineed-sync/index.ts")
    assert "from public.ineed_open_risk_exposures r" in place
    assert "for update" in place
    assert 'from("ineed_open_risk_exposures").select("*")' in edge
    assert 'from("ineed_shadow_bets").select("*")' in edge
    assert 'open_bets: openBets || []' in edge
    assert 'risk_exposures: normalizedRiskExposures' in edge


def test_builder_and_v1_open_status_namespaces_are_separate():
    money = _text(ROOT / "backend/ineed_money.py")
    assert 'OPEN = {"PENDING", "SHADOW_PLACED"}' in money
    assert 'BUILDER_OPEN = {"SHADOW_RESERVED"}' in money
    assert "builder risk exposure status must be SHADOW_RESERVED" in money


def test_builder_settlement_is_still_not_implemented_and_v1_only():
    ticket = _text(ROOT / "backend/ineed_builder_ticket_shadow.py")
    settlement = _text(ROOT / "backend/ineed_settlement_runner.py")
    assert '"settlement_contract_status": "NOT_IMPLEMENTED"' in ticket
    assert "BET_BUILDER_COMPOSITION" not in settlement
    assert "SHADOW_RESERVED" not in settlement


def test_future_v1_migration_boundary_is_explicitly_blocking():
    text = _text(AUDIT)
    assert "cannot be enabled while `ineed_system_place_bet()` reads only `ineed_shadow_bets`" in text
    assert "V1-only population must produce exactly the same" in text
    assert "`ineed-sync::activeState()` still returns exposure from V1 `ineed_shadow_bets` only" in text
    assert "must read the shared exposure source" in text


def test_future_builder_rpc_must_not_recompute_model_economics():
    text = _text(AUDIT)
    assert "do not recompute model probability, joint probability, odds, EV or Kelly" in text
    assert "revalidate the proposed stake against current unchanged iNeed$ risk caps" in text
