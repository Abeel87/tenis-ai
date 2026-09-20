from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATE = (ROOT / ".github/workflows/update-and-pages.yml").read_text(encoding="utf-8")
UI = (ROOT / ".github/workflows/ui-smoke.yml").read_text(encoding="utf-8")
WORKFLOWS = UPDATE + "\n" + UI

LEGACY_UI_ALIASES = (
    "scripts/verify_v84d1.py",
    "scripts/verify_v84d2.py",
    "scripts/verify_v84e11.py",
    "scripts/verify_v853_runtime_ui.py",
    "scripts/verify_v87_decision_center.py",
)


def test_legacy_ui_compatibility_aliases_are_not_active_guard_owners():
    for alias in LEGACY_UI_ALIASES:
        assert alias not in WORKFLOWS


def test_update_has_one_canonical_ui_guard_before_operator_projection():
    assert UPDATE.count("python scripts/verify_ui.py") == 1
    assert UPDATE.index("Canonical UI presentation guard") < UPDATE.index("Superbet exact-offer projection PROJECT frontend + stats")


def test_ui_health_revalidates_ui_only_at_real_payload_mutation_boundaries():
    assert UI.count("python scripts/verify_ui.py") == 2
    assert UI.index("Prune publication-only results payload") < UI.index("Post-prune UI presentation guard")
    assert UI.index("Compact safe publication payloads") < UI.index("Post-compaction UI presentation guard")


def test_specific_guards_keep_specific_owners():
    assert "node tests/match_time_smoke.mjs" in UI
    assert "node tests/decision_center_smoke.mjs" in UPDATE
    assert "node tests/decision_center_smoke.mjs" in UI
    assert "python scripts/verify_v87_decision_center.py" not in WORKFLOWS
