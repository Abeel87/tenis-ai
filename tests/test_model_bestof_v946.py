import math

from backend.model import _match_distribution_conditional, _set_distribution


def _distribution(best_of):
    base = _set_distribution(0.78, 0.74)
    return _match_distribution_conditional(
        base,
        first_target=0.58,
        second_if_win=0.61,
        second_if_loss=0.53,
        later_target=0.56,
        best_of=best_of,
    )


def test_bo3_distribution_preserves_legacy_score_space_and_mass():
    total_games, winner, total_sets, exact = _distribution(3)
    assert set(exact) == {"2:0", "2:1", "1:2", "0:2"}
    assert set(total_sets) == {"2 sety", "3 sety"}
    assert math.isclose(sum(exact.values()), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(winner.values()), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(total_games.values()), 1.0, abs_tol=1e-9)


def test_bo5_distribution_uses_full_three_win_score_space():
    total_games, winner, total_sets, exact = _distribution(5)
    assert set(exact) == {"3:0", "3:1", "3:2", "2:3", "1:3", "0:3"}
    assert set(total_sets) == {"3 sety", "4 sety", "5 sety"}
    assert math.isclose(sum(exact.values()), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(winner.values()), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(total_games.values()), 1.0, abs_tol=1e-9)
    assert min(total_games) >= 18
    assert max(total_games) > 30


def test_invalid_best_of_falls_back_to_bo3():
    _, _, _, exact = _distribution(7)
    assert set(exact) == {"2:0", "2:1", "1:2", "0:2"}
