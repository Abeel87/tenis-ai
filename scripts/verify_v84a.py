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
    workflow=read(".github/workflows/update-and-pages.yml")
    settle=read("backend/live_history_settle.py") + read("backend/signal_settlement.py")
    auto=read("backend/autolearn_v84.py")
    tab=read("backend/tabpfn_challenger_v84.py")
    front=read("frontend/autolearn-v84.js")

    req(index,'autolearn-v84.js?v=84a1','brak JS AutoLearn')
    req(index,'autolearn-v84.css?v=84a1','brak CSS AutoLearn')
    req(settle,'autolearn_signals_v84','Settlement nie rozlicza AutoLearn')
    req(auto,'chronological_split','Brak chronologicznego splitu')
    req(auto,'ML is not allowed to create new Live Tennis API settlement work','Brak guarda zerowego dodatkowego settlement work')
    req(tab,'ModelVersion.V2','TabPFN nie jest jawnie przypięty do V2')
    req(front,'Porównanie modeli AI','Brak panelu porównania modeli')
    if 'new MutationObserver(' in front or 'setInterval(' in front: ERRORS.append('AutoLearn UI zawiera globalny observer/interval')
    for marker in ['Optional TabPFN V2 runtime v8.4A','AutoLearn Ensemble v8.4A','AutoLearn Integration Guard v8.4A']:
        req(workflow,marker,f'workflow: brak {marker}')
    if workflow.count('AutoLearn Ensemble v8.4A')!=1: ERRORS.append('workflow: AutoLearn powinien wystąpić dokładnie raz')

    # Scenario Composer was retired in favor of Symphony 2.0. AutoLearn remains
    # an independent model/evidence layer and must not require any Scenario files.
    for retired in ('scenario-studio-v82a.js','generator-quality-v888.js','scenario-runtime-v202.js'):
        if retired in index: ERRORS.append(f'index nadal ładuje wycofany asset: {retired}')

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
