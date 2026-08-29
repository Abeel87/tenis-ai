from __future__ import annotations

"""Runtime adapter for Symphony deep MODEL/RAW lattice.

BO3 keeps the v9.3A game-by-game exact lattice. BO5 now uses v9.3C compact exact
set-score states: exact sets 1/2 + match-level totals/final score, while
checkpoint and set-3-specific markets remain evidence-only. This avoids the
set-path cartesian explosion without pretending unsupported fields are exact.

v9.3F adds a shared predicate-mask cache around the unchanged exact-state maths:
each candidate predicate is evaluated against a match lattice once, then reused
for marginal scoring, beam masks and top-path extraction.

v9.3H adds a runtime coherence guard: player name order no longer breaks exact
side resolution, first-set game handicaps use the already-existing exact set-1
score state, and duplicate/opposing handicap legs from the same period cannot be
composed into one story.

v9.3L keeps the same beam and score maths but precomputes candidate-pair
compatibility and pair affinity once per sorted pool instead of recalculating the
same pair-only values for thousands of expanded combinations.

v9.3M adds zero-influence progress markers around major deep stages. If the parent
watchdog kills the child, the last atomic marker shows the exact match/stage where
time was being spent without changing any scenario maths.

v9.3N keeps payload output exact but avoids full matching-state sorts for every
best/alternate scenario and memoizes repeated payload mask probability sums.

v9.3O keeps the beam result exact while carrying each parent's joint truth-mask
forward and memoizing exact probability mass by the resulting mask. Repeated
line-ladder combinations therefore stop re-summing the same 306k-state subsets.
"""

try:
    from . import symphony_engine_v90 as core
    from . import symphony_engine_v91 as fast
    from . import symphony_scenario_lattice_v93 as deep
    from . import symphony_bo5_compact_v93c as compact
    from . import symphony_deep_mask_cache_v93f as mask_cache
    from . import symphony_coherence_guard_v93h as coherence
    from . import symphony_pair_matrix_v93l as pair_cache
    from . import symphony_deep_progress_v93m as progress_telemetry
    from . import symphony_payload_rank_cache_v93n as payload_rank_cache
    from . import symphony_beam_mask_mass_v93o as beam_mass_cache
except ImportError:
    import symphony_engine_v90 as core
    import symphony_engine_v91 as fast
    import symphony_scenario_lattice_v93 as deep
    import symphony_bo5_compact_v93c as compact
    import symphony_deep_mask_cache_v93f as mask_cache
    import symphony_coherence_guard_v93h as coherence
    import symphony_pair_matrix_v93l as pair_cache
    import symphony_deep_progress_v93m as progress_telemetry
    import symphony_payload_rank_cache_v93n as payload_rank_cache
    import symphony_beam_mask_mass_v93o as beam_mass_cache

# Keep the historical runtime contract stable for BO5/runtime consumers.
# Later adapters are exposed independently below.
VERSION = "v9.3C-runtime-compact-bo5"
PERFORMANCE_VERSION = mask_cache.VERSION
PAIR_MATRIX_VERSION = pair_cache.VERSION
PROGRESS_TELEMETRY_VERSION = progress_telemetry.VERSION
PAYLOAD_RANK_CACHE_VERSION = payload_rank_cache.VERSION
BEAM_MASK_MASS_VERSION = beam_mass_cache.VERSION
COHERENCE_VERSION = coherence.VERSION


def _scope_comp(comp):
    if not isinstance(comp, dict):
        return comp
    comp["exact_path_scope"] = "SET1_SCORE+SET2_SCORE+MATCH_COMPACT_BO5"
    comp["bo5_evidence_only_markets"] = sorted(compact.BO5_EVIDENCE_ONLY_MARKETS)
    for alt in comp.get("alternatives") or []:
        _scope_comp(alt)
    return comp


def run(legs: int = 4) -> dict:
    original_outcomes = deep._build_deep_outcomes
    original_deep_predicate = deep._deep_predicate
    original_path_text = deep._path_text_v93
    original_decorate = deep._decorate_comp_v93
    original_build_match = deep.build_match_model_scenario

    def bounded(match: dict):
        if core._best_of(match) == 5:
            return compact.build_bo5_compact_outcomes(match)
        return original_outcomes(match)

    def compact_predicate(base_predicate):
        regular = original_deep_predicate(base_predicate)

        def predicate(match: dict, candidate):
            if core._best_of(match) == 5 and not compact.exact_market_supported(candidate.market):
                return None
            return regular(match, candidate)

        return predicate

    def path_text(outcome: dict) -> str:
        if outcome.get("bo5_compact_scope"):
            s1 = outcome.get("set1") or ("?", "?")
            s2 = outcome.get("set2") or ("?", "?")
            sets = outcome.get("sets") or ("?", "?")
            return (
                f"1S {s1[0]}:{s1[1]} · 2S {s2[0]}:{s2[1]} "
                f"→ mecz {sets[0]}:{sets[1]} · {outcome.get('total_games')} gemów"
            )
        return original_path_text(outcome)

    def decorate(match, comp, candidates_by_key, evidence_by_key, outcomes):
        out = original_decorate(match, comp, candidates_by_key, evidence_by_key, outcomes)
        if core._best_of(match) == 5:
            _scope_comp(out)
        return out

    def build_match(match: dict, shadow_for_match: dict[str, dict[str, float]], legs: int = 4):
        row = original_build_match(match, shadow_for_match, legs=legs)
        if row and core._best_of(match) == 5:
            row["path_engine"] = "COMPACT_EXACT_BO5_SET_SCORES"
            row["exact_path_scope"] = "SET1_SCORE+SET2_SCORE+MATCH_COMPACT_BO5"
            row["bo5_evidence_only_markets"] = sorted(compact.BO5_EVIDENCE_ONLY_MARKETS)
            adapter = dict(row.get("market_adapter") or {})
            adapter["bo5_compact_version"] = compact.VERSION
            adapter["bo5_compact_scope"] = compact.SCOPE
            adapter["bo5_evidence_only_markets"] = sorted(compact.BO5_EVIDENCE_ONLY_MARKETS)
            adapter["coherence_guard_version"] = COHERENCE_VERSION
            adapter["pair_matrix_cache_version"] = PAIR_MATRIX_VERSION
            adapter["progress_telemetry_version"] = PROGRESS_TELEMETRY_VERSION
            adapter["payload_rank_cache_version"] = PAYLOAD_RANK_CACHE_VERSION
            adapter["beam_mask_mass_cache_version"] = BEAM_MASK_MASS_VERSION
            row["market_adapter"] = adapter
        elif row:
            adapter = dict(row.get("market_adapter") or {})
            adapter["pair_matrix_cache_version"] = PAIR_MATRIX_VERSION
            adapter["progress_telemetry_version"] = PROGRESS_TELEMETRY_VERSION
            adapter["payload_rank_cache_version"] = PAYLOAD_RANK_CACHE_VERSION
            adapter["beam_mask_mass_cache_version"] = BEAM_MASK_MASS_VERSION
            row["market_adapter"] = adapter
        return row

    deep._build_deep_outcomes = bounded
    deep._deep_predicate = compact_predicate
    deep._path_text_v93 = path_text
    deep._decorate_comp_v93 = decorate
    deep.build_match_model_scenario = build_match
    coherence_guard = coherence.install(core)
    shared_masks = mask_cache.install(deep)
    payload_rank = payload_rank_cache.install(deep, shared_masks)
    pair_matrix = pair_cache.install(fast)
    beam_mass = beam_mass_cache.install(fast)
    progress = progress_telemetry.install(deep, fast, core)
    try:
        result = dict(deep.run(legs=legs))
        progress.finish(result)
    except Exception as exc:
        progress.fail(exc)
        raise
    finally:
        progress.uninstall()
        beam_mass.uninstall()
        pair_matrix.uninstall()
        payload_rank.uninstall()
        shared_masks.uninstall()
        coherence_guard.uninstall()
        deep._build_deep_outcomes = original_outcomes
        deep._deep_predicate = original_deep_predicate
        deep._path_text_v93 = original_path_text
        deep._decorate_comp_v93 = original_decorate
        deep.build_match_model_scenario = original_build_match

    report = core._read(deep.REPORT, {})
    if isinstance(report, dict):
        report["runtime_adapter_version"] = VERSION
        report["performance_adapter_version"] = PERFORMANCE_VERSION
        report["pair_matrix_cache_version"] = PAIR_MATRIX_VERSION
        report["progress_telemetry_version"] = PROGRESS_TELEMETRY_VERSION
        report["payload_rank_cache_version"] = PAYLOAD_RANK_CACHE_VERSION
        report["beam_mask_mass_cache_version"] = BEAM_MASK_MASS_VERSION
        report["coherence_guard_version"] = COHERENCE_VERSION
        contract = dict(report.get("contract") or {})
        contract.update({
            "bo5_compact_exact_set_score_state": True,
            "bo5_compact_scope": compact.SCOPE,
            "bo5_checkpoint_and_set3_specific_markets_evidence_only": True,
            "bo5_evidence_only_markets": sorted(compact.BO5_EVIDENCE_ONLY_MARKETS),
            "bo5_checkpoint_fabrication": False,
            "shared_predicate_masks_exact_equivalent": True,
            "shared_predicate_masks_version": PERFORMANCE_VERSION,
            "pair_compatibility_affinity_precomputed_exact_equivalent": True,
            "pair_matrix_cache_version": PAIR_MATRIX_VERSION,
            "candidate_pool_beam_width_and_sort_order_unchanged": True,
            "deep_progress_telemetry_zero_influence": True,
            "progress_telemetry_version": PROGRESS_TELEMETRY_VERSION,
            "payload_topn_without_full_sort_exact_equivalent": True,
            "payload_mask_mass_memoized_exact_equivalent": True,
            "payload_rank_cache_version": PAYLOAD_RANK_CACHE_VERSION,
            "beam_parent_joint_mask_reused_exact_equivalent": True,
            "beam_joint_mask_mass_memoized_exact_equivalent": True,
            "beam_mask_mass_cache_version": BEAM_MASK_MASS_VERSION,
            "player_name_order_coherence_guard": True,
            "set1_game_handicap_exact_path_supported": True,
            "one_handicap_per_period_in_scenario": True,
            "coherence_guard_version": COHERENCE_VERSION,
            "external_requests": 0,
            "bookmaker_prices_used": False,
        })
        report["contract"] = contract
        core._write(deep.REPORT, report)

    result["runtime_guard_version"] = VERSION
    result["performance_adapter_version"] = PERFORMANCE_VERSION
    result["pair_matrix_cache_version"] = PAIR_MATRIX_VERSION
    result["progress_telemetry_version"] = PROGRESS_TELEMETRY_VERSION
    result["payload_rank_cache_version"] = PAYLOAD_RANK_CACHE_VERSION
    result["beam_mask_mass_cache_version"] = BEAM_MASK_MASS_VERSION
    result["coherence_guard_version"] = COHERENCE_VERSION
    result["bo3_exact_scope"] = "SET1+SET2+MATCH"
    result["bo5_scope"] = compact.SCOPE
    result["bo5_evidence_only_markets"] = sorted(compact.BO5_EVIDENCE_ONLY_MARKETS)
    result["bo5_checkpoint_fabrication"] = False
    result["set1_game_handicap_exact_path_supported"] = True
    result["one_handicap_per_period_in_scenario"] = True
    result["external_requests"] = 0
    return result
