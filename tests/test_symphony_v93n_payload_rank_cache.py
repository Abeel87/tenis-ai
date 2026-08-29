from __future__ import annotations

from backend import symphony_deep_mask_cache_v93f as mask_cache
from backend import symphony_engine_v90 as core
from backend import symphony_payload_rank_cache_v93n as payload_cache
from backend import symphony_scenario_lattice_v93 as deep


def _match():
    return {"id": 9930, "p1": "Alpha", "p2": "Beta", "best_of": 3}


def _candidate(market="match_winner", pick="Alpha", line=None):
    return core.Candidate(
        key=f"{market}|{line or ''}|{pick}",
        label=f"{market} {pick}",
        market=market,
        pick=pick,
        line=line,
        checkpoint=None,
        prod_score=80.0,
        shadow_scores={},
        path_probability=None,
        evidence_score=80.0,
        agreement=0.5,
        conflict=0.0,
    )


def _row(prob, winner, set1, set2, total_games, cp6=(3, 3)):
    return {
        "cp2": (1, 1),
        "cp4": (2, 2),
        "cp6": cp6,
        "set1": set1,
        "set2_cp2": (1, 1),
        "set2_cp4": (2, 2),
        "set2_cp6": (3, 3),
        "set2": set2,
        "set3": None,
        "sets": (2, 0) if winner == 1 else (0, 2),
        "total_games": total_games,
        "p1_games": total_games // 2,
        "p2_games": total_games - total_games // 2,
        "set_count": 2,
        "winner": winner,
        "set1_winner": 1 if set1[0] > set1[1] else 2,
        "set2_winner": 1 if set2[0] > set2[1] else 2,
        "set3_winner": None,
        "set1_tiebreak": False,
        "set2_tiebreak": False,
        "any_set_to_nil": False,
        "prob": prob,
    }


def test_v93n_top_paths_and_fragility_are_exact_equivalent_with_stable_ties():
    rows = [
        _row(0.20, 1, (6, 4), (6, 3), 19, cp6=(3, 3)),
        _row(0.20, 1, (7, 5), (6, 4), 22, cp6=(4, 2)),
        _row(0.15, 1, (6, 2), (7, 5), 20, cp6=(3, 3)),
        _row(0.30, 2, (4, 6), (3, 6), 19, cp6=(2, 4)),
        _row(0.10, 2, (5, 7), (4, 6), 22, cp6=(3, 3)),
        _row(0.05, 1, (6, 1), (6, 0), 13, cp6=(4, 2)),
    ]
    match = _match()
    winner = _candidate()
    total = _candidate(market="match_total", pick="over", line=18.5)
    combo = (winner, total)

    original_predicate = core._predicate
    core._predicate = deep._deep_predicate(original_predicate)
    try:
        legacy_deep = deep._top_paths_v93(match, combo, rows, limit=3)
        legacy_core = core._top_matching_paths(match, combo, rows, limit=3)
        legacy_fragility = core._fragility(match, combo, rows)
    finally:
        core._predicate = original_predicate

    shared = mask_cache.install(deep)
    base_predicate = core._predicate
    rank = None
    try:
        cached_rows = deep._deep_outcome_finalize(list(rows))
        core._predicate = deep._deep_predicate(base_predicate)
        for candidate in combo:
            core._marginal(cached_rows, core._predicate(match, candidate))

        rank = payload_cache.install(deep, shared)
        cached_deep = deep._top_paths_v93(match, combo, cached_rows, limit=3)
        cached_core = core._top_matching_paths(match, combo, cached_rows, limit=3)
        cached_fragility = core._fragility(match, combo, cached_rows)

        assert cached_deep == legacy_deep
        assert cached_core == legacy_core
        assert cached_fragility == legacy_fragility
        assert [row["set1"] for row in cached_deep[:2]] == ["6:4", "7:5"]
        assert rank.topn_calls >= 2

        hits_before = rank.mass_hits
        assert core._fragility(match, combo, cached_rows) == legacy_fragility
        assert rank.mass_hits > hits_before
    finally:
        if rank is not None:
            rank.uninstall()
        core._predicate = base_predicate
        shared.uninstall()


def test_v93n_uses_only_payload_reuse_and_never_changes_shared_mask_math():
    assert payload_cache.VERSION == "v9.3N-payload-topn-mask-mass"
    assert mask_cache.VERSION == "v9.3F-shared-predicate-masks"
