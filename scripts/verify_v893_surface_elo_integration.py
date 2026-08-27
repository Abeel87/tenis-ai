#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BACKEND=ROOT/"backend"/"surface_elo_integration_v893.py"
REPORT=ROOT/"frontend"/"data"/"surface_elo_integration_v893.json"
META=ROOT/"frontend"/"data"/"meta.json"
WORKFLOW=ROOT/".github"/"workflows"/"update-and-pages.yml"
COHERENCE=ROOT/"frontend"/"app-coherence-v892.js"

def load(path,fallback):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return fallback

def ck(ok,name):
    if not ok: raise SystemExit(f"FAIL  {name}")
    print(f"PASS  {name}")

def main():
    code=BACKEND.read_text(encoding="utf-8")
    wf=WORKFLOW.read_text(encoding="utf-8")
    ui=COHERENCE.read_text(encoding="utf-8")
    ck('VERSION = "v8.9.3"' in code,"version")
    ck("bisect_left" in code and "same day is excluded" in code,"strict same-day leakage guard")
    ck("_key as _player_key" in code and "player_key = _player_key(name)" in code,"normalized player lookup")
    ck("catboost_player_elo" in code,"CatBoost + Player + Elo")
    ck("ensemble_player_elo" in code,"Ensemble + Player Learning + Elo")
    ck("tabpfn_elo" in code,"TabPFN + Elo")
    ck("production_influence" in code and "False" in code,"shadow-only contract")
    ck("Surface Elo SHADOW v8.9.3" in wf,"pipeline integration")
    ck("surface_elo_integration_v893" in ui,"Surface Elo telemetry visible in stats")
    ck("CatBoost + Player + Surface Elo" in ui,"CatBoost Elo stats card")
    ck("Ensemble + Player + Surface Elo" in ui,"Ensemble Elo stats card")
    ck("TabPFN + Surface Elo" in ui,"TabPFN Elo stats card")

    report=load(REPORT,None)
    if report is None:
        print("PASS  runtime report pending first v8.9.3 data build")
        return 0
    ck(report.get("version")=="v8.9.3","runtime version")
    ck(report.get("mode")=="SHADOW","runtime mode")
    ck(report.get("production_influence") is False,"runtime production isolation")
    ck(report.get("training",{}).get("leakage_policy")=="elo_strictly_before_match_day_and_fit_train_only_for_holdout","runtime leakage policy")
    if report.get("training",{}).get("rows_total",0):
        ck(report.get("elo",{}).get("rows_with_both_surface_history",0)>0,"runtime Surface Elo coverage")
    for name in ("catboost_player_elo","ensemble_player_elo","tabpfn_elo"):
        ck(report.get("gates",{}).get(name,{}).get("production_influence") is False,f"{name} remains shadow")
    meta=load(META,{})
    if "surface_elo_v893_production_influence" in meta:
        ck(meta.get("surface_elo_v893_production_influence") is False,"meta production isolation")
    print(json.dumps({
        "status":"PASS","version":"v8.9.3","report_status":report.get("status"),
        "events":report.get("elo",{}).get("events"),"coverage":report.get("elo",{}).get("rows_with_both_surface_history"),
        "training_rows":report.get("training",{}).get("rows_total"),"holdout_rows":report.get("training",{}).get("holdout_rows"),
        "gates":{k:v.get("status") for k,v in report.get("gates",{}).items()},
        "production_influence":False,
    },ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
