#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ERR=[]
def read(rel):
    p=ROOT/rel
    if not p.exists(): ERR.append(f"brak pliku: {rel}"); return ""
    return p.read_text(encoding="utf-8")
def req(text,needle,msg):
    if needle not in text: ERR.append(msg)
def main():
    back=read("backend/model_telemetry_v84c.py"); js=read("frontend/model-trends.js"); css=read("frontend/model-trends.css"); idx=read("frontend/index.html"); ui=read(".github/workflows/ui-smoke.yml"); pages=read(".github/workflows/update-and-pages.yml")
    req(back,'TREND_VERSION = "v8.4E2"','backend nie ma wersji trendu E2')
    req(back,'"trends_v84e2": trends','raport nie eksportuje trendów')
    req(back,'"game_state_progress_v84e2": game_state','raport nie eksportuje Po2/4/6')
    req(back,'def trend_summary(','brak trend_summary'); req(back,'def game_state_progress(','brak game_state_progress')
    req(back,'"model_trend_version": TREND_VERSION','meta nie raportuje E2')
    req(js,"const VERSION='v8.4E2'",'frontend nie ma wersji E2'); req(js,'TENIS_AI_AUTOLEARN_V84','frontend nie używa AutoLearn bridge')
    req(js,'Po2 / Po4 / Po6','brak panelu Po2/4/6'); req(js,'OSTROŻNIE','brak statusu ostrożnie'); req(js,'ROŚNIE','brak statusu rośnie')
    if 'fetch(' in js or 'XMLHttpRequest' in js: ERR.append('Trend Monitor nie może wykonywać własnych requestów')
    if 'new MutationObserver(' in js: ERR.append('Trend Monitor nie może dodawać MutationObservera')
    if 'setInterval(' in js: ERR.append('Trend Monitor nie może dodawać interwału')
    req(css,'.mt84e2','brak CSS E2'); req(idx,'model-trends.css','index nie ładuje kanonicznego CSS Trend Monitor'); req(idx,'model-trends.js','index nie ładuje kanonicznego JS Trend Monitor')
    req(idx,'autolearn-v84.css?v=84a1&hf=84a3','naruszono chroniony AutoLearn CSS pin'); req(idx,'autolearn-v84.js?v=84a1&hf=84b1','naruszono chroniony AutoLearn JS pin')
    if 'scenario-studio-v82a.js' in idx:
        ERR.append('legacy Scenario Studio nie może wrócić do aktywnego indexu')
    req(ui,'Model Trend Monitor Guard v8.4E2','UI smoke nie ma guarda E2'); req(pages,'Model Trend Monitor Guard v8.4E2','deploy workflow nie ma guarda E2')
    if ERR:
        print('❌ Model Trend Monitor Guard v8.4E2 — FAIL'); [print('  -',e) for e in ERR]; return 1
    print('✅ Model Trend Monitor Guard v8.4E2 — PASS'); return 0
if __name__=='__main__': raise SystemExit(main())
