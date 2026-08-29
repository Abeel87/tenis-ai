from __future__ import annotations

"""Fast screening + exact boundary recheck for deep MODEL/RAW Symphony beam.

Production v9.3O telemetry showed that the first BO3 still spends the watchdog
budget inside depth-2 beam scoring even though the exact predicate masks are
already built.  The expensive part is summing hundreds of large 306k-state mask
intersections in Python.

This adapter does NOT change the candidate pool, compatibility, beam width,
score formula, sort keys or final probability maths.  It uses a NumPy vector
sum only as a *screen* for the large set of expanded rows, then recomputes the
whole beam boundary with the legacy ascending-index exact accumulator before a
row can survive to the next depth.  Candidate-mask masses already computed by
v9.3F are seeded into the exact cache, so singleton scoring never re-sums the
same lattice.

Rows close to the screen cutoff are always exact-rechecked.  The screen envelope
is intentionally much wider than normal floating point reduction noise.  Exact
ties retain the original expansion order.  If NumPy is unavailable the adapter
falls back to v9.3O unchanged.

No bookmaker prices, external requests, training, settlement, thresholds or
production model inputs are touched.
"""

try:
    import numpy as np
except Exception:  # pragma: no cover - production fallback is intentionally safe
    np = None

try:
    from . import symphony_beam_mask_mass_v93o as beam
    from . import symphony_pair_matrix_v93l as pair_cache
except ImportError:
    import symphony_beam_mask_mass_v93o as beam
    import symphony_pair_matrix_v93l as pair_cache

VERSION = "v9.3P-vector-screen-exact-boundary"
SCORE_ENVELOPE = 1e-5
EXACT_HEADROOM = 32


def _sort_key(row):
    """Legacy reverse sort plus explicit stable-order tie breaker."""
    metrics = row[2]
    ordinal = row[5]
    return (
        metrics["score"],
        metrics["path_coverage"],
        metrics["avg_evidence"],
        -ordinal,
    )


def _metrics_from_joint(
    fast,
    combo: tuple,
    indexes: tuple[int, ...],
    joint,
    supported: int,
    affinity: list[list[float]],
):
    """Same v9.3O metric formula when the joint mass is already known."""
    coverage = supported / len(combo) if combo else 0.0
    avg_evidence = sum(candidate.evidence_score for candidate in combo) / len(combo)
    avg_agreement = sum(candidate.agreement for candidate in combo) / len(combo)
    conflict = max((candidate.conflict for candidate in combo), default=0.0)

    if supported >= 2 and joint is not None:
        path_component = joint * 100.0
    else:
        path_component = avg_evidence

    score = 0.55 * path_component + 0.35 * avg_evidence + 10.0 * avg_agreement - 9.0 * conflict
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


def _seed_exact_masses(shared_masks) -> dict[int, float]:
    """Reuse exact ascending-order candidate marginals already computed by v9.3F."""
    out: dict[int, float] = {}
    cache = getattr(shared_masks, "cache", None)
    masks = getattr(cache, "_masks", {}) if cache is not None else {}
    masses = getattr(cache, "_mass", {}) if cache is not None else {}
    for key, mask in masks.items():
        if key not in masses:
            continue
        # Equal truth masks have the same legacy ascending-index sum.
        out.setdefault(int(mask), float(masses[key]))
    return out


class _VectorScreenMass:
    def __init__(self, probabilities: tuple[float, ...], seeded: dict[int, float]):
        self.probabilities = probabilities
        self.count = len(probabilities)
        self.byte_count = (self.count + 7) // 8
        self.cache = dict(seeded)
        self.hits = 0
        self.sums = 0
        self.available = np is not None
        self.array = np.asarray(probabilities, dtype=np.float64) if self.available else None

    def mass(self, mask: int) -> float:
        mask = int(mask)
        if mask in self.cache:
            self.hits += 1
            return self.cache[mask]
        if not mask:
            self.cache[0] = 0.0
            self.sums += 1
            return 0.0
        if not self.available:
            raise RuntimeError("NUMPY_SCREEN_UNAVAILABLE")

        raw = mask.to_bytes(self.byte_count, "little", signed=False)
        packed = np.frombuffer(raw, dtype=np.uint8)
        bits = np.unpackbits(packed, bitorder="little", count=self.count)
        value = float(np.dot(bits, self.array))
        self.cache[mask] = value
        self.sums += 1
        return value


def _exactify_boundary(
    fast,
    rows: list,
    probabilities: tuple[float, ...],
    exact_cache: dict[int, float],
    exact_stats: dict[str, int],
    affinity: list[list[float]],
    beam_width: int,
):
    if not rows:
        return [], 0

    approx_sorted = sorted(rows, key=_sort_key, reverse=True)
    need = min(int(beam_width), len(approx_sorted))
    cutoff = float(approx_sorted[need - 1][2]["score"])

    selected = []
    selected_ids = set()
    for pos, row in enumerate(approx_sorted):
        if pos < need + EXACT_HEADROOM or float(row[2]["score"]) >= cutoff - SCORE_ENVELOPE:
            selected.append(row)
            selected_ids.add(row[5])

    def exact_row(row):
        indexes, combo, _, joint_mask, supported, ordinal = row
        joint = beam._mass(joint_mask, probabilities, exact_cache, exact_stats) if supported else None
        metrics = _metrics_from_joint(fast, combo, indexes, joint, supported, affinity)
        if (
            supported == len(combo)
            and joint is not None
            and joint <= fast.base.core.EPS
        ):
            return None
        return (indexes, combo, metrics, joint_mask, supported, ordinal)

    exact_rows = []
    exactified = 0
    for row in selected:
        checked = exact_row(row)
        exactified += 1
        if checked is not None:
            exact_rows.append(checked)

    # Extremely tiny non-zero states could be rejected by the legacy EPS gate.
    # If that leaves fewer than a full beam, exact-check more screen rows until
    # the legacy beam can be filled.
    if len(exact_rows) < need:
        for row in approx_sorted:
            if row[5] in selected_ids:
                continue
            checked = exact_row(row)
            exactified += 1
            if checked is not None:
                exact_rows.append(checked)
            if len(exact_rows) >= need:
                break

    exact_rows.sort(key=_sort_key, reverse=True)
    return exact_rows[:beam_width], exactified


def _cached_compositions(fast, shared_masks, match: dict, candidates: list, outcomes: list[dict], stats_out=None):
    cache = getattr(shared_masks, "cache", None)
    if np is None or cache is None or outcomes is not getattr(cache, "outcomes", None):
        return beam._cached_compositions(fast, match, candidates, outcomes)

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

    exact_cache = _seed_exact_masses(shared_masks)
    exact_stats = {"mass_hits": 0, "mass_sums": 0}
    screen = _VectorScreenMass(probabilities, exact_cache)
    exact_rechecks = 0

    beam_rows = []
    for idx, candidate in enumerate(pool):
        ordinal = idx
        candidate_mask = masks[idx]
        supported = 0 if candidate_mask is None else 1
        joint_mask = full_mask if candidate_mask is None else candidate_mask
        # Singleton score never uses the joint mass, but use the already-computed
        # exact marginal when available so the internal metric stays legacy-equal.
        joint = exact_cache.get(joint_mask) if supported else None
        if supported and joint is None:
            joint = screen.mass(joint_mask)
        combo = (candidate,)
        metrics = _metrics_from_joint(fast, combo, (idx,), joint, supported, affinity)
        beam_rows.append(((idx,), combo, metrics, joint_mask, supported, ordinal))

    beam_rows.sort(key=_sort_key, reverse=True)
    beam_rows = beam_rows[:fast.base.core.BEAM_WIDTH]

    out = {}
    for depth in range(2, 7):
        beam._progress(
            fast,
            "BEAM_DEPTH_START",
            beam_depth=depth,
            beam_rows=len(beam_rows),
            beam_screen_version=VERSION,
            beam_screen_cache_entries=len(screen.cache),
            beam_screen_hits=screen.hits,
            beam_screen_sums=screen.sums,
            beam_exact_cache_entries=len(exact_cache),
            beam_exact_cache_hits=exact_stats["mass_hits"],
            beam_exact_mass_sums=exact_stats["mass_sums"],
            beam_exact_rechecks=exact_rechecks,
        )

        expanded = []
        ordinal = 0
        for indexes, combo, _, parent_mask, parent_supported, _ in beam_rows:
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
                if next_supported == len(next_combo) and not next_mask:
                    continue

                if next_supported >= 2:
                    screen_joint = screen.mass(next_mask)
                elif next_supported == 1:
                    screen_joint = exact_cache.get(next_mask)
                    if screen_joint is None:
                        screen_joint = screen.mass(next_mask)
                else:
                    screen_joint = None

                metrics = _metrics_from_joint(
                    fast,
                    next_combo,
                    next_indexes,
                    screen_joint,
                    next_supported,
                    affinity,
                )
                expanded.append((
                    next_indexes,
                    next_combo,
                    metrics,
                    next_mask,
                    next_supported,
                    ordinal,
                ))
                ordinal += 1

        beam_rows, checked = _exactify_boundary(
            fast,
            expanded,
            probabilities,
            exact_cache,
            exact_stats,
            affinity,
            fast.base.core.BEAM_WIDTH,
        )
        exact_rechecks += checked

        beam._progress(
            fast,
            "BEAM_DEPTH_DONE",
            beam_depth=depth,
            expanded_rows=len(expanded),
            beam_rows=len(beam_rows),
            beam_screen_version=VERSION,
            beam_screen_cache_entries=len(screen.cache),
            beam_screen_hits=screen.hits,
            beam_screen_sums=screen.sums,
            beam_exact_cache_entries=len(exact_cache),
            beam_exact_cache_hits=exact_stats["mass_hits"],
            beam_exact_mass_sums=exact_stats["mass_sums"],
            beam_exact_rechecks=exact_rechecks,
            beam_score_envelope=SCORE_ENVELOPE,
        )

        if not beam_rows:
            break

        _, best_combo, best_metrics, _, _, _ = beam_rows[0]
        out[str(depth)] = {
            **fast.base.core._scenario_payload(match, best_combo, best_metrics, outcomes),
            "legs": depth,
            "alternatives": [
                fast.base.core._scenario_payload(match, combo, metrics, outcomes)
                for _, combo, metrics, _, _, _ in beam_rows[1:4]
            ],
        }

    if isinstance(stats_out, dict):
        stats_out.update({
            "screen_sums": int(screen.sums),
            "screen_hits": int(screen.hits),
            "screen_cache_entries": int(len(screen.cache)),
            "exact_mass_sums": int(exact_stats["mass_sums"]),
            "exact_mass_hits": int(exact_stats["mass_hits"]),
            "exact_rechecks": int(exact_rechecks),
        })
    return out


class InstalledAdapter:
    def __init__(self, fast_module, shared_masks) -> None:
        self.fast = fast_module
        self.shared_masks = shared_masks
        self.original = None
        self.last_stats = {}

    def install(self):
        if self.original is not None:
            return self
        self.original = self.fast._fast_one_pass_compositions
        fast = self.fast
        shared = self.shared_masks
        adapter = self

        def cached(match: dict, candidates: list, outcomes: list[dict]):
            stats = {}
            result = _cached_compositions(fast, shared, match, candidates, outcomes, stats_out=stats)
            adapter.last_stats = stats
            return result

        self.fast._fast_one_pass_compositions = cached
        return self

    def uninstall(self) -> None:
        if self.original is None:
            return
        self.fast._fast_one_pass_compositions = self.original
        self.original = None


def install(fast_module, shared_masks) -> InstalledAdapter:
    return InstalledAdapter(fast_module, shared_masks).install()
