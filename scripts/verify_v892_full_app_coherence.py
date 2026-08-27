from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    app_meta = read(FRONTEND / "app-meta.js")
    index = read(FRONTEND / "index.html")
    coherence = read(FRONTEND / "app-coherence-v892.js")
    generator = read(FRONTEND / "generator-quality-v888.js")
    scenario = read(FRONTEND / "scenario-studio-v82a.js")
    sw = read(FRONTEND / "sw.js")
    telemetry = json.loads(read(FRONTEND / "data" / "model_telemetry_v84c.json"))
    meta = json.loads(read(FRONTEND / "data" / "meta.json"))

    checks = {
        "protected_core_version": "appVersion: 'v8.0.1'" in app_meta,
        "release_version": "displayVersion: 'v8.9.2'" in app_meta,
        "legacy_release_marker": "displayVersion: 'v8.8.7'" in app_meta and "Tenis AI v8.8.7" in index,
        "player_model_meta": "playerModelShadowVersion: 'v8.9'" in app_meta,
        "player_learning_meta": "ensemblePlayerLearningVersion: 'v8.9.1'" in app_meta,
        "quality_lock_meta": "generatorQualityLockVersion: 'v8.8.9'" in app_meta,
        "coherence_addon_loaded": "app-coherence-v892.js?v=892" in app_meta,
        "human_pi_addon_loaded": "player-intelligence-v888-human.js?v=888" in app_meta,
        "coherence_shadow_only": "productionInfluence:false" in coherence and "0% wpływu na PROD" in coherence,
        "coherence_player_model_visible": "player_model_shadow_v89" in coherence,
        "coherence_player_learning_visible": "ensemble_player_learning_v891" in coherence,
        "balanced_floor_aligned": "balanced:{minItem:72,minAvg:72" in generator and "balanced:{strong:76,floor:72,minAverage:72" in scenario,
        "stable_floor_aligned": "stable:{minItem:74,minAvg:74" in generator and "stable:{strong:78,floor:74,minAverage:74" in scenario,
        "strong_floor_aligned": "strong:{minItem:80,minAvg:80" in generator and "strong:{strong:84,floor:80,minAverage:80" in scenario,
        "large_json_not_sw_cached": "url.pathname.endsWith('/data/results.json')" in sw and "url.pathname.endsWith('/data/history.json')" in sw,
        "player_model_report_present": (telemetry.get("player_model_shadow_v89") or {}).get("version") == "v8.9",
        "player_learning_report_present": (telemetry.get("ensemble_player_learning_v891") or {}).get("version") == "v8.9.1",
        "player_model_shadow": (telemetry.get("player_model_shadow_v89") or {}).get("production_influence") is False,
        "player_learning_shadow": (telemetry.get("ensemble_player_learning_v891") or {}).get("production_influence") is False,
        "meta_player_model_shadow": meta.get("player_model_shadow_v89_production_influence") is False,
        "meta_player_learning_shadow": meta.get("ensemble_player_learning_v891_production_influence") is False,
    }

    failed = [name for name, ok in checks.items() if not ok]
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if failed:
        raise SystemExit(f"Full App Coherence v8.9.2 failed: {', '.join(failed)}")

    print(json.dumps({
        "status": "PASS",
        "version": "v8.9.2",
        "checks": len(checks),
        "player_model_gate": ((telemetry.get("player_model_shadow_v89") or {}).get("gate") or {}).get("status"),
        "player_learning_gate": ((telemetry.get("ensemble_player_learning_v891") or {}).get("gate") or {}).get("status"),
        "production_influence": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
