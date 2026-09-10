# Presentation checks: scripts/verify_ui.py. Backend/data checks retained below.
from pathlib import Path
import json
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
    telemetry = read('backend/model_telemetry_v84c.py')
    workflow = read('.github/workflows/update-and-pages.yml')
    auto = read('backend/autolearn_v84.py')
    report_text = read('frontend/data/model_telemetry_v84c.json')
    req(telemetry, 'VERSION = "v8.4C"', 'telemetry backend nie jest v8.4C')
    req(telemetry, 'learning_signals_v79b', 'telemetry nie czyta modeli specjalistycznych')
    req(telemetry, 'autolearn_signals_v84', 'telemetry nie czyta predykcji ML')
    req(telemetry, 'segments_30d', 'telemetry nie raportuje segmentów 30d')
    req(telemetry, 'roi_status', 'ROI nie ma jawnego statusu N/D')
    req(auto, 'VERSION = "v8.4B"', 'v8.4C naruszyło chroniony core AutoLearn v8.4B')
    req(workflow, 'Model Telemetry v8.4C', 'workflow nie buduje telemetrii v8.4C')
    req(workflow, 'Model Telemetry Guard v8.4C', 'workflow nie uruchamia guarda v8.4C')
    if report_text:
        try:
            report = json.loads(report_text)
            if report.get('version') != 'v8.4C':
                ERRORS.append('raport telemetryczny ma złą wersję')
            models = ((report.get('scopes') or {}).get('30d') or {}).get('by_model') or {}
            for name in ('adaptive', 'early', 'serve', 'form', 'surface', 'consensus', 'current', 'catboost', 'tabpfn', 'ensemble'):
                if name not in models:
                    ERRORS.append(f'raport 30d nie ma modelu: {name}')
        except json.JSONDecodeError:
            ERRORS.append('raport telemetryczny nie jest poprawnym JSON')
    if ERRORS:
        print('❌ Model Telemetry Guard v8.4C — FAIL')
        for e in ERRORS:
            print('  -', e)
        return 1
    print('✅ Model Telemetry Guard v8.4C — PASS')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
