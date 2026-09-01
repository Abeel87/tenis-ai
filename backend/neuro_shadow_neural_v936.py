from __future__ import annotations

"""Small deterministic neural meta-model for NEURO SHADOW only.

Training is per canonical market, chronological and settled-history only. The
model never reads bookmaker prices, never auto-promotes and returns no neural
probability until its sample/class gates are satisfied.
"""

import math
import random
from typing import Any

VERSION = "neuro-shadow-neural-v9.3.6"
MODE = "SHADOW"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False
AUTO_PROMOTE = False

FEATURE_NAMES = (
    "state_probability",
    "base_probability",
    "current_probability",
    "catboost_probability",
    "tabpfn_probability",
    "adaptive_probability",
    "best_of_5",
    "surface_hard",
    "surface_clay",
    "surface_grass",
)
MODEL_PROBABILITY_FEATURES = FEATURE_NAMES[:6]
MIN_SETTLED = 80
MIN_CLASS_COUNT = 20
VALIDATION_FRACTION = 0.20
HIDDEN_UNITS = 6
LEARNING_RATE = 0.025
EPOCHS = 180
L2 = 0.0005
SEED = 935


def _num(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _time_key(row: dict[str, Any]) -> str:
    return str(row.get("scheduled_time") or row.get("created_at") or "")


def _feature_vector(row: dict[str, Any]) -> list[float] | None:
    snapshot = row.get("feature_snapshot")
    if not isinstance(snapshot, dict):
        return None
    numeric = snapshot.get("numeric")
    if not isinstance(numeric, dict):
        return None
    values: list[float] = []
    missing: list[float] = []
    for name in FEATURE_NAMES:
        value = _num(numeric.get(name))
        if name in MODEL_PROBABILITY_FEATURES:
            missing.append(1.0 if value is None else 0.0)
            values.append(0.5 if value is None else max(0.0, min(1.0, value)))
        else:
            values.append(0.0 if value is None else value)
    values.extend(missing)
    return values


def _target(row: dict[str, Any]) -> float | None:
    status = row.get("settlement")
    if status == "hit":
        return 1.0
    if status == "miss":
        return 0.0
    return None


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _standardizer(xs: list[list[float]]) -> tuple[list[float], list[float]]:
    width = len(xs[0])
    means, scales = [], []
    for col in range(width):
        vals = [row[col] for row in xs]
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        means.append(mean)
        scales.append(max(math.sqrt(var), 1e-6))
    return means, scales


def _transform(x: list[float], means: list[float], scales: list[float]) -> list[float]:
    return [(v - means[i]) / scales[i] for i, v in enumerate(x)]


def _init_network(width: int, hidden: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    scale1 = 1.0 / math.sqrt(max(1, width))
    scale2 = 1.0 / math.sqrt(max(1, hidden))
    return {
        "w1": [[rng.uniform(-scale1, scale1) for _ in range(width)] for _ in range(hidden)],
        "b1": [0.0] * hidden,
        "w2": [rng.uniform(-scale2, scale2) for _ in range(hidden)],
        "b2": 0.0,
    }


def _forward(net: dict[str, Any], x: list[float]) -> tuple[list[float], float]:
    hidden = []
    for weights, bias in zip(net["w1"], net["b1"]):
        z = sum(w * v for w, v in zip(weights, x)) + bias
        hidden.append(math.tanh(z))
    out = _sigmoid(sum(w * h for w, h in zip(net["w2"], hidden)) + net["b2"])
    return hidden, out


def _fit(xs: list[list[float]], ys: list[float], *, seed: int) -> dict[str, Any]:
    net = _init_network(len(xs[0]), HIDDEN_UNITS, seed)
    order = list(range(len(xs)))
    rng = random.Random(seed)
    for _ in range(EPOCHS):
        rng.shuffle(order)
        for idx in order:
            x, y = xs[idx], ys[idx]
            hidden, p = _forward(net, x)
            dz2 = p - y
            old_w2 = list(net["w2"])
            for j in range(HIDDEN_UNITS):
                net["w2"][j] -= LEARNING_RATE * (dz2 * hidden[j] + L2 * net["w2"][j])
            net["b2"] -= LEARNING_RATE * dz2
            for j in range(HIDDEN_UNITS):
                dz1 = dz2 * old_w2[j] * (1.0 - hidden[j] ** 2)
                for k in range(len(x)):
                    net["w1"][j][k] -= LEARNING_RATE * (dz1 * x[k] + L2 * net["w1"][j][k])
                net["b1"][j] -= LEARNING_RATE * dz1
    return net


def _metrics(probabilities: list[float], targets: list[float]) -> dict[str, Any]:
    if not probabilities:
        return {"n": 0, "accuracy": None, "brier": None, "log_loss": None}
    n = len(probabilities)
    hits = sum(int((p >= 0.5) == bool(y)) for p, y in zip(probabilities, targets))
    brier = sum((p - y) ** 2 for p, y in zip(probabilities, targets)) / n
    eps = 1e-12
    log_loss = 0.0
    for p, y in zip(probabilities, targets):
        pc = min(1.0 - eps, max(eps, p))
        log_loss += -(y * math.log(pc) + (1.0 - y) * math.log(1.0 - pc))
    return {"n": n, "accuracy": hits / n, "brier": brier, "log_loss": log_loss / n}


def train_market(rows: list[dict[str, Any]], market: str) -> dict[str, Any]:
    """Train one chronological market model or return COLLECTING_DATA."""
    eligible = []
    for row in rows or []:
        if not isinstance(row, dict) or str(row.get("market") or "") != str(market):
            continue
        y = _target(row)
        x = _feature_vector(row)
        if y is None or x is None:
            continue
        eligible.append((row, x, y))
    eligible.sort(key=lambda item: _time_key(item[0]))
    positives = sum(int(y == 1.0) for _, _, y in eligible)
    negatives = len(eligible) - positives
    gate = {
        "min_settled": MIN_SETTLED,
        "min_class_count": MIN_CLASS_COUNT,
        "settled": len(eligible),
        "hits": positives,
        "misses": negatives,
    }
    if len(eligible) < MIN_SETTLED or min(positives, negatives) < MIN_CLASS_COUNT:
        return {
            "version": VERSION,
            "market": market,
            "mode": MODE,
            "status": "COLLECTING_DATA",
            "gate": gate,
            "model": None,
            "validation": None,
            "auto_promote": False,
            "production_influence": False,
            "playable_influence": False,
        }

    split = max(1, min(len(eligible) - 1, int(len(eligible) * (1.0 - VALIDATION_FRACTION))))
    train, validation = eligible[:split], eligible[split:]
    train_y = [item[2] for item in train]
    if min(sum(int(y == 1.0) for y in train_y), sum(int(y == 0.0) for y in train_y)) < MIN_CLASS_COUNT // 2:
        return {
            "version": VERSION,
            "market": market,
            "mode": MODE,
            "status": "COLLECTING_DATA",
            "gate": {**gate, "reason": "insufficient_train_class_balance"},
            "model": None,
            "validation": None,
            "auto_promote": False,
            "production_influence": False,
            "playable_influence": False,
        }

    means, scales = _standardizer([item[1] for item in train])
    train_x = [_transform(item[1], means, scales) for item in train]
    net = _fit(train_x, train_y, seed=SEED + sum(ord(ch) for ch in str(market)))
    val_x = [_transform(item[1], means, scales) for item in validation]
    val_y = [item[2] for item in validation]
    val_p = [_forward(net, x)[1] for x in val_x]
    baseline_p = [max(0.0, min(1.0, item[1][0])) for item in validation]

    return {
        "version": VERSION,
        "market": market,
        "mode": MODE,
        "status": "SHADOW_MODEL_READY",
        "gate": gate,
        "feature_names": list(FEATURE_NAMES) + [f"missing_{name}" for name in MODEL_PROBABILITY_FEATURES],
        "train_rows": len(train),
        "validation_rows": len(validation),
        "validation_start": _time_key(validation[0][0]) if validation else None,
        "validation_end": _time_key(validation[-1][0]) if validation else None,
        "validation": _metrics(val_p, val_y),
        "state_baseline_validation": _metrics(baseline_p, val_y),
        "model": {"means": means, "scales": scales, **net},
        "auto_promote": False,
        "production_influence": False,
        "playable_influence": False,
    }


def predict(model_report: dict[str, Any], feature_snapshot: dict[str, Any]) -> float | None:
    """Return a neural SHADOW probability only for a gated ready model."""
    if not isinstance(model_report, dict) or model_report.get("status") != "SHADOW_MODEL_READY":
        return None
    model = model_report.get("model")
    if not isinstance(model, dict):
        return None
    x = _feature_vector({"feature_snapshot": feature_snapshot})
    if x is None:
        return None
    means, scales = model.get("means"), model.get("scales")
    if not isinstance(means, list) or not isinstance(scales, list) or len(x) != len(means) or len(x) != len(scales):
        return None
    _, p = _forward(model, _transform(x, means, scales))
    return max(0.0, min(1.0, p))
