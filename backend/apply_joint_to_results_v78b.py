from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from joint_builder_v78b import add_joint_builder
from pbp_cache_recovery_v941 import recover_rows_from_cache
from pbp_market_evidence_v940 import enrich_market_evidence

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "frontend" / "data" / "results.json"
META = ROOT / "frontend" / "data" / "meta.json"


def main():
    if not RESULTS.exists():
        raise SystemExit(f"STOP: missing {RESULTS}")
    rows = json.loads(RESULTS.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("STOP: results.json is not a list")

    rows, recovery = recover_rows_from_cache(rows)
    enriched = [enrich_market_evidence(add_joint_builder(m)) for m in rows]
    ready = sum(1 for m in enriched if (m.get("joint_builder_v78b") or {}).get("status") == "READY")
    nd = sum(1 for m in enriched if (m.get("joint_builder_v78b") or {}).get("status") == "N/D")
    failed = sum(1 for m in enriched if (m.get("joint_builder_v78b") or {}).get("status") == "FAIL")
    pbp_market_ready = 0
    ready_by_market = Counter()
    for match in enriched:
        evidence = ((match.get("early_hold_v7") or {}).get("market_evidence_v940") or {})
        if evidence.get("market_ready"):
            pbp_market_ready += 1
        for market in evidence.get("ready_markets") or []:
            ready_by_market[str(market)] += 1

    tmp = RESULTS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(RESULTS)

    try:
        meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
    except Exception:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    meta["pbp_cache_recovery_v941"] = recovery
    meta["pbp_market_ready_v940"] = pbp_market_ready
    meta["pbp_market_ready_by_market_v940"] = dict(sorted(ready_by_market.items()))
    meta_tmp = META.with_suffix(".json.tmp")
    meta_tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_tmp.replace(META)

    print(json.dumps({
        "matches": len(enriched),
        "READY": ready,
        "N/D": nd,
        "FAIL": failed,
        "pbp_market_ready": pbp_market_ready,
        "pbp_market_ready_by_market": dict(sorted(ready_by_market.items())),
        "pbp_cache_recovery": recovery,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
