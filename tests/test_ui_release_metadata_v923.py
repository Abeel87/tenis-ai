from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def has_pair(js, key, value):
    return re.search(rf"{re.escape(key)}\s*:\s*'{re.escape(value)}'", js) is not None


def test_user_facing_release_matches_current_ui_release():
    js = read("frontend/app-meta.js")
    assert has_pair(js, "releaseVersion", "v9.2.3")
    assert has_pair(js, "appVersion", "v8.0.1")
    assert has_pair(js, "displayVersion", "v8.8.7")
    assert has_pair(js, "currentUiArchitecture", "v8.8.7-checkpoint-quality-lock")


def test_release_metadata_does_not_touch_model_contract_versions():
    js = read("frontend/app-meta.js")
    assert has_pair(js, "modelVersion", "v7.8D")
    assert has_pair(js, "productionModelVersion", "v8.4B")
    assert has_pair(js, "dynamicWeightsVersion", "v8.4D")
    assert has_pair(js, "playerIntelligenceVersion", "v8.5")
