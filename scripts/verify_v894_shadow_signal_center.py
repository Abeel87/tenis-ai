#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend" / "shadow_signal_center_v894.py"
UI = ROOT / "frontend" / "shadow-signals-v894.js"
CSS = ROOT / "frontend" / "shadow-signals-v894.css"
BOOT = ROOT / "frontend" / "loading-fix-v889.js"
REPORT = ROOT / "frontend" / "data" / "shadow_signals_v894.json"
WORKFLOW = ROOT / ".github" / "workflows" / "update-and-pages.yml"
UI_WORKFLOW = ROOT / ".github" / "workflows" / "ui-smoke.yml"


def ck(ok, name):
    if not ok:
        raise SystemExit(f"FAIL  {name}")
    print(f"PASS  {name}")


def load(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def main():
    backend = BACKEND.read_text(encoding="utf-8")
    ui = UI.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    boot = BOOT.read_text(encoding="utf-8")
    wf = WORKFLOW.read_text(encoding="utf-8")
    ui_wf = UI_WORKFLOW.read_text(encoding="utf-8")

    ck('VERSION = "v8.9.4"' in backend, "backend version")
    ck('production_influence": False' in backend, "backend shadow-only contract")
    for model in (
        "player_intelligence",
        "catboost_player",
        "ensemble_player",
        "catboost_player_elo",
        "ensemble_player_elo",
        "tabpfn_elo",
    ):
        ck(model in backend, f"feed model {model}")

    ck('data-p751-nav="shadow-signals"' in ui, "dedicated SHADOW bottom-nav route")
    ck("data/shadow_signals_v894.json" in ui, "compact SHADOW feed fetch")
    ck("0% PROD" in ui, "visible production isolation")
    ck("repeat(8" in css and ".sh894-view" in css, "8-item mobile nav + isolated view")
    ck("shadow-signals-v894.css?v=894" in boot, "SHADOW CSS bootstrap")
    ck("shadow-signals-v894.js?v=894" in boot, "SHADOW JS bootstrap")
    ck("Shadow Signal Center v8.9.4" in wf, "data pipeline integration")
    ck("Shadow Signal Center Guard v8.9.4" in wf, "data pipeline guard")
    ck("Shadow Signal Center Guard v8.9.4" in ui_wf, "UI health guard")

    report = load(REPORT, None)
    if report is None:
        print("PASS  runtime report pending first v8.9.4 data build")
        return 0

    ck(report.get("version") == "v8.9.4", "runtime version")
    ck(report.get("mode") == "SHADOW", "runtime mode")
    ck(report.get("production_influence") is False, "runtime production isolation")
    ck(isinstance(report.get("models"), list) and len(report["models"]) >= 6, "runtime model registry")
    ck(all(m.get("production_influence") is False for m in report["models"]), "all runtime models remain shadow")
    ck(isinstance(report.get("matches"), list), "runtime match feed")

    print(json.dumps({
        "status": "PASS",
        "version": report.get("version"),
        "matches": report.get("matches_count"),
        "model_signal_counts": report.get("model_signal_counts"),
        "production_influence": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
