from __future__ import annotations

"""Exact-equivalent payload ranking/mass cache for deep MODEL/RAW Symphony.

v9.3M showed the first BO3 match entering BEAM_COMPOSITIONS with 306k+ exact
states. Beam maths itself already reuses predicate masks, but payload rendering
still materialized and fully sorted every matching state for each best/alternate
scenario. Fragility also re-summed the same reduced masks repeatedly.

This adapter keeps the exact same candidate pool, masks, joint maths and output
ordering while:
- selecting only the requested top matching paths with a fixed-size heap instead
  of building/sorting the full matching-state list;
- memoizing probability mass for payload combo masks only.

v9.3S fixes payload rendering for compact BO5 rows, which intentionally do not
contain game checkpoint fields. This changes presentation of the intermediate
core payload only; candidate selection, masks, probabilities, beam ranking and
the final deep MODEL/RAW decoration remain unchanged.

No bookmaker prices, external requests, training or settlement inputs are used.
"""

import heapq

try:
    from . import symphony_engine_v90 as core
    from . import symphony_deep_mask_cache_v93f as mask_cache
except ImportError:
    import symphony_engine_v90 as core
    import symphony_deep_mask_cache_v93f as mask_cache

VERSION = "v9.3N-payload-topn-mask-mass"
COMPACT_PAYLOAD_GUARD_VERSION = "v9.3S-compact-bo5-payload-guard"


def _core_payload_row(deep, row: dict) -> dict:
    if row.get("bo5_compact_scope") or not all(key in row for key in ("cp2", "cp4", "cp6")):
        s1 = row.get("set1") or ("?", "?")
        s2 = row.get("set2") or ("?", "?")
        sets = row.get("sets") or ("?", "?")
        path = (
            f"1S {s1[0]}:{s1[1]} · 2S {s2[0]}:{s2[1]} "
            f"→ mecz {sets[0]}:{sets[1]} · {row.get('total_games')} gemów"
        )
        return {
            "path": path,
            "cp2": None,
            "cp4": None,
            "cp6": None,
            "set1": f"{s1[0]}:{s1[1]}",
            "match_score": f"{sets[0]}:{sets[1]}",
            "total_games": row.get("total_games"),
            "probability_mass": round(float(row.get("prob") or 0.0) * 100.0, 3),
        }
    return {
        "path": core._path_text(row),
        "cp2": f"{row['cp2'][0]}:{row['cp2'][1]}",
        "cp4": f"{row['cp4'][0]}:{row['cp4'][1]}",
        "cp6": f"{row['cp6'][0]}:{row['cp6'][1]}",
        "set1": f"{row['set1'][0]}:{row['set1'][1]}",
        "match_score": f"{row['sets'][0]}:{row['sets'][1]}",
        "total_games": row["total_games"],
        "probability_mass": round(row["prob"] * 100.0, 3),
    }


class InstalledPayloadRankCache:
    def __init__(self, deep_module, shared_masks) -> None:
        self.deep = deep_module
        self.shared_masks = shared_masks
        self.cache = shared_masks.cache
        self._installed = False
        self._outcomes_ref = None
        self._mass_by_mask: dict[int, float] = {}
        self.mass_hits = 0
        self.mass_sums = 0
        self.topn_calls = 0

    def _reset_if_needed(self, outcomes) -> bool:
        if outcomes is not self.cache.outcomes:
            return False
        if outcomes is not self._outcomes_ref:
            self._outcomes_ref = outcomes
            self._mass_by_mask = {}
            self.mass_hits = 0
            self.mass_sums = 0
            self.topn_calls = 0
        return True

    def _combo_mask(self, match: dict, combo, outcomes):
        if not self._reset_if_needed(outcomes):
            return None
        mask = self.cache.full_mask
        supported = 0
        for candidate in combo:
            predicate = core._predicate(match, candidate)
            if predicate is None:
                continue
            supported += 1
            key = getattr(
                predicate,
                mask_cache._CACHE_KEY_ATTR,
                mask_cache._candidate_key(candidate),
            )
            candidate_mask, _ = self.cache._ensure(key, predicate)
            mask &= candidate_mask
            if not mask:
                break
        if not supported:
            return 0, 0
        return mask, supported

    def _mass(self, mask: int) -> float:
        cached = self._mass_by_mask.get(mask)
        if cached is not None or mask in self._mass_by_mask:
            self.mass_hits += 1
            return float(cached or 0.0)
        probability = 0.0
        work = mask
        probabilities = self.cache.probabilities
        while work:
            bit = work & -work
            idx = bit.bit_length() - 1
            probability += probabilities[idx]
            work ^= bit
        self._mass_by_mask[mask] = probability
        self.mass_sums += 1
        return probability

    def _top_rows(self, mask: int, outcomes, limit: int):
        if limit <= 0 or not mask:
            return []
        self.topn_calls += 1
        heap = []
        work = mask
        probabilities = self.cache.probabilities
        while work:
            bit = work & -work
            idx = bit.bit_length() - 1
            rank = (probabilities[idx], -idx)
            item = (rank, idx)
            if len(heap) < limit:
                heapq.heappush(heap, item)
            elif rank > heap[0][0]:
                heapq.heapreplace(heap, item)
            work ^= bit
        heap.sort(key=lambda item: item[0], reverse=True)
        return [outcomes[idx] for _, idx in heap]

    def install(self):
        if self._installed:
            return self
        deep = self.deep

        self.original_deep_top_paths = deep._top_paths_v93
        self.original_core_top_paths = core._top_matching_paths
        self.original_fragility = core._fragility
        self.original_build_match = deep.build_match_model_scenario

        def deep_top_paths(match: dict, combo, outcomes: list[dict], limit=5):
            combo_mask = self._combo_mask(match, combo, outcomes)
            if combo_mask is None:
                return self.original_deep_top_paths(match, combo, outcomes, limit=limit)
            mask, supported = combo_mask
            if not supported:
                return []
            rows = self._top_rows(mask, outcomes, int(limit))
            return [
                {
                    "path": deep._path_text_v93(row),
                    "set1": f"{row['set1'][0]}:{row['set1'][1]}",
                    "set2": f"{row['set2'][0]}:{row['set2'][1]}",
                    "set3": f"{row['set3'][0]}:{row['set3'][1]}" if row.get("set3") else None,
                    "match_score": f"{row['sets'][0]}:{row['sets'][1]}",
                    "total_games": row["total_games"],
                    "probability_mass": round(row["prob"] * 100.0, 3),
                }
                for row in rows
            ]

        def core_top_paths(match: dict, combo, outcomes: list[dict], limit=5):
            combo_mask = self._combo_mask(match, combo, outcomes)
            if combo_mask is None:
                return self.original_core_top_paths(match, combo, outcomes, limit=limit)
            mask, supported = combo_mask
            if not supported:
                return []
            rows = self._top_rows(mask, outcomes, int(limit))
            return [_core_payload_row(deep, row) for row in rows]

        def fragility(match: dict, combo, outcomes: list[dict]):
            if len(combo) < 2 or not self._reset_if_needed(outcomes):
                return self.original_fragility(match, combo, outcomes)
            full = self._combo_mask(match, combo, outcomes)
            if full is None:
                return self.original_fragility(match, combo, outcomes)
            full_mask, full_supported = full
            full_joint = self._mass(full_mask)
            rows = []
            for i, candidate in enumerate(combo):
                reduced = combo[:i] + combo[i + 1:]
                reduced_result = self._combo_mask(match, reduced, outcomes)
                if reduced_result is None:
                    return self.original_fragility(match, combo, outcomes)
                reduced_mask, reduced_supported = reduced_result
                reduced_joint = self._mass(reduced_mask)
                lift = 0.0
                if (
                    full_joint > core.EPS
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
                        if reduced_supported == len(reduced)
                        else None
                    ),
                })
            rows.sort(key=lambda row: row["fragility"], reverse=True)
            return rows

        def build_match(match: dict, shadow_for_match: dict[str, dict[str, float]], legs: int = 4):
            row = self.original_build_match(match, shadow_for_match, legs=legs)
            if row:
                adapter = dict(row.get("market_adapter") or {})
                adapter.update({
                    "payload_rank_cache_version": VERSION,
                    "payload_compact_bo5_guard_version": COMPACT_PAYLOAD_GUARD_VERSION,
                    "payload_topn_without_full_sort": True,
                    "payload_mask_mass_memoized": True,
                    "payload_topn_calls": int(self.topn_calls),
                    "payload_mass_sums": int(self.mass_sums),
                    "payload_mass_hits": int(self.mass_hits),
                })
                row["market_adapter"] = adapter
            return row

        deep._top_paths_v93 = deep_top_paths
        core._top_matching_paths = core_top_paths
        core._fragility = fragility
        deep.build_match_model_scenario = build_match
        self._installed = True
        return self

    def uninstall(self) -> None:
        if not self._installed:
            return
        deep = self.deep
        deep._top_paths_v93 = self.original_deep_top_paths
        core._top_matching_paths = self.original_core_top_paths
        core._fragility = self.original_fragility
        deep.build_match_model_scenario = self.original_build_match
        self._installed = False


def install(deep_module, shared_masks) -> InstalledPayloadRankCache:
    return InstalledPayloadRankCache(deep_module, shared_masks).install()
