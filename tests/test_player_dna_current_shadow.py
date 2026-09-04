from datetime import datetime, timezone

from backend.player_dna_current_shadow import (
    _profile_map,
    _serve_feature_row,
)


def _profile(match_id, player_id, opponent_id, matches, serve=0.64, ret=0.38):
    return {
        "target_match_id": match_id,
        "player_id": player_id,
        "opponent_id": opponent_id,
        "strict_as_of": True,
        "current_card_excluded_from_history": True,
        "overall_prior": {
            "matches": matches,
            "serve_win_rate": serve,
            "return_win_rate": ret,
        },
        "same_surface_prior": {
            "matches": max(0, matches - 1),
            "serve_win_rate": serve - 0.01,
            "return_win_rate": ret - 0.01,
        },
    }


def test_current_profile_map_requires_leakage_contract():
    good = _profile("m1", 1, 2, 3)
    bad = _profile("m1", 2, 1, 3)
    bad["current_card_excluded_from_history"] = False
    index = _profile_map([good, bad])
    assert ("m1", 1) in index
    assert ("m1", 2) not in index


def test_serve_features_are_directional_for_server_and_receiver():
    target = {
        "id": 10,
        "surface": "clay",
        "tour": "challenger",
        "best_of": 3,
    }
    server = _profile("10", 1, 2, 5, serve=0.66, ret=0.39)
    receiver = _profile("10", 2, 1, 7, serve=0.62, ret=0.42)
    row = _serve_feature_row(target, server, receiver)
    assert row["surface"] == "clay"
    assert row["tour"] == "CHALLENGER"
    assert row["match_format"] == "BO3"
    assert row["server_overall_serve_rate"] == 0.66
    assert row["receiver_overall_return_rate"] == 0.42
    assert row["server_overall_matches"] == 5
    assert row["receiver_overall_matches"] == 7


def test_current_output_preserves_best_of_for_downstream_simulation():
    from backend.player_dna_current_shadow import _serve_feature_row

    target = {
        "id": 11,
        "surface": "hard",
        "tour": "atp",
        "best_of": 5,
    }
    server = _profile("11", 1, 2, 5)
    receiver = _profile("11", 2, 1, 5)
    features = _serve_feature_row(target, server, receiver)
    assert features["match_format"] == "BO5"
