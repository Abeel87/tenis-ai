from __future__ import annotations

from types import SimpleNamespace

from backend import symphony_beam_screen_v93p as screen_p
from backend import symphony_beam_screen_v93q as screen_q
from backend import symphony_engine_v90 as core
from backend import symphony_engine_v91 as fast
from backend import symphony_scenario_runtime_v93 as runtime


def _candidate(idx: int, evidence: float):
    return core.Candidate(
        key=f"q{idx}",
        label=f"candidate {idx}",
        market=f"synthetic_q_{idx}",
        pick=f"pick_{idx}",
        line=None,
        checkpoint=None,
        prod_score=evidence,
        shadow_scores={},
        path_probability=None,
        evidence_score=evidence,
        agreement=0.52 + idx * 0.015,
        conflict=0.01 * (idx % 3),
    )


def _legacy_mass(mask: int, outcomes: list[dict]) -> float:
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
        masses[key] = _legacy_mass(mask, outcomes)
    return SimpleNamespace(cache=SimpleNamespace(outcomes=outcomes, _masks=masks, _mass=masses))


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


def test_v93q_byte_lut_screen_mass_tracks_v93p_screen_inside_safety_envelope():
    raw = [1.0 + ((idx * 29) % 17) / 13.0 for idx in range(8193)]
    denom = sum(raw)
    probabilities = tuple(value / denom for value in raw)
    mask = sum(1 << idx for idx in range(len(probabilities)) if idx % 7 not in {0, 6})

    old = screen_p._VectorScreenMass(probabilities, {})
    new = screen_q._ByteLookupScreenMass(probabilities, {})
    old_value = old.mass(mask)
    new_value = new.mass(mask)

    assert abs(new_value - old_value) < screen_q.SCORE_ENVELOPE / 100.0


def test_v93q_compositions_are_exact_v93p_equivalent(monkeypatch):
    raw = [1.0 + ((idx * 19) % 23) / 10.0 for idx in range(512)]
    denom = sum(raw)
    outcomes = [{"prob": value / denom} for value in raw]
    candidates = [_candidate(i, 96.0 - i * 1.7) for i in range(12)]

    full = (1 << len(outcomes)) - 1
    mask_by_key = {
        "q0": full,
        "q1": sum(1 << i for i in range(len(outcomes)) if i % 2 == 0),
        "q2": sum(1 << i for i in range(len(outcomes)) if i % 3 != 0),
        "q3": sum(1 << i for i in range(len(outcomes)) if i % 4 in {0, 1}),
        "q4": sum(1 << i for i in range(len(outcomes)) if i % 5 <= 2),
        "q5": sum(1 << i for i in range(len(outcomes)) if i % 7 <= 3),
        "q6": sum(1 << i for i in range(len(outcomes)) if i % 8 in {1, 2, 3, 4}),
        "q7": sum(1 << i for i in range(len(outcomes)) if i % 9 not in {0, 8}),
        "q8": sum(1 << i for i in range(len(outcomes)) if i % 11 <= 6),
        "q9": sum(1 << i for i in range(len(outcomes)) if i % 13 <= 8),
        "q10": full,
        "q11": None,
    }
    mask_by_key["q10"] = mask_by_key["q4"]

    monkeypatch.setattr(fast, "_predicate_masks", lambda match, pool, rows: [mask_by_key[c.key] for c in pool])
    monkeypatch.setattr(fast.base.core, "_scenario_payload", _payload)

    shared = _shared(outcomes, candidates, mask_by_key)
    match = {"id": 9392, "p1": "Alpha", "p2": "Beta", "best_of": 3}

    exact_p = screen_p._cached_compositions(fast, shared, match, candidates, outcomes)
    stats = {}
    exact_q = screen_q._cached_compositions(
        fast, shared, match, candidates, outcomes, stats_out=stats
    )

    assert exact_q == exact_p
    assert stats["screen_sums"] > 0
    assert stats["exact_rechecks"] > 0
    assert runtime.BEAM_SCREEN_VERSION == screen_q.VERSION
    assert runtime.VERSION == "v9.3C-runtime-compact-bo5"


def test_v93q_install_restores_v93p_module_class_and_version():
    original_class = screen_p._VectorScreenMass
    original_version = screen_p.VERSION
    fake_shared = SimpleNamespace(cache=SimpleNamespace(outcomes=[]))

    installed = screen_q.install(fast, fake_shared)
    try:
        assert screen_p._VectorScreenMass is screen_q._ByteLookupScreenMass
        assert screen_p.VERSION == screen_q.VERSION
    finally:
        installed.uninstall()

    assert screen_p._VectorScreenMass is original_class
    assert screen_p.VERSION == original_version
