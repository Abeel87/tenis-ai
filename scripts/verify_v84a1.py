# Presentation checks: scripts/verify_ui.py. Backend/data checks retained below.
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ERRORS = []

def read(path):
    p = ROOT / path
    if not p.exists():
        ERRORS.append(f'brak pliku: {path}')
        return ''
    return p.read_text(encoding='utf-8')

def req(text, needle, msg):
    if needle not in text:
        ERRORS.append(msg)

def main():
    auto = read('backend/autolearn_v84.py')
    workflow = read('.github/workflows/update-and-pages.yml')
    if not any((v in auto for v in ('VERSION = "v8.4A.1"', 'VERSION = "v8.4A.2"', 'VERSION = "v8.4B"'))):
        ERRORS.append('backend AutoLearn nie jest kompatybilny z v8.4A.1+')
    req(auto, 'def _choose_weights', 'brak zachowania wagi challengera między retrainingami')
    req(auto, 'def _bounded_tabpfn_weights', 'brak bounded weight policy TabPFN')
    changelog = read('CHANGELOG.md')
    req(changelog, 'quality_lock_no_forced_fill_v852', 'CHANGELOG nie opisuje polityki quality_lock_no_forced_fill_v852')
    req(auto, 'quality_lock_no_forced_fill_v852', 'backend/autolearn_v84.py nie ustawia polityki quality_lock_no_forced_fill_v852')
    req(auto, '"weight_policy": weight_policy', 'report nie publikuje weight_policy')
    req(workflow, 'AutoLearn Hotfix Guard v8.4A.1', 'workflow nie ma guarda AutoLearn')
    report = ROOT / 'frontend/data/autolearn_v84.json'
    if report.exists():
        try:
            x = json.loads(report.read_text(encoding='utf-8'))
            if x.get('version') not in ('v8.4A', 'v8.4A.1', 'v8.4A.2', 'v8.4B'):
                ERRORS.append(f"nieznana wersja autolearn_v84.json: {x.get('version')!r}")
        except Exception as exc:
            ERRORS.append(f'autolearn_v84.json invalid: {exc}')
    if ERRORS:
        print('❌ AutoLearn Hotfix Guard v8.4A.1 — FAIL')
        for e in ERRORS:
            print('  -', e)
        return 1
    print('✅ AutoLearn Hotfix Guard v8.4A.1 — PASS')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
