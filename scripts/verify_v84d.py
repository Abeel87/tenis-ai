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
    dyn = read("backend/dynamic_weights_v84d.py")
    auto = read("backend/autolearn_v84.py")
    tel = read("backend/model_telemetry_v84c.py")
    ui = read("frontend/autolearn-v84.js")
    idx = read("frontend/index.html")
    wf = read(".github/workflows/update-and-pages.yml")

    req(dyn, 'VERSION = "v8.4D"', "Dynamic Weights nie są v8.4D")
    req(dyn, "MIN_SEGMENT_N = 18", "brak minimalnej próbki segmentu")
    req(dyn, "MAX_ABS_SHIFT = 0.12", "brak capu przesunięcia lokalnych wag")
    req(dyn, "CURRENT_FLOOR = 0.10", "brak floor Current Engine")
    req(dyn, "TABPFN_CAP = 0.35", "brak lokalnego capu TabPFN")
    req(dyn, "def resolve_weights", "brak resolvera dynamicznych wag")
    req(dyn, "No model can be silently re-enabled", "brak ochrony przed re-enable modelu")

    req(auto, 'VERSION = "v8.4B"', "naruszono chroniony VERSION AutoLearn v8.4B")
    req(auto, 'DYNAMIC_WEIGHTS_VERSION = "v8.4D"', "AutoLearn nie deklaruje warstwy v8.4D")
    req(auto, "model_telemetry_v84c.json", "AutoLearn nie używa poprzedniego snapshotu telemetryki")
    req(auto, "_resolve_dynamic_weights", "AutoLearn nie rozwiązuje wag per sygnał")
    req(auto, '"dynamic_weighting": s.get("dynamic_weighting")', "frozen history nie zapisuje polityki dynamicznej")
    req(auto, '"local_weights": s.get("local_weights")', "frozen history nie zapisuje lokalnych wag")
    req(auto, '"dynamic_weights": dynamic_summary', "raport AutoLearn nie pokazuje v8.4D")

    req(tel, '"dynamic": "Dynamic Ensemble v8.4D"', "telemetria nie ma osobnego modelu Dynamic v8.4D")
    req(tel, 'dyn.get("active")', "telemetria nie filtruje aktywnych decyzji v8.4D")
    req(ui, "'dynamic'", "UI telemetrii nie pokazuje Dynamic Ensemble")

    req(idx, 'autolearn-v84.css?v=84a1&hf=84a3', "naruszono chroniony pin CSS")
    req(idx, 'scenario-studio-v82a.js?v=82a6', "naruszono chroniony pin Scenario Studio")
    req(wf, "Dynamic Weights Guard v8.4D", "workflow nie uruchamia guarda v8.4D")

    if ERRORS:
        print("❌ Dynamic Weights Guard v8.4D — FAIL")
        for e in ERRORS:
            print("  -", e)
        return 1
    print("✅ Dynamic Weights Guard v8.4D — PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
