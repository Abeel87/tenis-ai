import math

from backend.player_dna_hold_calibration import (
    calibrated_hold_probability,
    fit_hold_platt,
    inverse_hold_probability,
)
from backend.player_dna_tennis_simulator import hold_probability


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
