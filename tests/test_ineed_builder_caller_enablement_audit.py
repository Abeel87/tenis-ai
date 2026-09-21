from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
BUILDER = (ROOT / "backend/ineed_builder_shadow.py").read_text(encoding="utf-8")
TICKET = (ROOT / "backend/ineed_builder_ticket_shadow.py").read_text(encoding="utf-8")
SCOPED = (ROOT / "backend/ineed_scoped_runner.py").read_text(encoding="utf-8")
DIRECT = (ROOT / "backend/superbet_direct.py").read_text(encoding="utf-8")
EDGE = (ROOT / "supabase/functions/ineed-sync/index.ts").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/ineed-shadow.yml").read_text(encoding="utf-8")
DATA = json.loads((ROOT / "frontend/data/superbet_direct_current.json").read_text(encoding="utf-8"))


def test_phase4_and_phase5_are_runtime_produced_but_not_synced_or_reserved():
    assert "ineed_builder_shadow" in SCOPED
    assert "ineed_builder_ticket_shadow" in SCOPED
    assert "build_shadow_composition(" in SCOPED
    assert "evaluate_builder_economics_shadow(" in SCOPED
    assert "build_builder_ticket_shadow(" in SCOPED
    assert "build_builder_shadow_runtime(state)" in SCOPED
    assert '{"action": "sync", "payload": payload}' in SCOPED
    assert '"edge_sync_enabled": False' in SCOPED
    assert '"reservation_writes_enabled": False' in SCOPED
    assert "ineed_system_reserve_builder_ticket" not in SCOPED
    assert "reserve_builder_ticket" not in EDGE
    assert "payload.builder_shadow" not in EDGE


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


def test_ineed_workflow_guards_builder_modules_without_reservation_stage():
    lower = WORKFLOW.lower()
    assert "backend/ineed_builder_shadow.py" in WORKFLOW
    assert "backend/ineed_builder_ticket_shadow.py" in WORKFLOW
    assert "tests/test_ineed_builder_scoped_runtime.py" in WORKFLOW
    assert "reserve_builder_ticket" not in lower
    assert "backend/ineed_scoped_runner.py" in WORKFLOW
