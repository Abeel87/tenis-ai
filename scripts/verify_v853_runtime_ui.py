from pathlib import Path
import re

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

def verify_visible_version_contract():
    meta = read("frontend/app-meta.js")
    html = read("frontend/index.html")
    match = re.search(r"displayVersion:\s*'([^']+)'", meta)
    if not match:
        errors.append("frontend/app-meta.js: brak centralnego displayVersion")
        return
    version = match.group(1)
    if f"Tenis AI {version}" not in html:
        errors.append(f"frontend/index.html: wersja widoczna nie zgadza się z displayVersion {version}")

def verify_checkpoint_lock_order():
    html = read("frontend/index.html")
    required = [
        "v883-final.js?v=883",
        "stats-ranking-v886.js?v=886",
        "checkpoint-quality-v887.js?v=887",
    ]
    if not all(token in html for token in required):
        errors.append("frontend/index.html: niepełne warstwy v8.8.3/v8.8.6/v8.8.7+")
        return
    if not (html.index(required[0]) < html.index(required[1]) < html.index(required[2])):
        errors.append("frontend/index.html: CORE Market Quality Lock nie jest ostatnią warstwą selekcji")

need("frontend/index.html", "runtime-fetch-v853.js", "runtime data dedupe v8.5.3")
need("frontend/index.html", "ui-organizer-v853.js", "UI organizer v8.5.3")
need("frontend/index.html", "ui-organizer-v853.css", "UI organizer CSS v8.5.3")
verify_visible_version_contract()
verify_checkpoint_lock_order()
need("frontend/app-meta.js", "appVersion: 'v8.0.1'", "chroniony kontrakt bazowy v8.0.1")
need("frontend/app-meta.js", "generatorPolicyVersion: 'v8.8.10-cross-view-quality-source'", "politykę jednego źródła FINAL v8.8.10")
need("frontend/index.html", "autolearn-v84.js?v=84a1&hf=84b1", "chroniony pin AutoLearn")
need("frontend/index.html", "dynamic-weights-v84d1.js?v=84e0", "chroniony pin Dynamic Weights")
need("frontend/index.html", "model-trends-v84e2.js?v=84e2&hf=852a1", "chroniony pin Trend Monitor")
need("frontend/index.html", "checkpoint-quality-v887.js?v=887", "CORE Market Quality Layer")

need("frontend/checkpoint-quality-v887.js", "CP_MIN_SETTLED=30", "minimalną próbkę checkpoint n=30")
need("frontend/checkpoint-quality-v887.js", "CP_MIN_ACCURACY=65", "minimalną trafność checkpoint 65%")
need("frontend/checkpoint-quality-v887.js", "CP_MIN_WILSON=45", "minimalny dolny Wilson checkpoint 45%")
need("frontend/checkpoint-quality-v887.js", "CP_MIN_RECENT_WHEN_FALLING=60", "ochronę spadającego trendu checkpoint")
need("frontend/checkpoint-quality-v887.js", "early_hold_v7?.ready!==true", "wymóg PBP per mecz")
need("frontend/checkpoint-quality-v887.js", "game_state_progress_v84e2", "tracker dokładnych checkpointów")

need("frontend/checkpoint-quality-v887.js", "RESULT_MIN_SETTLED=30", "minimalną próbkę rynków wyniku n=30")
need("frontend/checkpoint-quality-v887.js", "RESULT_MIN_ACCURACY=65", "minimalną trafność rynków wyniku 65%")
need("frontend/checkpoint-quality-v887.js", "RESULT_MIN_WILSON=45", "minimalny dolny Wilson rynków wyniku 45%")
need("frontend/checkpoint-quality-v887.js", "match_winner','set1_winner','set2_winner','set3_winner", "chronione rynki winner")
need("frontend/checkpoint-quality-v887.js", "RESULT_MARKETS=new Set([...WINNER_MARKETS,'total_sets'])", "ochronę rynku liczby setów")
need("frontend/checkpoint-quality-v887.js", "segments_30d?.market", "telemetrię per rynek")
need("frontend/checkpoint-quality-v887.js", "adaptive_prod||null", "FINAL Adaptive PROD jako kryterium rynków wyniku")
need("frontend/checkpoint-quality-v887.js", "window.TENIS_AI_WINNER_QUALITY_V888", "publiczny helper Winner Quality v8.8.8")
need("frontend/checkpoint-quality-v887.js", "window.TENIS_AI_RESULT_QUALITY_V889", "publiczny helper Result Quality v8.8.9")

# Totals in games are mature and must NOT be added to the result-market lock.
forbid("frontend/checkpoint-quality-v887.js", "RESULT_MARKETS=new Set([...WINNER_MARKETS,'total_sets','set1_total'", "blokadę set1_total")
forbid("frontend/checkpoint-quality-v887.js", "RESULT_MARKETS=new Set([...WINNER_MARKETS,'total_sets','match_total'", "blokadę match_total")

# allSignals must stay raw outside one synchronous CORE generator event.
need("frontend/checkpoint-quality-v887.js", "return state.coreEventDepth>0?filteredSignals(rows,match):rows", "ograniczenie filtra allSignals wyłącznie do CORE Generate")
need("frontend/checkpoint-quality-v887.js", "activeScenarioProfile()!=='experimental'", "bypass Model Test / SHADOW")
need("frontend/checkpoint-quality-v887.js", "Manual i Model Test/SHADOW zachowują pełne rynki", "granicę CORE vs manual/SHADOW")

# Legacy match cards must use the same selected FINAL source as Top/Generator.
need("frontend/checkpoint-quality-v887.js", "function finalSelectedSignals(match,limit=3)", "wspólne źródło FINAL dla widoków")
need("frontend/checkpoint-quality-v887.js", "api.signals(match,Math.max(wanted,3))", "wykorzystanie publicznego API FINAL")
need("frontend/checkpoint-quality-v887.js", "window.bestSignalsData=(match,limit=3)=>finalSelectedSignals", "mostek bestSignalsData")
need("frontend/checkpoint-quality-v887.js", "window.bestSignals=match=>", "mostek dużych Najmocniejszych sygnałów")
need("frontend/checkpoint-quality-v887.js", "window.compactSignals=match=>", "mostek kompaktowych sygnałów")
need("frontend/checkpoint-quality-v887.js", "window.TENIS_AI_CROSS_VIEW_QUALITY_V8810", "publiczny helper cross-view v8.8.10")
need("frontend/checkpoint-quality-v887.js", "Karty meczu, Top i Generator korzystają z jednego źródła FINAL", "komunikat jednego źródła FINAL")
forbid("frontend/checkpoint-quality-v887.js", "new MutationObserver(", "globalny MutationObserver w Market Quality Lock")
forbid("frontend/checkpoint-quality-v887.js", "setInterval(", "interwał w Market Quality Lock")

# Serve Props is presentation/lab only and must not scan the whole app DOM.
forbid("frontend/serve-props-v72.js", "new MutationObserver(", "globalny MutationObserver Serve Props")
forbid("frontend/serve-props-v72.js", "obs.observe(document.body", "body-wide observer Serve Props")
need("frontend/serve-props-v72.js", "scheduleRefresh(document)", "celowane odświeżenie Serve Props")
need("frontend/serve-props-v72.js", "requestAnimationFrame", "zgrupowane odświeżenie Serve Props")

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
need(".github/workflows/update-and-pages.yml", "verify_v853_runtime_ui.py", "guard v8.5.3+ w produkcyjnym workflow")
need(".github/workflows/update-and-pages.yml", "compact_frontend_data_v853.py", "kompaktowanie dużych JSON-ów")
need("scripts/compact_frontend_data_v853.py", "separators=(',', ':')", "kompaktowy zapis JSON")
need(".github/workflows/ui-smoke.yml", "python -m pytest -q", "pełny pytest na PR")
need(".github/workflows/ui-smoke.yml", "verify_v853_runtime_ui.py", "guard v8.5.3+ na PR")

if errors:
    print("v8.5.3+ Runtime/UI Guard: FAIL")
    for err in errors:
        print(" -", err)
    raise SystemExit(1)

print("v8.5.3+ Runtime/UI Guard: PASS")
