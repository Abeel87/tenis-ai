from __future__ import annotations

"""Tenis AI v9.1 — market-aware Tennis Symphony runner.

The operator layer can expose a broad ladder of real Superbet lines.  The
scenario maths stays exactly the same, but the v9.2.4 performance adapter
pre-evaluates every exact-state predicate once per candidate and reuses compact
outcome masks during beam search.  This avoids repeatedly evaluating the same
predicate functions for thousands of candidate combinations.

v9.3E additionally isolates the much heavier deep MODEL/RAW lattice in a bounded
subprocess.  A slow deep build can no longer hold the whole FULL data workflow
forever; the previously published deep report remains intact if the subprocess
times out or fails.  Operator-aware Symphony output is still written first.

v9.3H adds a hard scenario-coherence guard without changing model probability:
``Last, First`` player labels resolve to the same side as ``First Last``, first-set
game handicaps use the exact set-1 score already present in the state engine, and
duplicate/opposite handicap legs from one period cannot share one Symphony.
"""

import json
import os
import subprocess
import sys

try:
    from . import symphony_engine_v90c as base
    from . import symphony_coherence_guard_v93h as coherence
    from .symphony_operator_guard_v91 import VERSION as OPERATOR_VERSION, apply_superbet_market_guard
except ImportError:
    import symphony_engine_v90c as base
    import symphony_coherence_guard_v93h as coherence
    from symphony_operator_guard_v91 import VERSION as OPERATOR_VERSION, apply_superbet_market_guard

VERSION = "v9.1"
PERFORMANCE_VERSION = "v9.2.4-fast-outcome-masks"
DEEP_EXECUTION_VERSION = "v9.3E-bounded-subprocess"
COHERENCE_VERSION = coherence.VERSION
DEEP_TIMEOUT_SECONDS_DEFAULT = 480
DEEP_RUNTIME_STATUS = base.core.OUT / "symphony_model_runtime_v93e.json"
DEEP_INCREMENTAL_STATUS = base.core.OUT / "symphony_model_incremental_v93r.json"
DEEP_PROGRESS_STATUS = base.core.OUT / "symphony_model_progress_v93m.json"
BASE_VERSION = base.VERSION
_BASE_AUGMENT = base.augment_match_c4


def _guarded_augment(match: dict):
    augmented, evidence = _BASE_AUGMENT(match)
    return apply_superbet_market_guard(augmented, evidence, match)


def _predicate_masks(match: dict, pool: list, outcomes: list[dict]):
    """Evaluate each exact-state predicate once, preserving outcome order."""
    masks = []
    for candidate in pool:
        predicate = base.core._predicate(match, candidate)
        if predicate is None:
            masks.append(None)
            continue
        mask = 0
        for idx, outcome in enumerate(outcomes):
            if predicate(outcome):
                mask |= 1 << idx
        masks.append(mask)
    return masks


def _masked_joint(indexes: tuple[int, ...], masks: list, probabilities: tuple[float, ...], full_mask: int):
    """Exact equivalent of core._joint, using cached predicate truth masks."""
    if not probabilities:
        return None, 0
    supported = [idx for idx in indexes if masks[idx] is not None]
    if not supported:
        return None, 0

    mask = full_mask
    for idx in supported:
        mask &= masks[idx]
        if not mask:
            return 0.0, len(supported)

    probability = 0.0
    # Visit matching outcomes in their original ascending order so floating
    # point accumulation follows the same order as core._joint.
    while mask:
        bit = mask & -mask
        outcome_idx = bit.bit_length() - 1
        probability += probabilities[outcome_idx]
        mask ^= bit
    return probability, len(supported)


def _fast_metrics(combo: tuple, indexes: tuple[int, ...], masks: list, probabilities: tuple[float, ...], full_mask: int):
    """Same core + coverage-first formula, with only predicate evaluation cached."""
    joint, supported = _masked_joint(indexes, masks, probabilities, full_mask)
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
        base.core._pair_affinity(combo[i], combo[j])
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

    # Exact equivalent of symphony_c4.coverage_first_metrics.
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


def _fast_one_pass_compositions(match: dict, candidates: list, outcomes: list[dict]):
    """v9.0D.1 one-pass beam search with mathematically identical cached masks."""
    pool = sorted(
        candidates,
        key=lambda candidate: (candidate.evidence_score, candidate.agreement, -candidate.conflict),
        reverse=True,
    )[:base.core.POOL_LIMIT]
    if len(pool) < 2:
        return {}

    masks = _predicate_masks(match, pool, outcomes)
    probabilities = tuple(float(outcome["prob"]) for outcome in outcomes)
    full_mask = (1 << len(outcomes)) - 1 if outcomes else 0

    beam = []
    for idx, candidate in enumerate(pool):
        combo = (candidate,)
        metrics = _fast_metrics(combo, (idx,), masks, probabilities, full_mask)
        beam.append(((idx,), combo, metrics))
    beam.sort(key=lambda row: (row[2]["score"], row[2]["path_coverage"]), reverse=True)
    beam = beam[:base.core.BEAM_WIDTH]

    out = {}
    for depth in range(2, 7):
        expanded = []
        for indexes, combo, _ in beam:
            start = indexes[-1] + 1
            for idx in range(start, len(pool)):
                candidate = pool[idx]
                if any(not base.core._compatible(candidate, old) for old in combo):
                    continue
                next_indexes = indexes + (idx,)
                next_combo = combo + (candidate,)
                metrics = _fast_metrics(next_combo, next_indexes, masks, probabilities, full_mask)
                if (
                    metrics["supported_legs"] == len(next_combo)
                    and metrics["joint_supported_only"] is not None
                    and metrics["joint_supported_only"] <= base.core.EPS
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
        beam = expanded[:base.core.BEAM_WIDTH]
        if not beam:
            break

        _, best_combo, best_metrics = beam[0]
        out[str(depth)] = {
            **base.core._scenario_payload(match, best_combo, best_metrics, outcomes),
            "legs": depth,
            "alternatives": [
                base.core._scenario_payload(match, combo, metrics, outcomes)
                for _, combo, metrics in beam[1:4]
            ],
        }
    return out


def build_report(legs: int = 4) -> dict:
    previous_augment = base.augment_match_c4
    previous_compositions = base._one_pass_compositions
    coherence_guard = coherence.install(base.core)
    base.augment_match_c4 = _guarded_augment
    base._one_pass_compositions = _fast_one_pass_compositions
    try:
        report = base.build_report(legs=legs)
    finally:
        base.augment_match_c4 = previous_augment
        base._one_pass_compositions = previous_compositions
        coherence_guard.uninstall()
    report = dict(report)
    report["version"] = VERSION
    report["base_symphony_version"] = BASE_VERSION
    report["operator_market_context_version"] = OPERATOR_VERSION
    report["performance_adapter_version"] = PERFORMANCE_VERSION
    report["coherence_guard_version"] = COHERENCE_VERSION
    contract = dict(report.get("contract") or {})
    contract.update({
        "real_superbet_availability_gates_ready_to_bet_pool": True,
        "bookmaker_prices_used": False,
        "bookmaker_lines_are_context_not_training_targets": True,
        "core_prod_adaptive_shadow_scores_unchanged": True,
        "unavailable_markets_remain_analysis_only": True,
        "full_superbet_line_ladders_preserved": True,
        "beam_math_unchanged_predicates_cached_only": True,
        "player_name_order_coherence_guard": True,
        "set1_game_handicap_exact_path_supported": True,
        "one_handicap_per_period_in_scenario": True,
        "coherence_guard_version": COHERENCE_VERSION,
    })
    report["contract"] = contract
    return report


def _deep_timeout_seconds() -> int:
    raw = os.getenv("SYMPHONY_DEEP_TIMEOUT_SECONDS", str(DEEP_TIMEOUT_SECONDS_DEFAULT))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEEP_TIMEOUT_SECONDS_DEFAULT
    return max(30, min(1800, value))


def _mark_deep_terminal(status: str, reason: str | None = None) -> None:
    """Reconcile diagnostics after the parent stops the deep child."""
    for path, replace_status in (
        (DEEP_INCREMENTAL_STATUS, True),
        (DEEP_PROGRESS_STATUS, False),
    ):
        payload = base.core._read(path, {})
        if not isinstance(payload, dict) or not payload:
            continue
        payload = dict(payload)
        if replace_status:
            payload.setdefault("child_status_at_termination", payload.get("status"))
            payload["status"] = status
        payload["terminal_status"] = status
        payload["terminal_execution_version"] = DEEP_EXECUTION_VERSION
        if reason:
            payload["terminal_reason"] = reason
        payload["production_influence"] = False
        payload["playable_influence"] = False
        payload["prices_used"] = False
        base.core._write(path, payload)


def _write_deep_runtime_status(payload: dict) -> None:
    status = dict(payload)
    status["execution_version"] = DEEP_EXECUTION_VERSION
    status["production_influence"] = False
    status["playable_influence"] = False
    status["prices_used"] = False
    base.core._write(DEEP_RUNTIME_STATUS, status)
    terminal = str(status.get("status") or "").upper()
    if terminal in {"TIMEOUT", "ERROR"}:
        _mark_deep_terminal(terminal, status.get("reason") or status.get("stderr_tail"))


def _run_deep_bounded(legs: int = 4) -> dict:
    """Run deep MODEL/RAW in a child process with a hard wall-clock bound.

    The deep report writer is atomic, so a killed/failed child cannot replace the
    last complete `symphony_model_v93.json` with a partial file.
    """
    timeout_seconds = _deep_timeout_seconds()
    runner = base.core.ROOT / "backend" / "symphony_deep_runner_v93e.py"
    command = [sys.executable, str(runner), "--legs", str(int(legs))]

    try:
        completed = subprocess.run(
            command,
            cwd=str(base.core.ROOT),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        result = {
            "status": "TIMEOUT",
            "timeout_seconds": timeout_seconds,
            "preserved_previous_report": True,
            "reason": "DEEP_MODEL_RAW_EXCEEDED_WALL_CLOCK_BOUND",
        }
        _write_deep_runtime_status(result)
        return result

    if completed.returncode != 0:
        result = {
            "status": "ERROR",
            "returncode": int(completed.returncode),
            "timeout_seconds": timeout_seconds,
            "preserved_previous_report": True,
            "stderr_tail": (completed.stderr or "")[-2000:],
        }
        _write_deep_runtime_status(result)
        return result

    stdout = (completed.stdout or "").strip()
    try:
        result = json.loads(stdout.splitlines()[-1]) if stdout else {}
    except (json.JSONDecodeError, IndexError):
        result = {
            "status": "ERROR",
            "returncode": 0,
            "timeout_seconds": timeout_seconds,
            "preserved_previous_report": True,
            "reason": "DEEP_RUNNER_DID_NOT_RETURN_JSON",
            "stdout_tail": stdout[-2000:],
        }
        _write_deep_runtime_status(result)
        return result

    result = dict(result) if isinstance(result, dict) else {"status": "ERROR", "reason": "INVALID_DEEP_RESULT"}
    result["timeout_seconds"] = timeout_seconds
    result["preserved_previous_report"] = False
    result["execution_version"] = DEEP_EXECUTION_VERSION
    _write_deep_runtime_status(result)
    return result


def run(legs: int = 4) -> dict:
    report = build_report(legs=legs)
    # Save the small operator-aware layer before starting the expensive deep
    # analysis. Even if deep MODEL/RAW hits the watchdog, PLAYABLE projection and
    # the rest of FULL can continue from a complete operator-aware report.
    base.core._write(base.core.REPORT, report)
    deep = _run_deep_bounded(legs=legs)

    source_rows = base.core._read(base.core.RESULTS, [])
    active = sum(
        1 for row in (source_rows if isinstance(source_rows, list) else [])
        if isinstance(row, dict)
        and (row.get("superbet_market_v91") or {}).get("operator_verified") is True
    )
    return {
        "status": "OK",
        "version": VERSION,
        "base_version": BASE_VERSION,
        "operator_market_context_version": OPERATOR_VERSION,
        "performance_adapter_version": PERFORMANCE_VERSION,
        "coherence_guard_version": COHERENCE_VERSION,
        "deep_execution_version": DEEP_EXECUTION_VERSION,
        "matches": report.get("matches_count", 0),
        "operator_context_matches": active,
        "deep_model_scenario": deep,
        "production_influence": False,
        "prices_used": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
