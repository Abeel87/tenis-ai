from __future__ import annotations

from backend import symphony_beam_mask_mass_v93o as beam_mass
from backend import symphony_engine_v90 as core
from backend import symphony_engine_v91 as fast
from backend import symphony_pair_matrix_v93l as pair_cache
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
        agreement=0.55 + idx * 0.01,
        conflict=0.02 * idx,
    )


def test_v93o_beam_output_is_exact_pair_matrix_equivalent(monkeypatch):
    outcomes = [
        {"prob": 0.11},
        {"prob": 0.17},
        {"prob": 0.13},
        {"prob": 0.19},
        {"prob": 0.23},
        {"prob": 0.17},
    ]
    candidates = [_candidate(i, 90.0 - i * 3.0) for i in range(6)]
    mask_by_key = {
        "c0": 0b111011,
        "c1": 0b111011,  # deliberate identical truth mask: mass reuse must be legal
        "c2": 0b110010,
        "c3": 0b011110,
        "c4": 0b001010,
        "c5": None,      # preserve evidence-only/unsupported coverage semantics
    }

    def fake_masks(match, pool, rows):
        assert rows is outcomes
        return [mask_by_key[c.key] for c in pool]

    def fake_payload(match, combo, metrics, rows):
        assert rows is outcomes
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

    monkeypatch.setattr(fast, "_predicate_masks", fake_masks)
    monkeypatch.setattr(fast.base.core, "_scenario_payload", fake_payload)

    match = {"id": 9300, "p1": "Alpha", "p2": "Beta", "best_of": 3}
    legacy = pair_cache._cached_compositions(fast, match, candidates, outcomes)
    cached = beam_mass._cached_compositions(fast, match, candidates, outcomes)

    assert cached == legacy


def test_v93o_probability_mass_keeps_legacy_order_and_memoizes_identical_mask():
    probabilities = (0.11, 0.17, 0.13, 0.19, 0.23, 0.17)
    mask = 0b101101
    memo = {}
    stats = {"mass_hits": 0, "mass_sums": 0}

    expected = 0.0
    for idx in (0, 2, 3, 5):
        expected += probabilities[idx]

    first = beam_mass._mass(mask, probabilities, memo, stats)
    second = beam_mass._mass(mask, probabilities, memo, stats)

    assert first == expected
    assert second == expected
    assert stats == {"mass_hits": 1, "mass_sums": 1}


def test_v93o_emits_zero_influence_depth_progress_without_changing_runtime_contract(monkeypatch):
    outcomes = [{"prob": 0.4}, {"prob": 0.35}, {"prob": 0.25}]
    candidates = [_candidate(i, 85.0 - i) for i in range(4)]
    masks = {"c0": 0b111, "c1": 0b011, "c2": 0b101, "c3": 0b001}
    events = []

    monkeypatch.setattr(fast, "_predicate_masks", lambda match, pool, rows: [masks[c.key] for c in pool])
    monkeypatch.setattr(fast.base.core, "_scenario_payload", lambda match, combo, metrics, rows: {"keys": [c.key for c in combo]})
    monkeypatch.setattr(fast, "_deep_beam_progress_hook", lambda stage, **extra: events.append((stage, extra)), raising=False)

    beam_mass._cached_compositions(
        fast,
        {"id": 9301, "p1": "Alpha", "p2": "Beta", "best_of": 3},
        candidates,
        outcomes,
    )

    assert any(stage == "BEAM_DEPTH_START" for stage, _ in events)
    assert any(stage == "BEAM_DEPTH_DONE" for stage, _ in events)
    assert beam_mass.VERSION == "v9.3O-beam-joint-mask-mass-cache"
    assert runtime.BEAM_MASK_MASS_VERSION == beam_mass.VERSION
    assert runtime.VERSION == "v9.3C-runtime-compact-bo5"
