from __future__ import annotations

"""Production iNeed$ runner with an explicit market-scope adapter.

All bankroll/value/risk mathematics remain in ``ineed_money`` unchanged.
Existing open bets are still supplied to settlement through the original history
path; only new evaluation candidates are filtered before evaluation.
"""

import argparse
from datetime import datetime, timezone
import json

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
except ImportError:
    from ineed_money import evaluate, build_settlements
    from ineed_runner import CONFIG, DIRECT, HISTORY, RESULTS, post, read, refresh_direct_for_ineed
    from ineed_scope import filter_results


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
    payload = build_payload(state)
    result = post(args.edge_url, args.oidc_token, {"action": "sync", "payload": payload})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
