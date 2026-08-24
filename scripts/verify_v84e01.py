#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
ERR=[]

def read(path):
    p=ROOT/path
    if not p.exists():
        ERR.append(f"brak pliku: {path}")
        return ""
    return p.read_text(encoding="utf-8")

def req(text,needle,msg):
    if needle not in text:
        ERR.append(msg)

def main():
    idx=read("frontend/index.html")
    js=read("frontend/hotfix-v84e01.js")
    app=read("frontend/app.js")
    scenario=read("frontend/scenario-studio-v82a.js")

    req(js,"const VERSION='v8.4E0.1'","hotfix nie ma wersji v8.4E0.1")
    req(js,"isUnavailableFixture","brak filtra niedostępnych fixture")
    for marker in ("cancelled","canceled","walkover","abandoned","postponed"):
        req(js,marker,f"filtr nie obsługuje statusu: {marker}")
    req(js,"data/history.json","hotfix nie odświeża history.json")
    req(js,"data/history_stats.json","hotfix nie odświeża history_stats.json")
    if "data/results.json" in js:
        ERR.append("History hotfix nie może pobierać results.json")

    req(idx,'runtime-health-v84e0.js?v=84e0',"brak Runtime Health v8.4E0")
    req(idx,'hotfix-v84e01.js?v=84e01',"index nie ładuje v8.4E0.1")
    req(idx,'scenario-studio-v82a.js?v=82a6&hf=84a1',"naruszono chroniony Scenario Studio")

    app_pos=idx.find("app.js")
    runtime_pos=idx.find("runtime-health-v84e0.js")
    hotfix_pos=idx.find("hotfix-v84e01.js")
    scenario_pos=idx.find("scenario-studio-v82a.js")
    if min(app_pos,runtime_pos,hotfix_pos,scenario_pos)<0 or not (app_pos<runtime_pos<hotfix_pos<scenario_pos):
        ERR.append("kolejność musi być app.js -> runtime v8.4E0 -> hotfix v8.4E0.1 -> Scenario Studio")

    # We intentionally keep protected legacy files unchanged; the hotfix wraps them additively.
    req(app,"function filteredReady()","brak bazowego filteredReady w app.js")
    req(scenario,"function allMatches()","brak bazowego allMatches w Scenario Studio")

    if ERR:
        print("❌ Fixture + History Freshness Guard v8.4E0.1 — FAIL")
        for e in ERR:
            print("  -",e)
        return 1
    print("✅ Fixture + History Freshness Guard v8.4E0.1 — PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
