from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_superbet_stats_show_real_line_coverage_without_mixing_shadow_accuracy():
    js = (ROOT / "frontend/superbet-playable-stats.js").read_text(encoding="utf-8")

    assert "superbet_line_coverage_v922" in js
    assert "Pokrycie realnych linii Superbet" in js
    assert "playable_model_covered_selections" in js
    assert "shadow_model_covered_selections" in js
    assert "display_model_covered_selections" in js
    assert "operator_only_selections" in js
    assert "SHADOW służy tylko do diagnostyki/pokrycia" in js
    assert "nie wchodzi do skuteczności PLAYABLE" in js
    assert "MODEL/RAW pozostaje niezależny" in js


def test_superbet_stats_keep_existing_playable_accuracy_panel_separate():
    js = (ROOT / "frontend/superbet-playable-stats.js").read_text(encoding="utf-8")

    assert "Historyczna skuteczność PLAYABLE" in js
    assert "To jest statystyka pokrycia realnej oferty, nie skuteczność typów" in js
    assert "superbet_playable_stats_v912.json" in js
    assert "meta.json" in js


def test_superbet_stats_read_canonical_top_level_payload_instead_of_removed_schema():
    js = (ROOT / "frontend/superbet-playable-stats.js").read_text(encoding="utf-8")

    assert "const matches=Number(data?.matches||0);" in js
    assert "const signals=Number(data?.signals||0);" in js
    assert "Object.entries(data?.history||{})" in js
    assert "raw_model_fields_preserved" in js
    assert "Mecze PLAYABLE w raporcie" in js
    assert "Sygnały PLAYABLE w raporcie" in js
    assert "data?.current" not in js
    assert "data?.models" not in js
    assert "verified_superbet_matches" not in js
    assert "playable_green_signals" not in js
