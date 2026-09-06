from backend.player_dna_opponent_adjustment_audit import (
    OPPONENT_NUMERIC,
    OPPONENT_STRENGTH_NUMERIC,
    OPPONENT_SUPPORT_NUMERIC,
    build_opponent_context_index,
)


def _prior(matches, serve, ret):
    if matches <= 0:
        return {
            "matches": 0,
            "serve_points": 0,
            "serve_wins": 0,
            "serve_win_rate": None,
            "return_points": 0,
            "return_wins": 0,
            "return_win_rate": None,
        }
    return {
        "matches": matches,
        "serve_points": matches * 100,
        "serve_wins": round(matches * 100 * serve),
        "serve_win_rate": serve,
        "return_points": matches * 100,
        "return_wins": round(matches * 100 * ret),
        "return_win_rate": ret,
    }


def _match_rows(
    match_id,
    when,
    p1,
    p2,
    *,
    surface="hard",
    p1_prior=(0, 0.60, 0.40),
    p2_prior=(0, 0.60, 0.40),
    p1_surface_prior=None,
    p2_surface_prior=None,
):
    p1_surface_prior = p1_prior if p1_surface_prior is None else p1_surface_prior
    p2_surface_prior = p2_prior if p2_surface_prior is None else p2_surface_prior

    def row(player, opponent, side, prior, surface_prior):
        return {
            "mode": "SHADOW_AS_OF_PROFILE",
            "strict_as_of": True,
            "same_time_matches_count_as_prior": False,
            "target_match_id": match_id,
            "target_scheduled_time": when,
            "target_surface": surface,
            "target_tour": "atp",
            "target_format": "BO3",
            "player_side": side,
            "player_id": player,
            "opponent_id": opponent,
            "overall_prior": _prior(*prior),
            "same_surface_prior": _prior(*surface_prior),
        }

    return [
        row(p1, p2, "p1", p1_prior, p1_surface_prior),
        row(p2, p1, "p2", p2_prior, p2_surface_prior),
    ]


def test_same_timestamp_matches_never_enter_each_others_opponent_history():
    rows = []
    rows += _match_rows(
        "a-x",
        "2026-01-01T10:00:00Z",
        1,
        9,
        p2_prior=(3, 0.70, 0.30),
    )
    rows += _match_rows(
        "a-y",
        "2026-01-01T10:00:00Z",
        1,
        8,
        p2_prior=(4, 0.65, 0.35),
    )
    rows += _match_rows(
        "a-z",
        "2026-01-02T10:00:00Z",
        1,
        7,
        p2_prior=(5, 0.66, 0.34),
    )

    index, counts = build_opponent_context_index(rows)

    same_a = index[("a-x", 1)]
    same_b = index[("a-y", 1)]
    later = index[("a-z", 1)]

    assert same_a["overall_support"] == 0
    assert same_b["overall_support"] == 0
    assert later["overall_support"] == 2
    assert later["opponent_return_mean"] == 0.325
    assert later["opponent_serve_mean"] == 0.675
    assert later["same_time_matches_count_as_prior"] is False
    assert counts["paired_matches"] == 3


def test_opponent_context_uses_opponents_own_pre_match_profile():
    rows = []
    rows += _match_rows(
        "a-x",
        "2026-01-01T10:00:00Z",
        1,
        9,
        p1_prior=(8, 0.90, 0.10),
        p2_prior=(4, 0.62, 0.38),
    )
    rows += _match_rows(
        "a-b",
        "2026-01-02T10:00:00Z",
        1,
        2,
        p1_prior=(9, 0.88, 0.12),
        p2_prior=(2, 0.55, 0.45),
    )

    index, _ = build_opponent_context_index(rows)
    target = index[("a-b", 1)]

    # Player 1's own strong 0.90/0.10 snapshot must not become opponent quality.
    assert target["opponent_serve_mean"] == 0.62
    assert target["opponent_return_mean"] == 0.38
    assert target["overall_support"] == 1


def test_l5_uses_only_five_most_recent_historical_opponents():
    rows = []
    return_rates = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45]
    for idx, ret in enumerate(return_rates, start=1):
        rows += _match_rows(
            f"m{idx}",
            f"2026-01-{idx:02d}T10:00:00Z",
            1,
            100 + idx,
            p2_prior=(3, 1.0 - ret, ret),
        )

    rows += _match_rows(
        "target",
        "2026-01-10T10:00:00Z",
        1,
        999,
        p2_prior=(3, 0.60, 0.40),
    )

    index, _ = build_opponent_context_index(rows)
    target = index[("target", 1)]

    assert target["overall_support"] == 6
    assert target["opponent_return_mean"] == 0.325
    assert target["opponent_return_l5"] == 0.35


def test_same_surface_context_ignores_other_surface_matches():
    rows = []
    rows += _match_rows(
        "hard-1",
        "2026-01-01T10:00:00Z",
        1,
        9,
        surface="hard",
        p2_prior=(3, 0.70, 0.30),
        p2_surface_prior=(3, 0.68, 0.32),
    )
    rows += _match_rows(
        "clay-1",
        "2026-01-02T10:00:00Z",
        1,
        8,
        surface="clay",
        p2_prior=(3, 0.60, 0.40),
        p2_surface_prior=(3, 0.58, 0.42),
    )
    rows += _match_rows(
        "target",
        "2026-01-03T10:00:00Z",
        1,
        7,
        surface="hard",
        p2_prior=(3, 0.64, 0.36),
    )

    index, _ = build_opponent_context_index(rows)
    target = index[("target", 1)]

    assert target["overall_support"] == 2
    assert target["surface_support"] == 1
    assert target["opponent_return_surface_mean"] == 0.32
    assert target["opponent_serve_surface_mean"] == 0.68


def test_support_counts_only_usable_bidirectional_opponent_profiles():
    rows = []
    rows += _match_rows(
        "missing-profile",
        "2026-01-01T10:00:00Z",
        1,
        9,
        p2_prior=(0, 0.60, 0.40),
    )
    rows += _match_rows(
        "ready-profile",
        "2026-01-02T10:00:00Z",
        1,
        8,
        p2_prior=(3, 0.64, 0.36),
    )
    rows += _match_rows(
        "target",
        "2026-01-03T10:00:00Z",
        1,
        7,
        p2_prior=(3, 0.62, 0.38),
    )

    index, _ = build_opponent_context_index(rows)
    target = index[("target", 1)]

    assert target["overall_history_matches"] == 2
    assert target["overall_support"] == 1
    assert target["opponent_serve_mean"] == 0.64
    assert target["opponent_return_mean"] == 0.36


def test_primary_opponent_strength_features_exclude_support_proxy():
    strength = set(OPPONENT_STRENGTH_NUMERIC)
    support = set(OPPONENT_SUPPORT_NUMERIC)

    assert strength
    assert support
    assert strength.isdisjoint(support)
    assert set(OPPONENT_NUMERIC) == strength | support
    assert all("support" not in name for name in OPPONENT_STRENGTH_NUMERIC)
    assert all("support" in name for name in OPPONENT_SUPPORT_NUMERIC)
