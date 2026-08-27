import pandas as pd

from backend.surface_elo_integration_v893 import EloIndex, _events, _elo_features


def sample_rows():
    return pd.DataFrame([
        {"date":"2026-01-01","surface":"hard","player_key":"a","opponent_key":"b","won":1},
        {"date":"2026-01-01","surface":"hard","player_key":"b","opponent_key":"a","won":0},
        {"date":"2026-01-10","surface":"hard","player_key":"a","opponent_key":"c","won":1},
        {"date":"2026-01-10","surface":"hard","player_key":"c","opponent_key":"a","won":0},
    ])


def test_surface_elo_deduplicates_mirrored_player_rows():
    assert len(_events(sample_rows())) == 2


def test_surface_elo_excludes_entire_target_match_day():
    idx=EloIndex(sample_rows())
    snap=idx.match("a","b","hard","2026-01-01T18:00:00Z")
    assert snap["p1"]["general_n"] == 0
    assert snap["p2"]["general_n"] == 0
    assert snap["p1_probability"] == 0.5


def test_surface_elo_moves_toward_repeated_winner():
    idx=EloIndex(sample_rows())
    snap=idx.match("a","b","hard","2026-01-20T12:00:00Z")
    assert snap["p1"]["surface_n"] == 2
    assert snap["p2"]["surface_n"] == 1
    assert snap["blended_edge_p1"] > 0
    assert snap["p1_probability"] > 0.5


def test_unseen_surface_shrinks_to_general_elo():
    idx=EloIndex(sample_rows())
    p=idx.player("a","grass","2026-02-01")
    assert p["surface_n"] == 0
    assert p["blended"] == p["general"]


def test_pick_side_reverses_elo_probability_and_edge():
    idx=EloIndex(sample_rows())
    snap=idx.match("a","b","hard","2026-01-20")
    p1=_elo_features(snap,"p1")
    p2=_elo_features(snap,"p2")
    assert round(p1["elo_probability_for_pick"] + p2["elo_probability_for_pick"],8) == 1.0
    assert p1["elo_edge_for_pick"] == -p2["elo_edge_for_pick"]


def test_display_name_is_normalized_to_database_player_key():
    rows=pd.DataFrame([
        {"date":"2026-01-01","surface":"hard","player_key":"iga swiatek","opponent_key":"aryna sabalenka","won":1},
        {"date":"2026-01-01","surface":"hard","player_key":"aryna sabalenka","opponent_key":"iga swiatek","won":0},
    ])
    idx=EloIndex(rows)
    snap=idx.match("Iga Świątek","Aryna Sabalenka","HARD","2026-01-15T10:00:00Z")
    assert snap["p1"]["general_n"] == 1
    assert snap["p1"]["surface_n"] == 1
    assert snap["p2"]["general_n"] == 1
    assert snap["p1_probability"] > 0.5
