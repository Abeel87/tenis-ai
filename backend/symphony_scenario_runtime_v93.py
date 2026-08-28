from __future__ import annotations

"""Runtime adapter for Symphony deep MODEL/RAW lattice.

BO3 keeps the v9.3A game-by-game exact lattice. BO5 now uses v9.3C compact exact
set-score states: exact sets 1/2 + match-level totals/final score, while
checkpoint and set-3-specific markets remain evidence-only. This avoids the
set-path cartesian explosion without pretending unsupported fields are exact.
"""

try:
    from . import symphony_engine_v90 as core
    from . import symphony_scenario_lattice_v93 as deep
    from . import symphony_bo5_compact_v93c as compact
except ImportError:
    import symphony_engine_v90 as core
    import symphony_scenario_lattice_v93 as deep
    import symphony_bo5_compact_v93c as compact

VERSION = "v9.3C-runtime-compact-bo5"


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
            row["market_adapter"] = adapter
        return row

    deep._build_deep_outcomes = bounded
    deep._deep_predicate = compact_predicate
    deep._path_text_v93 = path_text
    deep._decorate_comp_v93 = decorate
    deep.build_match_model_scenario = build_match
    try:
        result = dict(deep.run(legs=legs))
    finally:
        deep._build_deep_outcomes = original_outcomes
        deep._deep_predicate = original_deep_predicate
        deep._path_text_v93 = original_path_text
        deep._decorate_comp_v93 = original_decorate
        deep.build_match_model_scenario = original_build_match

    result["runtime_guard_version"] = VERSION
    result["bo3_exact_scope"] = "SET1+SET2+MATCH"
    result["bo5_scope"] = compact.SCOPE
    result["bo5_evidence_only_markets"] = sorted(compact.BO5_EVIDENCE_ONLY_MARKETS)
    result["bo5_checkpoint_fabrication"] = False
    result["external_requests"] = 0
    return result
