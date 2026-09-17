from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = (
    "AGENTS.md",
    "TENIS_AI_LOGIC_CONSTITUTION.md",
    "TENIS_AI_MODEL_DATA_REGISTRY.md",
    "TENIS_AI_EXECUTION_CHECKLIST.md",
    "ARCHITECTURE.md",
    "README.md",
)


def _text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_canonical_project_contract_documents_exist():
    missing = [name for name in REQUIRED_DOCS if not (ROOT / name).is_file()]
    assert not missing, f"Missing canonical project contract docs: {missing}"


def test_agent_protocol_points_to_logic_contract_registry_and_checkpoint():
    text = _text("AGENTS.md")
    assert "TENIS_AI_LOGIC_CONSTITUTION.md" in text
    assert "TENIS_AI_MODEL_DATA_REGISTRY.md" in text
    assert "TENIS_AI_EXECUTION_CHECKLIST.md" in text
    assert "NEXT EXACT ACTION" in text
    assert "naprawa w miejscu" in text.lower()
    assert "nie tworzymy" in text.lower() or "nie wolno" in text.lower()


def test_readme_uses_canonical_document_entrypoint():
    text = _text("README.md")
    assert "AGENTS.md" in text
    assert "TENIS_AI_LOGIC_CONSTITUTION.md" in text
    assert "TENIS_AI_MODEL_DATA_REGISTRY.md" in text
    assert "TENIS_AI_EXECUTION_CHECKLIST.md" in text
    assert "LIVE CHECKPOINT" in text
    assert "RAW DATA" in text
    assert "PLAYABLE" in text


def test_architecture_declares_document_authority_and_frontend_audit_debt():
    text = _text("ARCHITECTURE.md")
    assert "AGENTS.md" in text
    assert "TENIS_AI_LOGIC_CONSTITUTION.md" in text
    assert "TENIS_AI_MODEL_DATA_REGISTRY.md" in text
    assert "TENIS_AI_EXECUTION_CHECKLIST.md" in text
    assert "LIVE CHECKPOINT" in text
    assert "NEXT EXACT ACTION" in text
    assert "ownership map pending LOGIC-11" in text


def test_logic_constitution_preserves_critical_module_boundaries():
    text = _text("TENIS_AI_LOGIC_CONSTITUTION.md")
    required = (
        "2026",
        "2025",
        "Player DNA",
        "Player State",
        "Opponent-Adjusted Performance",
        "Superbet",
        "PLAYABLE",
        "Symfonia",
        "iNeed$",
        "Frontend",
        "Guard contract",
    )
    missing = [item for item in required if item not in text]
    assert not missing, f"Logic constitution lost required boundaries: {missing}"


def test_registry_keeps_sequenced_repair_program():
    text = _text("TENIS_AI_MODEL_DATA_REGISTRY.md")
    for phase in range(0, 13):
        assert f"LOGIC-{phase:02d}" in text
    assert "P0" in text
    assert "P1" in text
    assert "P2" in text
    assert "Freshness Counterfactual" in text
    assert "Learning Integrity" in text
    assert "Guard Ownership Audit" in text
    assert "Frontend Ownership" in text


def test_execution_checklist_has_resume_state_and_full_program():
    text = _text("TENIS_AI_EXECUTION_CHECKLIST.md")
    required = (
        "LIVE CHECKPOINT",
        "NEXT EXACT ACTION",
        "CHECKPOINT PRZERWANIA",
        "PROTOKÓŁ WZNOWIENIA",
        "DO NOT REDO",
        "Freshness Counterfactual",
        "Feature Provenance",
        "Opponent Strength",
        "Player State",
        "Learning Integrity",
        "Guard Ownership",
        "Frontend Ownership",
        "iNeed$ Bet Builder",
    )
    missing = [item for item in required if item not in text]
    assert not missing, f"Execution checklist lost required resume/program fields: {missing}"
    for phase in range(0, 13):
        assert f"LOGIC-{phase:02d}" in text
