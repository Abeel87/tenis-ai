from backend.neuro_shadow_neural_v936 import VALIDATION_FRACTION, _chronological_match_split


def test_row_rich_fixture_cannot_distort_match_based_validation_fraction():
    eligible = []
    for index in range(10):
        copies = 30 if index == 4 else 1
        for suffix in range(copies):
            row = {
                "match_id": f"m-{index}",
                "scheduled_time": f"2026-01-{index + 1:02d}T12:00:00Z",
                "prediction_key": f"p-{index}-{suffix}",
            }
            eligible.append((row, [0.5], float((index + suffix) % 2 == 0)))

    train, validation, train_matches, validation_matches = _chronological_match_split(eligible)
    expected_train_matches = int(10 * (1.0 - VALIDATION_FRACTION))
    assert train_matches == expected_train_matches
    assert validation_matches == 10 - expected_train_matches
    train_ids = {item[0]["match_id"] for item in train}
    validation_ids = {item[0]["match_id"] for item in validation}
    assert train_ids.isdisjoint(validation_ids)
    assert "m-4" in train_ids
