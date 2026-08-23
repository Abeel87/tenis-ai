from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
WARNINGS: list[str] = []


def read(path: str) -> str:
    p = ROOT / path
    if not p.exists():
        ERRORS.append(f"brak pliku: {path}")
        return ""
    return p.read_text(encoding="utf-8")


def read_json(path: str):
    p = ROOT / path
    if not p.exists():
        WARNINGS.append(f"brak danych: {path}")
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        ERRORS.append(f"niepoprawny JSON {path}: {exc}")
        return None


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        ERRORS.append(label)


def main() -> int:
    index = read("frontend/index.html")
    studio = read("frontend/scenario-studio-v82a.js")
    settlement = read("frontend/scenario-settlement-v83c.js")
    backend = read("backend/scenario_settlement_v83c.py")
    workflow = read(".github/workflows/update-and-pages.yml")
    backfill = read("backend/history_backfill_v83.py")

    require(index, 'scenario-studio-v82a.js?v=82a6', "Scenario Studio cache pin został zmieniony")
    require(index, 'scenario-settlement-v83c.js?v=83d1', "brak assetu Scenario Settlement v8.3D")
    if index.count("scenario-studio-v82a.js") != 1:
        ERRORS.append("Scenario Studio jest załadowany więcej/mniej niż raz")
    if index.count("scenario-settlement-v83c.js") != 1:
        ERRORS.append("Scenario Settlement jest załadowany więcej/mniej niż raz")

    require(studio, "s=m&&scenarioSignals(m).find(x=>x.key===sk)", "manualny builder nie używa pełnej drabinki scenarioSignals")
    if "new MutationObserver(" in studio or "setInterval(" in studio:
        ERRORS.append("Scenario Studio zawiera globalny observer/interval")

    require(settlement, "const VERSION='v8.3D'", "frontend settlement nie jest v8.3D")
    require(settlement, "PBP_GRACE_HOURS=36", "brak grace period dla PBP")
    require(settlement, "function terminalResult(item)", "brak ochrony przed ponownym rozliczaniem")
    require(settlement, "function pbpUnavailable(item,outcome,reason)", "brak bezpiecznego fallbacku PBP")
    require(settlement, "market==='game_state'", "brak mapowania game_state")
    require(settlement, "push na linii", "brak neutralnego PUSH dla równej linii")
    if "new MutationObserver(" in settlement or "setInterval(" in settlement:
        ERRORS.append("Scenario Settlement zawiera globalny observer/interval")

    require(backend, 'VERSION = "v8.3D"', "backend settlement nie jest v8.3D")
    require(backend, "idless_by_key", "feed nie eksportuje bezpiecznie meczów bez match_id")
    require(backend, '"scenario_settlement_version": VERSION', "meta nie ma wspólnego klucza wersji settlement")
    require(backfill, "from .api_quota_v83b import quota_budget, record_calls", "history_backfill nie działa jako import pakietu")
    require(backfill, "from api_quota_v83b import quota_budget, record_calls", "history_backfill nie działa jako bezpośredni skrypt")

    order = [
        "Central API Quota Guard v8.3B",
        "Update analysis",
        "Enrich Early Hold from BASIC point-by-point",
        "Track + backtest PBP",
        "Settle history from Live Tennis API",
        "Build Scenario Settlement feed v8.3C",
        "Historical backfill v8.3B (central spare quota)",
        "Adaptive Learning v7.9B",
        "Final API quota report v8.3B",
        "Integration Guard v8.3D",
    ]
    positions = []
    for marker in order:
        if marker not in workflow:
            ERRORS.append(f"workflow: brak kroku {marker}")
        else:
            positions.append(workflow.index(marker))
    if len(positions) == len(order) and positions != sorted(positions):
        ERRORS.append("workflow: kolejność krytycznych kroków jest niepoprawna")
    if workflow.count("Build Scenario Settlement feed v8.3C") != 1:
        ERRORS.append("workflow: Scenario Settlement feed występuje inną liczbę razy niż 1")
    if workflow.count("Integration Guard v8.3D") != 1:
        ERRORS.append("workflow: Integration Guard występuje inną liczbę razy niż 1")

    meta = read_json("frontend/data/meta.json")
    if isinstance(meta, dict):
        integrity = meta.get("integrity_v78a_status")
        if integrity not in (None, "PASS"):
            ERRORS.append(f"meta: integrity_v78a_status={integrity!r}")
        remaining = meta.get("api_quota_v83b_remaining_estimate")
        if remaining is not None:
            try:
                if float(remaining) < 0:
                    ERRORS.append("meta: ujemny szacowany zapas API")
            except Exception:
                ERRORS.append("meta: api_quota_v83b_remaining_estimate nie jest liczbą")

    feed = read_json("frontend/data/scenario_results_v83c.json")
    if isinstance(feed, dict):
        if feed.get("version") not in ("v8.3C", "v8.3D"):
            ERRORS.append(f"feed: nieznana wersja {feed.get('version')!r}")
        if not isinstance(feed.get("matches", []), list):
            ERRORS.append("feed: matches nie jest listą")

    if ERRORS:
        print("❌ Integration Guard v8.3D — FAIL")
        for e in ERRORS:
            print(f"  - {e}")
        for w in WARNINGS:
            print(f"  ⚠️ {w}")
        return 1

    print("✅ Integration Guard v8.3D — PASS")
    for w in WARNINGS:
        print(f"  ⚠️ {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
