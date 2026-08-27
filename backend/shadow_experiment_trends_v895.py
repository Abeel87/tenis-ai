from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
PLAYER = OUT / "player_model_shadow_v89.json"
LEARNING = OUT / "ensemble_player_learning_v891.json"
ELO = OUT / "surface_elo_integration_v893.json"
REPORT = OUT / "shadow_experiment_trends_v895.json"

VERSION = "v8.9.5"
MODE = "SHADOW"
MAX_POINTS = 60

MODELS = {
    "catboost_player": "CatBoost + Player Intelligence",
    "ensemble_player": "Ensemble + Player Learning",
    "catboost_player_elo": "CatBoost + Player + Surface Elo",
    "ensemble_player_elo": "Ensemble + Player + Surface Elo",
    "tabpfn_elo": "TabPFN + Surface Elo",
}


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _num(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _metric(row):
    row = row or {}
    return {
        "accuracy": _num(row.get("accuracy")),
        "brier": _num(row.get("brier")),
        "log_loss": _num(row.get("log_loss")),
        "n": int(row.get("n") or 0),
        "selected_n": int(row.get("selected_n") or 0),
    }


def _point(source_generated_at, status, current, baseline=None):
    c = _metric(current)
    b = _metric(baseline)
    return {
        "source_generated_at": source_generated_at,
        "status": str(status or "collecting"),
        **c,
        "base_accuracy": b["accuracy"],
        "base_brier": b["brier"],
        "base_log_loss": b["log_loss"],
    }


def _snapshots(player, learning, elo):
    ph = player.get("holdout") or {}
    lh = learning.get("holdout") or {}
    eh = elo.get("holdout") or {}
    return {
        "catboost_player": _point(
            player.get("generated_at"),
            (player.get("gate") or {}).get("status"),
            ph.get("player_catboost_shadow"),
            (ph.get("baselines") or {}).get("catboost"),
        ),
        "ensemble_player": _point(
            learning.get("generated_at"),
            (learning.get("gate") or {}).get("status"),
            lh.get("ensemble_player_learning"),
            (lh.get("baselines") or {}).get("ensemble_player_formula")
            or (lh.get("baselines") or {}).get("ensemble"),
        ),
        "catboost_player_elo": _point(
            elo.get("generated_at"),
            ((elo.get("gates") or {}).get("catboost_player_elo") or {}).get("status"),
            eh.get("catboost_player_elo"),
            eh.get("catboost_player"),
        ),
        "ensemble_player_elo": _point(
            elo.get("generated_at"),
            ((elo.get("gates") or {}).get("ensemble_player_elo") or {}).get("status"),
            eh.get("ensemble_player_elo"),
            eh.get("ensemble_player"),
        ),
        "tabpfn_elo": _point(
            elo.get("generated_at"),
            ((elo.get("gates") or {}).get("tabpfn_elo") or {}).get("status"),
            eh.get("tabpfn_elo"),
            eh.get("tabpfn"),
        ),
    }


def _same_point(a, b):
    keys = (
        "source_generated_at", "accuracy", "brier", "log_loss", "n", "selected_n",
        "base_accuracy", "base_brier", "base_log_loss", "status",
    )
    return all(a.get(k) == b.get(k) for k in keys)


def run(now=None):
    now = now or datetime.now(timezone.utc)
    player = _read(PLAYER, {})
    learning = _read(LEARNING, {})
    elo = _read(ELO, {})
    previous = _read(REPORT, {})
    old_models = previous.get("models") if isinstance(previous, dict) else {}
    old_models = old_models if isinstance(old_models, dict) else {}

    snapshots = _snapshots(player, learning, elo)
    models = {}
    appended = 0

    for model_id, label in MODELS.items():
        old = old_models.get(model_id) or {}
        points = [p for p in (old.get("points") or []) if isinstance(p, dict)]
        point = snapshots[model_id]
        # Keep a real history point only when the model produced a usable holdout metric.
        if point.get("n", 0) > 0 and (point.get("accuracy") is not None or point.get("brier") is not None):
            if not points or not _same_point(points[-1], point):
                points.append(point)
                appended += 1
        models[model_id] = {
            "label": label,
            "points": points[-MAX_POINTS:],
            "points_count": min(len(points), MAX_POINTS),
        }

    report = {
        "version": VERSION,
        "generated_at": now.isoformat(),
        "mode": MODE,
        "production_influence": False,
        "max_points_per_model": MAX_POINTS,
        "models": models,
        "note": "Historia tylko do wykresów SHADOW. Nie zmienia modeli, Generatora, Adaptive PROD ani final_score.",
    }
    _write(REPORT, report)
    return {
        "status": "ok",
        "appended": appended,
        "points": {k: v["points_count"] for k, v in models.items()},
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
