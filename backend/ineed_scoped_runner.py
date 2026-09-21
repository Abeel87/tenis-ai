from __future__ import annotations

"""Production iNeed$ runner with an explicit market-scope adapter.

All bankroll/value/risk mathematics remain in ``ineed_money`` unchanged.
Existing open bets are still supplied to settlement through the original history
path; only new evaluation candidates are filtered before evaluation.
"""

import argparse
from datetime import datetime, timezone
import json

BUILDER_RESERVATION_CONTRACT_VERSION = "logic12-builder-reservation-shadow-v1"

try:
    from .ineed_money import evaluate, build_settlements
    from .ineed_runner import (
        CONFIG,
        DIRECT,
        HISTORY,
        RESULTS,
        post,
        read,
        refresh_direct_for_ineed,
    )
    from .ineed_scope import filter_results
    from .ineed_builder_shadow import (
        attach_verified_combined_quote,
        build_shadow_composition,
        evaluate_builder_economics_shadow,
        resolve_artifact_combined_quote,
    )
    from .ineed_builder_ticket_shadow import build_builder_ticket_shadow
    from .superbet_builder_quotes import OUTPUT_PATH as BUILDER_QUOTES
except ImportError:
    from ineed_money import evaluate, build_settlements
    from ineed_runner import CONFIG, DIRECT, HISTORY, RESULTS, post, read, refresh_direct_for_ineed
    from ineed_scope import filter_results
    from ineed_builder_shadow import (
        attach_verified_combined_quote,
        build_shadow_composition,
        evaluate_builder_economics_shadow,
        resolve_artifact_combined_quote,
    )
    from ineed_builder_ticket_shadow import build_builder_ticket_shadow
    from superbet_builder_quotes import OUTPUT_PATH as BUILDER_QUOTES


def build_builder_shadow_runtime(state: dict, *, now: datetime | None = None) -> dict:
    """Produce Phase-4/5 SHADOW evidence without V1 sync or reservation writes."""
    results = read(RESULTS, [])
    direct = read(DIRECT, {})
    quote_artifact = read(BUILDER_QUOTES, {})
    experiment = state.get("experiment") or {}
    cfg = experiment.get("config") or read(CONFIG, {})

    result_rows = results if isinstance(results, list) else []
    scoped_results, scope = filter_results(result_rows)
    direct_feed = direct if isinstance(direct, dict) else {}
    artifact = quote_artifact if isinstance(quote_artifact, dict) else {}

    compositions = []
    for match in scoped_results:
        composition = build_shadow_composition(match)
        if composition is None:
            continue
        quote = resolve_artifact_combined_quote(composition, direct_feed, artifact)
        compositions.append(attach_verified_combined_quote(composition, quote))

    evaluations = evaluate_builder_economics_shadow(compositions, cfg, state, now=now)
    by_composition = {
        str(row.get("composition_id") or ""): row
        for row in evaluations
        if isinstance(row, dict) and row.get("composition_id")
    }
    tickets = []
    for composition in compositions:
        evaluation = by_composition.get(str(composition.get("composition_id") or ""))
        if not isinstance(evaluation, dict) or evaluation.get("status") != "SHADOW_QUALIFIED":
            continue
        ticket = build_builder_ticket_shadow(composition, evaluation)
        if ticket is not None:
            tickets.append(ticket)

    return {
        "mode": "SHADOW",
        "economic_unit": "BET_BUILDER_COMPOSITION",
        "quote_artifact_status": artifact.get("status"),
        "quote_artifact_generated_at": artifact.get("generated_at"),
        "direct_generated_at": direct_feed.get("generated_at"),
        "market_scope": scope,
        "compositions": compositions,
        "evaluations": evaluations,
        "tickets": tickets,
        "compositions_count": len(compositions),
        "evaluations_count": len(evaluations),
        "qualified_count": sum(1 for row in evaluations if row.get("status") == "SHADOW_QUALIFIED"),
        "tickets_count": len(tickets),
        "edge_sync_enabled": False,
        "reservation_writes_enabled": False,
        "settlement_enabled": False,
        "automatic_real_betting": False,
    }


def _builder_shadow_unavailable(reason_code: str) -> dict:
    return {
        "mode": "SHADOW",
        "economic_unit": "BET_BUILDER_COMPOSITION",
        "status": "SOURCE_UNAVAILABLE",
        "reason_code": reason_code,
        "quote_artifact_status": None,
        "compositions": [],
        "evaluations": [],
        "tickets": [],
        "compositions_count": 0,
        "evaluations_count": 0,
        "qualified_count": 0,
        "tickets_count": 0,
        "edge_sync_enabled": False,
        "reservation_writes_enabled": False,
        "settlement_enabled": False,
        "automatic_real_betting": False,
    }



def _builder_shadow_summary(payload: dict) -> dict:
    return {
        "mode": payload.get("mode"),
        "economic_unit": payload.get("economic_unit"),
        "status": payload.get("status", "OK"),
        "reason_code": payload.get("reason_code"),
        "quote_artifact_status": payload.get("quote_artifact_status"),
        "compositions_count": payload.get("compositions_count"),
        "evaluations_count": payload.get("evaluations_count"),
        "qualified_count": payload.get("qualified_count"),
        "tickets_count": payload.get("tickets_count"),
        "edge_sync_enabled": False,
        "reservation_writes_enabled": False,
        "settlement_enabled": False,
        "automatic_real_betting": False,
    }

def _builder_reservation_gate(state: dict) -> tuple[bool, str | None]:
    experiment = state.get("experiment") if isinstance(state, dict) else None
    cfg = experiment.get("config") if isinstance(experiment, dict) else None
    reservation = cfg.get("builder_reservation") if isinstance(cfg, dict) else None
    if not isinstance(reservation, dict) or reservation.get("enabled") is not True:
        return False, "BUILDER_RESERVATION_DISABLED"
    if str(reservation.get("contract_version") or "").strip() != BUILDER_RESERVATION_CONTRACT_VERSION:
        return False, "BUILDER_RESERVATION_CONTRACT_MISMATCH"
    return True, None


def sync_builder_ticket_reservations(edge_url: str, oidc_token: str, state: dict, builder_shadow: dict) -> dict:
    """Persist qualified builder tickets only behind the explicit SHADOW reservation gate."""
    enabled, reason_code = _builder_reservation_gate(state)
    tickets = builder_shadow.get("tickets") if isinstance(builder_shadow, dict) else None
    ticket_rows = tickets if isinstance(tickets, list) else []
    summary = {
        "mode": "SHADOW",
        "contract_version": BUILDER_RESERVATION_CONTRACT_VERSION,
        "status": "DISABLED",
        "reason_code": reason_code,
        "tickets_count": len(ticket_rows),
        "attempted_count": 0,
        "reservations_count": 0,
        "reserved_count": 0,
        "idempotent_count": 0,
        "reservation_writes_enabled": enabled,
        "settlement_enabled": False,
        "automatic_real_betting": False,
    }
    if not enabled:
        return summary
    if builder_shadow.get("status", "OK") != "OK":
        summary.update(status="SKIPPED_SOURCE_UNAVAILABLE", reason_code=builder_shadow.get("reason_code"))
        return summary
    if not ticket_rows:
        summary.update(status="NO_TICKETS", reason_code=None)
        return summary

    experiment = state.get("experiment") if isinstance(state, dict) else None
    experiment_id = experiment.get("id") if isinstance(experiment, dict) else None
    if not experiment_id:
        raise RuntimeError("BUILDER_RESERVATION_EXPERIMENT_MISSING")

    result = post(edge_url, oidc_token, {
        "action": "reserve_builder_tickets",
        "payload": {
            "experiment_id": experiment_id,
            "operator": "superbet.pl",
            "mode": "SHADOW",
            "contract_version": BUILDER_RESERVATION_CONTRACT_VERSION,
            "automatic_real_betting": False,
            "tickets": ticket_rows,
        },
    })
    reservations = result.get("reservations") if isinstance(result, dict) else None
    if result.get("ok") is not True or not isinstance(reservations, list):
        raise RuntimeError("BUILDER_RESERVATION_SYNC_INVALID_RESPONSE")
    summary.update(
        status="OK",
        reason_code=None,
        attempted_count=len(ticket_rows),
        reservations_count=len(reservations),
        reserved_count=sum(1 for row in reservations if isinstance(row, dict) and row.get("status") == "RESERVED"),
        idempotent_count=sum(1 for row in reservations if isinstance(row, dict) and row.get("status") == "IDEMPOTENT"),
    )
    return summary


def build_payload(state: dict) -> dict:
    results = read(RESULTS, [])
    direct = read(DIRECT, {})
    history = read(HISTORY, [])
    experiment = state.get("experiment") or {}
    cfg = experiment.get("config") or read(CONFIG, {})

    result_rows = results if isinstance(results, list) else []
    scoped_results, scope = filter_results(result_rows)
    direct_feed = direct if isinstance(direct, dict) else {}
    fresh_direct, enrichment = refresh_direct_for_ineed(scoped_results, direct_feed)

    evaluations = evaluate(scoped_results, fresh_direct, cfg, state)
    settlements = build_settlements(
        state.get("open_bets") or [], history if isinstance(history, list) else [], cfg
    )
    return {
        "experiment_id": experiment.get("id"),
        "operator": "superbet.pl",
        "mode": "SHADOW",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluations": evaluations,
        "settlements": settlements,
        "health": {
            "automatic_real_betting": False,
            "results_rows": len(result_rows),
            "scoped_results_rows": len(scoped_results),
            "market_scope": scope,
            "direct_status": fresh_direct.get("status") if isinstance(fresh_direct, dict) else None,
            "direct_source": fresh_direct.get("source") if isinstance(fresh_direct, dict) else None,
            "direct_enrichment": enrichment,
            "evaluations": len(evaluations),
            "settlements": len(settlements),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edge-url", required=True)
    ap.add_argument("--oidc-token", required=True)
    args = ap.parse_args()
    state = post(args.edge_url, args.oidc_token, {"action": "state"})
    try:
        builder_shadow = build_builder_shadow_runtime(state)
    except Exception:
        # Builder evidence is additive SHADOW only. It must never block or
        # alter the established V1 sync path when its local evidence is bad.
        builder_shadow = _builder_shadow_unavailable("BUILDER_SHADOW_PRODUCER_FAILED")
    payload = build_payload(state)
    result = post(args.edge_url, args.oidc_token, {"action": "sync", "payload": payload})
    sync_state = result.get("state") if isinstance(result, dict) and isinstance(result.get("state"), dict) else state
    builder_persistence = sync_builder_ticket_reservations(
        args.edge_url, args.oidc_token, sync_state, builder_shadow
    )
    print(json.dumps({
        "sync": result,
        "builder_shadow": _builder_shadow_summary(builder_shadow),
        "builder_persistence": builder_persistence,
    }, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
