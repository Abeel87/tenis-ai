from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ERRORS=[]

def read(path):
    p=ROOT/path
    if not p.exists():
        ERRORS.append(f"brak pliku: {path}"); return ""
    return p.read_text(encoding="utf-8")

def req(text,needle,msg):
    if needle not in text: ERRORS.append(msg)

def main():
    index=read("frontend/index.html")
    auto=read("backend/autolearn_v84.py")
    front=read("frontend/autolearn-v84.js")
    workflow=read(".github/workflows/update-and-pages.yml")
    old_guard=read("scripts/verify_v84a.py")

    if not any(v in auto for v in ('VERSION = "v8.4A.1"', 'VERSION = "v8.4A.2"', 'VERSION = "v8.4B"')):
        ERRORS.append("backend AutoLearn nie jest kompatybilny z v8.4A.1+")
    req(auto,"def _choose_weights","brak zachowania wagi challengera między retrainingami")
    req(auto,"def _bounded_tabpfn_weights","brak bounded weight policy TabPFN")
    changelog=read("CHANGELOG.md")
    req(changelog,'quality_lock_no_forced_fill_v852',"CHANGELOG nie opisuje polityki quality_lock_no_forced_fill_v852")
    req(auto,'quality_lock_no_forced_fill_v852',"backend/autolearn_v84.py nie ustawia polityki quality_lock_no_forced_fill_v852")
    req(auto,'"weight_policy": weight_policy',"report nie publikuje weight_policy")

    if not any(v in front for v in ("const VERSION='v8.4A.1'", "const VERSION='v8.4A.2'", "const VERSION='v8.4B'")):
        ERRORS.append("frontend AutoLearn nie jest kompatybilny z v8.4A.1+")
    req(front,"Wagi produkcyjne","statystyki nie pokazują wag produkcyjnych")
    req(front,"Challenger","statystyki nie pokazują stanu challengera")

    if not any(x in index for x in ("autolearn-v84.js?v=84a1&hf=84a2", "autolearn-v84.js?v=84a1&hf=84a3", "autolearn-v84.js?v=84a1&hf=84b1")):
        ERRORS.append("brak kompatybilnego cache-bust JS v8.4A.1+")
    if not any(x in index for x in ("autolearn-v84.css?v=84a1&hf=84a2", "autolearn-v84.css?v=84a1&hf=84a3")):
        ERRORS.append("brak kompatybilnego cache-bust CSS v8.4A.1+")

    req(workflow,"AutoLearn Hotfix Guard v8.4A.1","workflow nie ma guarda AutoLearn")
    if "scenario-studio-v82a" in index or "generator-quality-v888" in index:
        ERRORS.append("wycofany Scenario Generator nadal jest bootstrappowany")
    if "scenario-studio-v82a" in old_guard:
        ERRORS.append("AutoLearn Integration Guard nadal zależy od Scenario Studio")

    report=ROOT/"frontend/data/autolearn_v84.json"
    if report.exists():
        try:
            x=json.loads(report.read_text(encoding="utf-8"))
            if x.get("version") not in ("v8.4A","v8.4A.1","v8.4A.2","v8.4B"):
                ERRORS.append(f"nieznana wersja autolearn_v84.json: {x.get('version')!r}")
        except Exception as exc:
            ERRORS.append(f"autolearn_v84.json invalid: {exc}")

    if ERRORS:
        print("❌ AutoLearn Hotfix Guard v8.4A.1 — FAIL")
        for e in ERRORS: print("  -",e)
        return 1
    print("✅ AutoLearn Hotfix Guard v8.4A.1 — PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
