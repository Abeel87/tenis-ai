from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
NEURON_BRIDGE = (ROOT / "frontend" / "neuron-data-bridge.js").read_text(encoding="utf-8")
POINT_TAPE_WORKFLOW = (ROOT / ".github" / "workflows" / "point-tape-audit.yml").read_text(encoding="utf-8")


CURRENT_NEURON_ARTIFACTS = (
    "neuron_current.json",
    "neuron_metrics.json",
    "neuron_model.json",
)

RETIRED_NEURO_ARTIFACTS = (
    "neuro_shadow_current_v936.json",
    "neuro_shadow_stats_v935.json",
    "neuro_shadow_neural_v936.json",
    "neuro_shadow_history_v935.json",
    "neuro_shadow_phase8_challenger_walk_forward.json",
)


def test_phase11_regression_uses_only_current_neuron_publication_artifacts():
    """The historical Phase-12 checkpoint now guards the rebuilt/current Neuron UI only."""
    published_ui = APP + "\n" + NEURON_BRIDGE

    for artifact in CURRENT_NEURON_ARTIFACTS:
        assert artifact in published_ui

    for retired in RETIRED_NEURO_ARTIFACTS:
        assert retired not in published_ui


def test_phase11_regression_does_not_restore_retired_neuro_training_path():
    """Removing old NEURO must not be bypassed by reintroducing its Phase-8 training module."""
    assert "backend.neuro_shadow_training" not in POINT_TAPE_WORKFLOW
    assert "Evaluate Phase-8 NEURO model-class challengers" not in POINT_TAPE_WORKFLOW
    assert "neuro_model_class_challenger" not in POINT_TAPE_WORKFLOW


def test_phase11_regression_keeps_admin_neuron_reports_read_only():
    """Admin may inspect current Neuron artifacts; the UI must not mutate model/training state."""
    assert "data/neuron_current.json" in APP
    assert "data/neuron_metrics.json" in APP
    assert "data/neuron_model.json" in APP
    assert "data-report" in APP
