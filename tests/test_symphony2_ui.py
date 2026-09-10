from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
PLAYABLE_UI = (ROOT / "frontend" / "playable-ui.js").read_text(encoding="utf-8")
ARCH = (ROOT / "SYMPHONY_2_ARCHITECTURE.md").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update-and-pages.yml").read_text(encoding="utf-8")


def test_no_runtime_reads_legacy_compact_card_feed():
    assert "symphony_match_cards_v90.json" not in JS
    assert "symphony_match_cards_v90.json" not in PLAYABLE_UI
    assert "patchSymphonyMinis" not in PLAYABLE_UI
    assert "reloadCompact" not in PLAYABLE_UI


def test_symphony2_is_documented_as_single_final_playable_authority():
    assert "superbet_playable_v912" in ARCH
    assert "nie jest `P_final` Symfonii 2.0" in ARCH
    assert "nie jest authority finalnego PLAYABLE" in ARCH
    assert "symphony2_playable" in ARCH
    assert "AKTUALNA OFERTA SUPERBET -> SUPERVISED P(HIT) -> EXACT JOINT -> SYMFONIA 2.0 -> PLAYABLE" in ARCH
    assert "zerowym supportem jest `N/D` / unscored" in ARCH


def test_main_workflow_names_operator_projection_separately_from_final_playable():
    assert "Superbet exact-offer projection INJECT current real lines" in WORKFLOW
    assert "Superbet exact-offer projection PROJECT frontend + stats" in WORKFLOW
    assert "Superbet exact-offer projection Guard" in WORKFLOW
    assert "Superbet PLAYABLE PROJECT frontend + stats" not in WORKFLOW


