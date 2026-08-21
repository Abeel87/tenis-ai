from __future__ import annotations

import json
from pathlib import Path

from joint_builder_v78b import add_joint_builder

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "frontend" / "data" / "results.json"


def main():
    if not RESULTS.exists():
        raise SystemExit(f"STOP: missing {RESULTS}")
    rows = json.loads(RESULTS.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("STOP: results.json is not a list")

    enriched = [add_joint_builder(m) for m in rows]
    ready = sum(1 for m in enriched if (m.get("joint_builder_v78b") or {}).get("status") == "READY")
    nd = sum(1 for m in enriched if (m.get("joint_builder_v78b") or {}).get("status") == "N/D")
    failed = sum(1 for m in enriched if (m.get("joint_builder_v78b") or {}).get("status") == "FAIL")

    tmp = RESULTS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(RESULTS)
    print(json.dumps({"matches": len(enriched), "READY": ready, "N/D": nd, "FAIL": failed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
