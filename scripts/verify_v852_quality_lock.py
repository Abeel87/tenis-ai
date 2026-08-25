from __future__ import annotations

import sys
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
    scenario = read("frontend/scenario-studio-v82a.js")
    changelog = read("CHANGELOG.md")
    auto = read("backend/autolearn_v84.py")
    telemetry = read("backend/model_telemetry_v84c.py")
    front_auto = read("frontend/autolearn-v84.js")
    tests_auto = read("tests/test_autolearn_v84.py")

    # 1. hard floors: Balanced 72, Stable 74, Strong 80, Experimental 62
    req(scenario, "floor:72", "brak hard floor 72 dla Balanced w scenario-studio-v82a.js")
    req(scenario, "floor:74", "brak hard floor 74 dla Stable w scenario-studio-v82a.js")
    req(scenario, "floor:80", "brak hard floor 80 dla Strong w scenario-studio-v82a.js")
    req(scenario, "floor:62", "brak hard floor 62 dla Experimental w scenario-studio-v82a.js")

    # 2. brak starych progów 57/58/63
    for old in ("floor:57", "floor:58", "floor:63"):
        if old in scenario:
            ERRORS.append(f"wykryto stary próg {old} w scenario-studio-v82a.js")

    # 3. obecność quality_lock_no_forced_fill_v852
    req(changelog, "quality_lock_no_forced_fill_v852", "brak quality_lock_no_forced_fill_v852 w CHANGELOG.md")
    req(auto, "quality_lock_no_forced_fill_v852", "brak quality_lock_no_forced_fill_v852 w backend/autolearn_v84.py")

    # 3b. progów profilowych w backend/autolearn_v84.py
    req(auto, '"stable": {"strong": 78, "floor": 74, "min_average": 74}', "brak nowych progów stable w backend/autolearn_v84.py")
    req(auto, '"balanced": {"strong": 76, "floor": 72, "min_average": 72}', "brak nowych progów balanced w backend/autolearn_v84.py")
    req(auto, '"strong": {"strong": 84, "floor": 80, "min_average": 80}', "brak nowych progów strong w backend/autolearn_v84.py")
    req(auto, '"experimental": {"strong": 68, "floor": 62, "min_average": 62}', "brak nowych progów experimental w backend/autolearn_v84.py")

    # 4. obecność tracking_governor w weight_policy
    req(auto, "tracking_governor", "brak tracking_governor w backend/autolearn_v84.py")

    # 5. nazwa Ensemble selector proxy
    req(telemetry, "Ensemble selector proxy", "brak nazwy Ensemble selector proxy w backend/model_telemetry_v84c.py")
    req(front_auto, "Ensemble selector proxy", "brak nazwy Ensemble selector proxy w frontend/autolearn-v84.js")

    # 6. obecność testów governora
    req(tests_auto, "test_tracking_governor", "brak testów governora w tests/test_autolearn_v84.py")

    if ERRORS:
        print("❌ Quality Lock Guard v8.5.2 — FAIL")
        for e in ERRORS:
            print("  -", e)
        return 1

    print("✅ Quality Lock Guard v8.5.2 — PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
