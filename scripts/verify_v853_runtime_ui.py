from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

errors = []

def need(rel, needle, label):
    text = read(rel)
    if needle not in text:
        errors.append(f"{rel}: brak {label}")

def forbid(rel, needle, label):
    text = read(rel)
    if needle in text:
        errors.append(f"{rel}: nadal zawiera {label}")

need("frontend/index.html", "runtime-fetch-v853.js", "runtime data dedupe v8.5.3")
need("frontend/index.html", "ui-organizer-v853.js", "UI organizer v8.5.3")
need("frontend/index.html", "ui-organizer-v853.css", "UI organizer CSS v8.5.3")
need("frontend/app-meta.js", "displayVersion: \'v8.7\'", "aktualną wersję wyświetlaną aplikacji")
need("frontend/app-meta.js", "appVersion: \'v8.0.1\'", "chroniony kontrakt bazowy v8.0.1")
need("frontend/index.html", "autolearn-v84.js?v=84a1&hf=84b1", "chroniony pin AutoLearn")
need("frontend/index.html", "dynamic-weights-v84d1.js?v=84e0", "chroniony pin Dynamic Weights")
need("frontend/index.html", "model-trends-v84e2.js?v=84e2&hf=852a1", "chroniony pin Trend Monitor")
need("frontend/hotfix-v84e01.js", "refreshHistoryOnly(false)", "history refresh bez wymuszonego pobrania przy każdym kliknięciu")
need("frontend/hotfix-v84e01.js", "candidates.find", "fallback do pierwszego niepustego statusu")
need("frontend/dynamic-weights-v84d1.js", "memoryResults", "reuse results z pamięci")
need("frontend/dynamic-weights-v84d1.js", "if(memory)", "preferencję danych z pamięci")
need("frontend/autolearn-v84.js", "Selektor Ensemble (proxy)", "jednoznaczną etykietę proxy")
need("frontend/autolearn-v84.js", "let injectTimer=null", "debounce renderu AutoLearn")
forbid("frontend/autolearn-v84.js", "[0,120,450,1000].forEach", "wielokrotny force-inject")
need("frontend/player-search.js", "buildPlayerIndex", "indeks zawodników")
need("frontend/player-search.js", "searchTimer", "debounce wyszukiwarki")
need("frontend/account.js", "community_public_stats", "bezpieczne RPC statystyk społeczności")
forbid("frontend/community-hub.js", "setInterval(refreshPublicStats, 15000)", "polling społeczności co 15 s")
need("frontend/sw.js", "skipLargeDataCache", "bypass Cache Storage dla wielkich JSON")
need("frontend/player-intelligence-v85.js", "Trafność ≥65", "spójne polskie nazewnictwo metryk")
need("frontend/player-intelligence-v851b-ui.js", "Generator proxy + Player", "jednoznaczną etykietę PI proxy")
need("frontend/model-trends-v84e2.js", "Zmiana trafności", "spójne nazewnictwo trendu")
need("frontend/ui-organizer-v853.js", "No model math", "deklarację UI-only")
forbid("frontend/ui-organizer-v853.js", "fetch(", "requesty sieciowe w organizerze UI")
forbid("frontend/ui-organizer-v853.js", "new MutationObserver(", "MutationObserver w organizerze UI")
forbid("frontend/ui-organizer-v853.js", "setInterval(", "interwał w organizerze UI")
need(".github/workflows/update-and-pages.yml", "verify_v853_runtime_ui.py", "guard v8.5.3 w produkcyjnym workflow")
need(".github/workflows/update-and-pages.yml", "compact_frontend_data_v853.py", "kompaktowanie dużych JSON-ów")
need("scripts/compact_frontend_data_v853.py", "separators=(',', ':')", "kompaktowy zapis JSON")
need(".github/workflows/ui-smoke.yml", "python -m pytest -q", "pełny pytest na PR")
need(".github/workflows/ui-smoke.yml", "verify_v853_runtime_ui.py", "guard v8.5.3 na PR")

if errors:
    print("v8.5.3 Runtime/UI Guard: FAIL")
    for err in errors:
        print(" -", err)
    raise SystemExit(1)

print("v8.5.3 Runtime/UI Guard: PASS")
