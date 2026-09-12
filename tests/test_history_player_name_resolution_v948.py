import pandas as pd

from backend import model


def _keys(*names):
    return pd.DataFrame({
        "player": list(names),
        "player_key": [model._core._key(name) for name in names],
    })


def test_compound_name_token_reorder_resolves_when_unique():
    df = _keys("Guiomar Maristany Zuleta De Reales")

    resolved, mode = model._resolve_history_player_key(
        df, "Guiomar Zuleta De Reales Maristany"
    )

    assert resolved == "guiomar maristany zuleta de reales"
    assert mode == "expanded-name"


def test_three_token_reorder_resolves_when_unique():
    df = _keys("Antonia Vergara Rivera")

    resolved, mode = model._resolve_history_player_key(df, "Rivera Antonia Vergara")

    assert resolved == "antonia vergara rivera"
    assert mode == "expanded-name"


def test_given_name_initial_resolves_when_unique():
    df = _keys("Alexandra Panova")

    resolved, mode = model._resolve_history_player_key(df, "A. Panova")

    assert resolved == "alexandra panova"
    assert mode == "expanded-name"


def test_given_name_initial_supports_surname_first_provider_form():
    df = _keys("Lajovic Dusan")

    resolved, mode = model._resolve_history_player_key(df, "D. Lajovic")

    assert resolved == "lajovic dusan"
    assert mode == "expanded-name"


def test_initial_identity_stays_fail_closed_when_ambiguous():
    df = _keys("Alexandra Panova", "Anna Panova")

    resolved, mode = model._resolve_history_player_key(df, "A. Panova")

    assert resolved is None
    assert mode == "ambiguous"


def test_initial_never_matches_different_surname():
    df = _keys("Alexandra Petrova")

    resolved, mode = model._resolve_history_player_key(df, "A. Panova")

    assert resolved is None
    assert mode == "none"
