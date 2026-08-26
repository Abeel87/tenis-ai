from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "frontend" / "data" / "accuracy_lab_v86.json"


def main():
    if not REPORT.exists():
        print("v8.6 Accuracy Shadow: SKIP — report not generated; production remains unchanged")
        return
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    assert data.get("production_mode") == "shadow_only"
    assert data.get("production_changed") is False
    assert data.get("status") in ("ACTIVE", "ACTIVE_PARTIAL", "UNAVAILABLE")
    if data.get("status") in ("ACTIVE", "ACTIVE_PARTIAL"):
        training = data.get("training") or {}
        assert int(training.get("train") or 0) > 0
        assert int(training.get("val") or 0) > 0
        current = data.get("current") or {}
        assert (current.get("validation") or {}).get("brier") is not None
        assert isinstance(data.get("market_thresholds_shadow"), dict)
    print(f"v8.6 Accuracy Shadow: PASS ({data.get('status')})")


if __name__ == "__main__":
    main()
