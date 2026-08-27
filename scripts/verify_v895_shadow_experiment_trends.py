from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data" / "shadow_experiment_trends_v895.json"
BACKEND = ROOT / "backend" / "shadow_experiment_trends_v895.py"
UI = ROOT / "frontend" / "shadow-experiment-charts-v895.js"
BOOT = ROOT / "frontend" / "loading-fix-v889.js"

EXPECTED = {
    "catboost_player",
    "ensemble_player",
    "catboost_player_elo",
    "ensemble_player_elo",
    "tabpfn_elo",
}


def main():
    assert BACKEND.exists(), "missing trend backend"
    assert UI.exists(), "missing trend UI"
    assert DATA.exists(), "trend data was not built"

    data = json.loads(DATA.read_text(encoding="utf-8"))
    assert data.get("version") == "v8.9.5"
    assert data.get("mode") == "SHADOW"
    assert data.get("production_influence") is False
    models = data.get("models") or {}
    assert EXPECTED.issubset(models), f"missing trend models: {EXPECTED-set(models)}"

    for model_id in EXPECTED:
        row = models.get(model_id) or {}
        points = row.get("points") or []
        assert isinstance(points, list)
        assert len(points) <= 60
        for p in points:
            assert isinstance(p, dict)
            assert int(p.get("n") or 0) >= 0
            assert "accuracy" in p and "brier" in p

    ui = UI.read_text(encoding="utf-8")
    for token in ("Jak model idzie?", "Trafność", "Brier", "SHADOW · 0% PROD", DATA.name):
        assert token in ui, f"missing UI token {token!r}"
    boot = BOOT.read_text(encoding="utf-8")
    assert "shadow-experiment-charts-v895.js?v=895" in boot
    assert "productionInfluence:false" in ui
    workflow = (ROOT / '.github/workflows/update-and-pages.yml').read_text(encoding='utf-8')
    build = 'python backend/shadow_experiment_trends_v895.py'
    assert build in workflow, 'trend history must be rebuilt by the scheduled pipeline'
    assert workflow.index('python backend/surface_elo_integration_v893.py') < workflow.index(build)
    assert workflow.index(build) < workflow.index('git add frontend/data')
    print("v8.9.5 SHADOW experiment trend charts: PASS")


if __name__ == "__main__":
    main()
