from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_user_facing_release_matches_current_ui_release():
    js = read("frontend/app-meta.js")
    assert "releaseVersion: 'v9.2.3'" in js
    assert "appVersion: 'v8.0.1'" in js
    assert "displayVersion: 'v8.8.7'" in js
    assert "currentUiArchitecture: 'v8.8.7-checkpoint-quality-lock'" in js


def test_release_metadata_does_not_touch_model_contract_versions():
    js = read("frontend/app-meta.js")
    assert "modelVersion: 'v7.8D'" in js
    assert "productionModelVersion: 'v8.4B'" in js
    assert "dynamicWeightsVersion: 'v8.4D'" in js
    assert "playerIntelligenceVersion: 'v8.5'" in js
