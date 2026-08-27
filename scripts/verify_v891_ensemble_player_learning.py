from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend" / "ensemble_player_learning_v891.py"
REPORT = ROOT / "frontend" / "data" / "ensemble_player_learning_v891.json"
TELEMETRY = ROOT / "frontend" / "data" / "model_telemetry_v84c.json"
META = ROOT / "frontend" / "data" / "meta.json"


def main():
    src = SOURCE.read_text(encoding="utf-8")
    assert 'VERSION = "v8.9.1"' in src
    assert 'MODE = "SHADOW"' in src
    assert '"production_influence": False' in src
    assert 'final_score"] =' not in src
    assert 'generator_selected"] =' not in src
    assert "hierarchical_segment_blend" in src
    assert "market_quality" in src
    assert "surface_quality" in src
    assert "policy_fit_train_only_holdout_untouched" in src

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report.get("version") == "v8.9.1"
    assert report.get("mode") == "SHADOW"
    assert report.get("production_influence") is False
    assert report.get("auto_promotion") is False
    assert ((report.get("training") or {}).get("leakage_policy")
            == "policy_fit_train_only_holdout_untouched")
    policy = report.get("policy") or {}
    assert policy.get("method") == "hierarchical_segment_blend"
    assert 0 <= float(policy.get("global_alpha") or 0) <= 0.45

    telemetry = json.loads(TELEMETRY.read_text(encoding="utf-8"))
    assert (telemetry.get("ensemble_player_learning_v891") or {}).get("version") == "v8.9.1"

    meta = json.loads(META.read_text(encoding="utf-8"))
    assert meta.get("ensemble_player_learning_v891_production_influence") is False

    print(json.dumps({
        "status": "PASS",
        "shadow_status": report.get("status"),
        "training_rows": (report.get("training") or {}).get("rows_total"),
        "holdout_rows": (report.get("training") or {}).get("holdout_rows"),
        "global_alpha": policy.get("global_alpha"),
        "gate": (report.get("gate") or {}).get("status"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
