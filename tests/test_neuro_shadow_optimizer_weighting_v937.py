from backend.neuro_shadow_neural import _fit


def test_zero_weight_sample_has_zero_optimizer_effect_including_l2():
    seed = 12345
    single = _fit([[0.25]], [0.0], seed=seed, weights=[1.0])
    with_ignored = _fit([[0.25], [0.75]], [0.0, 1.0], seed=seed, weights=[1.0, 0.0])
    assert with_ignored == single
