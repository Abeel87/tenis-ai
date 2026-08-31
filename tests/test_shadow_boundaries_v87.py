from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def test_player_intelligence_remains_strictly_shadow():
    backend = read("backend/player_intelligence_v85.py")
    symphony = read("backend/symphony2_engine.py")

    assert '"mode": "SHADOW"' in backend
    assert '"production_influence": False' in backend
    assert '"generator_assist": "disabled_shadow_only"' in backend
    assert "PLAYER_INTELLIGENCE_V85_SHADOW_ONLY" not in symphony


def test_accuracy_lab_remains_shadow_only():
    accuracy = read("backend/accuracy_lab_v86.py")

    assert 'PRODUCTION_MODE = "shadow_only"' in accuracy
    assert '"production_changed": False' in accuracy
    assert "no automatic production promotion" in accuracy


def test_adaptive_runs_after_raw_ensemble_and_before_shadow_accuracy_lab():
    workflow = read(".github/workflows/update-and-pages.yml")

    ensemble = workflow.index("AutoLearn Ensemble v8.4A")
    adaptive = workflow.index("Adaptive Learning v7.9B controlled PROD")
    accuracy = workflow.index("Accuracy Shadow Lab v8.6")
    assert ensemble < adaptive < accuracy
