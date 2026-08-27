from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend" / "player_model_shadow_v89.py"
REPORT = ROOT / "frontend" / "data" / "player_model_shadow_v89.json"
TELEMETRY = ROOT / "frontend" / "data" / "model_telemetry_v84c.json"
META = ROOT / "frontend" / "data" / "meta.json"


def main():
    src = SOURCE.read_text(encoding="utf-8")
    assert 'VERSION = "v8.9"' in src
    assert 'MODE = "SHADOW"' in src
    assert '"production_influence": False' in src
    assert 'final_score"] =' not in src
    assert 'generator_selected"] =' not in src
    assert "pre_match_frozen_features_only" in src
    assert "split_by_match" in src

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report.get("version") == "v8.9"
    assert report.get("mode") == "SHADOW"
    assert report.get("production_influence") is False
    assert report.get("auto_promotion") is False
    assert (report.get("features") or {}).get("leakage_policy") == "pre_match_frozen_features_only"

    telemetry = json.loads(TELEMETRY.read_text(encoding="utf-8"))
    assert (telemetry.get("player_model_shadow_v89") or {}).get("version") == "v8.9"

    meta = json.loads(META.read_text(encoding="utf-8"))
    assert meta.get("player_model_shadow_v89_production_influence") is False

    print(json.dumps({
        "status": "PASS",
        "shadow_status": report.get("status"),
        "training_rows": (report.get("training") or {}).get("rows_total"),
        "holdout_rows": (report.get("training") or {}).get("holdout_rows"),
        "gate": (report.get("gate") or {}).get("status"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
