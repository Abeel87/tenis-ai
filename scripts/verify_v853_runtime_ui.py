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
        "ui-cleanup.js",
        "stats-ranking.js",
        "market-quality.js",
    ]
    if not all(token in html for token in required):
        errors.append("frontend/index.html: niepełne kanoniczne warstwy UI cleanup / stats ranking / Market Quality")
        return
    if not (html.index(required[0]) < html.index(required[1]) < html.index(required[2])):
        errors.append("frontend/index.html: CORE Market Quality Lock nie jest ostatnią warstwą selekcji MODEL/RAW")


# Runtime/UI baseline retained after Scenario retirement.
need("frontend/index.html", "runtime-fetch.js", "kanoniczny runtime data dedupe")
need("frontend/index.html", "ui-organizer.js", "kanoniczny UI organizer")
need("frontend/index.html", "ui-organizer.css", "kanoniczny UI organizer CSS")
verify_visible_version_contract()
verify_checkpoint_lock_order()
need("frontend/app-meta.js", "appVersion: 'v8.0.1'", "chroniony kontrakt bazowy v8.0.1")
need("frontend/app-meta.js", "symphonyVersion:'v2.1'", "aktywną wersję Symfonii 2.0")
need("frontend/index.html", "autolearn-v84.js?v=84a1&hf=84b1", "chroniony pin AutoLearn")
need("frontend/index.html", "dynamic-weights-v84d1.js?v=84e0", "chroniony pin Dynamic Weights")
need("frontend/index.html", "model-trends.js", "kanoniczny Trend Monitor")
need("frontend/index.html", "market-quality.js", "kanoniczny CORE Market Quality Layer")

# Scenario/Generator is retired. It must not return through runtime assets.
for retired in (
    "scenario-studio-v82a.js",
    "scenario-runtime-v202.js",
    "generator-quality-v888.js",
):
    forbid("frontend/index.html", retired, f"wycofany asset {retired}")
need("frontend/index.html", "symphony2.js", "runtime Symfonii 2.0")

# MODEL/RAW quality remains independent from PLAYABLE/Symphony 2.0.
need("frontend/market-quality.js", "CP_MIN_SETTLED=30", "minimalną próbkę checkpoint n=30")
need("frontend/market-quality.js", "CP_MIN_ACCURACY=65", "minimalną trafność checkpoint 65%")
need("frontend/market-quality.js", "CP_MIN_WILSON=45", "minimalny dolny Wilson checkpoint 45%")
need("frontend/market-quality.js", "CP_MIN_RECENT_WHEN_FALLING=60", "ochronę spadającego trendu checkpoint")
need("frontend/market-quality.js", "early_hold_v7?.ready!==true", "wymóg PBP per mecz")
need("frontend/market-quality.js", "game_state_progress_v84e2", "tracker dokładnych checkpointów")
need("frontend/market-quality.js", "RESULT_MIN_SETTLED=30", "minimalną próbkę rynków wyniku n=30")
need("frontend/market-quality.js", "RESULT_MIN_ACCURACY=65", "minimalną trafność rynków wyniku 65%")
need("frontend/market-quality.js", "RESULT_MIN_WILSON=45", "minimalny dolny Wilson rynków wyniku 45%")
need("frontend/market-quality.js", "segments_30d?.market", "telemetrię per rynek")
need("frontend/market-quality.js", "adaptive_prod||null", "Adaptive PROD jako cechę warstwy modelowej")
forbid("frontend/market-quality.js", "new MutationObserver(", "globalny MutationObserver w Market Quality Lock")
forbid("frontend/market-quality.js", "setInterval(", "interwał w Market Quality Lock")

# Serve Props is presentation/lab only and must not scan the whole app DOM.
forbid("frontend/serve-props-v72.js", "new MutationObserver(", "globalny MutationObserver Serve Props")
forbid("frontend/serve-props-v72.js", "obs.observe(document.body", "body-wide observer Serve Props")
need("frontend/serve-props-v72.js", "scheduleRefresh(document)", "celowane odświeżenie Serve Props")
need("frontend/serve-props-v72.js", "requestAnimationFrame", "zgrupowane odświeżenie Serve Props")

need("frontend/fixture-history-freshness.js", "refreshHistoryOnly(false)", "history refresh bez wymuszonego pobrania przy każdym kliknięciu")
need("frontend/fixture-history-freshness.js", "candidates.find", "fallback do pierwszego niepustego statusu")
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
need("frontend/model-trends.js", "Zmiana trafności", "spójne nazewnictwo trendu")
need("frontend/ui-organizer.js", "No model math", "deklarację UI-only")
forbid("frontend/ui-organizer.js", "fetch(", "requesty sieciowe w organizerze UI")
forbid("frontend/ui-organizer.js", "new MutationObserver(", "MutationObserver w organizerze UI")
forbid("frontend/ui-organizer.js", "setInterval(", "interwał w organizerze UI")

need(".github/workflows/update-and-pages.yml", "verify_v853_runtime_ui.py", "guard v8.5.3+ w produkcyjnym workflow")
need(".github/workflows/update-and-pages.yml", "compact_frontend_data.py", "kanoniczne kompaktowanie dużych JSON-ów")
need("scripts/compact_frontend_data.py", "separators=(',', ':')", "kompaktowy zapis JSON")
need(".github/workflows/ui-smoke.yml", "python -m pytest -q", "pełny pytest na PR")
need(".github/workflows/ui-smoke.yml", "verify_v853_runtime_ui.py", "guard v8.5.3+ na PR")

if errors:
    print("v8.5.3+ Runtime/UI Guard: FAIL")
    for err in errors:
        print(" -", err)
    raise SystemExit(1)

print("v8.5.3+ Runtime/UI Guard: PASS")
