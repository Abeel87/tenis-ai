from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORY = ROOT / "frontend" / "symphony-raw-story-v93j.js"
GUARD = ROOT / "frontend" / "symphony-playable-detail-guard-v915.js"


def test_raw_story_reads_only_compact_model_raw_feed_and_is_non_playable():
    text = STORY.read_text(encoding="utf-8")
    assert "symphony_match_cards_v90.json" in text
    assert "MODEL_RAW_DEEP" in text
    assert "data.analysis_only !== true" in text
    assert "data.operator_playable !== false" in text
    assert "row.analysis_only !== true" in text
    assert "row.operator_playable !== false" in text
    assert "comp.operator_playable !== false" in text
    assert "scenario_narrative" in text
    assert "top_paths" in text
    assert "exact_path_scope" in text

    # The human-readable RAW story must not consult or mutate the operator layer.
    assert "TENIS_AI_PLAYABLE_UI" not in text
    assert "canonical_selections" not in text
    assert "symphony_v90.json" not in text
    assert "operator_reprojection" not in text
    assert "compositionPlayable" not in text


def test_existing_playable_guard_loads_raw_story_as_separate_addon():
    text = GUARD.read_text(encoding="utf-8")
    assert "symphony-raw-story-v93j.js?v=93j" in text
    assert "symphony-raw-story-v93j-addon" in text
    # Keep the established PLAYABLE source and contract unchanged.
    assert "const DATA_URL = './data/symphony_v90.json';" in text
    assert "PLAYABLE_SUPERBET_ONLY" in text
