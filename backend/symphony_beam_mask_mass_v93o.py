from __future__ import annotations

"""Exact-equivalent beam joint-mask/mass reuse for deep MODEL/RAW Symphony.

v9.3M showed the production timeout happens inside BEAM_COMPOSITIONS after the
306k-state BO3 lattice is already built. v9.3F caches candidate predicate masks,
v9.3L caches pair compatibility/affinity and v9.3N makes payload top-path work
bounded, but beam scoring still recomputed the same exact-state intersection and
re-summed matching outcome probabilities for every expanded combination.

This adapter keeps the same candidate pool, beam width, candidate order,
compatibility rules, score formula, sort keys and exact probability accumulation
order. It only carries the parent's joint truth-mask forward, intersects one new
candidate mask, and memoizes probability mass by the resulting exact mask.

No bookmaker prices, external requests, training or settlement inputs are used.
"""

try:
    from . import symphony_pair_matrix_v93l as pair_cache
except ImportError:
    import symphony_pair_matrix_v93l as pair_cache

VERSION = "v9.3O-beam-joint-mask-mass-cache"


def _mass(mask: int, probabilities: tuple[float, ...], cache: dict[int, float], stats: dict[str, int]) -> float:
    if mask in cache:
        stats["mass_hits"] = stats.get("mass_hits", 0) + 1
        return cache[mask]
    probability = 0.0
    work = mask
    # Exact legacy order: lowest matching outcome index first.
    while work:
        bit = work & -work
        idx = bit.bit_length() - 1
        probability += probabilities[idx]
        work ^= bit
    cache[mask] = probability
    stats["mass_sums"] = stats.get("mass_sums", 0) + 1
    return probability


def _metrics(
    fast,
    combo: tuple,
    indexes: tuple[int, ...],
    joint_mask: int,
    supported: int,
    probabilities: tuple[float, ...],
    mass_cache: dict[int, float],
    stats: dict[str, int],
    affinity: list[list[float]],
):
    joint = _mass(joint_mask, probabilities, mass_cache, stats) if supported else None
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


def _progress(fast, stage: str, **extra) -> None:
    hook = getattr(fast, "_deep_beam_progress_hook", None)
    if callable(hook):
        hook(stage, **extra)


def _cached_compositions(fast, match: dict, candidates: list, outcomes: list[dict]):
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
    compatible, affinity = pair_cache._pair_tables(fast, pool)
    mass_cache: dict[int, float] = {}
    stats = {"mass_hits": 0, "mass_sums": 0}

    beam = []
    for idx, candidate in enumerate(pool):
        candidate_mask = masks[idx]
        supported = 0 if candidate_mask is None else 1
        joint_mask = full_mask if candidate_mask is None else candidate_mask
        combo = (candidate,)
        metrics = _metrics(
            fast,
            combo,
            (idx,),
            joint_mask,
            supported,
            probabilities,
            mass_cache,
            stats,
            affinity,
        )
        beam.append(((idx,), combo, metrics, joint_mask, supported))
    beam.sort(key=lambda row: (row[2]["score"], row[2]["path_coverage"]), reverse=True)
    beam = beam[:fast.base.core.BEAM_WIDTH]

    out = {}
    for depth in range(2, 7):
        _progress(
            fast,
            "BEAM_DEPTH_START",
            beam_depth=depth,
            beam_rows=len(beam),
            beam_mass_cache_entries=len(mass_cache),
            beam_mass_cache_hits=stats["mass_hits"],
            beam_mass_sums=stats["mass_sums"],
        )
        expanded = []
        for indexes, combo, _, parent_mask, parent_supported in beam:
            start = indexes[-1] + 1
            for idx in range(start, len(pool)):
                if any(not compatible[old_idx][idx] for old_idx in indexes):
                    continue
                candidate = pool[idx]
                candidate_mask = masks[idx]
                if candidate_mask is None:
                    next_mask = parent_mask
                    next_supported = parent_supported
                else:
                    next_mask = parent_mask & candidate_mask
                    next_supported = parent_supported + 1
                next_indexes = indexes + (idx,)
                next_combo = combo + (candidate,)
                metrics = _metrics(
                    fast,
                    next_combo,
                    next_indexes,
                    next_mask,
                    next_supported,
                    probabilities,
                    mass_cache,
                    stats,
                    affinity,
                )
                if (
                    metrics["supported_legs"] == len(next_combo)
                    and metrics["joint_supported_only"] is not None
                    and metrics["joint_supported_only"] <= fast.base.core.EPS
                ):
                    continue
                expanded.append((next_indexes, next_combo, metrics, next_mask, next_supported))

        expanded.sort(
            key=lambda row: (
                row[2]["score"],
                row[2]["path_coverage"],
                row[2]["avg_evidence"],
            ),
            reverse=True,
        )
        beam = expanded[:fast.base.core.BEAM_WIDTH]
        _progress(
            fast,
            "BEAM_DEPTH_DONE",
            beam_depth=depth,
            expanded_rows=len(expanded),
            beam_rows=len(beam),
            beam_mass_cache_entries=len(mass_cache),
            beam_mass_cache_hits=stats["mass_hits"],
            beam_mass_sums=stats["mass_sums"],
        )
        if not beam:
            break

        _, best_combo, best_metrics, _, _ = beam[0]
        out[str(depth)] = {
            **fast.base.core._scenario_payload(match, best_combo, best_metrics, outcomes),
            "legs": depth,
            "alternatives": [
                fast.base.core._scenario_payload(match, combo, metrics, outcomes)
                for _, combo, metrics, _, _ in beam[1:4]
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
