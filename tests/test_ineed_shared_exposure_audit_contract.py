from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "TENIS_AI_LOGIC12_SHARED_EXPOSURE_READ_MODEL_AUDIT.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_shared_exposure_audit_freezes_read_model_only():
    text = _text(AUDIT)
    required = (
        "AUDIT + CONTRACT DESIGN ONLY",
        "available_capital",
        "risk_exposures",
        "V1_SINGLE_BET",
        "BET_BUILDER_COMPOSITION",
        "bankroll_equity = available_capital + active_exposure",
        "Do **not** overload `open_bets` with builder records",
        "builder settlement `NOT_IMPLEMENTED`",
    )
    for fragment in required:
        assert fragment in text


def test_current_edge_state_is_v1_bet_backed():
    edge = _text(ROOT / "supabase/functions/ineed-sync/index.ts")
    assert 'from("ineed_shadow_bets").select("*")' in edge
    assert '.in("status", ["SHADOW_PLACED", "PENDING"])' in edge
    assert "available + exposure" in edge
    assert 'open_bets: openBets || []' in edge


def test_v1_sql_exposure_is_currently_shadow_bet_only():
    sql = _text(ROOT / "supabase/migrations/20260910222554_ineed_v1_risk_guards.sql").lower()
    compact = "".join(sql.split())
    assert "sum(stake),0)intototal_exposurefrompublic.ineed_shadow_bets" in compact
    assert "intomatch_exposurefrompublic.ineed_shadow_bets" in compact
    assert "intomarket_exposurefrompublic.ineed_shadow_bets" in compact
    assert "intoplayer_exposurefrompublic.ineed_shadow_bets" in compact
    assert "equity:=available+total_exposure" in compact


def test_phase4_builder_consumes_normalized_ephemeral_risk_exposures():
    builder = _text(ROOT / "backend/ineed_builder_shadow.py")
    assert 'risk = risk_exposure_state(state)' in builder
    assert 'allocated = list(risk["risk_exposures"])' in builder
    assert '"economic_unit": RISK_UNIT_BUILDER' in builder
    assert '"status": "SHADOW_PROPOSED"' in builder
    assert '"runtime_publishable": False' in builder


def test_shared_schema_is_dormant_without_edge_or_settlement_wiring():
    migrations = list((ROOT / "supabase/migrations").glob("*.sql"))
    shared = [path for path in migrations if "risk_exposures" in _text(path)]
    assert len(shared) == 1
    assert shared[0].name.endswith("_ineed_builder_shared_exposure_dormant.sql")
    assert "create view public.ineed_open_risk_exposures" in _text(shared[0]).lower()
    assert "risk_exposures" not in _text(ROOT / "supabase/functions/ineed-sync/index.ts")
    assert "normalize_risk_exposures" in _text(ROOT / "backend/ineed_money.py")
    assert "risk_exposure_state" in _text(ROOT / "backend/ineed_builder_shadow.py")
    settlement = _text(ROOT / "backend/ineed_settlement_runner.py")
    assert 'state.get("open_bets") or []' in settlement
    assert "risk_exposures" not in settlement
