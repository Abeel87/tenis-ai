from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
WRITER_PATH = MIGRATIONS / "20260921123000_ineed_builder_reservation_writer_shadow.sql"
WRITER = WRITER_PATH.read_text(encoding="utf-8")
LOWER = WRITER.lower()
EDGE = (ROOT / "supabase/functions/ineed-sync/index.ts").read_text(encoding="utf-8")
SETTLEMENT = (ROOT / "backend/ineed_settlement_runner.py").read_text(encoding="utf-8")


def test_writer_is_dormant_service_role_only_and_fail_closed():
    assert "create or replace function public.ineed_system_reserve_builder_ticket" in LOWER
    assert "security definer" in LOWER
    assert "where id = target_experiment_id\n  for update" in LOWER
    assert "{builder_reservation,enabled}" in LOWER
    assert "coalesce(e.config #>> '{builder_reservation,enabled}', 'false')" in LOWER
    assert "builder_reservation_disabled" in LOWER
    assert "from public, anon, authenticated" in LOWER
    assert "to service_role" in LOWER
    assert "ineed_system_reserve_builder_ticket" not in EDGE.lower()
    assert "bet_builder_composition" not in SETTLEMENT.lower()
    assert "shadow_reserved" not in SETTLEMENT.lower()


def test_writer_accepts_only_frozen_phase5_shadow_ticket_contract():
    required = (
        "logic12-builder-ticket-shadow-v1",
        "shadow_ticket_proposed",
        "bet_builder_composition",
        "mode' <> 'shadow'",
        "operator' <> 'superbet.pl'",
        "runtime_publishable",
        "persistence_ready",
        "settlement_ready",
        "not_implemented",
        "automatic_real_betting",
        "shadow_proposed",
        "builder_stake_mismatch",
        "invalid_builder_operator_provenance",
        "invalid_builder_component_identity",
        "invalid_phase4_snapshot",
        "builder_evidence_mismatch",
        "builder_market_dimension_mismatch",
    )
    for marker in required:
        assert marker in LOWER


def test_identity_digest_replay_and_conflict_are_database_owned():
    assert "expected_ticket_key := 'builder-ticket:' || composition_id" in LOWER
    assert "expected_reservation_key := 'builder:' || composition_id" in LOWER
    assert "extensions.digest(ticket_snapshot::text, 'sha256')" in LOWER
    assert "where experiment_id = e.id and ticket_key = expected_ticket_key" in LOWER
    assert "immutable_ticket_conflict" in LOWER
    assert "builder_reservation_inconsistent" in LOWER
    assert "'status','idempotent'" in LOWER
    assert "'reserve:' || expected_reservation_key" in LOWER


def test_replay_is_resolved_before_any_new_bankroll_debit():
    lock_at = LOWER.index("where id = target_experiment_id")
    replay_at = LOWER.index("select * into existing")
    available_at = LOWER.index("select coalesce((\n    select bankroll_after")
    ticket_insert_at = LOWER.index("insert into public.ineed_builder_tickets")
    ledger_insert_at = LOWER.index("insert into public.ineed_bankroll_ledger")
    assert lock_at < replay_at < available_at < ticket_insert_at < ledger_insert_at


def test_writer_revalidates_current_shared_risk_caps_without_resizing_ticket():
    required = (
        "from public.ineed_open_risk_exposures r",
        "total_exposure + stake_value > total_cap + 0.0001",
        "match_exposure + stake_value > match_cap + 0.0001",
        "player_exposure + stake_value > player_cap + 0.0001",
        "foreach market_name in array market_dimensions loop",
        "one_market_exposure + stake_value > market_cap + 0.0001",
        "stake_value > single_cap + 0.0001",
        "stake_value > available",
    )
    for marker in required:
        assert marker in LOWER


def test_writer_never_recomputes_model_economics_or_builder_price():
    for forbidden in (
        "expected_value_net :=",
        "kelly_full :=",
        "joint_probability :=",
        "combined_odds :=",
        "fractional_kelly :=",
        "potential_payout :=",
    ):
        assert forbidden not in LOWER


def test_ticket_owner_and_reservation_debit_are_one_atomic_function_body():
    assert "'shadow_reserved'" in LOWER
    assert "reservation_contract_version" in LOWER
    assert "returning * into ticket_row" in LOWER
    assert "'stake_reserved'" in LOWER
    assert "'ineed_builder_ticket'" in LOWER
    assert "builder_ticket_id" in LOWER
    assert "available - stake_value" in LOWER
    assert "returning * into ledger_row" in LOWER
    assert "'status','reserved'" in LOWER
    assert "'automatic_real_betting',false" in LOWER


def test_deployment_closeout_keeps_writer_dormant_and_edge_unchanged():
    audit = (ROOT / "TENIS_AI_LOGIC12_BUILDER_RESERVATION_WRITER_AUDIT.md").read_text(encoding="utf-8")
    required = (
        "20260921134348 ineed_builder_reservation_writer_shadow",
        "BUILDER_RESERVATION_DISABLED",
        "builder ticket rows = 0",
        "unsent email events = 0",
        "ineed-sync` remains ACTIVE v11",
        "Caller wiring and enablement remain a separate SHADOW-only phase",
        "Builder settlement remains `NOT_IMPLEMENTED`",
    )
    for marker in required:
        assert marker in audit
    assert "ineed_system_reserve_builder_ticket" not in EDGE.lower()
