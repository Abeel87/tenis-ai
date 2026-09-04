from backend.atomic_point_transition import classify_atomic_transition


def row(points, games=(0, 0), sets=(0, 0), winner=None, tb=False):
    return {
        "points": list(points),
        "games": list(games),
        "sets": list(sets),
        "point_winner": winner,
        "is_tiebreak": tb,
    }


def test_standard_single_point_is_atomic():
    result = classify_atomic_transition(row(("15", "15")), row(("30", "15"), winner=1))
    assert result["atomic_transition"] is True
    assert result["reason"] == "atomic_point_step"


def test_compressed_standard_jump_is_rejected():
    result = classify_atomic_transition(row(("0", "0")), row(("30", "0"), winner=1))
    assert result["atomic_transition"] is False
    assert result["reason"] == "compressed_or_wrong_point_step"


def test_deuce_advantage_and_back_to_deuce_are_atomic():
    assert classify_atomic_transition(row(("40", "40")), row(("A", "40"), winner=1))["atomic_transition"] is True
    assert classify_atomic_transition(row(("40", "A")), row(("40", "40"), winner=1))["atomic_transition"] is True


def test_normal_game_boundary_requires_real_game_point():
    accepted = classify_atomic_transition(
        row(("40", "30"), games=(3, 2)),
        row(("0", "0"), games=(4, 2), winner=1),
    )
    assert accepted["atomic_transition"] is True
    assert accepted["reason"] == "atomic_game_boundary"

    compressed = classify_atomic_transition(
        row(("30", "30"), games=(3, 2)),
        row(("0", "0"), games=(4, 2), winner=1),
    )
    assert compressed["atomic_transition"] is False
    assert compressed["reason"] == "game_boundary_requires_missing_points"


def test_wrong_game_winner_or_jump_is_rejected():
    result = classify_atomic_transition(
        row(("40", "0"), games=(1, 1)),
        row(("0", "0"), games=(1, 2), winner=1),
    )
    assert result["atomic_transition"] is False
    assert result["reason"] == "game_score_jump_or_wrong_winner"


def test_tiebreak_single_increment_is_atomic_but_double_change_is_not():
    ok = classify_atomic_transition(row(("4", "4"), tb=True), row(("5", "4"), winner=1, tb=True))
    assert ok["atomic_transition"] is True

    compressed = classify_atomic_transition(row(("0", "0"), tb=True), row(("1", "1"), winner=2, tb=True))
    assert compressed["atomic_transition"] is False
    assert compressed["reason"] == "compressed_or_wrong_point_step"


def test_set_boundary_remains_conservatively_excluded():
    result = classify_atomic_transition(
        row(("40", "30"), games=(5, 4), sets=(0, 0)),
        row(("0", "0"), games=(0, 0), sets=(1, 0), winner=1),
    )
    assert result["atomic_transition"] is False
    assert result["reason"] == "set_boundary_not_yet_proven"


def test_missing_winner_never_becomes_atomic():
    result = classify_atomic_transition(row(("0", "0")), row(("15", "0")))
    assert result["atomic_transition"] is False
    assert result["reason"] == "winner_missing_or_invalid"
