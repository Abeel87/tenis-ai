from __future__ import annotations

"""Tenis AI v9.0C — full-market runner for Tennis Symphony.

Keeps the v9.0B exact state engine isolated and feeds it a richer, canonical
market catalogue built from data that Tenis AI already stores in results.json.
"""

import json

try:
    from . import symphony_engine_v90 as core
    from .symphony_evidence_v90c import VERSION as EVIDENCE_VERSION, augment_match
except ImportError:
    import symphony_engine_v90 as core
    from symphony_evidence_v90c import VERSION as EVIDENCE_VERSION, augment_match

VERSION = "v9.0C.1"
MODE = "ANALYSIS_ONLY"


def _decorate_leg(leg: dict, evidence_meta: dict):
    if not isinstance(leg, dict):
        return leg
    raw = (evidence_meta.get("by_key") or {}).get(str(leg.get("key") or "")) or {}
    if not raw:
        return leg
    out = dict(leg)
    out["market_source"] = raw.get("symphony_source")
    out["raw_market_probability"] = raw.get("symphony_raw_probability")
    out["score_kind"] = (
        "relative_family_strength"
        if str(raw.get("market")) in {"game_state", "set1_exact_score", "exact_match_score"}
        else "existing_model_percentage"
    )
    return out


def _decorate_scenario(scenario: dict, evidence_meta: dict):
    if not isinstance(scenario, dict):
        return scenario
    out = dict(scenario)
    if isinstance(out.get("selection"), list):
        out["selection"] = [_decorate_leg(x, evidence_meta) for x in out["selection"]]
    if isinstance(out.get("alternatives"), list):
        out["alternatives"] = [_decorate_scenario(x, evidence_meta) for x in out["alternatives"]]
    return out


def _decorate_match(row: dict, evidence_meta: dict):
    out = dict(row)
    out["market_adapter"] = {
        "version": evidence_meta.get("version"),
        "catalog_size": evidence_meta.get("catalog_size", 0),
        "composer_added": evidence_meta.get("composer_added", 0),
        "existing_signals": evidence_meta.get("existing_signals", 0),
        "families": evidence_meta.get("families") or {},
    }
    out["selection"] = [_decorate_leg(x, evidence_meta) for x in out.get("selection") or []]
    out["candidate_pool"] = [_decorate_leg(x, evidence_meta) for x in out.get("candidate_pool") or []]
    if isinstance(out.get("compositions"), dict):
        out["compositions"] = {
            str(k): _decorate_scenario(v, evidence_meta)
            for k, v in out["compositions"].items()
        }
    return out


def _extended_predicate(base_predicate):
    """Extend v9.0B path maths where its existing outcome state is sufficient.

    BO3 final score + first-set winner uniquely determine set 2, and set 3 is
    always won by the eventual match winner. BO5 is intentionally left N/D
    until the state engine retains the full set sequence.
    """
    def predicate(match: dict, candidate):
        existing = base_predicate(match, candidate)
        if existing is not None:
            return existing
        if core._best_of(match) != 3:
            return None
        side = core._side_for_pick(match, candidate.pick)
        if side is None:
            return None
        if candidate.market == "set2_winner":
            return lambda o: (
                o.get("set_count") in {2, 3}
                and (
                    o.get("winner")
                    if o.get("set_count") == 2
                    else 3 - int(o.get("set1_winner"))
                ) == side
            )
        if candidate.market == "set3_winner":
            return lambda o: o.get("set_count") == 3 and o.get("winner") == side
        return None
    return predicate


def build_report(legs: int = 4) -> dict:
    results = core._read(core.RESULTS, [])
    shadow = core._read(core.SHADOW, {})
    if not isinstance(results, list):
        results = []
    if not isinstance(shadow, dict):
        shadow = {}

    shadow_idx = core._shadow_index(shadow)
    matches = []

    # v9.0B deliberately used a small global pool. v9.0C has more market
    # families, so widen the candidate window while keeping the same bounded
    # beam-search architecture.
    old_pool = core.POOL_LIMIT
    old_beam = core.BEAM_WIDTH
    old_predicate = core._predicate
    core.POOL_LIMIT = max(old_pool, 56)
    core.BEAM_WIDTH = max(old_beam, 160)
    core._predicate = _extended_predicate(old_predicate)
    try:
        for match in results:
            if not isinstance(match, dict):
                continue
            augmented, evidence = augment_match(match)
            mk = core._match_key(match)
            row = core.build_match_symphony(
                augmented,
                shadow_idx.get(mk, {}),
                legs=legs,
            )
            if row:
                matches.append(_decorate_match(row, evidence))
    finally:
        core.POOL_LIMIT = old_pool
        core.BEAM_WIDTH = old_beam
        core._predicate = old_predicate

    matches.sort(key=lambda x: (
        -float(x.get("symphony_score") or 0.0),
        str(x.get("scheduled_time") or ""),
    ))

    return {
        "version": VERSION,
        "engine_version": core.VERSION,
        "evidence_adapter_version": EVIDENCE_VERSION,
        "mode": MODE,
        "production_influence": False,
        "shadow_auto_promotion": False,
        "matches_count": len(matches),
        "matches": matches,
        "contract": {
            "prod_is_source_of_truth": True,
            "shadow_is_supporting_evidence": True,
            "shadow_weight_cap": core.SHADOW_WEIGHT_CAP,
            "does_not_modify_final_score": True,
            "joint_probability_only_when_path_coverage_is_1": True,
            "relative_strength_is_not_probability": True,
            "raw_market_probability_is_preserved": True,
            "bo3_set2_set3_exact_joint": True,
            "bo5_set_sequence_exact_joint": False,
        },
    }


def run(legs: int = 4) -> dict:
    report = build_report(legs=legs)
    core._write(core.REPORT, report)
    return {
        "status": "OK",
        "version": VERSION,
        "engine_version": core.VERSION,
        "markets": sum(int((m.get("market_adapter") or {}).get("catalog_size") or 0) for m in report.get("matches") or []),
        "matches": report.get("matches_count", 0),
        "production_influence": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
