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
    scenario=read("frontend/scenario-studio-v82a.js")
    auto=read("backend/autolearn_v84.py")
    front=read("frontend/autolearn-v84.js")
    workflow=read(".github/workflows/update-and-pages.yml")
    old_guard=read("scripts/verify_v84a.py")

    if not any(v in auto for v in ('VERSION = "v8.4A.1"', 'VERSION = "v8.4A.2"', 'VERSION = "v8.4B"')):
        ERRORS.append("backend AutoLearn nie jest kompatybilny z v8.4A.1+")
    req(auto,"def _choose_weights","brak zachowania wagi challengera między retrainingami")
    req(auto,"def _bounded_tabpfn_weights","brak bounded weight policy TabPFN")
    req(auto,'"quality_first_soft_fill_v84a1"',"report nie opisuje nowej polityki generatora")
    req(auto,'"weight_policy": weight_policy',"report nie publikuje weight_policy")

    if not any(v in front for v in ("const VERSION='v8.4A.1'", "const VERSION='v8.4A.2'", "const VERSION='v8.4B'")):
        ERRORS.append("frontend AutoLearn nie jest kompatybilny z v8.4A.1+")
    req(front,"Wagi produkcyjne","statystyki nie pokazują wag produkcyjnych")
    req(front,"Challenger","statystyki nie pokazują stanu challengera")

    req(scenario,"function repairGeneratorCandidate","brak soft-fill generatora")
    req(scenario,"function generatorProfilePolicy","brak progów per profil")
    req(scenario,"function autoLearnSourceLabel","brak czytelnego źródła CatBoost/TabPFN")
    req(scenario,".map(x=>repairGeneratorCandidate(x,spm,profile)).filter(x=>x.picked.length===spm)",
        "generator nadal odrzuca mecze przed próbą bezpiecznego uzupełnienia")
    req(scenario,"raw_ensemble_score","scenariusz nie zapisuje raw Ensemble")
    req(scenario,"base_source_model","scenariusz nie zachowuje bazowego modelu")

    if not any(x in index for x in ("autolearn-v84.js?v=84a1&hf=84a2", "autolearn-v84.js?v=84a1&hf=84a3", "autolearn-v84.js?v=84a1&hf=84b1")):
        ERRORS.append("brak kompatybilnego cache-bust JS v8.4A.1+")
    if not any(x in index for x in ("autolearn-v84.css?v=84a1&hf=84a2", "autolearn-v84.css?v=84a1&hf=84a3")):
        ERRORS.append("brak kompatybilnego cache-bust CSS v8.4A.1+")
    req(index,"scenario-studio-v82a.js?v=82a6&hf=84a1","brak cache-bust Scenario Studio hotfix")
    req(index,"scenario-studio-v82a.js?v=82a6","naruszono chroniony pin v82a6")

    req(workflow,"AutoLearn Hotfix Guard v8.4A.1","workflow nie ma nowego guarda")
    if not any(x in old_guard for x in (
        "('v8.4A','v8.4A.1')",
        "('v8.4A','v8.4A.1','v8.4A.2')",
        "('v8.4A','v8.4A.1','v8.4A.2','v8.4B')",
    )):
        ERRORS.append("stary v8.4A guard nie akceptuje raportów v8.4A.1+")

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
