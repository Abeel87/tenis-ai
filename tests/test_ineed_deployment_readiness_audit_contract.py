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
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readiness_audit_is_non_deploying_and_writer_blocking():
    text = _text(AUDIT)
    required = (
        "AUDIT / READINESS CONTRACT ONLY — NO DEPLOYMENT AUTHORIZED",
        "database objects/readers must be deployed and verified before the Edge candidate",
        "READY FOR CONTROLLED DEPLOYMENT VALIDATION, NOT READY FOR BUILDER WRITES",
        "Builder settlement remains `NOT_IMPLEMENTED`",
        "no explicit deployment/cost authorization has been given",
    )
    for fragment in required:
        assert fragment in text


def test_database_bundle_order_is_frozen_and_complete():
    text = _text(AUDIT)
    for idx, name in enumerate(ORDER, start=1):
        assert f"{idx}. `{name}`" in text
        assert (MIGRATIONS / name).exists()
    assert ORDER == sorted(ORDER)


def test_dormant_schema_has_no_builder_writer():
    migration = _text(MIGRATIONS / ORDER[0]).lower()
    all_sql = "\n".join(_text(path) for path in sorted(MIGRATIONS.glob("*.sql"))).lower()
    assert "create table public.ineed_builder_tickets" in migration
    assert "create view public.ineed_open_risk_exposures" in migration
    assert "insert into public.ineed_builder_tickets" not in migration
    assert "ineed_system_reserve_builder_ticket" not in all_sql


def test_readers_depend_on_schema_before_edge():
    placement = _text(MIGRATIONS / ORDER[1]).lower()
    admin = _text(MIGRATIONS / ORDER[2]).lower()
    settlement = _text(MIGRATIONS / ORDER[3]).lower()
    edge = _text(EDGE)
    assert "from public.ineed_open_risk_exposures" in placement
    assert "from public.ineed_open_risk_exposures" in admin
    assert "from public.ineed_open_risk_exposures" in settlement
    assert 'from("ineed_open_risk_exposures").select("*")' in edge


def test_settlement_rollout_must_preserve_live_mutex_and_v1_boundary():
    settlement = _text(MIGRATIONS / ORDER[3]).lower()
    audit = _text(AUDIT)
    assert settlement.count("for update") >= 2
    assert "v1_single_bet" in settlement
    assert "bet_builder_composition" not in settlement
    assert "Do **not** settle a bet as a rollout probe" in audit


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


def test_edge_rollout_preserves_existing_email_alert_contract():
    edge = _text(EDGE)
    audit = _text(AUDIT)
    assert 'from("ineed_email_events")' in edge
    assert 'event_type: "QUALIFIED"' in edge
    assert 'flushEmails(supabase)' in edge
    assert 'smtp.gmail.com' in edge
    assert 'INEED_GMAIL_APP_PASSWORD' in edge
    assert 'ineed_email_events' in audit
    assert '`QUALIFIED` alert generation' in audit
    assert 'Gmail SMTP' in audit
    assert 'must not silently disable or bypass iNeed$ email delivery' in audit
