import math

from backend.player_dna_hold_calibration import (
    HOLD_CALIBRATION_CONTRACT_ID,
    _game_observations,
    _strict_game_label_eligible,
    fit_hold_platt,
    hold_calibration_contract,
    hold_calibration_contract_fingerprint,
)
from backend.player_dna_tennis_simulator import (
    calibrated_hold_probability,
    hold_probability,
    inverse_hold_probability,
)


def test_inverse_hold_probability_round_trips_exact_game_formula():
    for point_p in (0.45, 0.50, 0.57, 0.63, 0.72):
        hold_p = hold_probability(point_p)
        recovered = inverse_hold_probability(hold_p)
        assert math.isclose(recovered, point_p, rel_tol=0.0, abs_tol=1e-7)


def test_platt_hold_calibrator_performs_real_converged_fit():
    raw = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90] * 30
    labels = []
    for _ in range(30):
        labels.extend([0, 0, 1, 0, 1, 1, 1, 1])

    model = fit_hold_platt(raw, labels, l2=0.02)
    assert model["converged"] is True
    assert model["iterations"] > 0
    assert math.isfinite(model["intercept"])
    assert math.isfinite(model["slope"])

    values = [calibrated_hold_probability(v, model) for v in (0.60, 0.75, 0.90)]
    assert all(0.0 < v < 1.0 for v in values)
    assert values[0] < values[1] < values[2]



def _game_row(
    *,
    transition_kind="game_score_changed",
    atomic_reason="atomic_game_boundary",
    trainable_point=True,
    atomic_transition=True,
    winner=1,
):
    return {
        "match_id": "m",
        "transition_kind": transition_kind,
        "atomic_reason": atomic_reason,
        "trainable_point": trainable_point,
        "atomic_transition": atomic_transition,
        "server": 1,
        "point_winner": winner,
    }


def test_hold_calibration_uses_only_strict_atomic_game_labels():
    strict = _game_row()
    assert _strict_game_label_eligible(strict) is True
    assert _strict_game_label_eligible(
        _game_row(transition_kind="set_score_changed")
    ) is False
    assert _strict_game_label_eligible(
        _game_row(atomic_reason="set_boundary_not_yet_proven")
    ) is False
    assert _strict_game_label_eligible(
        _game_row(atomic_reason="game_score_jump_or_wrong_winner")
    ) is False
    assert _strict_game_label_eligible(
        _game_row(trainable_point=False)
    ) is False

    observations = _game_observations(
        [
            strict,
            _game_row(transition_kind="set_score_changed"),
            _game_row(atomic_reason="game_boundary_requires_missing_points"),
            _game_row(trainable_point=False),
        ],
        {
            "m": {
                "p1_serve_point": 0.62,
                "p2_serve_point": 0.58,
            }
        },
    )
    assert len(observations) == 1
    assert observations[0]["match_id"] == "m"
    assert observations[0]["server_side"] == 1
    assert observations[0]["held"] == 1


def test_hold_calibration_semantic_contract_is_stable_and_excludes_set_boundaries():
    contract = hold_calibration_contract()
    fingerprint = hold_calibration_contract_fingerprint()

    assert contract["contract_id"] == HOLD_CALIBRATION_CONTRACT_ID
    assert contract["label_policy"]["transition_kind"] == "game_score_changed"
    assert contract["label_policy"]["atomic_reason"] == "atomic_game_boundary"
    assert contract["label_policy"]["trainable_point_required"] is True
    assert contract["label_policy"]["set_score_changed_included"] is False
    assert contract["label_policy"]["set_boundary_reconstruction_enabled"] is False
    assert len(fingerprint) == 64
    assert fingerprint == hold_calibration_contract_fingerprint()
