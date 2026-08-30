from __future__ import annotations

"""Symfonia 2.0 — operator-line learning core.

This module learns P(hit) for an *exact historical Superbet selection*.
It never invents a betting line and never treats the bookmaker line as a target.
The supervised target is the settled hit/miss result of the exact operator offer.
"""

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Any, Iterable

try:
    from catboost import CatBoostClassifier
except Exception:  # pragma: no cover - runtime fallback is deliberate
    CatBoostClassifier = None

VERSION = "symphony2-learning-1"
MIN_TRAIN_ROWS = 200
VALIDATION_FRACTION = 0.20
EPS = 1e-6

CAT_FEATURES = ["market", "pick", "surface", "tour", "player_scope"]
NUM_FEATURES = [
    "line", "checkpoint", "best_of", "base_score", "current_score",
    "catboost_score", "tabpfn_score", "adaptive_score",
]
FEATURES = CAT_FEATURES + NUM_FEATURES


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _date_key(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _pick(value: Any) -> str:
    raw = _norm(value)
    aliases = {
        "o": "over", "powyzej": "over", "więcej": "over", "wiecej": "over",
        "u": "under", "ponizej": "under", "mniej": "under",
        "tak": "yes", "nie": "no",
    }
    return aliases.get(raw, raw or "unknown")


def _player_scope(signal: dict, match: dict) -> str:
    player = _norm(signal.get("player"))
    if not player:
        return "none"
    p1, p2 = _norm(match.get("p1")), _norm(match.get("p2"))
    if player == p1:
        return "p1"
    if player == p2:
        return "p2"
    return "named"


def _score(signal: dict, key: str, fallback=None):
    models = signal.get("model_scores") or {}
    if key == "base_score":
        return _num(signal.get("score"), fallback)
    if key == "current_score":
        return _num(models.get("current"), _num(signal.get("current"), fallback))
    if key == "catboost_score":
        return _num(models.get("catboost"), _num(signal.get("catboost"), fallback))
    if key == "tabpfn_score":
        return _num(models.get("tabpfn"), _num(signal.get("tabpfn"), fallback))
    if key == "adaptive_score":
        adaptive = signal.get("adaptive_prod_v79") or {}
        return _num(adaptive.get("final_score"), fallback)
    return fallback


def feature_row(match: dict, signal: dict) -> dict:
    return {
        "market": _norm(signal.get("market")) or "unknown",
        "pick": _pick(signal.get("pick")),
        "surface": _norm(match.get("surface")) or "unknown",
        "tour": _norm(match.get("tour")) or "unknown",
        "player_scope": _player_scope(signal, match),
        "line": _num(signal.get("line"), -999.0),
        "checkpoint": _num(signal.get("checkpoint"), 0.0),
        "best_of": _num(match.get("best_of"), 3.0),
        "base_score": _score(signal, "base_score", 50.0),
        "current_score": _score(signal, "current_score", 50.0),
        "catboost_score": _score(signal, "catboost_score", 50.0),
        "tabpfn_score": _score(signal, "tabpfn_score", 50.0),
        "adaptive_score": _score(signal, "adaptive_score", 50.0),
    }


def _history_layer(entry: dict) -> list[dict]:
    # Prefer the operator-frozen AutoLearn row because it carries the richest
    # model features for the *same exact Superbet line*. Fall back to current PROD.
    for key in ("playable_autolearn_signals_v912", "playable_signals_v912"):
        rows = entry.get(key)
        if isinstance(rows, list) and rows:
            return [x for x in rows if isinstance(x, dict)]
    return []


def build_training_rows(history: Iterable[dict]) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple] = set()
    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        captured = entry.get("captured_at") or entry.get("playable_captured_at_v912") or entry.get("scheduled_time")
        match_id = entry.get("match_id") if entry.get("match_id") is not None else entry.get("id")
        for signal in _history_layer(entry):
            result = _norm(signal.get("result"))
            if result not in {"hit", "miss"}:
                continue
            signature = (
                str(match_id), _norm(signal.get("market")), _pick(signal.get("pick")),
                _num(signal.get("line")), _num(signal.get("checkpoint")), _norm(signal.get("player")),
            )
            if signature in seen:
                continue
            seen.add(signature)
            row = feature_row(entry, signal)
            row["target"] = 1 if result == "hit" else 0
            row["captured_ts"] = _date_key(captured)
            row["signature"] = signature
            rows.append(row)
    rows.sort(key=lambda x: x["captured_ts"])
    return rows


def _clip(p: float) -> float:
    return max(EPS, min(1.0 - EPS, float(p)))


def _logit(p: float) -> float:
    p = _clip(p)
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


@dataclass
class PlattCalibrator:
    a: float = 1.0
    b: float = 0.0
    fitted: bool = False

    def fit(self, probabilities: list[float], targets: list[int]) -> "PlattCalibrator":
        if len(probabilities) < 40 or len(set(targets)) < 2:
            return self
        a, b = 1.0, 0.0
        xs = [_logit(p) for p in probabilities]
        for _ in range(50):
            g_a = g_b = 0.0
            h_aa = h_ab = h_bb = 1e-6
            for x, y in zip(xs, targets):
                p = _sigmoid(a * x + b)
                d = p - y
                w = max(1e-6, p * (1.0 - p))
                g_a += d * x
                g_b += d
                h_aa += w * x * x
                h_ab += w * x
                h_bb += w
            det = h_aa * h_bb - h_ab * h_ab
            if abs(det) < 1e-12:
                break
            step_a = (h_bb * g_a - h_ab * g_b) / det
            step_b = (-h_ab * g_a + h_aa * g_b) / det
            a -= step_a
            b -= step_b
            if max(abs(step_a), abs(step_b)) < 1e-6:
                break
        self.a, self.b, self.fitted = float(a), float(b), True
        return self

    def predict(self, p: float) -> float:
        if not self.fitted:
            return _clip(p)
        return _clip(_sigmoid(self.a * _logit(p) + self.b))


def _brier(probabilities: list[float], targets: list[int]) -> float | None:
    if not probabilities:
        return None
    return sum((float(p) - int(y)) ** 2 for p, y in zip(probabilities, targets)) / len(probabilities)


@dataclass
class OperatorLineModel:
    model: Any = None
    calibrator: PlattCalibrator | None = None
    trained_rows: int = 0
    validation_rows: int = 0
    status: str = "not_trained"
    metrics: dict | None = None

    @property
    def ready(self) -> bool:
        return self.model is not None and self.status == "ready"

    def predict(self, row: dict) -> float | None:
        if not self.ready:
            return None
        x = [[row.get(name) for name in FEATURES]]
        p = float(self.model.predict_proba(x)[0][1])
        return self.calibrator.predict(p) if self.calibrator else _clip(p)


def train_operator_line_model(history: Iterable[dict]) -> OperatorLineModel:
    rows = build_training_rows(history)
    out = OperatorLineModel(trained_rows=len(rows), metrics={"version": VERSION})
    if CatBoostClassifier is None:
        out.status = "catboost_unavailable"
        return out
    if len(rows) < MIN_TRAIN_ROWS or len({r["target"] for r in rows}) < 2:
        out.status = "insufficient_history"
        return out

    split = max(1, min(len(rows) - 1, int(round(len(rows) * (1.0 - VALIDATION_FRACTION)))))
    train, valid = rows[:split], rows[split:]
    if len(valid) < 40 or len({r["target"] for r in valid}) < 2:
        train, valid = rows, []

    x_train = [[r.get(name) for name in FEATURES] for r in train]
    y_train = [r["target"] for r in train]
    cat_indexes = [FEATURES.index(name) for name in CAT_FEATURES]

    model = CatBoostClassifier(
        iterations=320,
        depth=6,
        learning_rate=0.035,
        loss_function="Logloss",
        random_seed=20260830,
        verbose=False,
        allow_writing_files=False,
        l2_leaf_reg=5.0,
    )
    model.fit(x_train, y_train, cat_features=cat_indexes)

    calibrator = PlattCalibrator()
    metrics = {
        "version": VERSION,
        "training_rows": len(train),
        "validation_rows": len(valid),
        "time_split": bool(valid),
        "feature_names": FEATURES,
        "cat_features": CAT_FEATURES,
    }
    if valid:
        x_valid = [[r.get(name) for name in FEATURES] for r in valid]
        y_valid = [r["target"] for r in valid]
        raw = [float(x[1]) for x in model.predict_proba(x_valid)]
        metrics["raw_brier"] = round(_brier(raw, y_valid), 6)
        calibrator.fit(raw, y_valid)
        calibrated = [calibrator.predict(p) for p in raw]
        metrics["calibrated_brier"] = round(_brier(calibrated, y_valid), 6)
        metrics["calibrator"] = {
            "fitted": calibrator.fitted,
            "a": round(calibrator.a, 6),
            "b": round(calibrator.b, 6),
        }
    else:
        metrics["raw_brier"] = None
        metrics["calibrated_brier"] = None
        metrics["calibrator"] = {"fitted": False}

    out.model = model
    out.calibrator = calibrator
    out.validation_rows = len(valid)
    out.status = "ready"
    out.metrics = metrics
    return out
