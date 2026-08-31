from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERRORS = []

def read(path):
    p = ROOT / path
    if not p.exists():
        ERRORS.append(f"brak pliku: {path}")
        return ""
    return p.read_text(encoding="utf-8")

def req(text, needle, label):
    if needle not in text:
        ERRORS.append(label)

def main():
    backend = read("backend/autolearn_v84.py")
    ui = read("frontend/autolearn-v84.js")
    index = read("frontend/index.html")
    workflow = read(".github/workflows/update-and-pages.yml")
    previous_guard = read("scripts/verify_v84a1.py")

    if not any(v in backend for v in ('VERSION = "v8.4A.2"', 'VERSION = "v8.4B"')):
        ERRORS.append("backend nie jest kompatybilny z v8.4A.2+")
    req(backend, "def _fit_current_calibration(rows", "brak fitu kalibracji")
    req(backend, "def _apply_current_calibration(", "brak aplikowania kalibracji")
    req(backend, '"fit_scope": "train_only"', "kalibracja nie jest train-only")
    req(backend, '"current_raw": _metrics(val, raw_base_val)', "brak raw-vs-calibrated validation")
    req(backend, 'tracking = tracking_stats(history, tracker_version=VERSION)', "tracking miesza metodologie")
    req(backend, '"tracking_all_versions": tracking_all_versions', "brak all-versions reference")
    req(backend, '"current_calibration": current_calibration', "raport nie eksportuje kalibracji")

    if not any(v in ui for v in ("const VERSION='v8.4A.2'", "const VERSION='v8.4B'")):
        ERRORS.append("UI nie jest kompatybilny z v8.4A.2+")
    req(ui, "Current Engine · kalibrowany", "UI nie opisuje kalibracji")
    req(ui, "Kalibracja Engine", "UI nie pokazuje statusu kalibracji")
    if not any(x in index for x in ("autolearn-v84.js?v=84a1&hf=84a3", "autolearn-v84.js?v=84a1&hf=84b1")):
        ERRORS.append("brak kompatybilnego cache-bust JS")
    req(index, "autolearn-v84.css?v=84a1&hf=84a3", "brak cache-bust CSS")
    req(index, "symphony2.js?v=210", "brak aktywnej Symfonii 2.0")
    if "scenario-studio-v82a.js" in index or "generator-quality-v888.js" in index:
        ERRORS.append("wycofany Scenario Generator nadal jest bootstrappowany")
    if "scenario-studio-v82a" in previous_guard:
        ERRORS.append("poprzedni AutoLearn guard nadal zależy od Scenario Studio")

    if 'current_probs = [_prob_from_score(r) for r in current_rows]' in backend:
        ERRORS.append("produkcja nadal traktuje /100 jak probability bez calibratora")

    markers = [
        "AutoLearn Hotfix Guard v8.4A.1",
        "AutoLearn Calibration Guard v8.4A.2",
        "Final API quota report v8.3B",
    ]
    if all(x in workflow for x in markers):
        pos = [workflow.index(x) for x in markers]
        if pos != sorted(pos):
            ERRORS.append("workflow: zła kolejność guardów")
    else:
        ERRORS.append("workflow: brak któregoś guarda")

    if ERRORS:
        print("❌ AutoLearn Calibration Guard v8.4A.2 — FAIL")
        for e in ERRORS:
            print("  -", e)
        return 1
    print("✅ AutoLearn Calibration Guard v8.4A.2 — PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
