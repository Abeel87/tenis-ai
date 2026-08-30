from __future__ import annotations

"""Symfonia 2.0 — supervised operator-line probability model.

One training row is one exact historical Superbet selection. The target is its
settled hit/miss outcome. Exact-state probability and existing model outputs are
features; no hand-written blend decides their weights in production.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
import math
from typing import Any, Iterable

try:
    from catboost import CatBoostClassifier
except Exception:  # pragma: no cover
    CatBoostClassifier = None

VERSION = "symphony2-learning-2"
MIN_TRAIN_ROWS = 200
VALIDATION_FRACTION = 0.20
MIN_MARKET_CALIBRATION_ROWS = 40
FULL_SUPPORT_ROWS = 120
EPS = 1e-6

CAT_FEATURES = ["market", "pick", "surface", "tour", "player_scope"]
NUM_FEATURES = [
    "line", "checkpoint", "best_of", "state_probability",
    "base_score", "current_score", "catboost_score", "tabpfn_score", "adaptive_score",
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
    try:
        return datetime.fromisoformat(str(value or "").replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _pick(value: Any) -> str:
    raw = _norm(value)
    aliases = {
        "o": "over", "powyzej": "over", "więcej": "over", "wiecej": "over",
        "u": "under", "ponizej": "under", "mniej": "under", "tak": "yes", "nie": "no",
    }
    return aliases.get(raw, raw or "unknown")


def _player_scope(signal: dict, match: dict) -> str:
    player = _norm(signal.get("player"))
    if not player:
        return "none"
    if player == _norm(match.get("p1")):
        return "p1"
    if player == _norm(match.get("p2")):
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
        return _num((signal.get("adaptive_prod_v79") or {}).get("final_score"), fallback)
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
        "state_probability": _num(signal.get("state_probability"), -1.0),
        "base_score": _score(signal, "base_score", 50.0),
        "current_score": _score(signal, "current_score", 50.0),
        "catboost_score": _score(signal, "catboost_score", 50.0),
        "tabpfn_score": _score(signal, "tabpfn_score", 50.0),
        "adaptive_score": _score(signal, "adaptive_score", 50.0),
    }


def _history_layer(entry: dict) -> list[dict]:
    for key in ("playable_autolearn_signals_v912", "playable_signals_v912"):
        rows = entry.get(key)
        if isinstance(rows, list) and rows:
            return [x for x in rows if isinstance(x, dict)]
    return []


def build_training_rows(history: Iterable[dict]) -> list[dict]:
    try:
        from .symphony2_state import build_outcomes, marginal_probability
    except ImportError:
        from symphony2_state import build_outcomes, marginal_probability

    rows: list[dict] = []
    seen: set[tuple] = set()
    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        captured = entry.get("captured_at") or entry.get("playable_captured_at_v912") or entry.get("scheduled_time")
        match_id = entry.get("match_id") if entry.get("match_id") is not None else entry.get("id")
        outcomes = build_outcomes(entry)
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
            enriched = dict(signal)
            state_p = marginal_probability(entry, signal, outcomes) if outcomes else None
            enriched["state_probability"] = state_p * 100.0 if state_p is not None else -1.0
            row = feature_row(entry, enriched)
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


def _brier(probabilities: list[float], targets: list[int]) -> float | None:
    return sum((float(p) - int(y)) ** 2 for p, y in zip(probabilities, targets)) / len(probabilities) if probabilities else None


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
                d, w = p - y, max(1e-6, p * (1.0 - p))
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
        return _clip(_sigmoid(self.a * _logit(p) + self.b)) if self.fitted else _clip(p)


def _accepted_calibrator(raw: list[float], targets: list[int]) -> tuple[PlattCalibrator, dict]:
    candidate = PlattCalibrator().fit(raw, targets)
    raw_brier = _brier(raw, targets)
    if not candidate.fitted:
        return PlattCalibrator(), {"fitted": False, "raw_brier": raw_brier, "calibrated_brier": None, "accepted": False}
    calibrated = [candidate.predict(p) for p in raw]
    calibrated_brier = _brier(calibrated, targets)
    accepted = calibrated_brier is not None and raw_brier is not None and calibrated_brier <= raw_brier + 1e-9
    chosen = candidate if accepted else PlattCalibrator()
    return chosen, {
        "fitted": candidate.fitted, "accepted": accepted,
        "raw_brier": round(raw_brier, 6) if raw_brier is not None else None,
        "calibrated_brier": round(calibrated_brier, 6) if calibrated_brier is not None else None,
        "a": round(candidate.a, 6), "b": round(candidate.b, 6),
    }


@dataclass
class OperatorLineModel:
    model: Any = None
    calibrator: PlattCalibrator = field(default_factory=PlattCalibrator)
    market_calibrators: dict[str, PlattCalibrator] = field(default_factory=dict)
    market_support: dict[str, int] = field(default_factory=dict)
    trained_rows: int = 0
    validation_rows: int = 0
    status: str = "not_trained"
    metrics: dict | None = None

    @property
    def ready(self) -> bool:
        return self.model is not None and self.status == "ready"

    def support_for(self, row: dict) -> int:
        return int(self.market_support.get(_norm(row.get("market")), 0))

    def predict(self, row: dict) -> float | None:
        if not self.ready:
            return None
        x = [[row.get(name) for name in FEATURES]]
        raw = float(self.model.predict_proba(x)[0][1])
        market = _norm(row.get("market"))
        calibrator = self.market_calibrators.get(market, self.calibrator)
        calibrated = calibrator.predict(raw)
        # Empirical-Bayes shrinkage for poorly represented market families.
        support = self.support_for(row)
        reliability = min(1.0, support / FULL_SUPPORT_ROWS)
        return _clip(0.5 + (calibrated - 0.5) * reliability)


def train_operator_line_model(history: Iterable[dict]) -> OperatorLineModel:
    rows = build_training_rows(history)
    support = Counter(r["market"] for r in rows)
    out = OperatorLineModel(trained_rows=len(rows), market_support=dict(support), metrics={"version": VERSION})
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
        iterations=360, depth=6, learning_rate=0.03, loss_function="Logloss",
        random_seed=20260830, verbose=False, allow_writing_files=False, l2_leaf_reg=6.0,
    )
    model.fit(x_train, y_train, cat_features=cat_indexes)

    metrics = {
        "version": VERSION, "training_rows": len(train), "validation_rows": len(valid),
        "time_split": bool(valid), "feature_names": FEATURES, "cat_features": CAT_FEATURES,
        "market_support": dict(sorted(support.items())),
        "calibration_policy": "market_platt_if_improves_brier_else_global_if_improves_else_raw",
        "low_support_policy": f"shrink_to_50_until_{FULL_SUPPORT_ROWS}_market_rows",
    }
    global_calibrator = PlattCalibrator()
    market_calibrators: dict[str, PlattCalibrator] = {}
    if valid:
        x_valid = [[r.get(name) for name in FEATURES] for r in valid]
        y_valid = [r["target"] for r in valid]
        raw = [float(x[1]) for x in model.predict_proba(x_valid)]
        global_calibrator, global_info = _accepted_calibrator(raw, y_valid)
        metrics["global_calibration"] = global_info
        per_market = {}
        for market in sorted({r["market"] for r in valid}):
            idx = [i for i, r in enumerate(valid) if r["market"] == market]
            if len(idx) < MIN_MARKET_CALIBRATION_ROWS:
                continue
            probs = [raw[i] for i in idx]
            targets = [y_valid[i] for i in idx]
            if len(set(targets)) < 2:
                continue
            calibrator, info = _accepted_calibrator(probs, targets)
            per_market[market] = {"rows": len(idx), **info}
            if calibrator.fitted:
                market_calibrators[market] = calibrator
        metrics["market_calibration"] = per_market
    else:
        metrics["global_calibration"] = {"fitted": False, "accepted": False}
        metrics["market_calibration"] = {}

    out.model = model
    out.calibrator = global_calibrator
    out.market_calibrators = market_calibrators
    out.validation_rows = len(valid)
    out.status = "ready"
    out.metrics = metrics
    return out
