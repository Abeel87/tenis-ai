from backend.ensemble_player_learning_v891 import (
    QUALITY_CAPS,
    _fit_alpha,
    alpha_for_row,
    learn_policy,
)


def _rows(player_good=True, market="set1_total", surface="HARD", quality="HIGH", n=80):
    rows = []
    for i in range(n):
        y = 1 if i % 4 != 0 else 0
        ensemble = 62.0 if y else 58.0
        if player_good:
            player = 82.0 if y else 35.0
        else:
            player = 35.0 if y else 82.0
        rows.append({
            "target": y,
            "match_key": f"m{i//3}",
            "scheduled_time": f"2026-08-{1 + (i//20):02d}T12:00:00+00:00",
            "ensemble_score": ensemble,
            "player_probability": player,
            "market": market,
            "surface": surface,
            "pi_quality": quality,
            "feature_coverage": 1.0,
        })
    return rows


def test_fit_alpha_moves_toward_player_only_when_player_adds_signal():
    good_alpha, _ = _fit_alpha(_rows(player_good=True))
    bad_alpha, _ = _fit_alpha(_rows(player_good=False))
    assert good_alpha >= 0.20
    assert bad_alpha <= 0.10


def test_policy_learns_segment_specific_player_trust():
    rows = _rows(True, market="set1_total", n=90) + _rows(False, market="game_state", n=90)
    policy = learn_policy(rows)
    good = {
        "market": "set1_total", "surface": "HARD", "pi_quality": "HIGH",
        "feature_coverage": 1.0,
    }
    bad = {
        "market": "game_state", "surface": "HARD", "pi_quality": "HIGH",
        "feature_coverage": 1.0,
    }
    good_alpha, _ = alpha_for_row(good, policy)
    bad_alpha, _ = alpha_for_row(bad, policy)
    assert good_alpha > bad_alpha


def test_quality_caps_bound_player_influence():
    policy = {"global_alpha": 0.45, "scopes": {}}
    for quality, cap in QUALITY_CAPS.items():
        alpha, _ = alpha_for_row({
            "pi_quality": quality,
            "feature_coverage": 1.0,
        }, policy)
        assert alpha <= cap + 1e-9
