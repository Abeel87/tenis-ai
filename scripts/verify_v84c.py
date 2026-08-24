from pathlib import Path
import json

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
    telemetry = read("backend/model_telemetry_v84c.py")
    ui = read("frontend/autolearn-v84.js")
    workflow = read(".github/workflows/update-and-pages.yml")
    auto = read("backend/autolearn_v84.py")
    scenario = read("frontend/scenario-studio-v82a.js")
    report_text = read("frontend/data/model_telemetry_v84c.json")

    req(telemetry, 'VERSION = "v8.4C"', "telemetry backend nie jest v8.4C")
    req(telemetry, 'learning_signals_v79b', "telemetry nie czyta modeli specjalistycznych")
    req(telemetry, 'autolearn_signals_v84', "telemetry nie czyta predykcji ML")
    req(telemetry, 'generator_selected', "telemetry nie śledzi finalnego generatora")
    req(telemetry, 'segments_30d', "telemetry nie raportuje segmentów 30d")
    req(telemetry, 'roi_status', "ROI nie ma jawnego statusu N/D")

    # v8.4C is additive: do not mutate the guarded v8.4B prediction core yet.
    req(auto, 'VERSION = "v8.4B"', "v8.4C naruszyło chroniony core AutoLearn v8.4B")
    req(scenario, "const VERSION='v8.2A-core'", "v8.4C naruszyło chroniony Scenario Studio core")

    req(ui, "🤖 AUTOLEARN v8.4B", "zniknął kompatybilny nagłówek AutoLearn v8.4B")
    req(ui, "📡 TELEMETRIA v8.4C", "UI nie pokazuje telemetrii v8.4C")
    req(ui, "model_telemetry_v84c.json", "UI nie pobiera raportu telemetrycznego")
    req(ui, "loadTelemetry", "UI nie ma bezpiecznego loadera telemetrii")

    req(workflow, "Model Telemetry v8.4C", "workflow nie buduje telemetrii v8.4C")
    req(workflow, "Model Telemetry Guard v8.4C", "workflow nie uruchamia guarda v8.4C")

    if report_text:
        try:
            report = json.loads(report_text)
            if report.get("version") != "v8.4C":
                ERRORS.append("raport telemetryczny ma złą wersję")
            models = ((report.get("scopes") or {}).get("30d") or {}).get("by_model") or {}
            for name in ("adaptive", "early", "serve", "form", "surface", "consensus", "current", "catboost", "tabpfn", "ensemble", "generator"):
                if name not in models:
                    ERRORS.append(f"raport 30d nie ma modelu: {name}")
        except json.JSONDecodeError:
            ERRORS.append("raport telemetryczny nie jest poprawnym JSON")

    if ERRORS:
        print("❌ Model Telemetry Guard v8.4C — FAIL")
        for e in ERRORS:
            print("  -", e)
        return 1
    print("✅ Model Telemetry Guard v8.4C — PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
