import math

from backend.neuro_shadow_neural_v936 import _match_balanced_weights, _standardizer


def test_match_balanced_standardizer_gives_each_fixture_equal_total_influence():
    items = [
        ({"match_id": "rich"}, [1.0], 1.0),
        ({"match_id": "rich"}, [1.0], 1.0),
        ({"match_id": "rich"}, [1.0], 1.0),
        ({"match_id": "rich"}, [1.0], 1.0),
        ({"match_id": "thin"}, [9.0], 0.0),
    ]
    weights = _match_balanced_weights(items)
    means, scales = _standardizer([item[1] for item in items], weights)

    # Equal fixture influence means mean=(1+9)/2=5, not row-weighted 2.6.
    assert math.isclose(means[0], 5.0, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(scales[0], 4.0, rel_tol=0, abs_tol=1e-12)
