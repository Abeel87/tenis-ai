from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "TENIS_AI_GUARD_OWNERSHIP_AUDIT.md"
WORKFLOWS = ROOT / ".github" / "workflows"


def _active_named_guard_steps() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        for line in workflow.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\s*- name:\s*(.+)", line)
            if match and re.search(r"guard|validat", match.group(1), re.IGNORECASE):
                rows.append((workflow.name, match.group(1).strip()))
    return rows


def test_guard_ownership_audit_covers_every_named_workflow_guard_invocation():
    text = AUDIT.read_text(encoding="utf-8")
    rows = _active_named_guard_steps()
    assert rows
    missing = [f"{workflow} :: {step}" for workflow, step in rows if f"{workflow} :: {step}" not in text]
    assert not missing, f"guard ownership audit missing active workflow invocations: {missing}"


def test_guard_ownership_audit_freezes_confirmed_bo5_owner_boundaries():
    text = AUDIT.read_text(encoding="utf-8")
    for token in (
        "backend/model.py",
        "backend/prediction_integrity_v78a.py::apply_pre_output_guards()",
        "backend/market_lab_v741.py",
        "backend/serve_props.py",
        "bo5_full_match_not_supported",
        "47/47 passed",
    ):
        assert token in text
