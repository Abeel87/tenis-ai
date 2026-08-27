from __future__ import annotations

"""Tenis AI v9.0C.4 — full-market runner for Tennis Symphony.

Keeps the v9.0B exact state engine isolated, adds the v9.0C market catalogue,
serve-comparison evidence and automatic 2..6 leg-count intelligence.
"""

import json

try:
    from . import symphony_engine_v90 as core
    from .symphony_evidence_v90c import VERSION as BASE_EVIDENCE_VERSION
    from .symphony_c4 import (
        VERSION,
        augment_match_c4,
        comparison_compatible,
        coverage_first_metrics,
        leg_count_intelligence,
    )
except ImportError:
    import symphony_engine_v90 as core
    from symphony_evidence_v90c import VERSION as BASE_EVIDENCE_VERSION
    from symphony_c4 import (
        VERSION,
        augment_match_c4,
        comparison_compatible,
        coverage_first_metrics,
        leg_count_intelligence,
    )

EVIDENCE_VERSION = VERSION
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
    if raw.get("symphony_approximation"):
        out["approximation"] = raw.get("symphony_approximation")
    if str(raw.get("market")) in {"game_state", "set1_exact_score", "exact_match_score"}:
        out["score_kind"] = "relative_family_strength"
    elif raw.get("symphony_approximation"):
        out["score_kind"] = "serve_comparison_estimate"
    else:
        out["score_kind"] = "existing_model_percentage"
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
        "base_version": BASE_EVIDENCE_VERSION,
        "catalog_size": evidence_meta.get("catalog_size", 0),
        "composer_added": evidence_meta.get("composer_added", 0),
        "serve_comparison_added": evidence_meta.get("serve_comparison_added", 0),
        "existing_signals": evidence_meta.get("existing_signals", 0),
        "alias_duplicates_removed": evidence_meta.get("alias_duplicates_removed", 0),
        "families": evidence_meta.get("families") or {},
    }
    out["selection"] = [_decorate_leg(x, evidence_meta) for x in out.get("selection") or []]
    out["candidate_pool"] = [_decorate_leg(x, evidence_meta) for x in out.get("candidate_pool") or []]
    if isinstance(out.get("compositions"), dict):
        out["compositions"] = {
            str(k): _decorate_scenario(v, evidence_meta)
            for k, v in out["compositions"].items()
        }
    intelligence = leg_count_intelligence(out)
    out["leg_count_intelligence"] = intelligence
    out["recommended_leg_count"] = intelligence.get("recommended")
    return out


def _semantic_market(signal: dict) -> str:
    market = core._canonical_market(signal.get("market"))
    key = core._ascii(core._signal_key(signal))
    checkpoint = core._checkpoint(signal)
    if checkpoint in core.CHECKPOINTS and (
        market == "game_state"
        or market.startswith("state")
        or key.startswith("state")
        or key.startswith("game_state")
        or key.startswith("gamestate")
    ):
        return "game_state"
    return market


def _semantic_pick(signal: dict, market: str) -> str:
    pick = str(signal.get("pick") or "").strip()
    if market == "game_state" and not core._score_pair(pick):
        parts = core._signal_key(signal).split("|")
        for part in reversed(parts):
            if core._score_pair(part):
                pick = part
                break
    return core._compact(pick)


def _semantic_signature(signal: dict):
    market = _semantic_market(signal)
    checkpoint = core._checkpoint(signal) if market == "game_state" else None
    line = core._line(signal)
    if market not in {
        "set1_total", "match_total", "total_sets",
        "player_aces", "player_double_faults",
    }:
        line = None
    return (
        market,
        _semantic_pick(signal, market),
        round(float(line), 6) if line is not None else None,
        int(checkpoint) if checkpoint is not None else None,
    )


def _dedupe_augmented(match: dict, evidence_meta: dict):
    """Remove semantic aliases while preserving the original PROD signal first."""
    auto = dict(match.get("autolearn_v84") or {})
    rows = [x for x in (auto.get("signals") or []) if isinstance(x, dict)]
    seen = set()
    kept = []
    removed = 0
    for row in rows:
        sig = _semantic_signature(row)
        if sig in seen:
            removed += 1
            continue
        seen.add(sig)
        kept.append(row)
    auto["signals"] = kept
    match["autolearn_v84"] = auto
    evidence_meta["alias_duplicates_removed"] = removed
    if removed:
        evidence_meta["composer_added"] = max(
            0,
            int(evidence_meta.get("composer_added") or 0) - removed,
        )
    return match, evidence_meta


def _extended_predicate(base_predicate):
    """Extend exact path maths where the v9.0B outcome state is sufficient."""
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


def _one_pass_compositions(match: dict, candidates: list, outcomes: list[dict]):
    """Build 2..6-leg compositions in one bounded beam pass."""
    pool = sorted(
        candidates,
        key=lambda c: (c.evidence_score, c.agreement, -c.conflict),
        reverse=True,
    )[:core.POOL_LIMIT]
    if len(pool) < 2:
        return {}

    beam = []
    for idx, candidate in enumerate(pool):
        combo = (candidate,)
        metrics = core._combo_metrics(match, combo, outcomes)
        beam.append(((idx,), combo, metrics))
    beam.sort(key=lambda x: (x[2]["score"], x[2]["path_coverage"]), reverse=True)
    beam = beam[:core.BEAM_WIDTH]

    out = {}
    for depth in range(2, 7):
        expanded = []
        for indexes, combo, _ in beam:
            start = indexes[-1] + 1
            for idx in range(start, len(pool)):
                candidate = pool[idx]
                if any(not core._compatible(candidate, old) for old in combo):
                    continue
                nxt = combo + (candidate,)
                metrics = core._combo_metrics(match, nxt, outcomes)
                if (
                    metrics["supported_legs"] == len(nxt)
                    and metrics["joint_supported_only"] is not None
                    and metrics["joint_supported_only"] <= core.EPS
                ):
                    continue
                expanded.append((indexes + (idx,), nxt, metrics))

        expanded.sort(
            key=lambda x: (
                x[2]["score"],
                x[2]["path_coverage"],
                x[2]["avg_evidence"],
            ),
            reverse=True,
        )
        beam = expanded[:core.BEAM_WIDTH]
        if not beam:
            break

        _, best_combo, best_metrics = beam[0]
        out[str(depth)] = {
            **core._scenario_payload(match, best_combo, best_metrics, outcomes),
            "legs": depth,
            "alternatives": [
                core._scenario_payload(match, combo, metrics, outcomes)
                for _, combo, metrics in beam[1:4]
            ],
        }
    return out


def build_report(legs: int = 4) -> dict:
    results = core._read(core.RESULTS, [])
    shadow = core._read(core.SHADOW, {})
    if not isinstance(results, list):
        results = []
    if not isinstance(shadow, dict):
        shadow = {}

    shadow_idx = core._shadow_index(shadow)
    matches = []

    old_pool = core.POOL_LIMIT
    old_beam = core.BEAM_WIDTH
    old_predicate = core._predicate
    old_compositions = core._compositions
    old_metrics = core._combo_metrics
    old_compatible = core._compatible

    core.POOL_LIMIT = 44
    core.BEAM_WIDTH = 104
    core._predicate = _extended_predicate(old_predicate)
    core._compositions = _one_pass_compositions
    core._combo_metrics = coverage_first_metrics(old_metrics)
    core._compatible = comparison_compatible(old_compatible)
    try:
        for match in results:
            if not isinstance(match, dict):
                continue
            augmented, evidence = augment_match_c4(match)
            augmented, evidence = _dedupe_augmented(augmented, evidence)
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
        core._compositions = old_compositions
        core._combo_metrics = old_metrics
        core._compatible = old_compatible

    matches.sort(key=lambda x: (
        -float(x.get("symphony_score") or 0.0),
        str(x.get("scheduled_time") or ""),
    ))

    return {
        "version": VERSION,
        "engine_version": core.VERSION,
        "evidence_adapter_version": EVIDENCE_VERSION,
        "base_evidence_adapter_version": BASE_EVIDENCE_VERSION,
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
            "semantic_alias_dedupe": True,
            "bo3_set2_set3_exact_joint": True,
            "bo5_set_sequence_exact_joint": False,
            "one_pass_bounded_beam": True,
            "coverage_first_ranking": True,
            "serve_comparisons_are_evidence_only": True,
            "auto_leg_count_2_to_6": True,
            "historical_leg_count_learning_active": False,
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
