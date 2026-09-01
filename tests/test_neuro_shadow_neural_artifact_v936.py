from backend.neuro_shadow_neural_artifact_v936 import (
    AUTO_PROMOTION,
    MODE,
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    build_training_report,
)


def test_neuro_artifact_compatibility_stays_shadow_only():
    assert MODE == "SHADOW"
    assert AUTO_PROMOTION is False
    assert PRODUCTION_INFLUENCE is False
    assert PLAYABLE_INFLUENCE is False
    assert SYMPHONY_PROD_INFLUENCE is False
    report = build_training_report([])
    assert report["status"] == "COLLECTING_DATA"
    assert report["auto_promote"] is False
    assert report["ready_markets"] == 0
