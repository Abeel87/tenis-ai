from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "TENIS_AI_LOGIC12_PHASE6_PERSISTENCE_SYNC_AUDIT.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_phase6_freezes_audit_only_persistence_contract():
    text = _text(AUDIT)
    required = (
        "AUDIT + CONTRACT DESIGN ONLY",
        "ticket_key = builder-ticket:<composition_id>",
        "ticket_digest",
        "IDEMPOTENT",
        "IMMUTABLE_TICKET_CONFLICT",
        "one shared bankroll/exposure view",
        "settlement remains `NOT_IMPLEMENTED`",
        "NO SCHEMA MIGRATION, NO EDGE DEPLOY, NO RUNTIME WIRING",
    )
    for fragment in required:
        assert fragment in text


def test_current_v1_persistence_is_still_signal_shaped_and_autoplaces_qualified():
    base_sql = _text(ROOT / "supabase/migrations/20260910221444_ineed_v1.sql")
    risk_sql = _text(ROOT / "supabase/migrations/20260910222554_ineed_v1_risk_guards.sql")
    guard_sql = _text(ROOT / "supabase/migrations/20260916182500_ineed_shadow_market_scope_insert_guard.sql")
    edge = _text(ROOT / "supabase/functions/ineed-sync/index.ts")

    assert "signal_id uuid not null unique" in base_sql.lower()
    assert "unique(experiment_id,fingerprint)" in base_sql.replace(" ", "").lower()
    assert "ineed_system_place_bet(target_signal_id uuid)" in risk_sql.lower()
    assert "wheresignal_id=s.id" in risk_sql.replace(" ", "").lower()
    assert "market_name = 'set1_winner'" in guard_sql
    assert "market_name = 'set1_total' and selection_name = 'over'" in guard_sql
    assert "before insert on public.ineed_shadow_bets" in guard_sql.lower()
    assert "payload.evaluations || []" in edge
    assert 'evaluation.status === "QUALIFIED"' in edge
    assert 'supabase.rpc("ineed_system_place_bet"' in edge


def test_phase5_ticket_stays_nonpersistent_and_nonsettling():
    owner = _text(ROOT / "backend/ineed_builder_ticket_shadow.py")
    assert '"ticket_key": f"builder-ticket:{composition_id}"' in owner
    assert '"persistence_ready": False' in owner
    assert '"settlement_ready": False' in owner
    assert '"settlement_contract_status": "NOT_IMPLEMENTED"' in owner
    assert '"automatic_real_betting": False' in owner


def test_scoped_builder_runtime_keeps_v1_separate_and_uses_guarded_edge_reservation_action():
    scoped = _text(ROOT / "backend/ineed_scoped_runner.py")
    settlement = _text(ROOT / "backend/ineed_settlement_runner.py")
    edge = _text(ROOT / "supabase/functions/ineed-sync/index.ts")
    config = _text(ROOT / "config/ineed_superbet_pl.json")

    assert "ineed_builder_ticket_shadow" in scoped
    assert "build_builder_shadow_runtime(state)" in scoped
    assert '"edge_sync_enabled": False' in scoped
    assert '"settlement_enabled": False' in scoped

    # V1 sync remains byte-shape separate from the builder reservation action.
    assert '{"action": "sync", "payload": payload}' in scoped
    assert '"action": "reserve_builder_tickets"' in scoped
    assert "payload.builder_shadow" not in edge
    assert "ineed_builder_ticket_shadow" not in edge

    # Runner never receives service-role access; the OIDC Edge boundary owns the RPC call.
    assert "ineed_system_reserve_builder_ticket" not in scoped
    assert 'body.action === "reserve_builder_tickets"' in edge
    assert 'supabase.rpc("ineed_system_reserve_builder_ticket"' in edge

    # Settlement and real-money paths remain out of scope; production config stays disabled.
    assert "ineed_builder_ticket_shadow" not in settlement
    assert "builder-ticket:" not in settlement
    assert '"builder_reservation"' not in config
    assert '"automatic_real_betting": false' in config


def test_phase6_is_superseded_by_dormant_schema_then_separate_fail_closed_writer():
    migrations = ROOT / "supabase" / "migrations"
    dormant = sorted(migrations.glob("*_ineed_builder_shared_exposure_dormant.sql"))
    writers = sorted(migrations.glob("*_ineed_builder_reservation_writer_shadow.sql"))
    assert len(dormant) == 1
    assert len(writers) == 1
    dormant_text = _text(dormant[0]).lower()
    writer_text = _text(writers[0]).lower()
    assert "create table public.ineed_builder_tickets" in dormant_text
    assert "create view public.ineed_open_risk_exposures" in dormant_text
    assert "ineed_system_reserve_builder_ticket" not in dormant_text
    assert "create or replace function public.ineed_system_reserve_builder_ticket" in writer_text
    assert "builder_reservation_disabled" in writer_text
    assert "to service_role" in writer_text
    for path in migrations.glob("*.sql"):
        if path not in dormant + writers:
            text = _text(path).lower()
            assert "create table public.ineed_builder_tickets" not in text
            assert "create or replace function public.ineed_system_reserve_builder_ticket" not in text

def test_audit_records_edge_source_parity_precondition():
    text = _text(AUDIT)
    assert "ACTIVE version 10" in text
    assert "not present in any currently fetched Git branch" in text
    assert "source-parity PR" in text
