# Presentation checks: scripts/verify_ui.py. Backend/data checks retained below.
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ERR = []

def read(p):
    f = ROOT / p
    if not f.exists():
        ERR.append(f'brak pliku: {p}')
        return ''
    return f.read_text(encoding='utf-8')

def req(text, needle, msg):
    if needle not in text:
        ERR.append(msg)

def main():
    bridge = read('frontend/signal-mapping-v84d4.js')
    wf = read('.github/workflows/update-and-pages.yml')
    req(bridge, "const VERSION='v8.4D.4'", 'Signal Mapping Bridge nie jest v8.4D.4')
    req(bridge, 'state|${cp}|${pick}', 'brak aliasu state')
    req(bridge, 'game_state|${cp}|${pick}', 'brak aliasu game_state')
    req(bridge, 'sameStateSignal', 'brak ścisłego porównania checkpoint + stan')
    req(bridge, 'resolveFromMatch', 'brak resolvera aliasów')
    req(bridge, 'auto.scoreFor=function', 'bridge nie podpina się pod AutoLearn scoreFor')
    req(bridge, 'No fuzzy matching', 'brak deklaracji zakazu fuzzy matchingu')
    req(wf, 'Signal Mapping Bridge Guard v8.4D.4', 'workflow nie uruchamia guarda v8.4D.4')
    if ERR:
        print('❌ Signal Mapping Bridge Guard v8.4D.4 — FAIL')
        for e in ERR:
            print('  -', e)
        return 1
    print('✅ Signal Mapping Bridge Guard v8.4D.4 — PASS')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
