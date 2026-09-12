import pandas as pd

from backend import model


def _history_rows(name: str, n: int = 5):
    key = model._core._key(name)
    rows = []
    for i in range(n):
        rows.append({
            "date": pd.Timestamp("2026-09-01") - pd.Timedelta(days=i),
            "surface": "hard",
            "player": name,
            "player_key": key,
            "rank": 100 + i,
            "won": 1.0,
            "hold_rate": 0.78,
            "break_rate": 0.24,
            "serve_points_won": 0.64,
            "return_points_won": 0.39,
            "first_serve_won": 0.72,
            "second_serve_won": 0.54,
            "first_set_won": 0.6,
            "second_set_won": 0.6,
            "second_after_first_win": 0.6,
            "second_after_first_loss": 0.5,
            "third_set_won": 0.5,
            "first_set_games": 10.0,
            "first_set_over85": 1.0,
            "first_set_over95": 1.0,
            "first_set_over105": 0.0,
            "first_set_over115": 0.0,
            "first_set_over125": 0.0,
            "sets_played": 2.0,
        })
    return rows


def test_expanded_middle_name_resolves_to_single_history_player():
    df = pd.DataFrame(_history_rows("Jay Dylan Hara Friend"))

    resolved, mode = model._resolve_history_player_key(df, "Jay Friend")

    assert resolved == "jay dylan hara friend"
    assert mode == "expanded-name"


def test_profile_uses_expanded_name_without_lowering_quality_gate():
    df = pd.DataFrame(_history_rows("Jay Dylan Hara Friend"))

    profile = model.player_profile(df, "Jay Friend", "hard", "2026-09-12T12:00:00Z")

    assert profile["player"] == "Jay Friend"
    assert profile["matches"] == 5
    assert profile["quality"] == "MEDIUM"
    assert profile["history_identity_mode"] == "expanded-name"
    assert profile["history_player_key"] == "jay dylan hara friend"


def test_ambiguous_expansions_fail_closed():
    df = pd.DataFrame(
        _history_rows("Jay Dylan Hara Friend")
        + _history_rows("Jay Alexander Friend")
    )

    resolved, mode = model._resolve_history_player_key(df, "Jay Friend")

    assert resolved is None
    assert mode == "ambiguous"


def test_non_boundary_partial_name_is_not_accepted():
    df = pd.DataFrame(_history_rows("Jay Dylan Hara Friend"))

    resolved, mode = model._resolve_history_player_key(df, "Jay Hara")

    assert resolved is None
    assert mode == "none"


def test_surname_first_and_extra_surname_variants_are_supported():
    surname_first = pd.DataFrame(_history_rows("Friend Jay Dylan Hara"))
    extra_surname = pd.DataFrame(_history_rows("Carlos Alcaraz Garfia"))

    resolved_friend, mode_friend = model._resolve_history_player_key(surname_first, "Jay Friend")
    resolved_alcaraz, mode_alcaraz = model._resolve_history_player_key(extra_surname, "Carlos Alcaraz")

    assert resolved_friend == "friend jay dylan hara"
    assert mode_friend == "expanded-name"
    assert resolved_alcaraz == "carlos alcaraz garfia"
    assert mode_alcaraz == "expanded-name"
