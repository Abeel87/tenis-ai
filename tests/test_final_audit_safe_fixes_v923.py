from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAYABLE = (ROOT / "backend" / "superbet_playable.py").read_text(encoding="utf-8")


def test_canonical_playable_stats_are_derived_from_additive_projection_only():
    # The retired _playable_stats aggregator mixed old coverage semantics into
    # the canonical runtime. Current stats must come from the separate
    # superbet_playable_v912 projection and preserve RAW model/SHADOW layers.
    assert "def _playable_stats(" not in PLAYABLE
    assert '"matches": sum(1 for m in projected_results if (m.get("superbet_playable_v912") or {}).get("playable"))' in PLAYABLE
    assert '"raw_model_fields_preserved": True' in PLAYABLE
    assert '"raw_autolearn_preserved": True' in PLAYABLE
    assert '"raw_shadow_files_preserved": True' in PLAYABLE
    assert '"operator_filter_fail_closed": True' in PLAYABLE
