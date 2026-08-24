from __future__ import annotations

import argparse
import json
import math

VERSION = "v8.4D"

MODELS = ("current", "catboost", "tabpfn")
DIMENSIONS = ("market", "tour", "surface")

MIN_SEGMENT_N = 18
FULL_SEGMENT_N = 60

PER_DIM_FACTOR_MIN = 0.90
PER_DIM_FACTOR_MAX = 1.12
MAX_ABS_SHIFT = 0.12
CURRENT_FLOOR = 0.10
TABPFN_CAP = 0.35
SINGLE_MODEL_CAP = 0.80
BRIER_SCALE = 4.0


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _normalize(weights):
    clean = {}
    for name, value in (weights or {}).items():
        if name not in MODELS:
            continue
        v = _num(value, 0.0)
        if v is not None and v > 0:
            clean[name] = float(v)
    total = sum(clean.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in clean.items()}


def _segment_value(row: dict, dimension: str) -> str:
    value = str(row.get(dimension) or "N/D")
    if dimension in ("tour", "surface"):
        return value.upper()
    return value.lower()


def _segment_models(telemetry: dict, dimension: str, value: str) -> dict:
    return (
        ((telemetry or {}).get("segments_30d") or {})
        .get(dimension, {})
        .get(value, {})
    ) or {}


def _reliability(n: int) -> float:
    if n < MIN_SEGMENT_N:
        return 0.0
    if n >= FULL_SEGMENT_N:
        return 1.0
    span = max(1, FULL_SEGMENT_N - MIN_SEGMENT_N)
    return 0.25 + 0.75 * ((n - MIN_SEGMENT_N) / span)


def _dimension_adjustment(base: dict, telemetry: dict, row: dict, dimension: str):
    value = _segment_value(row, dimension)
    stats = _segment_models(telemetry, dimension, value)

    usable = {}
    for model in base:
        m = stats.get(model) or {}
        n = int(m.get("selected_n") or 0)
        b = _num(m.get("brier"))
        if n >= MIN_SEGMENT_N and b is not None:
            usable[model] = {"n": n, "brier": b}

    if len(usable) < 2:
        return None

    briers = sorted(x["brier"] for x in usable.values())
    mid = len(briers) // 2
    reference = briers[mid] if len(briers) % 2 else (briers[mid - 1] + briers[mid]) / 2.0

    factors = {}
    for model, x in usable.items():
        rel = _reliability(x["n"])
        raw = math.exp((reference - x["brier"]) * BRIER_SCALE * rel)
        factors[model] = max(PER_DIM_FACTOR_MIN, min(PER_DIM_FACTOR_MAX, raw))

    return {
        "dimension": dimension,
        "value": value,
        "reference_brier": round(reference, 5),
        "models": {
            model: {
                "n": x["n"],
                "brier": round(x["brier"], 5),
                "reliability": round(_reliability(x["n"]), 3),
                "factor": round(factors[model], 4),
            }
            for model, x in usable.items()
        },
        "factors": factors,
    }


def _bounded_weights(base: dict, adjusted: dict) -> dict:
    base = _normalize(base)
    adjusted = _normalize(adjusted)
    if not base:
        return {}

    # No model can be silently re-enabled by telemetry.
    adjusted = {k: adjusted.get(k, 0.0) for k in base}

    clipped = {}
    for model, b in base.items():
        target = adjusted.get(model, b)
        lo = max(0.0, b - MAX_ABS_SHIFT)
        hi = min(1.0, b + MAX_ABS_SHIFT)
        clipped[model] = max(lo, min(hi, target))
    clipped = _normalize(clipped)

    if "current" in base and base.get("current", 0.0) > 0:
        clipped["current"] = max(CURRENT_FLOOR, clipped.get("current", 0.0))
    if "tabpfn" in clipped:
        clipped["tabpfn"] = min(TABPFN_CAP, clipped["tabpfn"])
    clipped = _normalize(clipped)

    if clipped:
        dominant = max(clipped, key=clipped.get)
        if clipped[dominant] > SINGLE_MODEL_CAP and len(clipped) > 1:
            excess = clipped[dominant] - SINGLE_MODEL_CAP
            clipped[dominant] = SINGLE_MODEL_CAP
            others = [k for k in clipped if k != dominant]
            other_mass = sum(clipped[k] for k in others)
            if other_mass > 0:
                for k in others:
                    clipped[k] += excess * (clipped[k] / other_mass)
            else:
                share = excess / len(others)
                for k in others:
                    clipped[k] = share

    clipped = _normalize(clipped)

    if "tabpfn" in clipped and clipped["tabpfn"] > TABPFN_CAP:
        extra = clipped["tabpfn"] - TABPFN_CAP
        clipped["tabpfn"] = TABPFN_CAP
        others = [k for k in clipped if k != "tabpfn"]
        mass = sum(clipped[k] for k in others)
        if others:
            if mass > 0:
                for k in others:
                    clipped[k] += extra * clipped[k] / mass
            else:
                for k in others:
                    clipped[k] = extra / len(others)

    if "current" in base and base.get("current", 0.0) > 0 and clipped.get("current", 0.0) < CURRENT_FLOOR:
        need = CURRENT_FLOOR - clipped.get("current", 0.0)
        donors = sorted(
            [k for k in clipped if k != "current"],
            key=lambda k: clipped[k],
            reverse=True,
        )
        for donor in donors:
            take = min(need, max(0.0, clipped[donor]))
            clipped[donor] -= take
            clipped["current"] = clipped.get("current", 0.0) + take
            need -= take
            if need <= 1e-12:
                break

    return _normalize(clipped)


def resolve_weights(base_weights: dict, row: dict, telemetry: dict):
    """Resolve conservative per-signal weights from the previous telemetry snapshot."""
    base = _normalize(base_weights)
    fallback = {
        "version": VERSION,
        "active": False,
        "status": "SAFE_FALLBACK",
        "reason": "no_eligible_segment_evidence",
        "dimensions": [],
        "base_weights": {k: round(v, 4) for k, v in base.items()},
        "effective_weights": {k: round(v, 4) for k, v in base.items()},
        "max_shift": 0.0,
    }
    if len(base) < 2:
        return base, {**fallback, "reason": "fewer_than_two_enabled_models"}
    if not isinstance(telemetry, dict) or telemetry.get("version") != "v8.4C":
        return base, {**fallback, "reason": "telemetry_unavailable"}

    factors = {model: 1.0 for model in base}
    evidence = []
    for dimension in DIMENSIONS:
        item = _dimension_adjustment(base, telemetry, row, dimension)
        if not item:
            continue
        evidence.append(item)
        for model, factor in item["factors"].items():
            if model in factors:
                factors[model] *= factor

    if not evidence:
        return base, fallback

    raw = {model: base[model] * factors.get(model, 1.0) for model in base}
    effective = _bounded_weights(base, raw)
    if not effective:
        return base, {**fallback, "reason": "normalization_fallback"}

    max_shift = max(abs(effective.get(k, 0.0) - base.get(k, 0.0)) for k in base)
    active = max_shift >= 0.005

    policy = {
        "version": VERSION,
        "active": active,
        "status": "ACTIVE" if active else "SAFE_FALLBACK",
        "reason": "bounded_segment_adjustment" if active else "evidence_too_weak_to_move_weights",
        "dimensions": [
            {
                "dimension": e["dimension"],
                "value": e["value"],
                "reference_brier": e["reference_brier"],
                "models": e["models"],
            }
            for e in evidence
        ],
        "base_weights": {k: round(v, 4) for k, v in base.items()},
        "effective_weights": {k: round(v, 4) for k, v in effective.items()},
        "max_shift": round(max_shift, 4),
    }
    return effective, policy


def weighted_probability(probabilities: dict, weights: dict) -> float:
    available = []
    for model, weight in (weights or {}).items():
        p = _num((probabilities or {}).get(model))
        w = _num(weight, 0.0)
        if p is not None and w is not None and w > 0:
            available.append((p, w))
    den = sum(w for _, w in available)
    if den > 0:
        return sum(p * w for p, w in available) / den

    for model in ("catboost", "current", "tabpfn"):
        p = _num((probabilities or {}).get(model))
        if p is not None:
            return p
    return 0.5


def self_check():
    telemetry = {
        "version": "v8.4C",
        "segments_30d": {
            "tour": {
                "ATP": {
                    "current": {"selected_n": 60, "brier": 0.12},
                    "catboost": {"selected_n": 60, "brier": 0.22},
                    "tabpfn": {"selected_n": 18, "brier": 0.09},
                }
            },
            "surface": {
                "HARD": {
                    "current": {"selected_n": 50, "brier": 0.14},
                    "catboost": {"selected_n": 50, "brier": 0.20},
                    "tabpfn": {"selected_n": 18, "brier": 0.10},
                }
            },
            "market": {},
        },
    }
    base = {"current": 0.35, "catboost": 0.55, "tabpfn": 0.10}
    row = {"tour": "ATP", "surface": "HARD", "market": "set1_total"}
    w, policy = resolve_weights(base, row, telemetry)
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert policy["active"] is True
    assert w["current"] > base["current"]
    assert w["catboost"] < base["catboost"]
    assert w["tabpfn"] <= TABPFN_CAP

    w2, _ = resolve_weights({"current": 0.4, "catboost": 0.6, "tabpfn": 0.0}, row, telemetry)
    assert "tabpfn" not in w2

    tiny = {
        "version": "v8.4C",
        "segments_30d": {
            "tour": {
                "ATP": {
                    "current": {"selected_n": 5, "brier": 0.05},
                    "catboost": {"selected_n": 5, "brier": 0.40},
                }
            }
        },
    }
    w3, p3 = resolve_weights({"current": 0.4, "catboost": 0.6}, row, tiny)
    assert w3 == {"current": 0.4, "catboost": 0.6}
    assert p3["active"] is False

    print(json.dumps({
        "version": VERSION,
        "self_check": "PASS",
        "weights": {k: round(v, 4) for k, v in w.items()},
        "policy": policy["status"],
    }, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    print(json.dumps({
        "version": VERSION,
        "status": "library",
        "message": "Dynamic weights are resolved inside backend/autolearn_v84.py.",
    }, indent=2))


if __name__ == "__main__":
    main()
