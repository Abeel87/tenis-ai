from backend import superbet_fixture_matching as matching
from backend import superbet_market_core as base


def _match():
    return {
        "p1": "Dalibor Svrcina",
        "p2": "Luciano Darderi",
        "scheduled_time": "2026-09-03T15:00:00Z",
    }


def test_reversed_cached_fixture_reorients_side_sensitive_markets_without_mutating_cache():
    cached = {
        "p1": "Luciano Darderi",
        "p2": "Svrcina, Dalibor",
        "start_time": "2026-09-03T15:00:00Z",
        "fixture_id": "185055",
        "canonical_selections": [
            {"market": "p2_exactly_1_set", "pick": "no", "player": "Svrcina, Dalibor"},
            {"market": "p2_wins_a_set", "pick": "no", "player": "Svrcina, Dalibor"},
            {"market": "set1_exact_score", "pick": "6:4"},
            {"market": "game_state", "checkpoint": 6, "pick": "4:2"},
            {"market": "match_total", "pick": "under", "line": 40.5},
        ],
    }
    index = {base._pair_key(cached["p1"], cached["p2"]): [cached]}

    got = matching.best_cached_fixture(_match(), index)

    assert got is not cached
    assert got["participant_order_reoriented"] is True
    assert got["p1"] == "Dalibor Svrcina"
    assert got["p2"] == "Luciano Darderi"
    assert [row["market"] for row in got["canonical_selections"]] == [
        "p1_exactly_1_set",
        "p1_wins_a_set",
        "set1_exact_score",
        "game_state",
        "match_total",
    ]
    assert got["canonical_selections"][0]["player"] == "Svrcina, Dalibor"
    assert got["canonical_selections"][2]["pick"] == "4:6"
    assert got["canonical_selections"][3]["pick"] == "2:4"

    # The cached operator snapshot is immutable; projection happens only for the app match.
    assert cached["p1"] == "Luciano Darderi"
    assert cached["canonical_selections"][0]["market"] == "p2_exactly_1_set"
    assert cached["canonical_selections"][2]["pick"] == "6:4"
    assert cached["canonical_selections"][3]["pick"] == "4:2"


def test_direct_cached_fixture_keeps_original_identity_and_semantics():
    cached = {
        "p1": "Svrcina, Dalibor",
        "p2": "Luciano Darderi",
        "start_time": "2026-09-03T15:00:00Z",
        "fixture_id": "185055",
        "canonical_selections": [
            {"market": "p2_exactly_1_set", "pick": "no", "player": "Luciano Darderi"},
            {"market": "set1_exact_score", "pick": "6:4"},
        ],
    }
    index = {base._pair_key(cached["p1"], cached["p2"]): [cached]}

    got = matching.best_cached_fixture(_match(), index)

    assert got is cached
    assert got["canonical_selections"][0]["market"] == "p2_exactly_1_set"
    assert got["canonical_selections"][0]["player"] == "Luciano Darderi"
    assert got["canonical_selections"][1]["pick"] == "6:4"
