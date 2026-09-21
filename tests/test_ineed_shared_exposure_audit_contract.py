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


def test_current_edge_keeps_v1_open_bets_but_uses_shared_risk_exposure():
    edge = _text(ROOT / "supabase/functions/ineed-sync/index.ts")
    assert 'from("ineed_shadow_bets").select("*")' in edge
    assert '.in("status", ["SHADOW_PLACED", "PENDING"])' in edge
    assert 'from("ineed_open_risk_exposures").select("*")' in edge
    assert "available + exposure" in edge
    assert 'open_bets: openBets || []' in edge
    assert 'risk_exposures: normalizedRiskExposures' in edge


def test_v1_sql_exposure_reader_migrates_from_legacy_bets_to_shared_view():
    legacy = _text(ROOT / "supabase/migrations/20260910222554_ineed_v1_risk_guards.sql").lower()
    assert "total_exposure from public.ineed_shadow_bets" in legacy
    reader_paths = sorted((ROOT / "supabase/migrations").glob("*_ineed_shared_exposure_readers.sql"))
    assert len(reader_paths) == 1
    reader = _text(reader_paths[0]).lower()
    assert "total_exposure from public.ineed_open_risk_exposures" in reader
    assert "match_exposure from public.ineed_open_risk_exposures" in reader
    assert "market_exposure from public.ineed_open_risk_exposures" in reader
    assert "player_exposure from public.ineed_open_risk_exposures" in reader
    assert "equity:=available+total_exposure" in reader


def test_phase4_builder_consumes_normalized_ephemeral_risk_exposures():
    builder = _text(ROOT / "backend/ineed_builder_shadow.py")
    assert 'risk = risk_exposure_state(state)' in builder
    assert 'allocated = list(risk["risk_exposures"])' in builder
    assert '"economic_unit": RISK_UNIT_BUILDER' in builder
    assert '"status": "SHADOW_PROPOSED"' in builder
    assert '"runtime_publishable": False' in builder


def test_shared_schema_is_consumed_by_readers_but_not_settlement_or_builder_writer():
    migrations = list((ROOT / "supabase/migrations").glob("*.sql"))
    schema = [path for path in migrations if path.name.endswith("_ineed_builder_shared_exposure_dormant.sql")]
    readers = [path for path in migrations if path.name.endswith("_ineed_shared_exposure_readers.sql")]
    assert len(schema) == 1 and len(readers) == 1
    assert "create view public.ineed_open_risk_exposures" in _text(schema[0]).lower()
    assert "from public.ineed_open_risk_exposures" in _text(readers[0]).lower()
    assert 'from("ineed_open_risk_exposures").select("*")' in _text(ROOT / "supabase/functions/ineed-sync/index.ts")
    assert "normalize_risk_exposures" in _text(ROOT / "backend/ineed_money.py")
    assert "risk_exposure_state" in _text(ROOT / "backend/ineed_builder_shadow.py")
    settlement = _text(ROOT / "backend/ineed_settlement_runner.py")
    assert 'state.get("open_bets") or []' in settlement
    assert "risk_exposures" not in settlement
