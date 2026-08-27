from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ERRORS=[]


def read(path):
    p=ROOT/path
    if not p.exists():
        ERRORS.append(f"brak pliku: {path}");return ""
    return p.read_text(encoding="utf-8")


def req(text,needle,msg):
    if needle not in text: ERRORS.append(msg)


def main():
    index=read("frontend/index.html")
    scenario=read("frontend/scenario-studio-v82a.js")
    workflow=read(".github/workflows/update-and-pages.yml")
    settle=read("backend/live_history_settle.py") + read("backend/signal_settlement.py")
    auto=read("backend/autolearn_v84.py")
    tab=read("backend/tabpfn_challenger_v84.py")
    front=read("frontend/autolearn-v84.js")
    req(index,'scenario-studio-v82a.js?v=82a6','zmieniono chroniony pin Scenario Studio')
    req(index,'autolearn-v84.js?v=84a1','brak JS AutoLearn')
    req(index,'autolearn-v84.css?v=84a1','brak CSS AutoLearn')
    if index.find('autolearn-v84.js?v=84a1')>index.find('scenario-studio-v82a.js?v=82a6'):
        ERRORS.append('AutoLearn musi być załadowany przed Scenario Studio')
    req(scenario,'TENIS_AI_AUTOLEARN_V84','Generator nie czyta AutoLearn')
    req(scenario,'const selectedMatches=ranked.length','Generator nadal wymaga pełnej liczby spotkań')
    if 'if(candidates.length<mc)' in scenario: ERRORS.append('Pozostał stary hard-fail pełnego scenariusza')
    req(settle,'autolearn_signals_v84','Settlement nie rozlicza AutoLearn')
    req(auto,'chronological_split','Brak chronologicznego splitu')
    req(auto,'ML is not allowed to create new Live Tennis API settlement work','Brak guarda zerowego dodatkowego settlement work')
    req(tab,'ModelVersion.V2','TabPFN nie jest jawnie przypięty do V2')
    req(front,'Porównanie modeli AI','Brak panelu porównania modeli')
    if 'new MutationObserver(' in front or 'setInterval(' in front: ERRORS.append('AutoLearn UI zawiera globalny observer/interval')
    for marker in ['Optional TabPFN V2 runtime v8.4A','AutoLearn Ensemble v8.4A','AutoLearn Integration Guard v8.4A']:
        req(workflow,marker,f'workflow: brak {marker}')
    if workflow.count('AutoLearn Ensemble v8.4A')!=1: ERRORS.append('workflow: AutoLearn powinien wystąpić dokładnie raz')
    report=ROOT/'frontend/data/autolearn_v84.json'
    if report.exists():
        try:
            x=json.loads(report.read_text(encoding='utf-8'))
            if x.get('version') not in ('v8.4A','v8.4A.1','v8.4A.2','v8.4B'): ERRORS.append('autolearn_v84.json ma złą wersję')
        except Exception as exc: ERRORS.append(f'autolearn_v84.json invalid: {exc}')
    if ERRORS:
        print('❌ AutoLearn Integration Guard v8.4A — FAIL')
        for e in ERRORS: print('  -',e)
        return 1
    print('✅ AutoLearn Integration Guard v8.4A — PASS')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
