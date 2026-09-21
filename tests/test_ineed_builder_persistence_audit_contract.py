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


def test_phase6_does_not_add_builder_runtime_wiring():
    runtime_paths = (
        ROOT / "backend/ineed_scoped_runner.py",
        ROOT / "backend/ineed_settlement_runner.py",
        ROOT / "supabase/functions/ineed-sync/index.ts",
        ROOT / ".github/workflows/ineed-shadow.yml",
    )
    for path in runtime_paths:
        text = _text(path)
        assert "ineed_builder_ticket_shadow" not in text
        assert "builder-ticket:" not in text


def test_phase6_adds_no_builder_supabase_migration():
    migrations = ROOT / "supabase" / "migrations"
    for path in migrations.glob("*.sql"):
        text = _text(path).lower()
        assert "builder_ticket" not in text
        assert "builder-ticket:" not in text


def test_audit_records_edge_source_parity_precondition():
    text = _text(AUDIT)
    assert "ACTIVE version 10" in text
    assert "not present in any currently fetched Git branch" in text
    assert "source-parity PR" in text
