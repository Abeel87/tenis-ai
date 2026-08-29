from __future__ import annotations

from types import SimpleNamespace

from backend import symphony_beam_mask_mass_v93o as exact_beam
from backend import symphony_beam_screen_v93p as screen_beam
from backend import symphony_engine_v90 as core
from backend import symphony_engine_v91 as fast
from backend import symphony_scenario_runtime_v93 as runtime


def _candidate(idx: int, evidence: float):
    return core.Candidate(
        key=f"c{idx}",
        label=f"candidate {idx}",
        market=f"synthetic_{idx}",
        pick=f"pick_{idx}",
        line=None,
        checkpoint=None,
        prod_score=evidence,
        shadow_scores={},
        path_probability=None,
        evidence_score=evidence,
        agreement=0.45 + idx * 0.025,
        conflict=0.01 * (idx % 4),
    )


def _mass(mask, outcomes):
    if mask is None:
        return None
    total = 0.0
    work = int(mask)
    while work:
        bit = work & -work
        idx = bit.bit_length() - 1
        total += outcomes[idx]["prob"]
        work ^= bit
    return total


def _shared(outcomes, candidates, mask_by_key):
    masks = {}
    masses = {}
    for candidate in candidates:
        mask = mask_by_key[candidate.key]
        if mask is None:
            continue
        key = (candidate.key,)
        masks[key] = mask
        masses[key] = _mass(mask, outcomes)
    cache = SimpleNamespace(outcomes=outcomes, _masks=masks, _mass=masses)
    return SimpleNamespace(cache=cache)


def _payload(match, combo, metrics, rows):
    return {
        "keys": [c.key for c in combo],
        "score": metrics["score"],
        "joint": metrics["joint"],
        "joint_supported_only": metrics["joint_supported_only"],
        "path_coverage": metrics["path_coverage"],
        "supported_legs": metrics["supported_legs"],
        "avg_evidence": metrics["avg_evidence"],
        "agreement": metrics["agreement"],
        "conflict": metrics["conflict"],
        "coverage_adjustment": metrics["coverage_adjustment"],
    }


def test_v93p_screen_survivors_are_exact_v93o_equivalent(monkeypatch):
    raw = [1.0 + ((idx * 17) % 11) / 10.0 for idx in range(96)]
    denom = sum(raw)
    outcomes = [{"prob": value / denom} for value in raw]
    candidates = [_candidate(i, 94.0 - i * 2.1) for i in range(10)]

    full = (1 << len(outcomes)) - 1
    mask_by_key = {
        "c0": full,
        "c1": sum(1 << i for i in range(len(outcomes)) if i % 2 == 0),
        "c2": sum(1 << i for i in range(len(outcomes)) if i % 3 != 0),
        "c3": sum(1 << i for i in range(len(outcomes)) if i % 4 in {0, 1}),
        "c4": sum(1 << i for i in range(len(outcomes)) if i % 5 <= 2),
        "c5": sum(1 << i for i in range(len(outcomes)) if i % 7 <= 3),
        "c6": sum(1 << i for i in range(len(outcomes)) if i % 8 in {1, 2, 3, 4}),
        "c7": sum(1 << i for i in range(len(outcomes)) if i % 9 not in {0, 8}),
        "c8": full,
        "c9": None,
    }
    mask_by_key["c8"] = mask_by_key["c4"]  # deliberate duplicate truth mask

    monkeypatch.setattr(fast, "_predicate_masks", lambda match, pool, rows: [mask_by_key[c.key] for c in pool])
    monkeypatch.setattr(fast.base.core, "_scenario_payload", _payload)

    shared = _shared(outcomes, candidates, mask_by_key)
    match = {"id": 9390, "p1": "Alpha", "p2": "Beta", "best_of": 3}

    exact = exact_beam._cached_compositions(fast, match, candidates, outcomes)
    stats = {}
    screened = screen_beam._cached_compositions(
        fast, shared, match, candidates, outcomes, stats_out=stats
    )

    assert screened == exact
    assert stats["screen_sums"] > 0
    assert stats["exact_rechecks"] > 0
    assert screen_beam.VERSION == "v9.3P-vector-screen-exact-boundary"
    assert runtime.BEAM_SCREEN_VERSION == screen_beam.VERSION
    assert runtime.VERSION == "v9.3C-runtime-compact-bo5"


def test_v93p_rechecks_near_cutoff_and_preserves_stable_exact_order(monkeypatch):
    outcomes = [
        {"prob": 0.1000000000001},
        {"prob": 0.0999999999999},
        {"prob": 0.2},
        {"prob": 0.2},
        {"prob": 0.2},
        {"prob": 0.2},
    ]
    candidates = [_candidate(i, 88.0 - i * 0.001) for i in range(6)]
    mask_by_key = {
        "c0": 0b111111,
        "c1": 0b111011,
        "c2": 0b110111,
        "c3": 0b101111,
        "c4": 0b011111,
        "c5": 0b001111,
    }
    shared = _shared(outcomes, candidates, mask_by_key)

    monkeypatch.setattr(fast, "_predicate_masks", lambda match, pool, rows: [mask_by_key[c.key] for c in pool])
    monkeypatch.setattr(fast.base.core, "_scenario_payload", _payload)
    monkeypatch.setattr(fast.base.core, "BEAM_WIDTH", 3)

    match = {"id": 9391, "p1": "Alpha", "p2": "Beta", "best_of": 3}
    exact = exact_beam._cached_compositions(fast, match, candidates, outcomes)
    screened = screen_beam._cached_compositions(fast, shared, match, candidates, outcomes)

    assert screened == exact


def test_v93p_seeds_candidate_masses_from_v93f_without_resumming():
    outcomes = [{"prob": 0.2}, {"prob": 0.3}, {"prob": 0.5}]
    candidates = [_candidate(0, 90.0), _candidate(1, 89.0)]
    masks = {"c0": 0b101, "c1": 0b011}
    shared = _shared(outcomes, candidates, masks)

    seeded = screen_beam._seed_exact_masses(shared)
    assert seeded[0b101] == 0.7
    assert seeded[0b011] == 0.5
