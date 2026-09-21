from pathlib import Path
from decimal import Decimal
import random


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
READER = (MIGRATIONS / "20260921091005_ineed_shared_exposure_readers.sql").read_text(encoding="utf-8")
READER_LOWER = READER.lower()
EDGE = (ROOT / "supabase/functions/ineed-sync/index.ts").read_text(encoding="utf-8")
SETTLEMENT = (ROOT / "backend/ineed_settlement_runner.py").read_text(encoding="utf-8")
OPEN = {"PENDING", "SHADOW_PLACED"}


def _view_rows(open_bets):
    rows = []
    for bet in open_bets:
        if bet.get("status") not in OPEN:
            continue
        snap = bet.get("placement_snapshot") or {}
        players = []
        for value in (snap.get("p1"), snap.get("p2")):
            text = str(value or "").strip()
            if text and text not in players:
                players.append(text)
        rows.append({
            "stake": Decimal(str(bet.get("stake") or 0)),
            "match_id": str(bet.get("match_id") or ""),
            "players": players,
            "markets": [str(bet.get("market") or "").strip()],
        })
    return rows


def _old_metrics(open_bets, match_id, market, p1, p2):
    active = [bet for bet in open_bets if bet.get("status") in OPEN]
    total = sum((Decimal(str(bet.get("stake") or 0)) for bet in active), Decimal("0"))
    same_match = sum((Decimal(str(bet.get("stake") or 0)) for bet in active if str(bet.get("match_id")) == match_id), Decimal("0"))
    same_market = sum((Decimal(str(bet.get("stake") or 0)) for bet in active if str(bet.get("market")) == market), Decimal("0"))
    wanted = {p1.strip().casefold(), p2.strip().casefold()}
    same_player = Decimal("0")
    for bet in active:
        snap = bet.get("placement_snapshot") or {}
        names = {
            str(snap.get("p1") or "").strip().casefold(),
            str(snap.get("p2") or "").strip().casefold(),
        }
        if wanted & names:
            same_player += Decimal(str(bet.get("stake") or 0))
    return total, same_match, same_market, same_player


def _shared_metrics(rows, match_id, market, p1, p2):
    total = sum((row["stake"] for row in rows), Decimal("0"))
    same_match = sum((row["stake"] for row in rows if row["match_id"] == match_id), Decimal("0"))
    same_market = sum((row["stake"] for row in rows if market.strip() in row["markets"]), Decimal("0"))
    wanted = {p1.strip().casefold(), p2.strip().casefold()}
    same_player = sum((
        row["stake"] for row in rows
        if wanted & {str(name).strip().casefold() for name in row["players"]}
    ), Decimal("0"))
    return total, same_match, same_market, same_player


def test_reader_migration_uses_shared_view_without_builder_writer():
    required = (
        "create or replace function public.ineed_system_place_bet",
        "from public.ineed_open_risk_exposures r",
        "unnest(r.markets)",
        "trim(market_name)=trim(s.market)",
        "unnest(r.players)",
        "lower(trim(player_name)) in (p1,p2)",
    )
    for marker in required:
        assert marker in READER_LOWER
    forbidden = (
        "insert into public.ineed_builder_tickets",
        "ineed_system_reserve_builder_ticket",
        "builder_ticket_id",
        "shadow_reserved",
    )
    for marker in forbidden:
        assert marker not in READER_LOWER


def test_v1_placement_lock_and_persistence_shape_is_preserved():
    required = (
        "where id=target_signal_id for update",
        "where id=s.experiment_id for update",
        "from public.ineed_shadow_bets where signal_id=s.id",
        "insert into public.ineed_shadow_bets",
        "insert into public.ineed_bankroll_ledger",
        "'ineed_shadow_bet','reserve:'||bet_row.id",
        "update public.ineed_signals set status='pending'",
    )
    for marker in required:
        assert marker in READER_LOWER


def test_edge_state_reads_shared_risk_but_keeps_v1_open_bets():
    assert 'supabase.from("ineed_shadow_bets").select("*")' in EDGE
    assert 'supabase.from("ineed_open_risk_exposures").select("*")' in EDGE
    assert 'risk_exposures: normalizedRiskExposures' in EDGE
    assert 'open_bets: openBets || []' in EDGE
    assert 'normalizedRiskExposures.reduce' in EDGE
    assert 'const exposure = (openBets || []).reduce' not in EDGE


def test_reader_step_has_no_direct_builder_table_write_and_settlement_stays_v1_only():
    edge_lower = EDGE.lower()
    assert 'supabase.rpc("ineed_system_reserve_builder_ticket"' in edge_lower
    assert "insert into public.ineed_builder_tickets" not in edge_lower
    assert "builder-ticket:" not in edge_lower
    assert "bet_builder_composition" not in SETTLEMENT
    assert "shadow_reserved" not in SETTLEMENT


def test_v1_exposure_metrics_are_exactly_equivalent_for_legal_states():
    rng = random.Random(12091005)
    statuses = ["PENDING", "SHADOW_PLACED", "WIN", "LOSS", "VOID", "CANCELLED"]
    markets = ["set1_winner", "set1_total", "game_state"]
    names = ["Alice", "BETTY", "  Carol  ", "Dora"]

    for case in range(500):
        bets = []
        for index in range(rng.randint(0, 10)):
            bets.append({
                "id": f"b-{case}-{index}",
                "status": rng.choice(statuses),
                "stake": round(rng.uniform(2, 25), 2),
                "match_id": f"match-{rng.randint(1, 5)}",
                "market": rng.choice(markets),
                "placement_snapshot": {"p1": rng.choice(names), "p2": rng.choice(names)},
            })
        match_id = f"match-{rng.randint(1, 5)}"
        market = rng.choice(markets)
        p1, p2 = rng.sample(names, 2)
        assert _old_metrics(bets, match_id, market, p1, p2) == _shared_metrics(
            _view_rows(bets), match_id, market, p1, p2
        )
