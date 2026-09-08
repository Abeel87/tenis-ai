from backend import symphony2_engine as engine
from backend.symphony2_state import (
    build_outcomes,
    build_player_dna_shared_outcomes,
)


def _match():
    return {
        "p1": "A",
        "p2": "B",
        "best_of": 3,
        "service_model": {"p1_hold": 0.78, "p2_hold": 0.74},
        "first_set_win": {"A": 0.56, "B": 0.44},
        "second_set_win": {"A": 0.55, "B": 0.45},
        "third_set_win": {"A": 0.54, "B": 0.46},
    }


class _FakeModel:
    ready = True

    def predict_diagnostics(self, features):
        legacy_state = float(features["legacy_state_probability"])
        return {
            "final": 0.60 + 0.001 * legacy_state,
            "raw": 0.59 + 0.001 * legacy_state,
            "calibrated": 0.60 + 0.001 * legacy_state,
            "reliability": 0.8,
            "market_calibrator": False,
            "support": 123,
        }


def test_phase9_shadow_state_does_not_change_operator_model_probability(monkeypatch):
    match = _match()
    selection = {
        "market": "match_winner",
        "pick": "A",
        "line": None,
        "checkpoint": None,
        "player": None,
        "market_id": "m1",
        "outcome_id": "o1",
    }

    monkeypatch.setattr(engine, "_current_offer", lambda _match: [selection])
    monkeypatch.setattr(engine, "_model_index", lambda _match: {})
    monkeypatch.setattr(
        engine,
        "feature_row",
        lambda _match, merged: {
            "legacy_state_probability": float(merged["state_probability"]),
        },
    )

    legacy = build_outcomes(match)
    phase9 = build_player_dna_shared_outcomes(match)

    without_phase9 = engine._score_offer(
        match,
        _FakeModel(),
        legacy,
        None,
    )
    with_phase9 = engine._score_offer(
        match,
        _FakeModel(),
        legacy,
        phase9,
    )

    assert len(without_phase9) == len(with_phase9) == 1
    left = without_phase9[0]
    right = with_phase9[0]

    assert left["operator_model_probability"] == right["operator_model_probability"]
    assert left["raw_model_probability"] == right["raw_model_probability"]
    assert left["calibrated_model_probability"] == right["calibrated_model_probability"]
    assert left["state_probability"] == right["state_probability"]
    assert left["player_dna_shared_state_probability_shadow"] is None
    assert right["player_dna_shared_state_probability_shadow"] is not None
    assert right["player_dna_shared_state_supported_shadow"] is True


def test_phase9_engine_reports_cross_family_joint_as_shadow_only():
    match = _match()
    phase9 = build_player_dna_shared_outcomes(match)
    scored = [
        {
            "market": "set1_winner",
            "pick": "A",
            "operator_model_probability": 61.0,
            "player_dna_shared_state_supported_shadow": True,
        },
        {
            "market": "set2_total",
            "pick": "over",
            "line": 8.5,
            "operator_model_probability": 60.0,
            "player_dna_shared_state_supported_shadow": True,
        },
        {
            "market": "match_winner",
            "pick": "A",
            "operator_model_probability": 62.0,
            "player_dna_shared_state_supported_shadow": True,
        },
    ]

    report = engine._phase9_shadow_shared_state_diagnostics(
        match,
        scored,
        phase9,
    )

    assert report["status"] == "SHADOW_SHARED_STATE_AVAILABLE"
    assert report["cross_family_exact_pairs"] >= 2
    assert report["cross_family_pairs"]
    assert all(
        row["joint_source"] == "PLAYER_DNA_SINGLE_WHOLE_MATCH_SHARED_STATE"
        for row in report["cross_family_pairs"]
    )
    assert report["ranking_influence"] is False
    assert report["operator_model_probability_influence"] is False
    assert report["recommended_leg_count_influence"] is False
    assert report["production_influence"] is False
    assert report["playable_influence"] is False
