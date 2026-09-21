from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "TENIS_AI_LOGIC12_DEPLOYMENT_READINESS_AUDIT.md"
MIGRATIONS = ROOT / "supabase" / "migrations"
EDGE = ROOT / "supabase" / "functions" / "ineed-sync" / "index.ts"

ORDER = [
    "20260921084010_ineed_builder_shared_exposure_dormant.sql",
    "20260921091005_ineed_shared_exposure_readers.sql",
    "20260921093354_ineed_admin_start_shared_exposure.sql",
    "20260921095220_ineed_settlement_shared_exposure.sql",
    "20260921101354_ineed_staff_exposure_summary.sql",
    "20260921115606_ineed_builder_ticket_fk_index.sql",
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_closeout_records_deployed_read_side_and_writer_stop():
    text = _text(AUDIT)
    required = (
        "DEPLOYED / VERIFIED READ-SIDE — BUILDER WRITES STILL DISABLED",
        "version: 11",
        "35596941111",
        "all 41 were `REJECTED`",
        "0 bets were placed",
        "Builder settlement remains `NOT_IMPLEMENTED`",
        "automatic_real_betting=false",
    )
    for fragment in required:
        assert fragment in text


def test_database_bundle_and_advisor_fix_are_frozen():
    text = _text(AUDIT)
    for name in ORDER:
        assert (MIGRATIONS / name).exists()
        assert name in text
    assert ORDER == sorted(ORDER)
    fk_fix = _text(MIGRATIONS / ORDER[-1]).lower()
    assert "ineed_bankroll_ledger_builder_ticket_id_idx" in fk_fix
    assert "on public.ineed_bankroll_ledger(builder_ticket_id)" in fk_fix


def test_schema_still_has_no_builder_writer():
    migration = _text(MIGRATIONS / ORDER[0]).lower()
    all_sql = "\n".join(_text(path) for path in sorted(MIGRATIONS.glob("*.sql"))).lower()
    assert "create table public.ineed_builder_tickets" in migration
    assert "create view public.ineed_open_risk_exposures" in migration
    assert "insert into public.ineed_builder_tickets" not in all_sql
    assert "ineed_system_reserve_builder_ticket" not in all_sql


def test_deployed_readers_share_one_exposure_source():
    placement = _text(MIGRATIONS / ORDER[1]).lower()
    admin = _text(MIGRATIONS / ORDER[2]).lower()
    settlement = _text(MIGRATIONS / ORDER[3]).lower()
    edge = _text(EDGE)
    assert "from public.ineed_open_risk_exposures" in placement
    assert "from public.ineed_open_risk_exposures" in admin
    assert "from public.ineed_open_risk_exposures" in settlement
    assert 'from("ineed_open_risk_exposures").select("*")' in edge


def test_settlement_keeps_live_mutex_and_v1_boundary():
    settlement = _text(MIGRATIONS / ORDER[3]).lower()
    assert settlement.count("for update") >= 2
    assert "v1_single_bet" in settlement
    assert "bet_builder_composition" not in settlement
    assert "ineed_system_reserve_builder_ticket" not in settlement


def test_staff_summary_keeps_normalized_view_private():
    summary = _text(MIGRATIONS / ORDER[4]).lower()
    assert "security definer" in summary
    assert "set search_path = ''" in summary
    assert "public.is_staff(uid)" in summary
    assert "revoke all on function public.ineed_staff_exposure_summary(uuid)" in summary
    assert "grant execute on function public.ineed_staff_exposure_summary(uuid)" in summary
    assert "to authenticated" in summary
    assert "from public.ineed_open_risk_exposures" in summary


def test_edge_keeps_open_bets_v1_only_and_builder_writer_absent():
    edge = _text(EDGE)
    assert 'from("ineed_shadow_bets").select("*")' in edge
    assert 'open_bets: openBets || []' in edge
    assert 'risk_exposures: normalizedRiskExposures' in edge
    assert "ineed_builder_tickets" not in edge
    assert "ineed_system_reserve_builder_ticket" not in edge


def test_edge_preserves_email_alert_contract_after_v11_rollout():
    edge = _text(EDGE)
    audit = _text(AUDIT)
    assert 'from("ineed_email_events")' in edge
    assert 'event_type: "QUALIFIED"' in edge
    assert 'flushEmails(supabase)' in edge
    assert 'smtp.gmail.com' in edge
    assert 'INEED_GMAIL_APP_PASSWORD' in edge
    assert "36 email events are `SENT`" in audit
    assert "zero events are currently pending/config-blocked/failed" in audit
    assert "No synthetic betting alert was created" in audit


def test_closeout_keeps_real_money_disabled_and_settlement_unimplemented():
    edge = _text(EDGE)
    audit = _text(AUDIT)
    assert 'automatic_real_betting !== false' in edge
    assert "automatic_real_betting=false" in audit
    assert "Builder one-ticket settlement: **NOT_IMPLEMENTED**" in audit
    assert "Real-money execution remains out of scope" in audit
