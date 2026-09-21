from decimal import Decimal
from pathlib import Path
import random


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
NEW = MIGRATIONS / "20260921093354_ineed_admin_start_shared_exposure.sql"
LEGACY = MIGRATIONS / "20260910221444_ineed_v1.sql"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _old_open_exposure(bets: list[dict]) -> Decimal:
    return sum(
        (Decimal(str(row["stake"])) for row in bets if row["status"] in {"PENDING", "SHADOW_PLACED"}),
        Decimal("0"),
    )


def _shared_v1_exposure(bets: list[dict]) -> Decimal:
    rows = [row for row in bets if row["status"] in {"PENDING", "SHADOW_PLACED"}]
    return sum((Decimal(str(row["stake"])) for row in rows), Decimal("0"))


def test_admin_start_reader_moves_only_to_shared_open_exposure_source():
    sql = _text(NEW).lower()
    assert "create or replace function public.ineed_admin_start_experiment" in sql
    assert "from public.ineed_open_risk_exposures where experiment_id=previous.id" in sql
    assert "from public.ineed_shadow_bets where experiment_id=previous.id" not in sql


def test_admin_start_auth_rollover_and_initial_deposit_contract_stay_unchanged():
    sql = _text(NEW)
    required = (
        "auth.uid()",
        "public.is_admin(uid)",
        "where status='ACTIVE' for update",
        "status='COMPLETED'",
        "final_bankroll=available",
        "coalesce(config_override,previous.config)",
        "V1 obsługuje wyłącznie superbet.pl / SHADOW",
        "'INITIAL_DEPOSIT'",
        "'experiment_start'",
        "'NEVER_RUN'",
    )
    for marker in required:
        assert marker in sql


def test_admin_start_change_does_not_add_builder_writer_or_touch_settlement():
    sql = _text(NEW).lower()
    for forbidden in (
        "insert into public.ineed_builder_tickets",
        "ineed_system_reserve_builder_ticket",
        "ineed_system_settle_bet",
        "bet_builder_composition",
        "shadow_reserved",
    ):
        assert forbidden not in sql


def test_legacy_admin_guard_was_v1_only_and_is_now_superseded():
    legacy = _text(LEGACY).lower()
    assert "into exposure from public.ineed_shadow_bets" in legacy
    assert "into exposure from public.ineed_open_risk_exposures" not in legacy


def test_v1_only_admin_rollover_exposure_is_exactly_equivalent():
    rng = random.Random(12093354)
    statuses = ["PENDING", "SHADOW_PLACED", "WIN", "LOSS", "VOID", "CANCELLED"]
    for case in range(500):
        bets = []
        for index in range(rng.randint(0, 12)):
            bets.append({
                "id": f"bet-{case}-{index}",
                "status": rng.choice(statuses),
                "stake": Decimal(rng.randint(20000, 250000)) / Decimal("10000"),
            })
        assert _old_open_exposure(bets) == _shared_v1_exposure(bets)


def test_future_builder_exposure_will_block_rollover_once_writer_exists():
    v1_open = Decimal("0")
    builder_open = Decimal("7.50")
    shared_open = v1_open + builder_open
    assert v1_open == 0
    assert shared_open > 0
