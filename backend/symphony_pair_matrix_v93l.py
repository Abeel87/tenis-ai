from __future__ import annotations

"""Semantics-preserving pair matrix cache for deep MODEL/RAW Symphony.

The v9.3F/v9.3K adapters already reuse exact-state predicate work. The remaining
beam hot path repeatedly asked the same candidate pairs whether they were
compatible and recalculated the same pair affinity for every expanded combo.

This adapter computes those pair-only values once for the stable, sorted candidate
pool and then reuses them. Candidate order, pool size, beam width, predicate masks,
probability accumulation, score formula, sort keys and payload generation are
unchanged. No bookmaker price or external request is involved.
"""

VERSION = "v9.3L-pair-matrix-cache"


def _pair_tables(fast, pool: list):
    """Return exact core compatibility/affinity values for every pool pair once."""
    size = len(pool)
    compatible = [[True] * size for _ in range(size)]
    affinity = [[0.0] * size for _ in range(size)]

    for i in range(size):
        for j in range(i + 1, size):
            a = pool[i]
            b = pool[j]
            ok = bool(fast.base.core._compatible(a, b))
            compatible[i][j] = compatible[j][i] = ok
            # core._pair_affinity returns the hard reject sentinel for an
            # incompatible pair. Reuse that exact value without a redundant
            # second compatibility call in that case.
            value = fast.base.core._pair_affinity(a, b) if ok else -1e9
            affinity[i][j] = affinity[j][i] = value

    return compatible, affinity


def _fast_metrics(fast, combo: tuple, indexes: tuple[int, ...], masks: list,
                  probabilities: tuple[float, ...], full_mask: int,
                  affinity: list[list[float]]):
    """Exact v9.2.4 metric formula using precomputed pair-only values."""
    joint, supported = fast._masked_joint(indexes, masks, probabilities, full_mask)
    coverage = supported / len(combo) if combo else 0.0
    avg_evidence = sum(candidate.evidence_score for candidate in combo) / len(combo)
    avg_agreement = sum(candidate.agreement for candidate in combo) / len(combo)
    conflict = max((candidate.conflict for candidate in combo), default=0.0)

    if supported >= 2 and joint is not None:
        path_component = joint * 100.0
    else:
        path_component = avg_evidence

    score = 0.55 * path_component + 0.35 * avg_evidence + 10.0 * avg_agreement - 9.0 * conflict
    # Preserve the legacy nested i/j summation order exactly.
    score += sum(
        affinity[indexes[i]][indexes[j]]
        for i in range(len(combo))
        for j in range(i + 1, len(combo))
    ) / max(1, len(combo))
    score = max(0.0, min(100.0, score))

    out = {
        "score": score,
        "joint": joint if coverage == 1.0 else None,
        "joint_supported_only": joint,
        "path_coverage": coverage,
        "supported_legs": supported,
        "avg_evidence": avg_evidence,
        "agreement": avg_agreement,
        "conflict": conflict,
    }

    adjustment = -28.0 * (1.0 - coverage)
    if coverage >= 0.999:
        adjustment += 5.0
    elif coverage >= 0.75:
        adjustment += 2.0
    if supported >= 2 and joint is not None:
        adjustment += 2.0
    out["coverage_adjustment"] = round(adjustment, 4)
    out["score"] = max(0.0, min(100.0, score + adjustment))
    return out


def _cached_compositions(fast, match: dict, candidates: list, outcomes: list[dict]):
    """Exact fast beam with pair compatibility/affinity reused from a matrix."""
    pool = sorted(
        candidates,
        key=lambda candidate: (candidate.evidence_score, candidate.agreement, -candidate.conflict),
        reverse=True,
    )[:fast.base.core.POOL_LIMIT]
    if len(pool) < 2:
        return {}

    masks = fast._predicate_masks(match, pool, outcomes)
    probabilities = tuple(float(outcome["prob"]) for outcome in outcomes)
    full_mask = (1 << len(outcomes)) - 1 if outcomes else 0
    compatible, affinity = _pair_tables(fast, pool)

    beam = []
    for idx, candidate in enumerate(pool):
        combo = (candidate,)
        metrics = _fast_metrics(fast, combo, (idx,), masks, probabilities, full_mask, affinity)
        beam.append(((idx,), combo, metrics))
    beam.sort(key=lambda row: (row[2]["score"], row[2]["path_coverage"]), reverse=True)
    beam = beam[:fast.base.core.BEAM_WIDTH]

    out = {}
    for depth in range(2, 7):
        expanded = []
        for indexes, combo, _ in beam:
            start = indexes[-1] + 1
            for idx in range(start, len(pool)):
                if any(not compatible[old_idx][idx] for old_idx in indexes):
                    continue
                candidate = pool[idx]
                next_indexes = indexes + (idx,)
                next_combo = combo + (candidate,)
                metrics = _fast_metrics(
                    fast, next_combo, next_indexes, masks, probabilities, full_mask, affinity
                )
                if (
                    metrics["supported_legs"] == len(next_combo)
                    and metrics["joint_supported_only"] is not None
                    and metrics["joint_supported_only"] <= fast.base.core.EPS
                ):
                    continue
                expanded.append((next_indexes, next_combo, metrics))

        expanded.sort(
            key=lambda row: (
                row[2]["score"],
                row[2]["path_coverage"],
                row[2]["avg_evidence"],
            ),
            reverse=True,
        )
        beam = expanded[:fast.base.core.BEAM_WIDTH]
        if not beam:
            break

        _, best_combo, best_metrics = beam[0]
        out[str(depth)] = {
            **fast.base.core._scenario_payload(match, best_combo, best_metrics, outcomes),
            "legs": depth,
            "alternatives": [
                fast.base.core._scenario_payload(match, combo, metrics, outcomes)
                for _, combo, metrics in beam[1:4]
            ],
        }
    return out


class InstalledAdapter:
    def __init__(self, fast_module) -> None:
        self.fast = fast_module
        self.original = None

    def install(self):
        if self.original is not None:
            return self
        self.original = self.fast._fast_one_pass_compositions
        fast = self.fast

        def cached(match: dict, candidates: list, outcomes: list[dict]):
            return _cached_compositions(fast, match, candidates, outcomes)

        self.fast._fast_one_pass_compositions = cached
        return self

    def uninstall(self) -> None:
        if self.original is None:
            return
        self.fast._fast_one_pass_compositions = self.original
        self.original = None


def install(fast_module) -> InstalledAdapter:
    return InstalledAdapter(fast_module).install()
