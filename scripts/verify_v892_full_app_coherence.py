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
    coherence = read(FRONTEND / "app-coherence.js")
    sw = read(FRONTEND / "sw.js")
    symphony = read(FRONTEND / "symphony2.js")
    telemetry = json.loads(read(FRONTEND / "data" / "model_telemetry_v84c.json"))
    meta = json.loads(read(FRONTEND / "data" / "meta.json"))

    checks = {
        "protected_core_version": "appVersion: 'v8.0.1'" in app_meta,
        "protected_display_contract": "displayVersion:'v8.8.7'" in app_meta,
        "protected_ui_architecture": "currentUiArchitecture:'v8.8.7-checkpoint-quality-lock'" in app_meta,
        "visible_release_version": "releaseVersion:'v9.2.3'" in app_meta and "window.TENIS_AI_APPLY_META?.()" in coherence,
        "legacy_release_marker": "Tenis AI v8.8.7" in index,
        "player_model_meta": "playerModelShadowVersion:'v8.9'" in app_meta,
        "player_learning_meta": "ensemblePlayerLearningVersion:'v8.9.1'" in app_meta,
        "symphony_meta": "symphonyVersion:'canonical'" in app_meta,
        "coherence_addon_loaded": "loadAddon('app-coherence.js','app-coherence-addon')" in app_meta,
        "human_pi_addon_loaded": "loadAddon('player-intelligence-human.js','player-intelligence-human-addon')" in app_meta,
        "legacy_scenario_removed": "scenario-studio-v82a.js" not in index and "scenario-runtime-v202.js" not in index,
        "legacy_generator_quality_removed": "generator-quality-v888.js" not in index and not (FRONTEND / "generator-quality-v888.js").exists(),
        "symphony_runtime_loaded": 'src="symphony2.js"' in index,
        "symphony_ui_loaded": 'href="symphony2.css"' in index,
        "symphony_current_feed": "data/symphony2_current.json" in symphony,
        "coherence_shadow_only": "productionInfluence:false" in coherence and "0% wpływu na PROD" in coherence,
        "coherence_player_model_visible": "player_model_shadow_v89" in coherence,
        "coherence_player_learning_visible": "ensemble_player_learning_v891" in coherence,
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
        "version": "v8.9.2-symphony2",
        "checks": len(checks),
        "player_model_gate": ((telemetry.get("player_model_shadow_v89") or {}).get("gate") or {}).get("status"),
        "player_learning_gate": ((telemetry.get("ensemble_player_learning_v891") or {}).get("gate") or {}).get("status"),
        "production_influence": False,
        "scenario_generator_retired": True,
        "symphony2_active": True,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
