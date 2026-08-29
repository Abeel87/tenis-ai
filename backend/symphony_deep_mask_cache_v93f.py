from __future__ import annotations

"""Shared exact-state predicate mask cache for deep MODEL/RAW Symphony.

This adapter changes only runtime evaluation reuse. The underlying predicates,
outcome probabilities, beam ranking maths and report semantics stay unchanged.
Each supported candidate predicate is evaluated against the current exact-state
outcomes at most once per match; the resulting bit mask is then reused by:
- candidate marginal probability scoring;
- the v9.2.4 fast beam mask adapter;
- deep top-path extraction;
- v9.3K payload fragility/top-path generation inside ``_scenario_payload``.

No bookmaker prices or external requests are used.
"""

from dataclasses import dataclass

try:
    from . import symphony_engine_v90 as core
    from . import symphony_engine_v91 as fast
except ImportError:
    import symphony_engine_v90 as core
    import symphony_engine_v91 as fast

# Historical contract kept stable for existing consumers/tests.
VERSION = "v9.3F-shared-predicate-masks"
PAYLOAD_REUSE_VERSION = "v9.3K-payload-mask-reuse"
_CACHE_KEY_ATTR = "_tenis_ai_v93f_mask_key"


def _candidate_key(candidate) -> tuple:
    return (
        str(getattr(candidate, "key", "") or ""),
        str(getattr(candidate, "market", "") or ""),
        str(getattr(candidate, "pick", "") or ""),
        getattr(candidate, "line", None),
        getattr(candidate, "checkpoint", None),
    )


@dataclass
class _Snapshot:
    masks: int = 0
    hits: int = 0
    predicate_evaluations: int = 0
    payload_joint_reuses: int = 0


class PredicateMaskCache:
    def __init__(self) -> None:
        self.outcomes: list[dict] | None = None
        self.probabilities: tuple[float, ...] = ()
        self.full_mask = 0
        self._masks: dict[tuple, int] = {}
        self._mass: dict[tuple, float] = {}
        self.hits = 0
        self.predicate_evaluations = 0
        self.payload_joint_reuses = 0

    def begin(self, outcomes: list[dict]) -> list[dict]:
        self.outcomes = outcomes
        self.probabilities = tuple(float(row.get("prob") or 0.0) for row in outcomes)
        self.full_mask = (1 << len(outcomes)) - 1 if outcomes else 0
        self._masks = {}
        self._mass = {}
        self.hits = 0
        self.predicate_evaluations = 0
        self.payload_joint_reuses = 0
        return outcomes

    def tag(self, predicate, candidate):
        if predicate is not None:
            setattr(predicate, _CACHE_KEY_ATTR, _candidate_key(candidate))
        return predicate

    def _ensure(self, key: tuple, predicate) -> tuple[int, float]:
        if key in self._masks:
            self.hits += 1
            return self._masks[key], self._mass[key]

        mask = 0
        mass = 0.0
        rows = self.outcomes or []
        for idx, outcome in enumerate(rows):
            self.predicate_evaluations += 1
            if predicate(outcome):
                mask |= 1 << idx
                mass += self.probabilities[idx]
        self._masks[key] = mask
        self._mass[key] = mass
        return mask, mass

    def marginal(self, outcomes, predicate, fallback):
        if outcomes is not self.outcomes or predicate is None:
            return fallback(outcomes, predicate)
        key = getattr(predicate, _CACHE_KEY_ATTR, None)
        if key is None:
            return fallback(outcomes, predicate)
        _, mass = self._ensure(key, predicate)
        return mass

    def masks_for_pool(self, match: dict, pool: list, outcomes, fallback):
        if outcomes is not self.outcomes:
            return fallback(match, pool, outcomes)
        masks = []
        for candidate in pool:
            predicate = core._predicate(match, candidate)
            if predicate is None:
                masks.append(None)
                continue
            key = getattr(predicate, _CACHE_KEY_ATTR, _candidate_key(candidate))
            mask, _ = self._ensure(key, predicate)
            masks.append(mask)
        return masks

    def matching_rows(self, match: dict, combo, outcomes):
        if outcomes is not self.outcomes:
            return None
        mask = self.full_mask
        supported = 0
        for candidate in combo:
            predicate = core._predicate(match, candidate)
            if predicate is None:
                continue
            supported += 1
            key = getattr(predicate, _CACHE_KEY_ATTR, _candidate_key(candidate))
            candidate_mask, _ = self._ensure(key, predicate)
            mask &= candidate_mask
            if not mask:
                break
        if not supported:
            return []

        rows = []
        while mask:
            bit = mask & -mask
            idx = bit.bit_length() - 1
            rows.append(outcomes[idx])
            mask ^= bit
        return rows

    def joint_for_combo(self, match: dict, combo, outcomes):
        """Exact-equivalent ``core._joint`` using cached candidate truth masks.

        Matching outcome probabilities are accumulated in ascending original
        outcome index order, preserving the same floating-point addition order as
        the legacy implementation.
        """
        if outcomes is not self.outcomes:
            return None
        mask = self.full_mask
        supported = 0
        for candidate in combo:
            predicate = core._predicate(match, candidate)
            if predicate is None:
                continue
            supported += 1
            key = getattr(predicate, _CACHE_KEY_ATTR, _candidate_key(candidate))
            candidate_mask, _ = self._ensure(key, predicate)
            mask &= candidate_mask
            if not mask:
                self.payload_joint_reuses += 1
                return 0.0, supported
        if not supported:
            return None, 0

        probability = 0.0
        while mask:
            bit = mask & -mask
            idx = bit.bit_length() - 1
            probability += self.probabilities[idx]
            mask ^= bit
        self.payload_joint_reuses += 1
        return probability, supported

    def snapshot(self) -> _Snapshot:
        return _Snapshot(
            masks=len(self._masks),
            hits=self.hits,
            predicate_evaluations=self.predicate_evaluations,
            payload_joint_reuses=self.payload_joint_reuses,
        )


class InstalledAdapter:
    def __init__(self, deep_module) -> None:
        self.deep = deep_module
        self.cache = PredicateMaskCache()
        self._installed = False

    def install(self):
        if self._installed:
            return self
        deep = self.deep
        cache = self.cache

        self.original_finalize = deep._deep_outcome_finalize
        self.original_predicate_factory = deep._deep_predicate
        self.original_top_paths = deep._top_paths_v93
        self.original_build_match = deep.build_match_model_scenario
        self.original_marginal = core._marginal
        self.original_fast_masks = fast._predicate_masks
        self.original_core_top_paths = core._top_matching_paths
        self.original_fragility = core._fragility

        def finalize(outcomes):
            return cache.begin(self.original_finalize(outcomes))

        def predicate_factory(base_predicate):
            regular = self.original_predicate_factory(base_predicate)

            def predicate(match: dict, candidate):
                return cache.tag(regular(match, candidate), candidate)

            return predicate

        def marginal(outcomes, predicate):
            return cache.marginal(outcomes, predicate, self.original_marginal)

        def predicate_masks(match: dict, pool: list, outcomes: list[dict]):
            return cache.masks_for_pool(match, pool, outcomes, self.original_fast_masks)

        def top_paths(match: dict, combo, outcomes: list[dict], limit=5):
            rows = cache.matching_rows(match, combo, outcomes)
            if rows is None:
                return self.original_top_paths(match, combo, outcomes, limit=limit)
            rows.sort(key=lambda row: row["prob"], reverse=True)
            out = []
            for row in rows[:limit]:
                out.append({
                    "path": deep._path_text_v93(row),
                    "set1": f"{row['set1'][0]}:{row['set1'][1]}",
                    "set2": f"{row['set2'][0]}:{row['set2'][1]}",
                    "set3": f"{row['set3'][0]}:{row['set3'][1]}" if row.get("set3") else None,
                    "match_score": f"{row['sets'][0]}:{row['sets'][1]}",
                    "total_games": row["total_games"],
                    "probability_mass": round(row["prob"] * 100.0, 3),
                })
            return out

        def core_top_paths(match: dict, combo, outcomes: list[dict], limit=5):
            rows = cache.matching_rows(match, combo, outcomes)
            if rows is None:
                return self.original_core_top_paths(match, combo, outcomes, limit=limit)
            rows.sort(key=lambda row: row["prob"], reverse=True)
            return [
                {
                    "path": core._path_text(row),
                    "cp2": f"{row['cp2'][0]}:{row['cp2'][1]}",
                    "cp4": f"{row['cp4'][0]}:{row['cp4'][1]}",
                    "cp6": f"{row['cp6'][0]}:{row['cp6'][1]}",
                    "set1": f"{row['set1'][0]}:{row['set1'][1]}",
                    "match_score": f"{row['sets'][0]}:{row['sets'][1]}",
                    "total_games": row["total_games"],
                    "probability_mass": round(row["prob"] * 100.0, 3),
                }
                for row in rows[:limit]
            ]

        def fragility(match: dict, combo, outcomes: list[dict]):
            if outcomes is not cache.outcomes:
                return self.original_fragility(match, combo, outcomes)
            if len(combo) < 2:
                return []

            full = cache.joint_for_combo(match, combo, outcomes)
            if full is None:
                return self.original_fragility(match, combo, outcomes)
            full_joint, full_supported = full
            rows = []
            for i, candidate in enumerate(combo):
                reduced = combo[:i] + combo[i + 1:]
                reduced_result = cache.joint_for_combo(match, reduced, outcomes)
                if reduced_result is None:
                    return self.original_fragility(match, combo, outcomes)
                reduced_joint, reduced_supported = reduced_result
                lift = 0.0
                if (
                    full_joint is not None
                    and reduced_joint is not None
                    and full_joint > core.EPS
                    and full_supported == len(combo)
                    and reduced_supported == len(reduced)
                ):
                    lift = max(0.0, (reduced_joint / full_joint - 1.0) * 20.0)
                frag = (
                    (100.0 - candidate.evidence_score)
                    + 18.0 * candidate.conflict
                    + min(50.0, lift)
                )
                rows.append({
                    "key": candidate.key,
                    "label": candidate.label,
                    "fragility": round(frag, 1),
                    "evidence_score": round(candidate.evidence_score, 1),
                    "remove_joint_probability": (
                        round(reduced_joint * 100.0, 2)
                        if reduced_joint is not None and reduced_supported == len(reduced)
                        else None
                    ),
                })
            rows.sort(key=lambda row: row["fragility"], reverse=True)
            return rows

        def build_match(match: dict, shadow_for_match: dict[str, dict[str, float]], legs: int = 4):
            row = self.original_build_match(match, shadow_for_match, legs=legs)
            if row:
                snap = cache.snapshot()
                adapter = dict(row.get("market_adapter") or {})
                adapter.update({
                    "deep_mask_cache_version": VERSION,
                    "shared_predicate_masks": True,
                    "predicate_mask_entries": snap.masks,
                    "predicate_mask_hits": snap.hits,
                    "predicate_evaluations": snap.predicate_evaluations,
                    "payload_mask_reuse_version": PAYLOAD_REUSE_VERSION,
                    "payload_fragility_top_paths_cached": True,
                    "payload_joint_reuses": snap.payload_joint_reuses,
                })
                row["market_adapter"] = adapter
            return row

        deep._deep_outcome_finalize = finalize
        deep._deep_predicate = predicate_factory
        deep._top_paths_v93 = top_paths
        deep.build_match_model_scenario = build_match
        core._marginal = marginal
        fast._predicate_masks = predicate_masks
        core._top_matching_paths = core_top_paths
        core._fragility = fragility
        self._installed = True
        return self

    def uninstall(self) -> None:
        if not self._installed:
            return
        deep = self.deep
        deep._deep_outcome_finalize = self.original_finalize
        deep._deep_predicate = self.original_predicate_factory
        deep._top_paths_v93 = self.original_top_paths
        deep.build_match_model_scenario = self.original_build_match
        core._marginal = self.original_marginal
        fast._predicate_masks = self.original_fast_masks
        core._top_matching_paths = self.original_core_top_paths
        core._fragility = self.original_fragility
        self._installed = False


def install(deep_module) -> InstalledAdapter:
    return InstalledAdapter(deep_module).install()
