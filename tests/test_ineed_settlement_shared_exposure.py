from decimal import Decimal
from pathlib import Path
import random


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
NEW = MIGRATIONS / "20260921095220_ineed_settlement_shared_exposure.sql"
LEGACY = MIGRATIONS / "20260910221444_ineed_v1.sql"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _old_other_exposure(bets: list[dict], target_id: str) -> Decimal:
    return sum(
        (
            Decimal(str(row["stake"]))
            for row in bets
            if row["id"] != target_id and row["status"] in {"PENDING", "SHADOW_PLACED"}
        ),
        Decimal("0"),
    )


def _shared_other_exposure(rows: list[dict], target_id: str) -> Decimal:
    return sum(
        (
            Decimal(str(row["stake"]))
            for row in rows
            if not (row["economic_unit"] == "V1_SINGLE_BET" and row["source_id"] == target_id)
        ),
        Decimal("0"),
    )


def test_settlement_preserves_live_mutex_and_v1_scope() -> None:
    sql = _text(NEW)
    assert "select * into b from public.ineed_shadow_bets where id=target_bet_id for update" in sql
    assert "select * into e from public.ineed_experiments where id=b.experiment_id for update" in sql
    assert "from public.ineed_open_risk_exposures r" in sql
    assert "r.economic_unit='V1_SINGLE_BET'" in sql
    assert "r.source_id=b.id::text" in sql
    assert "update public.ineed_builder_tickets" not in sql.lower()
    assert "insert into public.ineed_builder_tickets" not in sql.lower()


def test_settlement_outcome_and_ledger_contract_stays_v1() -> None:
    sql = _text(NEW)
    for marker in (
        "('WIN','LOSS','VOID','CANCELLED')",
        "when settlement_outcome='WIN' then greatest(coalesce(settlement_payout,0),0)",
        "when settlement_outcome in ('VOID','CANCELLED') then b.stake",
        "'BET_WIN'",
        "'BET_LOSS'",
        "'BET_VOID'",
        "'BET_CANCELLED'",
        "'ineed_settlement'",
        "'settle:'||b.id::text",
        "net_profit=credit-b.stake",
    ):
        assert marker in sql


def test_v1_only_other_exposure_is_exactly_equivalent_for_500_states() -> None:
    rng = random.Random(120947)
    statuses = ["PENDING", "SHADOW_PLACED", "WIN", "LOSS", "VOID", "CANCELLED"]
    for case in range(500):
        target_id = f"bet-{case}-target"
        bets: list[dict] = [{"id": target_id, "stake": Decimal("2.00"), "status": "PENDING"}]
        for idx in range(rng.randint(0, 20)):
            bets.append({
                "id": f"bet-{case}-{idx}",
                "stake": Decimal(rng.randint(200, 25000)) / Decimal("100"),
                "status": rng.choice(statuses),
            })
        view_rows = [
            {
                "economic_unit": "V1_SINGLE_BET",
                "source_id": row["id"],
                "stake": row["stake"],
            }
            for row in bets
            if row["status"] in {"PENDING", "SHADOW_PLACED"}
        ]
        assert _shared_other_exposure(view_rows, target_id) == _old_other_exposure(bets, target_id)


def test_builder_exposure_is_additive_but_never_settled_by_v1_rpc() -> None:
    target_id = "target-v1"
    rows = [
        {"economic_unit": "V1_SINGLE_BET", "source_id": target_id, "stake": Decimal("3.00")},
        {"economic_unit": "V1_SINGLE_BET", "source_id": "other-v1", "stake": Decimal("4.50")},
        {"economic_unit": "BET_BUILDER_COMPOSITION", "source_id": "builder-ticket:abc", "stake": Decimal("6.25")},
    ]
    assert _shared_other_exposure(rows, target_id) == Decimal("10.75")
    assert "target_bet_id uuid" in _text(NEW)
    assert "public.ineed_shadow_bets" in _text(NEW)


def test_repo_history_drift_is_made_explicit_not_silently_reused() -> None:
    legacy = _text(LEGACY)
    sql = _text(NEW)
    assert "select * into e from public.ineed_experiments where id=b.experiment_id for update" not in legacy
    assert "select * into e from public.ineed_experiments where id=b.experiment_id for update" in sql
    assert "Preserve the mutex already present in the live production RPC" in sql


def test_settlement_rpc_permissions_remain_service_only() -> None:
    sql = _text(NEW).lower()
    assert "revoke all on function public.ineed_system_settle_bet(uuid,text,numeric,jsonb)" in sql
    assert "from public,anon,authenticated" in sql
    assert "grant execute on function public.ineed_system_settle_bet(uuid,text,numeric,jsonb)" in sql
    assert "to service_role" in sql
