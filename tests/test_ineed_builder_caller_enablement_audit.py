from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SCOPED = (ROOT / "backend/ineed_scoped_runner.py").read_text(encoding="utf-8")
DIRECT = (ROOT / "backend/superbet_direct.py").read_text(encoding="utf-8")
EDGE = (ROOT / "supabase/functions/ineed-sync/index.ts").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/ineed-shadow.yml").read_text(encoding="utf-8")
CONFIG = json.loads((ROOT / "config/ineed_superbet_pl.json").read_text(encoding="utf-8"))
DATA = json.loads((ROOT / "frontend/data/superbet_direct_current.json").read_text(encoding="utf-8"))


def test_phase4_and_phase5_use_separate_guarded_reservation_contract():
    assert "build_builder_shadow_runtime(state)" in SCOPED
    assert '{"action": "sync", "payload": payload}' in SCOPED
    assert '"action": "reserve_builder_tickets"' in SCOPED
    assert "sync_builder_ticket_reservations(" in SCOPED
    assert "BUILDER_RESERVATION_CONTRACT_VERSION" in SCOPED
    assert "ineed_system_reserve_builder_ticket" not in SCOPED
    assert 'body.action === "reserve_builder_tickets"' in EDGE
    assert 'supabase.rpc("ineed_system_reserve_builder_ticket"' in EDGE
    assert "payload.builder_shadow" not in EDGE


def test_production_config_keeps_builder_reservations_disabled():
    assert CONFIG.get("automatic_real_betting") is False
    assert "builder_reservation" not in CONFIG


def test_standard_direct_feed_intentionally_excludes_builder_rows():
    assert 'Combination/BetBuilder rows are intentionally excluded' in DIRECT
    assert 'if int(odd.get("marketId") or 0) == COMBINATION_MARKET_ID' in DIRECT
    assert "parse_event_combination_quotes(" in DIRECT
    assert "build_dynamic_sga_quote_url(" in DIRECT
    assert "parse_dynamic_sga_quote(" in DIRECT


def test_current_runtime_direct_artifact_has_no_builder_quote_catalog():
    assert DATA.get("mode") == "SHADOW_SUPERBET_DIRECT_SELECTED_MATCH_FEED"
    assert isinstance(DATA.get("matches"), list)
    for forbidden in ("combination_quotes", "builder_quotes", "quotes"):
        assert forbidden not in DATA


def test_ineed_workflow_guards_builder_persistence_sync_contract():
    lower = WORKFLOW.lower()
    assert "backend/ineed_builder_shadow.py" in WORKFLOW
    assert "backend/ineed_builder_ticket_shadow.py" in WORKFLOW
    assert "tests/test_ineed_builder_scoped_runtime.py" in WORKFLOW
    assert "tests/test_ineed_builder_reservation_sync.py" in WORKFLOW
    assert "ineed_system_reserve_builder_ticket" not in lower
    assert "backend/ineed_scoped_runner.py" in WORKFLOW
