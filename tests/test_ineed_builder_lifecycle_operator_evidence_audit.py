from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECT = (ROOT / "backend/superbet_direct.py").read_text(encoding="utf-8")
QUOTES = (ROOT / "backend/superbet_builder_quotes.py").read_text(encoding="utf-8")
TICKET = (ROOT / "backend/ineed_builder_ticket_shadow.py").read_text(encoding="utf-8")
EDGE = (ROOT / "supabase/functions/ineed-sync/index.ts").read_text(encoding="utf-8")
SCHEMA = (ROOT / "supabase/migrations/20260921084010_ineed_builder_shared_exposure_dormant.sql").read_text(encoding="utf-8")
V1_SETTLEMENT = (ROOT / "supabase/migrations/20260921095220_ineed_settlement_shared_exposure.sql").read_text(encoding="utf-8")
SETTLEMENT_RUNNER = (ROOT / "backend/ineed_settlement_runner.py").read_text(encoding="utf-8")
AUDIT = (ROOT / "TENIS_AI_LOGIC12_BUILDER_LIFECYCLE_OPERATOR_EVIDENCE_AUDIT.md").read_text(encoding="utf-8")
CHECKLIST = (ROOT / "TENIS_AI_EXECUTION_CHECKLIST.md").read_text(encoding="utf-8")


def _segment(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def test_exact_combination_parser_is_quote_only_not_terminal_result_owner():
    segment = _segment(DIRECT, "def parse_event_combination_quotes", "def exact_combination_quote")
    assert "COMBINATION_MARKET_ID" in segment
    assert 'casefold() != "active"' in segment
    assert "operator_selection_id" in segment
    assert "component_selection_ids" in segment
    assert "combined_odds" in segment
    assert "oddsResults" not in segment
    assert "matchResults" not in segment
    assert "settlement" not in segment.lower()
    assert "payout" not in segment.lower()


def test_builder_quote_artifact_has_no_terminal_lifecycle_owner():
    assert "EXACT_PREPRICED_OPERATOR_ONLY" in QUOTES
    assert "parse_event_combination_quotes" in QUOTES
    for forbidden in ("settle_builder", "builder_payout", "builder_result", "release_builder"):
        assert forbidden not in QUOTES.lower()


def test_phase5_ticket_remains_explicitly_not_settlement_ready():
    assert '"settlement_ready": False' in TICKET
    assert '"settlement_contract_status": "NOT_IMPLEMENTED"' in TICKET
    assert '"automatic_real_betting": False' in TICKET


def test_builder_database_owner_has_only_open_reservation_status():
    lower = SCHEMA.lower()
    assert "status = 'shadow_reserved'" in lower
    assert "where t.status = 'shadow_reserved'" in lower
    assert "builder_ticket_id is null" in lower
    assert "entry_type = 'stake_reserved'" in lower
    for terminal in ("builder_win", "builder_loss", "builder_void", "builder_cancelled", "builder_settled"):
        assert terminal not in lower


def test_edge_has_reservation_action_but_no_builder_lifecycle_action():
    assert 'body.action === "reserve_builder_tickets"' in EDGE
    for forbidden in ("settle_builder_ticket", "release_builder_ticket", "cancel_builder_ticket", "void_builder_ticket"):
        assert forbidden not in EDGE


def test_v1_settlement_remains_v1_only():
    assert "ineed_shadow_bets" in V1_SETTLEMENT
    assert "ineed_system_settle_bet" in V1_SETTLEMENT
    assert "ineed_builder_tickets" not in V1_SETTLEMENT
    assert "BET_BUILDER_COMPOSITION" not in SETTLEMENT_RUNNER
    assert "builder-ticket:" not in SETTLEMENT_RUNNER


def test_audit_freezes_operator_evidence_blocker_and_current_production_gate():
    required = (
        "BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE",
        "builder_persistence.status=DISABLED",
        "BUILDER_RESERVATION_DISABLED",
        "zero builder tickets",
        "oddsResults=[]",
        "15059403",
        "25.02.2026",
        "31.07.2026",
        "builder_reservation.enabled",
        "automatic_real_betting=false",
        "V1 `backend/ineed_settlement_runner.py`",
        "NEXT EXACT ACTION",
    )
    for marker in required:
        assert marker in AUDIT
    assert "operator-evidence" in CHECKLIST.lower()
    assert "BLOCKED_BY_OPERATOR_SETTLEMENT_EVIDENCE" in CHECKLIST
