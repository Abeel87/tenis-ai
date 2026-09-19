from __future__ import annotations

"""Compose existing readiness evidence into one SHADOW semantic contract.

This module does not replace PROD ``model_ready`` and does not compute model
probability.  It only reads existing outputs/audits, preserves missingness, and
reports READY / NOT_READY / UNKNOWN with deterministic reason codes.
"""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .snapshot_digest import SNAPSHOT_CONTRACT, canonical_json_sha256
except ImportError:  # pragma: no cover - direct script execution
    from snapshot_digest import SNAPSHOT_CONTRACT, canonical_json_sha256

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "frontend" / "data" / "results.json"
HISTORY_COVERAGE = ROOT / "frontend" / "data" / "history_coverage_audit_v949.json"
PLAYER_STATE = ROOT / "frontend" / "data" / "player_dna_player_state_shadow.json"
PROFILE_READINESS = ROOT / "frontend" / "data" / "player_dna_profile_readiness.json"
SERVICE_SOURCE_READINESS = ROOT / "frontend" / "data" / "player_dna_service_split_source_readiness.json"
PBP_SPLIT_READINESS = ROOT / "frontend" / "data" / "player_dna_pbp_service_split_readiness.json"
MATCH_STATE_READINESS = ROOT / "frontend" / "data" / "player_dna_match_state_readiness.json"
MATCHUP_READINESS = ROOT / "frontend" / "data" / "player_dna_matchup_readiness_audit.json"
OUT = ROOT / "frontend" / "data" / "readiness_engine_shadow.json"
VERSION = "logic-08-readiness-engine-shadow-v1"
MODE = "SHADOW_READINESS_SEMANTICS_AUDIT_ONLY"
STATUS = "READINESS_SEMANTICS_SHADOW_EVIDENCE_READY"
READY = "READY"
NOT_READY = "NOT_READY"
UNKNOWN = "UNKNOWN"
VALID_STATES = {READY, NOT_READY, UNKNOWN}

# LOGIC-01 deliberately measured freshness scenarios without selecting a magic
# cutoff.  Until a separate evidence/promotion decision selects one, semantic
# freshness readiness must remain UNKNOWN rather than silently fail closed.
SELECTED_FRESHNESS_MAX_AGE_DAYS: int | None = None

PBP_MARKETS = (
    "game_state@2",
    "game_state@4",
    "game_state@6",
    "game_state_sequence_1:1-2:2-3:3",
    "set1_total_over_8.5",
    "set1_total_over_9.5",
    "set1_winner",
    "service_hold_1",
    "service_hold_2",
    "service_hold_3",
)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _match_key(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None


def results_snapshot_sha256(results: list[dict[str, Any]]) -> str:
    """Return the canonical digest of the exact current results snapshot."""
    return canonical_json_sha256(results)


def observability_snapshot_alignment(
    results: list[dict[str, Any]],
    report: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fail closed for observability when readiness and results are not the same snapshot."""
    if not isinstance(report, dict) or not report:
        return {"available": False, "reason": "READINESS_REPORT_UNAVAILABLE"}
    if report.get("status") != STATUS:
        return {"available": False, "reason": "READINESS_STATUS_NOT_READY"}
    source = report.get("source_snapshot") or {}
    if source.get("results_snapshot_contract") != SNAPSHOT_CONTRACT:
        return {"available": False, "reason": "READINESS_SNAPSHOT_CONTRACT_MISMATCH"}
    expected = source.get("results_snapshot_sha256")
    if not isinstance(expected, str) or not expected:
        return {"available": False, "reason": "READINESS_SNAPSHOT_DIGEST_MISSING"}
    current = results_snapshot_sha256(results)
    if expected != current:
        return {
            "available": False,
            "reason": "RESULTS_SNAPSHOT_MISMATCH",
            "expected_results_snapshot_sha256": expected,
            "current_results_snapshot_sha256": current,
        }
    if source.get("history_coverage_snapshot_aligned") is not True or source.get("player_state_snapshot_aligned") is not True:
        return {"available": False, "reason": "READINESS_SOURCE_ALIGNMENT_FAILED"}
    if int(source.get("legacy_model_ready_reference_mismatches") or 0) != 0:
        return {"available": False, "reason": "CURRENT_ENGINE_REFERENCE_MISMATCH"}
    return {
        "available": True,
        "reason": "EXACT_RESULTS_SNAPSHOT_ALIGNED",
        "results_snapshot_sha256": current,
    }


def _reason_code(value: Any) -> str:
    text = str(value or "UNKNOWN").strip().upper()
    chars = [ch if ch.isalnum() else "_" for ch in text]
    return "".join(chars).strip("_") or "UNKNOWN"


def _codes(*values: Any) -> list[str]:
    return sorted({_reason_code(value) for value in values if value})


def _dimension(
    status: str,
    reasons: list[str] | tuple[str, ...],
    provenance: str,
    *,
    support: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in VALID_STATES:
        raise ValueError(f"invalid readiness state: {status}")
    return {
        "status": status,
        "reason_codes": _codes(*reasons),
        "provenance": provenance,
        "support": support or {},
    }
def _history_index(
    report: dict[str, Any],
    result_count: int,
    result_ids: set[str],
    results_snapshot_sha256_value: str,
) -> tuple[dict[str, dict[str, Any]], bool]:
    summary = report.get("summary") or {}
    source_snapshot = report.get("source_snapshot") or {}
    try:
        audited_count = int(summary.get("visible_matches"))
    except (TypeError, ValueError):
        audited_count = -1
    rows = report.get("matches") or []
    index: dict[str, dict[str, Any]] = {}
    duplicate = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = _match_key(row.get("id"))
        if key is None:
            continue
        if key in index:
            duplicate = True
        index[key] = row
    aligned = bool(
        report
        and source_snapshot.get("results_snapshot_contract") == SNAPSHOT_CONTRACT
        and source_snapshot.get("results_snapshot_sha256") == results_snapshot_sha256_value
        and audited_count == result_count
        and len(result_ids) == result_count
        and not duplicate
        and set(index).issubset(result_ids)
    )
    return index, aligned


def _identity_dimension(
    match_id: str,
    history_index: dict[str, dict[str, Any]],
    history_aligned: bool,
) -> dict[str, Any]:
    source = "frontend/data/history_coverage_audit_v949.json"
    if not history_aligned:
        return _dimension(
            UNKNOWN,
            ["IDENTITY_AUDIT_SNAPSHOT_MISMATCH_OR_MISSING"],
            source,
        )
    row = history_index.get(match_id)
    if row is None:
        return _dimension(
            READY,
            ["IDENTITY_RESOLVED_BOTH_PLAYERS"],
            source,
            support={"history_audit_exception_row": False},
        )
    players = [item for item in (row.get("players") or []) if isinstance(item, dict)]
    if len(players) != 2:
        return _dimension(
            UNKNOWN,
            ["IDENTITY_AUDIT_PLAYER_PAIR_INCOMPLETE"],
            source,
        )
    unresolved = []
    player_support = []
    for item in players:
        mode = str(item.get("current_identity_mode") or "none").strip().lower()
        key = item.get("current_history_player_key")
        reason = str(item.get("reason") or "unknown")
        if mode in {"none", "ambiguous"} or not key:
            unresolved.append(f"IDENTITY_{reason}")
        player_support.append(
            {
                "player": item.get("player"),
                "identity_mode": mode,
                "reason": reason,
                "history_matches": int(item.get("matches") or 0),
            }
        )
    if unresolved:
        return _dimension(
            NOT_READY,
            unresolved,
            source,
            support={"players": player_support},
        )
    return _dimension(
        READY,
        ["IDENTITY_RESOLVED_BOTH_PLAYERS"],
        source,
        support={"players": player_support},
    )


def _player_state_index(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    matches = ((report.get("current_card") or {}).get("matches") or [])
    out: dict[str, dict[str, Any]] = {}
    for row in matches:
        if not isinstance(row, dict):
            continue
        key = _match_key(row.get("match_id"))
        if key is not None:
            out[key] = row
    return out
def _state_pair(row: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(row, dict):
        return []
    payload = row.get("player_state") or {}
    if not isinstance(payload, dict):
        return []
    pair = []
    for side in ("p1", "p2"):
        item = payload.get(side)
        if isinstance(item, dict):
            pair.append(item)
    return pair


def _freshness_dimension() -> dict[str, Any]:
    if SELECTED_FRESHNESS_MAX_AGE_DAYS is None:
        return _dimension(
            UNKNOWN,
            ["FRESHNESS_POLICY_NOT_SELECTED_LOGIC_01"],
            "LOGIC-01 history freshness counterfactual",
            support={
                "tested_scenarios_days": [30, 60, 90, 120, 180, 365],
                "selected_max_history_age_days": None,
            },
        )
    return _dimension(
        UNKNOWN,
        ["FRESHNESS_POLICY_SELECTED_BUT_MATCH_APPLICATION_NOT_IMPLEMENTED"],
        "LOGIC-01 history freshness counterfactual",
        support={"selected_max_history_age_days": SELECTED_FRESHNESS_MAX_AGE_DAYS},
    )


def _current_season_dimension(pair: list[dict[str, Any]]) -> dict[str, Any]:
    source = "frontend/data/player_dna_player_state_shadow.json"
    if len(pair) != 2:
        return _dimension(UNKNOWN, ["PLAYER_STATE_MATCH_EVIDENCE_MISSING"], source)
    counts = [int((item.get("current_season") or {}).get("matches") or 0) for item in pair]
    missing = [f"CURRENT_SEASON_HISTORY_MISSING_P{i + 1}" for i, value in enumerate(counts) if value <= 0]
    if missing:
        return _dimension(NOT_READY, missing, source, support={"matches": counts})
    return _dimension(
        UNKNOWN,
        ["CURRENT_SEASON_EVIDENCE_PRESENT_SUFFICIENCY_POLICY_NOT_SELECTED"],
        source,
        support={"matches": counts},
    )
def _surface_dimension(pair: list[dict[str, Any]]) -> dict[str, Any]:
    source = "frontend/data/player_dna_player_state_shadow.json"
    if len(pair) != 2:
        return _dimension(UNKNOWN, ["PLAYER_STATE_MATCH_EVIDENCE_MISSING"], source)
    surfaces = [str(item.get("target_surface") or "unknown").strip().lower() for item in pair]
    if any(value in {"", "unknown", "none"} for value in surfaces):
        return _dimension(
            NOT_READY,
            ["TARGET_SURFACE_UNKNOWN"],
            source,
            support={"target_surfaces": surfaces},
        )
    counts = [
        int((((item.get("current_surface_state") or {}).get("current_season") or {}).get("matches")) or 0)
        for item in pair
    ]
    missing = [f"CURRENT_SURFACE_HISTORY_MISSING_P{i + 1}" for i, value in enumerate(counts) if value <= 0]
    if missing:
        return _dimension(
            NOT_READY,
            missing,
            source,
            support={"target_surfaces": surfaces, "current_season_surface_matches": counts},
        )
    return _dimension(
        UNKNOWN,
        ["SURFACE_EVIDENCE_PRESENT_SUFFICIENCY_POLICY_NOT_SELECTED"],
        source,
        support={"target_surfaces": surfaces, "current_season_surface_matches": counts},
    )


def _rank_context_dimension(pair: list[dict[str, Any]]) -> dict[str, Any]:
    source = "frontend/data/player_dna_player_state_shadow.json"
    if len(pair) != 2:
        return _dimension(UNKNOWN, ["PLAYER_STATE_MATCH_EVIDENCE_MISSING"], source)
    ranks = [(item.get("ranking_momentum") or {}).get("effective_rank") for item in pair]
    missing = [f"RANK_CONTEXT_MISSING_P{i + 1}" for i, value in enumerate(ranks) if value is None]
    if missing:
        return _dimension(NOT_READY, missing, source, support={"effective_ranks": ranks})
    return _dimension(
        READY,
        ["RANK_CONTEXT_PRESENT_BOTH_PLAYERS"],
        source,
        support={"effective_ranks": ranks},
    )
def _opponent_context_dimension(pair: list[dict[str, Any]]) -> dict[str, Any]:
    source = "frontend/data/player_dna_player_state_shadow.json"
    if len(pair) != 2:
        return _dimension(UNKNOWN, ["PLAYER_STATE_MATCH_EVIDENCE_MISSING"], source)
    counts = [
        int((((item.get("opponent_adjusted_performance_trend") or {}).get("support") or {}).get("all_prior_matches")) or 0)
        for item in pair
    ]
    missing = [f"OPPONENT_CONTEXT_HISTORY_MISSING_P{i + 1}" for i, value in enumerate(counts) if value <= 0]
    if missing:
        return _dimension(NOT_READY, missing, source, support={"prior_matches": counts})
    return _dimension(
        UNKNOWN,
        ["OPPONENT_CONTEXT_EVIDENCE_PRESENT_SUFFICIENCY_POLICY_NOT_SELECTED"],
        source,
        support={"prior_matches": counts},
    )


def _serve_return_dimension(
    pair: list[dict[str, Any]],
    source_reports: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source = "Player State + Player DNA readiness audits"
    if len(pair) != 2:
        return _dimension(UNKNOWN, ["PLAYER_STATE_MATCH_EVIDENCE_MISSING"], source)
    current = [item.get("current_season") or {} for item in pair]
    missing = []
    for idx, state in enumerate(current, start=1):
        if state.get("serve_win_rate") is None:
            missing.append(f"SERVE_EVIDENCE_MISSING_P{idx}")
        if state.get("return_win_rate") is None:
            missing.append(f"RETURN_EVIDENCE_MISSING_P{idx}")
    if missing:
        return _dimension(NOT_READY, missing, source)
    audits_present = {
        name: bool(report)
        for name, report in source_reports.items()
        if name in {"profile", "service_source", "pbp_split"}
    }
    return _dimension(
        UNKNOWN,
        ["SERVE_RETURN_EVIDENCE_PRESENT_SUFFICIENCY_POLICY_NOT_SELECTED"],
        source,
        support={"source_audits_present": audits_present},
    )
def _pbp_market_support(evidence: dict[str, Any], market: str) -> dict[str, Any]:
    row: dict[str, Any] = {}
    if market.startswith("game_state@"):
        row = (evidence.get("game_state") or {}).get(market.split("@", 1)[1]) or {}
    elif market == "game_state_sequence_1:1-2:2-3:3":
        row = evidence.get("balanced_sequence") or {}
    elif market.startswith("set1_total_over_"):
        line = market.removeprefix("set1_total_over_")
        row = (evidence.get("set1_total") or {}).get(line) or {}
    elif market == "set1_winner":
        row = evidence.get("set1_winner") or {}
    elif market.startswith("service_hold_"):
        service_no = market.removeprefix("service_hold_")
        row = (evidence.get("service_holds") or {}).get(service_no) or {}
    sample_floor = row.get("sample_floor")
    if sample_floor is None and row:
        p1 = row.get("p1") or {}
        p2 = row.get("p2") or {}
        try:
            sample_floor = min(int(p1.get("n") or 0), int(p2.get("n") or 0))
        except (TypeError, ValueError):
            sample_floor = None
    return {
        "sample_floor": sample_floor,
        "min_matches_per_metric": evidence.get("min_matches_per_metric"),
    }


def _pbp_readiness(match: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    source = "backend/pbp_market_evidence.py::market_evidence_v940"
    evidence = ((match.get("early_hold_v7") or {}).get("market_evidence_v940") or {})
    if not isinstance(evidence, dict) or not evidence:
        unknown = {
            market: _dimension(UNKNOWN, ["PBP_MARKET_EVIDENCE_UNAVAILABLE"], source)
            for market in PBP_MARKETS
        }
        return _dimension(UNKNOWN, ["PBP_MARKET_EVIDENCE_UNAVAILABLE"], source), unknown
    if evidence.get("mode") != "EVIDENCE_ONLY":
        unknown = {
            market: _dimension(UNKNOWN, ["PBP_MARKET_EVIDENCE_CONTRACT_INVALID"], source)
            for market in PBP_MARKETS
        }
        return _dimension(UNKNOWN, ["PBP_MARKET_EVIDENCE_CONTRACT_INVALID"], source), unknown
    ready_markets = {str(value) for value in (evidence.get("ready_markets") or [])}
    markets: dict[str, Any] = {}
    for market in PBP_MARKETS:
        is_ready = market in ready_markets
        markets[market] = _dimension(
            READY if is_ready else NOT_READY,
            [
                "EXISTING_PBP_MARKET_GATE_PASSED"
                if is_ready
                else "EXISTING_PBP_MARKET_GATE_NOT_MET"
            ],
            source,
            support=_pbp_market_support(evidence, market),
        )
    any_ready = bool(ready_markets & set(PBP_MARKETS))
    dimension = _dimension(
        READY if any_ready else NOT_READY,
        ["PBP_HAS_READY_MARKET" if any_ready else "PBP_NO_READY_MARKET"],
        source,
        support={
            "ready_markets": sorted(ready_markets),
            "min_matches_per_metric": evidence.get("min_matches_per_metric"),
        },
    )
    return dimension, markets


def _source_summary(report: dict[str, Any]) -> dict[str, Any]:
    if not report:
        return {"available": False}
    return {
        "available": True,
        "version": report.get("version"),
        "mode": report.get("mode"),
        "gate": report.get("gate"),
        "production_influence": report.get("production_influence"),
        "runtime_scoring_enabled": report.get("runtime_scoring_enabled"),
    }


def _state_legacy_model_ready(row: dict[str, Any] | None) -> Any:
    if not isinstance(row, dict):
        return None
    reference = row.get("current_engine_reference") or {}
    selected = reference.get("selected_existing_fields") or {}
    return selected.get("model_ready")
def compose_readiness(
    results: list[dict[str, Any]],
    history_report: dict[str, Any],
    player_state_report: dict[str, Any],
    *,
    source_reports: dict[str, dict[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a descriptive readiness report without mutating source results."""
    source_reports = source_reports or {}
    result_keys = [_match_key(row.get("id")) for row in results if isinstance(row, dict)]
    result_ids = {key for key in result_keys if key is not None}
    result_ids_unique = len(result_ids) == len(results)
    current_results_snapshot_sha256 = results_snapshot_sha256(results)
    history_index, history_aligned = _history_index(
        history_report,
        len(results),
        result_ids,
        current_results_snapshot_sha256,
    )
    state_index = _player_state_index(player_state_report)
    player_state_aligned = bool(
        player_state_report
        and result_ids_unique
        and set(state_index) == result_ids
    )
    dimension_counts: dict[str, Counter[str]] = {}
    market_counts: dict[str, Counter[str]] = {
        market: Counter() for market in PBP_MARKETS
    }
    rows: list[dict[str, Any]] = []
    legacy_mismatches = 0

    for match in results:
        if not isinstance(match, dict):
            continue
        match_id = _match_key(match.get("id"))
        if match_id is None:
            continue
        state_row = state_index.get(match_id)
        pair = _state_pair(state_row)
        pbp_dimension, pbp_markets = _pbp_readiness(match)
        dimensions = {
            "identity": _identity_dimension(match_id, history_index, history_aligned),
            "freshness": _freshness_dimension(),
            "current_season": _current_season_dimension(pair),
            "surface": _surface_dimension(pair),
            "rank_context": _rank_context_dimension(pair),
            "serve_return": _serve_return_dimension(pair, source_reports),
            "pbp": pbp_dimension,
            "opponent_context": _opponent_context_dimension(pair),
        }
        for name, dimension in dimensions.items():
            dimension_counts.setdefault(name, Counter())[dimension["status"]] += 1
        for market, payload in pbp_markets.items():
            market_counts[market][payload["status"]] += 1

        legacy = match.get("model_ready") if isinstance(match.get("model_ready"), bool) else None
        state_legacy = _state_legacy_model_ready(state_row)
        legacy_consistent = state_legacy is None or state_legacy == legacy
        legacy_mismatches += int(not legacy_consistent)
        rows.append(
            {
                "match_id": match_id,
                "scheduled_time": match.get("scheduled_time"),
                "p1": match.get("p1"),
                "p2": match.get("p2"),
                "legacy_model_ready": legacy,
                "legacy_model_ready_source": "frontend/data/results.json",
                "legacy_model_ready_unchanged": True,
                "current_engine_reference_consistent": legacy_consistent,
                "dimensions": dimensions,
                "market_readiness": {
                    "pbp_early_hold": {
                        "contract_owner": "backend/pbp_market_evidence.py",
                        "markets": pbp_markets,
                    },
                    "current_engine_generic": _dimension(
                        UNKNOWN,
                        ["LEGACY_MODEL_READY_NOT_MARKET_SPECIFIC_READINESS"],
                        "frontend/data/results.json",
                        support={"legacy_model_ready": legacy},
                    ),
                },
            }
        )

    legacy_true = sum(row["legacy_model_ready"] is True for row in rows)
    legacy_false = sum(row["legacy_model_ready"] is False for row in rows)
    stamp = generated_at or datetime.now(timezone.utc).isoformat()
    return {
        "version": VERSION,
        "mode": MODE,
        "status": STATUS if (legacy_mismatches == 0 and history_aligned and player_state_aligned) else "READINESS_SEMANTICS_SOURCE_MISMATCH",
        "generated_at": stamp,
        "network_calls": 0,
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "runtime_gating_enabled": False,
        "training_join_enabled": False,
        "current_engine_write_enabled": False,
        "legacy_model_ready_write_enabled": False,
        "probability_created": False,
        "weights_created": False,
        "thresholds_created": False,
        "feature_activation": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "ineed_influence": False,
        "auto_promote": False,
        "promotion_gate": False,
        "semantic_contract": {
            "states": [READY, NOT_READY, UNKNOWN],
            "unknown_is_not_not_ready": True,
            "no_single_overall_ready_boolean": True,
            "legacy_model_ready_observational_only": True,
            "coverage_is_not_automatically_readiness": True,
            "missing_policy_stays_unknown": True,
            "market_readiness_requires_existing_explicit_contract": True,
            "no_probability_or_model_recalculation": True,
        },
        "source_snapshot": {
            "results_matches": len(results),
            "results_snapshot_contract": SNAPSHOT_CONTRACT,
            "results_snapshot_sha256": current_results_snapshot_sha256,
            "result_match_ids_unique": result_ids_unique,
            "history_coverage_available": bool(history_report),
            "history_coverage_snapshot_aligned": history_aligned,
            "player_state_available": bool(player_state_report),
            "player_state_matches": len(state_index),
            "player_state_snapshot_aligned": player_state_aligned,
            "legacy_model_ready_reference_mismatches": legacy_mismatches,
            "readiness_audits": {
                name: _source_summary(report) for name, report in sorted(source_reports.items())
            },
        },
        "summary": {
            "matches": len(rows),
            "legacy_model_ready_true": legacy_true,
            "legacy_model_ready_false": legacy_false,
            "legacy_model_ready_missing": len(rows) - legacy_true - legacy_false,
            "dimension_status_counts": {
                name: {state: int(counter[state]) for state in (READY, NOT_READY, UNKNOWN)}
                for name, counter in sorted(dimension_counts.items())
            },
            "pbp_market_status_counts": {
                market: {state: int(counter[state]) for state in (READY, NOT_READY, UNKNOWN)}
                for market, counter in sorted(market_counts.items())
            },
        },
        "matches": rows,
    }


def build(output_path: Path = OUT) -> dict[str, Any]:
    results = _load_json(RESULTS, [])
    if not isinstance(results, list):
        results = []
    history = _load_json(HISTORY_COVERAGE, {})
    player_state = _load_json(PLAYER_STATE, {})
    source_reports = {
        "profile": _load_json(PROFILE_READINESS, {}),
        "service_source": _load_json(SERVICE_SOURCE_READINESS, {}),
        "pbp_split": _load_json(PBP_SPLIT_READINESS, {}),
        "match_state": _load_json(MATCH_STATE_READINESS, {}),
        "matchup": _load_json(MATCHUP_READINESS, {}),
    }
    report = compose_readiness(
        results,
        history if isinstance(history, dict) else {},
        player_state if isinstance(player_state, dict) else {},
        source_reports={
            key: value if isinstance(value, dict) else {}
            for key, value in source_reports.items()
        },
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
