from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERRORS = []

def read(path):
    p = ROOT / path
    if not p.exists():
        ERRORS.append(f"brak pliku: {path}")
        return ""
    return p.read_text(encoding="utf-8")

def req(text, needle, msg):
    if needle not in text:
        ERRORS.append(msg)

def main():
    pbp = read("backend/pbp_enrich.py")
    specialist = read("backend/specialist_learning_v79b.py")
    auto = read("backend/autolearn_v84.py")
    hist = read("backend/history_tracker.py")
    sw = read("frontend/sw.js")
    app = read("frontend/app.js")
    ui = read("frontend/autolearn-v84.js")
    index = read("frontend/index.html")
    workflow = read(".github/workflows/update-and-pages.yml")

    # PBP: primary + retry branch only.
    if pbp.count('record_calls("pbp_current", 1)') != 2:
        ERRORS.append("PBP quota accounting nie ma dokładnie primary+retry")
    req(pbp, 'self.calls += 1\n            record_calls("pbp_current", 1)', "retry PBP nie zapisuje realnego calla")

    req(specialist, "def _consensus_family", "brak rodziny decyzji Consensus")
    req(specialist, "against_votes", "Consensus nie liczy głosów AGAINST")
    req(specialist, "if for_votes <= against_votes", "Consensus nie wymaga ścisłej większości")
    req(specialist, '"consensus_policy": "strict_directional_majority_v84b"', "brak wersji polityki Consensus")

    req(auto, 'VERSION = "v8.4B"', "AutoLearn backend nie jest v8.4B")
    req(auto, "def _gate_current_calibration", "brak CAL gate kalibracji")
    req(auto, "def _stabilize_ensemble_weights", "brak stabilizatora wag")
    req(auto, "ENSEMBLE_SINGLE_MODEL_CAP = 0.80", "brak cap 80% małej próbki")
    req(auto, "ENSEMBLE_CURRENT_FLOOR = 0.10", "brak floor Current Engine")
    req(auto, 'if state.get("version") != VERSION: return True', "zmiana logiki nie wymusza odświeżenia CatBoost")
    req(auto, "current_calibration = _gate_current_calibration(current_calibration_candidate, cal)", "produkcja omija CAL gate")

    req(hist, "def _tournament_compatible", "fallback historii nie sprawdza turnieju")
    req(hist, "if len(candidates) != 1:", "fallback historii nadal może wybrać arbitralny rekord")

    req(sw, "tenis-ai-v84b-logic-stability", "PWA cache nie został podbity")
    req(sw, "tenis-ai-v801-player-profile", "zniknął chroniony marker cache v801")
    req(sw, "canonicalDataRequest", "PWA nie kanonizuje data/*.json")
    req(app, "serviceWorker.register('sw.js?v=801')", "naruszono chroniony kontrakt rejestracji SW v801")
    req(app, ".then(r=>r.update())", "frontend nie wymusza sprawdzenia aktualizacji SW")
    req(app, "{cache:'no-store'}", "JSON loader nie wymusza świeżości")
    req(index, 'app.js?v=84b1', "brak cache-bust app.js")
    req(index, 'autolearn-v84.js?v=84a1&hf=84b1', "brak cache-bust AutoLearn v8.4B")
    req(index, 'scenario-studio-v82a.js?v=82a6', "naruszono chroniony pin Scenario Studio")
    req(ui, "🤖 AUTOLEARN v8.4B", "UI nie pokazuje v8.4B")

    markers = [
        "AutoLearn Calibration Guard v8.4A.2",
        "Logic & Stability Guard v8.4B",
        "Final API quota report v8.3B",
    ]
    if not all(m in workflow for m in markers):
        ERRORS.append("workflow: brakuje guarda v8.4B lub sąsiadów")
    elif not (workflow.index(markers[0]) < workflow.index(markers[1]) < workflow.index(markers[2])):
        ERRORS.append("workflow: zła kolejność guarda v8.4B")

    if ERRORS:
        print("❌ Logic & Stability Guard v8.4B — FAIL")
        for e in ERRORS:
            print("  -", e)
        return 1
    print("✅ Logic & Stability Guard v8.4B — PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
