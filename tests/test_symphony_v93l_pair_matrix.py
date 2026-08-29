from __future__ import annotations

from backend import symphony_engine_v90 as core
from backend import symphony_engine_v91 as fast
from backend import symphony_pair_matrix_v93l as pair_cache
from backend import symphony_scenario_lattice_v93 as deep
from backend import symphony_scenario_runtime_v93 as runtime


def _candidate(key, market, pick, evidence, line=None, checkpoint=None):
    return core.Candidate(
        key=key,
        label=key,
        market=market,
        pick=pick,
        line=line,
        checkpoint=checkpoint,
        prod_score=evidence,
        shadow_scores={},
        path_probability=None,
        evidence_score=evidence,
        agreement=0.7,
        conflict=0.0,
    )


def _match():
    return {"id": 9310, "p1": "Alpha", "p2": "Beta", "best_of": 3}


def _outcomes():
    return [
        {"cp2": (1, 1), "cp4": (2, 2), "cp6": (3, 3), "set1": (6, 4), "sets": (2, 0),
         "total_games": 19, "set_count": 2, "winner": 1, "set1_winner": 1, "set1_tiebreak": False, "prob": 0.35},
        {"cp2": (1, 1), "cp4": (2, 2), "cp6": (3, 3), "set1": (7, 5), "sets": (2, 1),
         "total_games": 31, "set_count": 3, "winner": 1, "set1_winner": 1, "set1_tiebreak": False, "prob": 0.25},
        {"cp2": (1, 1), "cp4": (2, 2), "cp6": (3, 3), "set1": (6, 7), "sets": (1, 2),
         "total_games": 30, "set_count": 3, "winner": 2, "set1_winner": 2, "set1_tiebreak": True, "prob": 0.20},
        {"cp2": (2, 0), "cp4": (3, 1), "cp6": (4, 2), "set1": (6, 2), "sets": (0, 2),
         "total_games": 17, "set_count": 2, "winner": 2, "set1_winner": 1, "set1_tiebreak": False, "prob": 0.20},
    ]


def _candidates():
    return [
        _candidate("winner", "match_winner", "Alpha", 88.0),
        _candidate("set1", "set1_winner", "Alpha", 84.0),
        _candidate("cp6", "game_state", "3:3", 82.0, checkpoint=6),
        _candidate("set1-over", "set1_total", "over", 80.0, line=8.5),
        _candidate("match-over", "match_total", "over", 78.0, line=18.5),
        _candidate("no-tb", "set1_tiebreak", "no", 76.0),
    ]


def test_pair_tables_are_exact_core_values():
    pool = _candidates()
    compatible, affinity = pair_cache._pair_tables(fast, pool)
    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            expected_compatible = core._compatible(pool[i], pool[j])
            expected_affinity = core._pair_affinity(pool[i], pool[j])
            assert compatible[i][j] is expected_compatible
            assert affinity[i][j] == expected_affinity
            assert compatible[j][i] == compatible[i][j]
            assert affinity[j][i] == affinity[i][j]


def test_cached_beam_output_is_bit_for_bit_equal_to_legacy_fast_beam():
    match = _match()
    candidates = _candidates()
    outcomes = _outcomes()
    legacy = fast._fast_one_pass_compositions(match, candidates, outcomes)

    installed = pair_cache.install(fast)
    try:
        cached = fast._fast_one_pass_compositions(match, candidates, outcomes)
    finally:
        installed.uninstall()

    assert cached == legacy


def test_pair_work_is_bounded_by_pool_pairs_not_beam_expansions(monkeypatch):
    candidates = _candidates()
    pairs = len(candidates) * (len(candidates) - 1) // 2
    calls = {"compatible": 0, "affinity": 0}
    original_compatible = core._compatible
    original_affinity = core._pair_affinity

    def compatible(a, b):
        calls["compatible"] += 1
        return original_compatible(a, b)

    def affinity(a, b):
        calls["affinity"] += 1
        return original_affinity(a, b)

    monkeypatch.setattr(core, "_compatible", compatible)
    monkeypatch.setattr(core, "_pair_affinity", affinity)
    installed = pair_cache.install(fast)
    try:
        result = fast._fast_one_pass_compositions(_match(), candidates, _outcomes())
    finally:
        installed.uninstall()

    assert result
    assert calls["affinity"] <= pairs
    # One direct compatibility check per pair plus at most one from legacy
    # pair_affinity for compatible pairs; no per-combination compatibility work.
    assert calls["compatible"] <= pairs * 2


def test_runtime_exposes_pair_matrix_contract(monkeypatch):
    monkeypatch.setattr(deep, "run", lambda legs=4: {"status": "OK", "matches": 0})
    stored = {}

    def fake_read(path, fallback):
        return stored.get(str(path), {})

    def fake_write(path, value):
        stored[str(path)] = value

    monkeypatch.setattr(runtime.core, "_read", fake_read)
    monkeypatch.setattr(runtime.core, "_write", fake_write)

    result = runtime.run()
    report = stored[str(deep.REPORT)]
    assert result["pair_matrix_cache_version"] == pair_cache.VERSION
    assert report["pair_matrix_cache_version"] == pair_cache.VERSION
    assert report["contract"]["pair_compatibility_affinity_precomputed_exact_equivalent"] is True
    assert report["contract"]["candidate_pool_beam_width_and_sort_order_unchanged"] is True
    assert report["contract"]["bookmaker_prices_used"] is False
    assert result["external_requests"] == 0
