from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERRORS = []


def read(path: str) -> str:
    p = ROOT / path
    if not p.exists():
        ERRORS.append(f"brak pliku: {path}")
        return ""
    return p.read_text(encoding="utf-8")


def req(text: str, needle: str, msg: str) -> None:
    if needle not in text:
        ERRORS.append(msg)


def main() -> int:
    index = read("frontend/index.html")
    changelog = read("CHANGELOG.md")
    auto = read("backend/autolearn_v84.py")
    telemetry = read("backend/model_telemetry_v84c.py")
    front_auto = read("frontend/autolearn-v84.js")
    tests_auto = read("tests/test_autolearn_v84.py")

    req(changelog, "quality_lock_no_forced_fill_v852", "brak quality_lock_no_forced_fill_v852 w CHANGELOG.md")
    req(auto, "quality_lock_no_forced_fill_v852", "brak quality_lock_no_forced_fill_v852 w backend/autolearn_v84.py")

    req(auto, '"stable": {"strong": 78, "floor": 74, "min_average": 74}', "brak progów stable w backend/autolearn_v84.py")
    req(auto, '"balanced": {"strong": 76, "floor": 72, "min_average": 72}', "brak progów balanced w backend/autolearn_v84.py")
    req(auto, '"strong": {"strong": 84, "floor": 80, "min_average": 80}', "brak progów strong w backend/autolearn_v84.py")
    req(auto, '"experimental": {"strong": 68, "floor": 62, "min_average": 62}', "brak progów experimental w backend/autolearn_v84.py")
    req(auto, "tracking_governor", "brak tracking_governor w backend/autolearn_v84.py")

    req(telemetry, "Ensemble selector proxy", "brak nazwy Ensemble selector proxy w backend/model_telemetry_v84c.py")
    req(front_auto, "Ensemble selector proxy", "brak nazwy Ensemble selector proxy w frontend/autolearn-v84.js")
    req(tests_auto, "test_tracking_governor", "brak testów governora w tests/test_autolearn_v84.py")

    for retired in ("scenario-studio-v82a.js", "scenario-runtime-v202.js", "generator-quality-v888.js"):
        if retired in index:
            ERRORS.append(f"wycofany asset nadal aktywny w index.html: {retired}")
    req(index, "symphony2.js?v=210", "Symfonia 2.0 nie jest aktywna w index.html")

    if ERRORS:
        print("❌ Quality Lock Guard v8.5.2 — FAIL")
        for e in ERRORS:
            print("  -", e)
        return 1

    print("✅ Quality Lock Guard v8.5.2 — PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
