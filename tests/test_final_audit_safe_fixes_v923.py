from backend import superbet_playable as playable


def _verified_match(*, model_ready: bool):
    return {"model_ready": model_ready, "superbet_market_v91": {"operator_verified": True, "status": "VERIFIED", "canonical_selections": [], "model_signals": []}}


def test_superbet_verified_match_coverage_uses_model_ready_intersection():
    results = [_verified_match(model_ready=True), _verified_match(model_ready=False), {"model_ready": True}]
    current = playable._playable_stats([], results, {}, {})["current"]
    assert current["model_ready_matches"] == 2
    assert current["verified_superbet_matches"] == 2
    assert current["verified_model_ready_matches"] == 1
    assert current["verified_match_coverage"] == 0.5
    assert 0.0 <= current["verified_match_coverage"] <= 1.0
