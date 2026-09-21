from decimal import Decimal
from pathlib import Path
import random


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "ineed.js"
MIGRATION = ROOT / "supabase" / "migrations" / "20260921101354_ineed_staff_exposure_summary.sql"
VIEW_MIGRATION = ROOT / "supabase" / "migrations" / "20260921084010_ineed_builder_shared_exposure_dormant.sql"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _legacy_v1_summary(bets: list[dict]) -> tuple[Decimal, int]:
    open_rows = [row for row in bets if row["status"] in {"PENDING", "SHADOW_PLACED"}]
    return sum((Decimal(str(row["stake"])) for row in open_rows), Decimal("0")), len(open_rows)


def _frontend_fallback_summary(bets: list[dict]) -> tuple[Decimal, int]:
    v1_open = [row for row in bets if row["status"] in {"PENDING", "SHADOW_PLACED"}]
    return sum((Decimal(str(row["stake"])) for row in v1_open), Decimal("0")), len(v1_open)


def test_summary_rpc_keeps_normalized_view_private_and_returns_only_aggregates() -> None:
    sql = _text(MIGRATION).lower()
    view = _text(VIEW_MIGRATION).lower()
    assert "security definer" in sql
    assert "set search_path = ''" in sql
    assert "auth.uid()" in sql
    assert "public.is_staff(uid)" in sql
    assert "from public.ineed_open_risk_exposures r" in sql
    assert "'total_exposure'" in sql
    assert "'open_units'" in sql
    assert "'v1_open_units'" in sql
    assert "'builder_open_units'" in sql
    assert "players" not in sql
    assert "markets" not in sql
    assert "composition_id" not in sql
    assert "grant select on table public.ineed_open_risk_exposures to service_role" in view
    assert "grant select on table public.ineed_open_risk_exposures to authenticated" not in view


def test_summary_rpc_permissions_are_explicit_and_staff_only() -> None:
    sql = _text(MIGRATION).lower()
    assert "revoke all on function public.ineed_staff_exposure_summary(uuid)" in sql
    assert "from public, anon, authenticated, service_role" in sql
    assert "grant execute on function public.ineed_staff_exposure_summary(uuid)" in sql
    assert "to authenticated" in sql
    assert "grant execute on function public.ineed_staff_exposure_summary(uuid)\n  to anon" not in sql


def test_frontend_uses_rpc_not_service_only_view() -> None:
    js = _text(FRONTEND)
    assert "c.rpc('ineed_staff_exposure_summary',{target_experiment_id:exp.id})" in js
    assert ".from('ineed_open_risk_exposures')" not in js
    assert "exposure=n(d.risk?.total_exposure)" in js
    assert "openUnits=Math.max(0,Math.trunc(n(d.risk?.open_units)))" in js
    assert "<span class=\"ineed-label\">Otwarte</span><strong>${openUnits}</strong>" in js
    assert "exposure=open.reduce" not in js


def test_frontend_fallback_is_missing_rpc_only_and_other_errors_fail_closed() -> None:
    js = _text(FRONTEND)
    assert "['PGRST202','42883'].includes(String(r.error.code||''))" in js
    assert "if(!['PGRST202','42883'].includes(String(r.error.code||'')))throw r.error" in js
    assert "V1_FALLBACK_SCHEMA_NOT_DEPLOYED" in js
    assert "42501" not in js
    assert "builder_open_units:0" in js


def test_v1_fallback_is_exact_for_500_deterministic_states() -> None:
    rng = random.Random(120949)
    statuses = ["PENDING", "SHADOW_PLACED", "WIN", "LOSS", "VOID", "CANCELLED", "SETTLED"]
    for _ in range(500):
        bets = [
            {"stake": Decimal(rng.randint(100, 50000)) / Decimal("100"), "status": rng.choice(statuses)}
            for _ in range(rng.randint(0, 40))
        ]
        assert _frontend_fallback_summary(bets) == _legacy_v1_summary(bets)


def test_rpc_and_frontend_do_not_enable_builder_write_or_settlement() -> None:
    sql = _text(MIGRATION).lower()
    js = _text(FRONTEND).lower()
    for forbidden in (
        "insert into public.ineed_builder_tickets",
        "update public.ineed_builder_tickets",
        "delete from public.ineed_builder_tickets",
        "ineed_system_reserve_builder",
    ):
        assert forbidden not in sql
        assert forbidden not in js
    assert "ineed_system_settle_bet" not in js
    assert "settlement_contract_status" not in js


def test_rpc_requires_known_experiment_without_mutating_it() -> None:
    sql = _text(MIGRATION).lower()
    assert "from public.ineed_experiments e where e.id = target_experiment_id" in sql
    assert "update public.ineed_experiments" not in sql
    assert "insert into public.ineed_experiments" not in sql
    assert "delete from public.ineed_experiments" not in sql
