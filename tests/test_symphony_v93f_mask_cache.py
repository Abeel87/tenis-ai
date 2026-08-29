from __future__ import annotations

from backend import symphony_deep_mask_cache_v93f as mask_cache
from backend import symphony_engine_v90 as core
from backend import symphony_engine_v91 as fast
from backend import symphony_scenario_lattice_v93 as deep
from backend import symphony_scenario_runtime_v93 as runtime


def _match():
    return {
        "id": 9350,
        "p1": "Alpha",
        "p2": "Beta",
        "best_of": 3,
    }


def _candidate(market="match_winner", pick="Alpha", line=None, checkpoint=None):
    return core.Candidate(
        key=f"{market}|{checkpoint or ''}|{line or ''}|{pick}",
        label=f"{market} {pick}",
        market=market,
        pick=pick,
        line=line,
        checkpoint=checkpoint,
        prod_score=80.0,
        shadow_scores={},
        path_probability=None,
        evidence_score=80.0,
        agreement=0.5,
        conflict=0.0,
    )


def _row(prob, winner, set1, set2, total_games):
    return {
        "cp2": (1, 1),
        "cp4": (2, 2),
        "cp6": (3, 3),
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


def test_shared_mask_reuses_exact_predicate_scan_for_marginal_beam_and_top_paths():
    rows = [
        _row(0.50, 1, (6, 4), (6, 3), 19),
        _row(0.20, 1, (7, 5), (6, 4), 22),
        _row(0.30, 2, (4, 6), (3, 6), 19),
    ]
    match = _match()
    candidate = _candidate()

    legacy_predicate = deep._deep_predicate(core._predicate)(match, candidate)
    legacy_mass = core._marginal(rows, legacy_predicate)
    legacy_mask = 0
    for idx, row in enumerate(rows):
        if legacy_predicate(row):
            legacy_mask |= 1 << idx

    adapter = mask_cache.install(deep)
    base_predicate = core._predicate
    try:
        rows = deep._deep_outcome_finalize(rows)
        core._predicate = deep._deep_predicate(base_predicate)

        predicate = core._predicate(match, candidate)
        cached_mass = core._marginal(rows, predicate)
        first = adapter.cache.snapshot()
        assert cached_mass == legacy_mass == 0.70
        assert first.predicate_evaluations == len(rows)
        assert first.masks == 1

        masks = fast._predicate_masks(match, [candidate], rows)
        after_beam = adapter.cache.snapshot()
        assert masks == [legacy_mask]
        assert after_beam.predicate_evaluations == first.predicate_evaluations
        assert after_beam.hits >= 1

        top = deep._top_paths_v93(match, (candidate,), rows, limit=5)
        after_paths = adapter.cache.snapshot()
        assert after_paths.predicate_evaluations == first.predicate_evaluations
        assert after_paths.hits > after_beam.hits
        assert [row["probability_mass"] for row in top] == [50.0, 20.0]
    finally:
        core._predicate = base_predicate
        adapter.uninstall()


def test_runtime_exposes_shared_mask_performance_contract(monkeypatch):
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
    assert result["performance_adapter_version"] == mask_cache.VERSION
    assert report["performance_adapter_version"] == mask_cache.VERSION
    assert report["contract"]["shared_predicate_masks_exact_equivalent"] is True
    assert report["contract"]["bookmaker_prices_used"] is False
    assert result["external_requests"] == 0
