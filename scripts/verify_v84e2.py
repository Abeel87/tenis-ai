# Presentation checks: scripts/verify_ui.py. Backend/data checks retained below.
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ERR = []

def read(rel):
    p = ROOT / rel
    if not p.exists():
        ERR.append(f'brak pliku: {rel}')
        return ''
    return p.read_text(encoding='utf-8')

def req(text, needle, msg):
    if needle not in text:
        ERR.append(msg)

def main():
    back = read('backend/model_telemetry_v84c.py')
    ui = read('.github/workflows/ui-smoke.yml')
    pages = read('.github/workflows/update-and-pages.yml')
    req(back, 'TREND_VERSION = "v8.4E2"', 'backend nie ma wersji trendu E2')
    req(back, '"trends_v84e2": trends', 'raport nie eksportuje trendów')
    req(back, '"game_state_progress_v84e2": game_state', 'raport nie eksportuje Po2/4/6')
    req(back, 'def trend_summary(', 'brak trend_summary')
    req(back, 'def game_state_progress(', 'brak game_state_progress')
    req(back, '"model_trend_version": TREND_VERSION', 'meta nie raportuje E2')
    req(ui, 'Model Trend Monitor Guard v8.4E2', 'UI smoke nie ma guarda E2')
    req(pages, 'Model Trend Monitor Guard v8.4E2', 'deploy workflow nie ma guarda E2')
    if ERR:
        print('❌ Model Trend Monitor Guard v8.4E2 — FAIL')
        [print('  -', e) for e in ERR]
        return 1
    print('✅ Model Trend Monitor Guard v8.4E2 — PASS')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
