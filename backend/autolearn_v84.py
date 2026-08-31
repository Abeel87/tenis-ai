from __future__ import annotations

try:
    from .history_sampling import unique_signals
except ImportError:
    from history_sampling import unique_signals

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
CACHE = ROOT / "data" / "cache" / "autolearn_v84"
RESULTS_PATH = OUT / "results.json"
HISTORY_PATH = OUT / "history.json"
REPORT_PATH = OUT / "autolearn_v84.json"
META_PATH = OUT / "meta.json"
CAT_MODEL_PATH = CACHE / "catboost_v84.cbm"
STATE_PATH = CACHE / "state.json"
TAB_INPUT_PATH = CACHE / "tabpfn_input.json"
TAB_OUTPUT_PATH = CACHE / "tabpfn_output.json"
TAB_MODEL_CACHE = ROOT / "data" / "cache" / "tabpfn_models"
DYNAMIC_TELEMETRY_PATH = OUT / "model_telemetry_v84c.json"
DYNAMIC_WEIGHTS_VERSION = "v8.4D"

try:
    from .dynamic_weights_v84d import (
        resolve_weights as _resolve_dynamic_weights,
        weighted_probability as _dynamic_weighted_probability,
    )
except ImportError:
    from dynamic_weights_v84d import (
        resolve_weights as _resolve_dynamic_weights,
        weighted_probability as _dynamic_weighted_probability,
    )

try:
    from .game_state_tracking_v84e1 import (
        VERSION as GAME_STATE_TRACKING_VERSION,
        checkpoint_from_signal as _game_state_checkpoint,
        current_signals as _game_state_current_signals,
        select_tracking_signals as _select_game_state_tracking_signals,
    )
except ImportError:
    from game_state_tracking_v84e1 import (
        VERSION as GAME_STATE_TRACKING_VERSION,
        checkpoint_from_signal as _game_state_checkpoint,
        current_signals as _game_state_current_signals,
        select_tracking_signals as _select_game_state_tracking_signals,
    )

VERSION = "v8.4B"
CATBOOST_NAME = "CatBoost AutoLearn"
TABPFN_NAME = "TabPFN-2 Challenger"
ENSEMBLE_NAME = "Ensemble Generator"
MIN_TRAIN_ROWS = 80
MIN_TRAIN_MATCHES = 24
RETRAIN_HOURS = 20
RETRAIN_NEW_ROWS = 40
CAPTURE_CUTOFF_MINUTES = 5
MODEL_SELECT_THRESHOLD = 0.65
GENERATOR_SELECT_THRESHOLD = 0.65
MAX_TRACK_SIGNALS_PER_MATCH = 12
GENERATOR_TOP_PER_MATCH = 2

# v8.4A.2 — Current Engine /100 jest siłą sygnału, nie literalnym prawdopodobieństwem.
# Platt/logit calibrator uczy się wyłącznie na TRAIN; CAL zostaje dla wag ensemble,
# a VAL jest nietkniętym przyszłym holdoutem.
CURRENT_CALIBRATION_MIN_ROWS = 40
CURRENT_CALIBRATION_REG = 0.25
CURRENT_CALIBRATION_MAX_ITERS = 80
CURRENT_CALIBRATION_GATE_MIN_ROWS = 30
CURRENT_CALIBRATION_GATE_MIN_MATCHES = 8
CURRENT_CALIBRATION_BRIER_TOL = 0.0020
CURRENT_CALIBRATION_LOGLOSS_TOL = 0.0050

# v8.4B — a small calibration slice must not hand 100% control to one model.
ENSEMBLE_SINGLE_MODEL_CAP = 0.80
ENSEMBLE_CURRENT_FLOOR = 0.10
ENSEMBLE_FULL_WEIGHT_MIN_CAL_MATCHES = 40

TABPFN_TRAIN_CAP = 300
TABPFN_CURRENT_CAP = 300
TABPFN_TIMEOUT_SECONDS = 150

# v8.4A.1 — bounded challenger policy.
# TabPFN dostaje mały realny głos, ale tylko w ograniczonym zakresie.
TABPFN_WARMUP_FLOOR = 0.10
TABPFN_VALIDATED_FLOOR = 0.10
TABPFN_VALIDATED_CAP = 0.25
TABPFN_STRONG_FLOOR = 0.15
TABPFN_STRONG_CAP = 0.35
TABPFN_GATE_MIN_N = 18
TABPFN_TRACK_MIN_N = 30
TABPFN_BRIER_MARGIN = 0.020
TABPFN_LOGLOSS_MARGIN = 0.040

NUMERIC_FEATURES = [
    "base_score", "adaptive", "early", "serve", "form", "surface_model",
    "consensus", "support", "mean_score", "std_score", "min_score", "max_score",
    "spread", "line", "model_confidence", "consensus_votes", "consensus_strong_votes",
]
CATEGORICAL_FEATURES = ["market", "pick_kind", "tour", "surface", "quality", "score_band"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def _read(path: Path, fallback):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(value)))


def _dt(value):
    try:
        d = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _norm(value):
    return " ".join(str(value or "").strip().casefold().split())


def _safe(value):
    return re.sub(r"[^a-z0-9.:-]+", "_", str(value or "").lower())


def _score_band(score):
    x = _num(score, 0.0)
    if x >= 90: return "90-100"
    if x >= 80: return "80-89"
    if x >= 72: return "72-79"
    if x >= 65: return "65-71"
    if x >= 55: return "55-64"
    return "<55"


def _canonical_market(market):
    m = _norm(market)
    return {
        "match_win": "match_winner",
        "set1_win": "set1_winner",
        "set2_win": "set2_winner",
        "set3_win": "set3_winner",
        "first_set": "set1_winner",
    }.get(m, m or "other")


def _candidate_key(signal: dict) -> str:
    raw_key = str(signal.get("key") or "")
    if "|" in raw_key:
        return raw_key
    market = _canonical_market(signal.get("market"))
    pick = str(signal.get("pick") or "")
    line = _num(signal.get("line"))
    checkpoint = signal.get("checkpoint")
    if market == "match_winner":
        return f"match_win|{_safe(pick)}"
    if market == "set1_winner":
        return f"set1_win|{_safe(pick)}"
    if market == "set2_winner":
        return f"set2_win|{_safe(pick)}"
    if market == "set3_winner":
        return f"set3_win|{_safe(pick)}"
    if market in ("set1_total", "match_total"):
        return f"{market}|{line:.1f}|{_norm(pick)}" if line is not None else f"{market}|?|{_norm(pick)}"
    if market == "game_state" and checkpoint is not None:
        return f"state|{int(checkpoint)}|{pick}"
    if market.startswith("state"):
        cp = market.replace("state", "")
        return f"state|{cp}|{pick}"
    return str(signal.get("key") or signal.get("id") or f"{market}|{pick}")


def _pick_kind(signal: dict) -> str:
    market = _canonical_market(signal.get("market"))
    pick = _norm(signal.get("pick"))
    if pick in ("over", "under"):
        return pick
    if market.startswith("state") or market == "game_state":
        return "state"
    if "winner" in market:
        return "player"
    if market == "total_sets":
        return "sets"
    return "other"


def _match_key(entry: dict) -> str:
    mid = entry.get("match_id") if entry.get("match_id") is not None else entry.get("id")
    if mid is not None and str(mid) != "":
        return f"id:{mid}"
    return "|".join([
        _norm(entry.get("p1")), _norm(entry.get("p2")),
        str(entry.get("scheduled_time") or "")[:10], _norm(entry.get("tournament")),
    ])


def _source_score_map(entry: dict) -> dict[str, dict[str, dict]]:
    grouped: dict[str, dict[str, dict]] = defaultdict(dict)
    for signal in unique_signals(entry, "signals"):
        if not isinstance(signal, dict):
            continue
        src = str(signal.get("source_model") or "adaptive")
        if src == "legacy": src = "adaptive"
        grouped[_candidate_key(signal)][src] = signal
    for signal in unique_signals(entry, "learning_signals_v79b"):
        if not isinstance(signal, dict):
            continue
        src = str(signal.get("source_model") or "specialist")
        grouped[_candidate_key(signal)][src] = signal
    for signal in unique_signals(entry, "game_state_learning_v84e1"):
        if not isinstance(signal, dict):
            continue
        grouped[_candidate_key(signal)].setdefault("adaptive", signal)
    return grouped


def _feature_row(entry: dict, key: str, sources: dict[str, dict], target=None) -> dict | None:
    if not sources:
        return None
    scored = {}
    for src, sig in sources.items():
        sc = _num(sig.get("score"))
        if sc is None:
            sc = _num(sig.get("value"))
        if sc is not None:
            scored[src] = _clamp(sc, 1.0, 99.0)
    if not scored:
        return None

    reference = next(iter(sources.values()))
    # Prefer the official/adaptive representation for market/pick/line.
    for name in ("adaptive", "consensus", "serve", "form", "surface", "early"):
        if name in sources:
            reference = sources[name]
            break

    vals = list(scored.values())
    base = scored.get("adaptive")
    if base is None:
        base = scored.get("consensus")
    if base is None:
        base = max(vals)

    consensus_sig = sources.get("consensus") or {}
    row = {
        "match_key": _match_key(entry),
        "scheduled_time": entry.get("scheduled_time"),
        "candidate_key": key,
        "market": _canonical_market(reference.get("market")),
        "pick": str(reference.get("pick") or ""),
        "pick_kind": _pick_kind(reference),
        "checkpoint": _game_state_checkpoint(reference),
        "line": _num(reference.get("line"), -1.0),
        "label": reference.get("label") or key,
        "tour": str(entry.get("tour") or "N/D").upper(),
        "surface": str(entry.get("surface") or "N/D").upper(),
        "quality": str(entry.get("quality") or "N/D"),
        "model_confidence": _num(entry.get("model_confidence"), 50.0),
        "base_score": base,
        "adaptive": scored.get("adaptive", 50.0),
        "early": scored.get("early", 50.0),
        "serve": scored.get("serve", 50.0),
        "form": scored.get("form", 50.0),
        "surface_model": scored.get("surface", 50.0),
        "consensus": scored.get("consensus", 50.0),
        "support": len(scored),
        "mean_score": mean(vals),
        "std_score": pstdev(vals) if len(vals) > 1 else 0.0,
        "min_score": min(vals),
        "max_score": max(vals),
        "spread": max(vals) - min(vals),
        "consensus_votes": _num(consensus_sig.get("votes"), 0.0),
        "consensus_strong_votes": _num(consensus_sig.get("strong_votes"), 0.0),
        "score_band": _score_band(base),
        "target": target,
    }
    return row


def build_training_rows(history: list[dict]) -> list[dict]:
    rows = []
    for entry in history or []:
        if not isinstance(entry, dict) or entry.get("status") not in ("settled", "void"):
            continue
        grouped = _source_score_map(entry)
        for key, sources in grouped.items():
            results = [str(s.get("result") or "") for s in sources.values()]
            hitmiss = [r for r in results if r in ("hit", "miss")]
            if not hitmiss:
                continue
            # A concrete market/pick has one ground truth. If legacy rows disagree, skip it.
            if len(set(hitmiss)) != 1:
                continue
            row = _feature_row(entry, key, sources, 1 if hitmiss[0] == "hit" else 0)
            if row:
                rows.append(row)
    rows.sort(key=lambda r: (str(r.get("scheduled_time") or ""), r["match_key"], r["candidate_key"]))
    return rows


def chronological_split(rows: list[dict]):
    by_match = defaultdict(list)
    match_time = {}
    for r in rows:
        by_match[r["match_key"]].append(r)
        match_time[r["match_key"]] = str(r.get("scheduled_time") or "")
    keys = sorted(by_match, key=lambda k: (match_time.get(k, ""), k))
    n = len(keys)
    if n < 3:
        return rows, [], []
    if n >= 24:
        n_train = max(1, int(n * 0.70))
        n_cal = max(1, int(n * 0.15))
        if n_train + n_cal >= n:
            n_cal = max(1, n - n_train - 1)
        train_keys = set(keys[:n_train])
        cal_keys = set(keys[n_train:n_train+n_cal])
        val_keys = set(keys[n_train+n_cal:])
    else:
        n_train = max(1, int(n * 0.8))
        train_keys = set(keys[:n_train])
        cal_keys = set()
        val_keys = set(keys[n_train:])
    train = [r for r in rows if r["match_key"] in train_keys]
    cal = [r for r in rows if r["match_key"] in cal_keys]
    val = [r for r in rows if r["match_key"] in val_keys]
    return train, cal, val


def _frame(rows):
    import pandas as pd
    data = []
    for r in rows:
        x = {}
        for c in NUMERIC_FEATURES:
            x[c] = _num(r.get(c), 0.0)
        for c in CATEGORICAL_FEATURES:
            x[c] = str(r.get(c) or "N/D")
        data.append(x)
    return pd.DataFrame(data, columns=FEATURE_COLUMNS)


def _raw_prob_from_score(row):
    """Raw signal-strength fraction. This is NOT a calibrated probability."""
    return _clamp(_num(row.get("base_score"), 50.0) / 100.0, 0.01, 0.99)


def _logit(p):
    p = _clamp(p, 1e-6, 1.0 - 1e-6)
    return math.log(p / (1.0 - p))


def _sigmoid(z):
    z = max(-35.0, min(35.0, float(z)))
    if z >= 0:
        e = math.exp(-z)
        return 1.0 / (1.0 + e)
    e = math.exp(z)
    return e / (1.0 + e)


def _apply_current_calibration(raw_probability, calibration=None):
    p = _clamp(raw_probability, 0.01, 0.99)
    calibration = calibration or {}
    if calibration.get("status") != "active":
        return p
    a = _num(calibration.get("a"), 1.0)
    b = _num(calibration.get("b"), 0.0)
    if a is None or b is None or a <= 0:
        return p
    return _clamp(_sigmoid(a * _logit(p) + b), 0.01, 0.99)


def _fit_current_calibration(rows):
    """Fit monotonic Platt scaling on TRAIN only.

    CatBoost may learn nonlinear relations from the same TRAIN rows. The separate
    CAL split remains untouched and is used only to choose ensemble weights.
    """
    usable = [
        r for r in (rows or [])
        if r.get("target") in (0, 1) and _num(r.get("base_score")) is not None
    ]
    matches = len({r.get("match_key") for r in usable if r.get("match_key")})
    base = {
        "method": "platt_logit",
        "fit_scope": "train_only",
        "fit_rows": len(usable),
        "fit_matches": matches,
        "status": "identity",
        "a": 1.0,
        "b": 0.0,
    }
    if len(usable) < CURRENT_CALIBRATION_MIN_ROWS:
        return {**base, "reason": "insufficient_rows"}
    ys = [int(r["target"]) for r in usable]
    if len(set(ys)) < 2:
        return {**base, "reason": "single_class"}

    xs = [_logit(_raw_prob_from_score(r)) for r in usable]
    raw_probs = [_raw_prob_from_score(r) for r in usable]

    # Start close to identity and regularize toward identity to avoid wild slopes
    # on a still-small tennis dataset.
    a, b = 1.0, 0.0
    reg = CURRENT_CALIBRATION_REG
    for _ in range(CURRENT_CALIBRATION_MAX_ITERS):
        probs = [_sigmoid(a * x + b) for x in xs]
        ws = [max(1e-6, p * (1.0 - p)) for p in probs]

        ga = sum((p - y) * x for p, y, x in zip(probs, ys, xs)) + reg * (a - 1.0)
        gb = sum((p - y) for p, y in zip(probs, ys)) + reg * b
        haa = sum(w * x * x for w, x in zip(ws, xs)) + reg
        hab = sum(w * x for w, x in zip(ws, xs))
        hbb = sum(ws) + reg
        det = haa * hbb - hab * hab
        if not math.isfinite(det) or abs(det) < 1e-10:
            break

        da = (ga * hbb - gb * hab) / det
        db = (gb * haa - ga * hab) / det
        next_a = max(0.05, min(8.0, a - da))
        next_b = max(-8.0, min(8.0, b - db))
        if abs(next_a - a) + abs(next_b - b) < 1e-8:
            a, b = next_a, next_b
            break
        a, b = next_a, next_b

    if not (math.isfinite(a) and math.isfinite(b) and a > 0):
        return {**base, "reason": "numeric_fallback"}

    calibrated = [_clamp(_sigmoid(a * x + b), 0.01, 0.99) for x in xs]
    return {
        **base,
        "status": "active",
        "reason": None,
        "a": round(a, 6),
        "b": round(b, 6),
        "train_raw_brier": round(_brier(ys, raw_probs), 5),
        "train_calibrated_brier": round(_brier(ys, calibrated), 5),
        "train_raw_log_loss": round(_logloss(ys, raw_probs), 5),
        "train_calibrated_log_loss": round(_logloss(ys, calibrated), 5),
    }


def _gate_current_calibration(candidate: dict, cal_rows: list[dict]) -> dict:
    """Accept Platt only on an untouched CAL slice; VAL remains final holdout."""
    candidate = dict(candidate or {})
    if candidate.get("status") != "active":
        return {
            **candidate,
            "gate_status": "not_applicable",
            "gate_scope": "calibration_split",
        }

    usable = [
        r for r in (cal_rows or [])
        if r.get("target") in (0, 1) and _num(r.get("base_score")) is not None
    ]
    matches = len({r.get("match_key") for r in usable if r.get("match_key")})
    if len(usable) < CURRENT_CALIBRATION_GATE_MIN_ROWS or matches < CURRENT_CALIBRATION_GATE_MIN_MATCHES:
        return {
            **candidate,
            "status": "gated_identity",
            "reason": "insufficient_calibration_gate_sample",
            "candidate_a": candidate.get("a"),
            "candidate_b": candidate.get("b"),
            "a": 1.0,
            "b": 0.0,
            "gate_status": "rejected",
            "gate_scope": "calibration_split",
            "gate_rows": len(usable),
            "gate_matches": matches,
        }

    y = [int(r["target"]) for r in usable]
    raw = [_raw_prob_from_score(r) for r in usable]
    calibrated = [_apply_current_calibration(p, candidate) for p in raw]
    raw_brier = _brier(y, raw)
    cal_brier = _brier(y, calibrated)
    raw_loss = _logloss(y, raw)
    cal_loss = _logloss(y, calibrated)
    brier_delta = None if raw_brier is None or cal_brier is None else cal_brier - raw_brier
    loss_delta = None if raw_loss is None or cal_loss is None else cal_loss - raw_loss

    accepted = (
        brier_delta is not None
        and loss_delta is not None
        and brier_delta <= CURRENT_CALIBRATION_BRIER_TOL
        and loss_delta <= CURRENT_CALIBRATION_LOGLOSS_TOL
    )
    gate = {
        "gate_scope": "calibration_split",
        "gate_rows": len(usable),
        "gate_matches": matches,
        "gate_raw_brier": round(raw_brier, 5) if raw_brier is not None else None,
        "gate_calibrated_brier": round(cal_brier, 5) if cal_brier is not None else None,
        "gate_brier_delta": round(brier_delta, 5) if brier_delta is not None else None,
        "gate_raw_log_loss": round(raw_loss, 5) if raw_loss is not None else None,
        "gate_calibrated_log_loss": round(cal_loss, 5) if cal_loss is not None else None,
        "gate_log_loss_delta": round(loss_delta, 5) if loss_delta is not None else None,
    }
    if accepted:
        improved = (brier_delta <= 0 and loss_delta <= 0)
        return {
            **candidate,
            **gate,
            "gate_status": "accepted_improved" if improved else "accepted_tolerance",
        }

    return {
        **candidate,
        **gate,
        "status": "gated_identity",
        "reason": "calibration_gate_rejected",
        "candidate_a": candidate.get("a"),
        "candidate_b": candidate.get("b"),
        "a": 1.0,
        "b": 0.0,
        "gate_status": "rejected",
    }


def _prob_from_score(row, calibration=None):
    return _apply_current_calibration(_raw_prob_from_score(row), calibration)


def _predict_cat(model, rows):
    if not rows:
        return []
    X = _frame(rows)
    probs = model.predict_proba(X)
    return [float(x[1]) for x in probs]


def _brier(y, p):
    if not y or not p or len(y) != len(p): return None
    return sum((float(pi) - float(yi)) ** 2 for yi, pi in zip(y, p)) / len(y)


def _logloss(y, p):
    if not y or not p or len(y) != len(p): return None
    total = 0.0
    for yi, pi in zip(y, p):
        pi = _clamp(pi, 1e-6, 1 - 1e-6)
        total += -(yi * math.log(pi) + (1 - yi) * math.log(1 - pi))
    return total / len(y)


def _metrics(rows, probs, threshold=MODEL_SELECT_THRESHOLD):
    if not rows or not probs or len(rows) != len(probs):
        return {"n": 0, "brier": None, "log_loss": None, "selected_n": 0, "accuracy": None}
    y = [int(r["target"]) for r in rows]
    selected = [(r, p) for r, p in zip(rows, probs) if p >= threshold]
    hits = sum(int(r["target"]) for r, _ in selected)
    return {
        "n": len(rows),
        "brier": round(_brier(y, probs), 5),
        "log_loss": round(_logloss(y, probs), 5),
        "selected_n": len(selected),
        "accuracy": round(hits * 100.0 / len(selected), 1) if selected else None,
        "threshold": round(threshold * 100, 1),
    }


def _optimize_weights(rows, probs_by_model: dict[str, list[float]]) -> dict[str, float]:
    names = [name for name, probs in probs_by_model.items() if len(probs) == len(rows) and rows]
    if len(names) <= 1 or len(rows) < 18:
        return {name: 1.0 if i == 0 else 0.0 for i, name in enumerate(names)}
    y = [int(r["target"]) for r in rows]
    best = None
    if len(names) == 2:
        for i in range(21):
            w0 = i / 20.0
            w = {names[0]: w0, names[1]: 1.0 - w0}
            p = [sum(w[n] * probs_by_model[n][j] for n in names) for j in range(len(rows))]
            score = (_brier(y, p), _logloss(y, p))
            if best is None or score < best[0]: best = (score, w)
    else:
        # 0.1 grid, enough for a small holdout and intentionally hard to overfit.
        for i in range(11):
            for j in range(11 - i):
                k = 10 - i - j
                ws = [i / 10.0, j / 10.0, k / 10.0]
                w = dict(zip(names[:3], ws))
                p = [sum(w[n] * probs_by_model[n][idx] for n in names[:3]) for idx in range(len(rows))]
                score = (_brier(y, p), _logloss(y, p))
                if best is None or score < best[0]: best = (score, w)
    return best[1] if best else {names[0]: 1.0}


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    clean = {}
    for name, value in (weights or {}).items():
        try:
            v = max(0.0, float(value))
        except (TypeError, ValueError):
            continue
        if v > 0:
            clean[name] = v
    total = sum(clean.values())
    if total <= 0:
        return {"current": 1.0}
    return {name: value / total for name, value in clean.items()}


def _calibration_match_count(rows) -> int:
    keys = {r.get("match_key") for r in (rows or []) if r.get("match_key")}
    return len(keys) if keys else len(rows or [])


def _stabilize_ensemble_weights(weights: dict[str, float], available_names, rows):
    """Prevent a tiny CAL sample from collapsing production to one model."""
    names = [str(x) for x in dict.fromkeys(available_names or []) if x]
    if not names:
        names = ["current"]

    raw = {}
    for name in names:
        try:
            raw[name] = max(0.0, float((weights or {}).get(name, 0.0)))
        except (TypeError, ValueError):
            raw[name] = 0.0
    if sum(raw.values()) <= 0:
        raw[names[0]] = 1.0
    total = sum(raw.values())
    w = {name: value / total for name, value in raw.items()}

    cal_matches = _calibration_match_count(rows)
    guard_active = len(names) >= 2 and cal_matches < ENSEMBLE_FULL_WEIGHT_MIN_CAL_MATCHES
    applied = False

    if guard_active:
        dominant = max(names, key=lambda n: w.get(n, 0.0))
        if w.get(dominant, 0.0) > ENSEMBLE_SINGLE_MODEL_CAP:
            excess = w[dominant] - ENSEMBLE_SINGLE_MODEL_CAP
            w[dominant] = ENSEMBLE_SINGLE_MODEL_CAP
            others = [n for n in names if n != dominant]
            other_mass = sum(w.get(n, 0.0) for n in others)
            if other_mass > 0:
                for n in others:
                    w[n] += excess * (w[n] / other_mass)
            elif others:
                share = excess / len(others)
                for n in others:
                    w[n] = share
            applied = True

        if "current" in names and w.get("current", 0.0) < ENSEMBLE_CURRENT_FLOOR:
            need = ENSEMBLE_CURRENT_FLOOR - w.get("current", 0.0)
            donors = sorted(
                [n for n in names if n != "current"],
                key=lambda n: w.get(n, 0.0),
                reverse=True,
            )
            for donor in donors:
                take = min(need, max(0.0, w.get(donor, 0.0)))
                if take <= 0:
                    continue
                w[donor] -= take
                w["current"] = w.get("current", 0.0) + take
                need -= take
                applied = True
                if need <= 1e-12:
                    break

    w = _normalize_weights(w)
    return w, {
        "guard_active": guard_active,
        "applied": applied,
        "calibration_matches": cal_matches,
        "full_weight_min_matches": ENSEMBLE_FULL_WEIGHT_MIN_CAL_MATCHES,
        "single_model_cap": ENSEMBLE_SINGLE_MODEL_CAP if guard_active else 1.0,
        "current_floor": ENSEMBLE_CURRENT_FLOOR if guard_active and "current" in names else 0.0,
    }


def _challenger_gate(previous_validation: dict, previous_tracking: dict) -> dict:
    """Use only evidence already persisted before this run.

    That keeps the current validation slice from becoming the tuning slice.
    """
    previous_validation = previous_validation or {}
    previous_tracking = previous_tracking or {}
    tv = previous_validation.get("tabpfn") or {}
    cv = previous_validation.get("current") or {}
    tt = previous_tracking.get("tabpfn") or {}
    ct = previous_tracking.get("current") or {}

    tn = int(tt.get("selected_n") or tt.get("n") or 0)
    if tn >= TABPFN_TRACK_MIN_N:
        tb, cb = _num(tt.get("brier")), _num(ct.get("brier"))
        tl, cl = _num(tt.get("log_loss")), _num(ct.get("log_loss"))
        ta, ca = _num(tt.get("accuracy")), _num(ct.get("accuracy"))
        brier_ok = tb is not None and (cb is None or tb <= cb + TABPFN_BRIER_MARGIN)
        loss_ok = tl is not None and (cl is None or tl <= cl + TABPFN_LOGLOSS_MARGIN)
        acc_ok = ta is None or ca is None or ta >= ca - 3.0
        if brier_ok and loss_ok and acc_ok:
            strong = (
                tn >= 60
                and tb is not None and cb is not None and tb <= cb
                and tl is not None and cl is not None and tl <= cl
            )
            return {
                "status": "strong" if strong else "tracking_pass",
                "allowed": True,
                "evidence": "tracking",
                "n": tn,
                "floor": TABPFN_STRONG_FLOOR if strong else TABPFN_VALIDATED_FLOOR,
                "cap": TABPFN_STRONG_CAP if strong else TABPFN_VALIDATED_CAP,
            }
        return {
            "status": "tracking_hold",
            "allowed": False,
            "evidence": "tracking",
            "n": tn,
            "floor": 0.0,
            "cap": 0.0,
        }

    vn = int(tv.get("selected_n") or tv.get("n") or 0)
    if vn >= TABPFN_GATE_MIN_N:
        tb, cb = _num(tv.get("brier")), _num(cv.get("brier"))
        tl, cl = _num(tv.get("log_loss")), _num(cv.get("log_loss"))
        brier_ok = tb is not None and (cb is None or tb <= cb + TABPFN_BRIER_MARGIN)
        loss_ok = tl is not None and (cl is None or tl <= cl + TABPFN_LOGLOSS_MARGIN)
        if brier_ok and loss_ok:
            return {
                "status": "validation_pass",
                "allowed": True,
                "evidence": "previous_validation",
                "n": vn,
                "floor": TABPFN_VALIDATED_FLOOR,
                "cap": TABPFN_VALIDATED_CAP,
            }
        return {
            "status": "validation_hold",
            "allowed": False,
            "evidence": "previous_validation",
            "n": vn,
            "floor": 0.0,
            "cap": 0.0,
        }

    return {
        "status": "warmup",
        "allowed": True,
        "evidence": "bounded_warmup",
        "n": vn,
        "floor": TABPFN_WARMUP_FLOOR,
        "cap": 0.15,
    }


def _bounded_tabpfn_weights(raw_weights: dict[str, float], previous_validation: dict,
                            previous_tracking: dict, tab_available: bool) -> tuple[dict[str, float], dict]:
    raw = _normalize_weights(raw_weights)
    if not tab_available:
        raw.pop("tabpfn", None)
        return _normalize_weights(raw), {
            "status": "no_fresh_tabpfn",
            "allowed": False,
            "floor": 0.0,
            "cap": 0.0,
        }

    gate = _challenger_gate(previous_validation, previous_tracking)
    if not gate.get("allowed"):
        raw.pop("tabpfn", None)
        return _normalize_weights(raw), gate

    floor = float(gate.get("floor") or 0.0)
    cap = float(gate.get("cap") or 0.0)
    target = max(floor, min(cap, float(raw.get("tabpfn") or 0.0)))

    others = {k: v for k, v in raw.items() if k != "tabpfn"}
    if not others:
        others = {"current": 1.0}
    others = _normalize_weights(others)
    out = {k: v * (1.0 - target) for k, v in others.items()}
    out["tabpfn"] = target
    out = _normalize_weights(out)
    gate = {**gate, "raw_tabpfn_weight": round(float(raw.get("tabpfn") or 0.0), 4),
            "effective_tabpfn_weight": round(float(out.get("tabpfn") or 0.0), 4)}
    return out, gate


def _apply_tracking_governor(weights: dict[str, float], previous_tracking: dict,
                            tabpfn_cap: float = 0.35, eligible_names=None) -> tuple[dict[str, float], dict]:
    weights = _normalize_weights(weights)
    initial_weights = dict(weights)
    eligible = [str(x) for x in dict.fromkeys(eligible_names or []) if x]
    if not previous_tracking or not isinstance(previous_tracking, dict):
        return weights, {
            "active": False,
            "status": "no_tracking_data",
            "catboost_capped": False,
            "tabpfn_boosted": False,
            "current_floored": False,
            "rules_applied": [],
            "governed_weights": {k: round(v, 4) for k, v in weights.items()},
        }

    cat_tr = previous_tracking.get("catboost") or {}
    cur_tr = previous_tracking.get("current") or {}
    tab_tr = previous_tracking.get("tabpfn") or {}

    cat_n = int(cat_tr.get("selected_n") or 0)
    cur_n = int(cur_tr.get("selected_n") or 0)
    tab_n = int(tab_tr.get("selected_n") or 0)

    cat_acc = _num(cat_tr.get("accuracy"))
    cur_acc = _num(cur_tr.get("accuracy"))
    tab_acc = _num(tab_tr.get("accuracy"))

    cat_brier = _num(cat_tr.get("brier"))
    cur_brier = _num(cur_tr.get("brier"))
    tab_brier = _num(tab_tr.get("brier"))

    catboost_capped = False
    tabpfn_boosted = False
    rules_applied = []

    if (cat_n >= 100 and cur_n >= 100 and cat_acc is not None and cur_acc is not None
            and cat_brier is not None and cur_brier is not None):
        if (cur_acc - cat_acc >= 1.0) and (cat_brier > cur_brier):
            catboost_capped = True
            rules_applied.append("catboost_capped_at_0.40")

    if ("tabpfn" in weights and tab_n >= 100 and cur_n >= 100 and tab_acc is not None and cur_acc is not None
            and tab_brier is not None and cur_brier is not None):
        if (tab_acc > cur_acc) and (tab_brier < cur_brier):
            tabpfn_boosted = True
            rules_applied.append("tabpfn_boosted_to_min_0.20")

    governor_active = catboost_capped or tabpfn_boosted

    if not governor_active:
        return weights, {
            "active": False,
            "status": "inactive",
            "catboost_capped": False,
            "tabpfn_boosted": False,
            "current_floored": False,
            "rules_applied": [],
            "sample_sizes": {
                "catboost_selected_n": cat_n,
                "current_selected_n": cur_n,
                "tabpfn_selected_n": tab_n,
            },
            "governed_weights": {k: round(v, 4) for k, v in weights.items()},
        }

    # Cached challenger weights can omit Current even though its probability is available.
    # Add it with zero mass before bounded redistribution so hard caps stay feasible instead
    # of being destroyed by a later normalization back to 100%.
    if "current" in eligible and "current" not in weights:
        weights = {**weights, "current": 0.0}

    lower_bounds = {m: 0.0 for m in weights}
    upper_bounds = {m: 1.0 for m in weights}

    if "tabpfn" in weights:
        upper_bounds["tabpfn"] = max(0.0, float(tabpfn_cap))

    if catboost_capped and "catboost" in weights:
        upper_bounds["catboost"] = 0.40

    current_floored = False
    if governor_active and "current" in weights:
        lower_bounds["current"] = 0.25
        current_floored = True
        rules_applied.append("current_floored_at_0.25")

    if tabpfn_boosted and "tabpfn" in weights:
        effective_tab_floor = min(0.20, upper_bounds.get("tabpfn", 0.35))
        lower_bounds["tabpfn"] = max(lower_bounds.get("tabpfn", 0.0), effective_tab_floor)

    w = {}
    for m, val in weights.items():
        lb = lower_bounds.get(m, 0.0)
        ub = upper_bounds.get(m, 1.0)
        w[m] = max(lb, min(ub, float(val)))

    for _ in range(30):
        tot = sum(w.values())
        diff = 1.0 - tot
        if abs(diff) < 1e-9:
            break
        if diff > 0:
            free = [m for m in w if w[m] < upper_bounds[m] - 1e-9]
            if not free:
                break
            free_weights = sum(w[m] for m in free)
            shares = {m: (w[m] / free_weights) if free_weights > 0 else (1.0 / len(free)) for m in free}
            for m in free:
                w[m] = min(upper_bounds[m], w[m] + diff * shares[m])
        else:
            free = [m for m in w if w[m] > lower_bounds[m] + 1e-9]
            if not free:
                break
            headrooms = {m: w[m] - lower_bounds[m] for m in free}
            tot_headroom = sum(headrooms.values())
            shares = {m: (headrooms[m] / tot_headroom) if tot_headroom > 0 else (1.0 / len(free)) for m in free}
            for m in free:
                w[m] = max(lower_bounds[m], w[m] - (-diff) * shares[m])

    # Do not call _normalize_weights here: proportional normalization can violate
    # the very upper/lower bounds enforced above. The loop already projects onto the
    # bounded simplex; only repair tiny floating-point residue inside remaining headroom.
    residue = 1.0 - sum(w.values())
    if abs(residue) > 1e-9:
        if residue > 0:
            free = [m for m in w if w[m] < upper_bounds[m] - 1e-9]
            for m in sorted(free, key=lambda n: upper_bounds[n] - w[n], reverse=True):
                add = min(residue, upper_bounds[m] - w[m])
                w[m] += add
                residue -= add
                if residue <= 1e-9:
                    break
        else:
            free = [m for m in w if w[m] > lower_bounds[m] + 1e-9]
            for m in sorted(free, key=lambda n: w[n] - lower_bounds[n], reverse=True):
                take = min(-residue, w[m] - lower_bounds[m])
                w[m] -= take
                residue += take
                if residue >= -1e-9:
                    break

    feasible = abs(sum(w.values()) - 1.0) <= 1e-7
    bounds_ok = all(lower_bounds[m] - 1e-9 <= w[m] <= upper_bounds[m] + 1e-9 for m in w)
    if not (feasible and bounds_ok):
        # Never publish a policy claiming caps were applied when the bounded simplex is
        # infeasible. Fall back to the incoming allocation and report the guard failure.
        return initial_weights, {
            "active": False,
            "status": "infeasible_bounds",
            "catboost_capped": False,
            "tabpfn_boosted": False,
            "current_floored": False,
            "rules_applied": [],
            "sample_sizes": {
                "catboost_selected_n": cat_n,
                "current_selected_n": cur_n,
                "tabpfn_selected_n": tab_n,
            },
            "initial_weights": {k: round(v, 4) for k, v in initial_weights.items()},
            "governed_weights": {k: round(v, 4) for k, v in initial_weights.items()},
        }

    w = {m: v for m, v in w.items() if v > 1e-12}

    policy_details = {
        "active": True,
        "status": "active",
        "catboost_capped": catboost_capped,
        "tabpfn_boosted": tabpfn_boosted,
        "current_floored": current_floored,
        "rules_applied": rules_applied,
        "sample_sizes": {
            "catboost_selected_n": cat_n,
            "current_selected_n": cur_n,
            "tabpfn_selected_n": tab_n,
        },
        "metrics_evaluated": {
            "catboost": {"accuracy": cat_acc, "brier": cat_brier},
            "current": {"accuracy": cur_acc, "brier": cur_brier},
            "tabpfn": {"accuracy": tab_acc, "brier": tab_brier},
        },
        "initial_weights": {k: round(v, 4) for k, v in weights.items()},
        "governed_weights": {k: round(v, 4) for k, v in w.items()},
    }

    return w, policy_details


def _choose_weights(rows, probs_by_model: dict[str, list[float]], previous_weights: dict,
                    previous_validation: dict, previous_tracking: dict,
                    tab_refreshed: bool, tab_cached_available: bool = False) -> tuple[dict[str, float], dict]:
    """Choose weights, then shrink extreme allocations while CAL is still small."""
    available = {
        name: probs for name, probs in (probs_by_model or {}).items()
        if rows and len(probs) == len(rows)
    }

    def finish(weights, policy, names):
        stable, stability = _stabilize_ensemble_weights(weights, names, rows)
        tab_cap = policy.get("cap", 0.35) if isinstance(policy, dict) else 0.35
        governed_weights, tracking_governor = _apply_tracking_governor(
            stable, previous_tracking, tabpfn_cap=tab_cap, eligible_names=names
        )
        return governed_weights, {**policy, "stability": stability, "tracking_governor": tracking_governor}

    if tab_refreshed and "tabpfn" in available:
        raw = _optimize_weights(rows, available)
        weights, policy = _bounded_tabpfn_weights(
            raw, previous_validation, previous_tracking, tab_available=True
        )
        return finish(weights, {**policy, "mode": "fresh_calibration"}, list(available))

    prev = _normalize_weights(previous_weights or {})
    if float(prev.get("tabpfn") or 0.0) > 0:
        names = list(dict.fromkeys([*available.keys(), *prev.keys()]))
        return finish(prev, {
            "status": "preserved",
            "allowed": True,
            "mode": "cached_challenger_weight",
            "effective_tabpfn_weight": round(float(prev.get("tabpfn") or 0.0), 4),
            "reason": "TabPFN nie był dziś przeliczany; zachowano ostatnią zatwierdzoną wagę.",
        }, names)

    raw = _optimize_weights(rows, available) if rows and available else {"current": 1.0}
    raw.pop("tabpfn", None)
    if tab_cached_available:
        bounded, policy = _bounded_tabpfn_weights(
            {**raw, "tabpfn": 0.0},
            previous_validation, previous_tracking, tab_available=True,
        )
        if policy.get("allowed"):
            return finish(bounded, {
                **policy,
                "mode": "cached_challenger_reenabled",
                "reason": "Poprzednia walidacja dopuściła TabPFN; przywrócono wyłącznie bounded floor.",
            }, list(dict.fromkeys([*available.keys(), *bounded.keys()])))

    return finish(_normalize_weights(raw), {
        "status": "optimizer",
        "allowed": False,
        "mode": "current_catboost_only",
        "effective_tabpfn_weight": 0.0,
    }, list(available) or ["current"])


def ensemble_probs(probs_by_model: dict[str, list[float]], weights: dict[str, float], n: int) -> list[float]:
    out = []
    for i in range(n):
        available = [(name, probs[i], weights.get(name, 0.0)) for name, probs in probs_by_model.items() if len(probs) > i and probs[i] is not None and weights.get(name, 0.0) > 0]
        den = sum(w for _, _, w in available)
        if den <= 0:
            # CatBoost/current fallback order.
            for name in ("catboost", "current", "tabpfn"):
                probs = probs_by_model.get(name) or []
                if len(probs) > i and probs[i] is not None:
                    out.append(float(probs[i])); break
            else: out.append(0.5)
        else:
            out.append(sum(float(p) * w for _, p, w in available) / den)
    return out


def _model_due(state: dict, training_rows: int, now: datetime) -> bool:
    if state.get("version") != VERSION: return True
    if not CAT_MODEL_PATH.exists(): return True
    trained = _dt(state.get("catboost_trained_at"))
    if not trained: return True
    if now - trained >= timedelta(hours=RETRAIN_HOURS): return True
    old_rows = int(state.get("training_rows") or 0)
    return training_rows - old_rows >= RETRAIN_NEW_ROWS


def tabpfn_due(now=None) -> bool:
    now = now or datetime.now(timezone.utc)
    state = _read(STATE_PATH, {})
    trained = _dt(state.get("tabpfn_trained_at"))
    if not trained: return True
    return now - trained >= timedelta(hours=RETRAIN_HOURS)


def _train_catboost(train, cal):
    from catboost import CatBoostClassifier
    model = CatBoostClassifier(
        iterations=320,
        depth=5,
        learning_rate=0.045,
        loss_function="Logloss",
        eval_metric="Logloss",
        l2_leaf_reg=5.0,
        random_seed=42,
        thread_count=2,
        verbose=False,
        allow_writing_files=False,
    )
    X_train = _frame(train)
    y_train = [int(r["target"]) for r in train]
    fit_kwargs = {"cat_features": CATEGORICAL_FEATURES}
    if cal:
        fit_kwargs["eval_set"] = (_frame(cal), [int(r["target"]) for r in cal])
        fit_kwargs["early_stopping_rounds"] = 45
        fit_kwargs["use_best_model"] = True
    model.fit(X_train, y_train, **fit_kwargs)
    CACHE.mkdir(parents=True, exist_ok=True)
    model.save_model(str(CAT_MODEL_PATH))
    return model


def _load_catboost():
    from catboost import CatBoostClassifier
    model = CatBoostClassifier()
    model.load_model(str(CAT_MODEL_PATH))
    return model


def _tabpfn_payload(train, cal, val, current):
    # Latest rows are most useful and V2 is intentionally kept under its CPU range.
    train = train[-TABPFN_TRAIN_CAP:]
    current_ranked = sorted(enumerate(current), key=lambda x: _num(x[1].get("base_score"), 0), reverse=True)[:TABPFN_CURRENT_CAP]
    current_idx = [i for i, _ in current_ranked]
    current_rows = [r for _, r in current_ranked]
    return {
        "version": VERSION,
        "train": train,
        "cal": cal,
        "val": val,
        "current": current_rows,
        "current_indices": current_idx,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
    }


def _run_tabpfn(train, cal, val, current, now: datetime):
    runner = ROOT / "backend" / "tabpfn_challenger_v84.py"
    if not runner.exists():
        return {"status": "unavailable", "reason": "runner_missing"}
    payload = _tabpfn_payload(train, cal, val, current)
    _write(TAB_INPUT_PATH, payload)
    try:
        if TAB_OUTPUT_PATH.exists(): TAB_OUTPUT_PATH.unlink()
        env = os.environ.copy()
        env["TABPFN_MODEL_CACHE_DIR"] = str(TAB_MODEL_CACHE)
        env["TABPFN_NO_BROWSER"] = "1"
        proc = subprocess.run(
            [sys.executable, str(runner), str(TAB_INPUT_PATH), str(TAB_OUTPUT_PATH)],
            cwd=ROOT, env=env, capture_output=True, text=True,
            timeout=TABPFN_TIMEOUT_SECONDS, check=False,
        )
        result = _read(TAB_OUTPUT_PATH, {})
        if proc.returncode != 0 or not isinstance(result, dict) or result.get("status") != "ok":
            reason = result.get("reason") if isinstance(result, dict) else None
            return {
                "status": "unavailable", "reason": reason or f"exit_{proc.returncode}",
                "stderr": (proc.stderr or "")[-600:],
            }
        result["trained_at"] = now.isoformat()
        return result
    except subprocess.TimeoutExpired:
        return {"status": "unavailable", "reason": "timeout_cpu_guard"}
    except Exception as exc:
        return {"status": "unavailable", "reason": type(exc).__name__}


def _current_sources(match: dict):
    try:
        try:
            from .specialist_learning_v79b import model_signals, consensus_signals
        except ImportError:
            from specialist_learning_v79b import model_signals, consensus_signals
    except Exception:
        return {}
    grouped = defaultdict(dict)
    for model_id in ("adaptive", "early", "serve", "form", "surface"):
        try:
            signals = model_signals(model_id, match)
        except Exception:
            signals = []
        for s in signals or []:
            s = dict(s)
            s["source_model"] = model_id
            grouped[_candidate_key(s)][model_id] = s
    try:
        cons = consensus_signals(match)
    except Exception:
        cons = []
    for s in cons or []:
        s = dict(s); s["source_model"] = "consensus"
        grouped[_candidate_key(s)]["consensus"] = s
    # v8.4E1: exact top state for Po 2 / Po 4 / Po 6.
    for s in _game_state_current_signals(match):
        s = dict(s); s["source_model"] = "adaptive"
        grouped[_candidate_key(s)].setdefault("adaptive", s)
    return grouped


def build_current_rows(results: list[dict]) -> tuple[list[dict], list[tuple[int, str]]]:
    rows = []
    locs = []
    for mi, match in enumerate(results or []):
        if not isinstance(match, dict) or not match.get("model_ready"):
            continue
        entry = {
            "match_id": match.get("id") or match.get("match_id"),
            "id": match.get("id") or match.get("match_id"),
            "p1": match.get("p1"), "p2": match.get("p2"),
            "scheduled_time": match.get("scheduled_time"),
            "tournament": match.get("tournament"), "tour": match.get("tour"),
            "surface": match.get("surface"), "quality": match.get("quality"),
            "model_confidence": match.get("model_confidence"),
        }
        for key, sources in _current_sources(match).items():
            row = _feature_row(entry, key, sources, None)
            if row:
                rows.append(row); locs.append((mi, key))
    return rows, locs


def _decorate_results(results, current_rows, current_probs, cat_probs, tab_probs, weights,
                      status="COLLECTING", dynamic_telemetry=None):
    per_match = defaultdict(list)
    telemetry = dynamic_telemetry if isinstance(dynamic_telemetry, dict) else {}

    for i, row in enumerate(current_rows):
        tab = tab_probs[i] if i < len(tab_probs) else None
        cat = cat_probs[i] if i < len(cat_probs) else None
        probs = {"current": current_probs[i], "catboost": cat, "tabpfn": tab}
        available_base = {
            name: float(weights.get(name, 0.0))
            for name, probability in probs.items()
            if probability is not None and float(weights.get(name, 0.0)) > 0
        }
        try:
            local_weights, dynamic_policy = _resolve_dynamic_weights(
                available_base, row, telemetry
            )
        except Exception as exc:
            local_weights = available_base
            dynamic_policy = {
                "version": DYNAMIC_WEIGHTS_VERSION,
                "active": False,
                "status": "SAFE_FALLBACK",
                "reason": f"resolver_{type(exc).__name__}",
                "dimensions": [],
                "base_weights": available_base,
                "effective_weights": available_base,
                "max_shift": 0.0,
            }

        ensemble_probability = _dynamic_weighted_probability(probs, local_weights)
        item = {
            "key": row["candidate_key"], "label": row["label"], "market": row["market"],
            "pick": row["pick"], "checkpoint": row.get("checkpoint"),
            "line": None if row["line"] == -1 else row["line"],
            "current": round(current_probs[i] * 100, 1),
            "catboost": round(cat * 100, 1) if cat is not None else None,
            "tabpfn": round(tab * 100, 1) if tab is not None else None,
            "ensemble": round(ensemble_probability * 100, 1),
            "support": int(row["support"]),
            "local_weights": {k: round(float(v), 4) for k, v in local_weights.items()},
            "dynamic_weighting": dynamic_policy,
        }
        per_match[row["match_key"]].append(item)

    out = []
    for match in results or []:
        m = dict(match)
        mk = _match_key({
            "match_id": m.get("id") or m.get("match_id"), "id": m.get("id") or m.get("match_id"),
            "p1": m.get("p1"), "p2": m.get("p2"), "scheduled_time": m.get("scheduled_time"),
            "tournament": m.get("tournament"),
        })
        sigs = sorted(per_match.get(mk, []), key=lambda x: (-float(x.get("ensemble") or 0), x.get("key") or ""))
        active_dynamic = sum(
            1 for x in sigs if ((x.get("dynamic_weighting") or {}).get("active"))
        )
        m["autolearn_v84"] = {
            "version": VERSION,
            "status": status if sigs else "COLLECTING",
            "weights": {k: round(v, 3) for k, v in weights.items()},
            "dynamic_weights": {
                "version": DYNAMIC_WEIGHTS_VERSION,
                "status": "ACTIVE" if active_dynamic else "SAFE_FALLBACK",
                "active_signals": active_dynamic,
                "total_signals": len(sigs),
                "policy": "previous_telemetry_bounded_segment_shrinkage",
            },
            "signals": sigs,
            "by_key": {x["key"]: x for x in sigs},
            "note": "ML rankuje wyłącznie istniejące sygnały/linie; nie tworzy nowych rynków.",
        }
        out.append(m)
    return out


def _summarize_dynamic(decorated_results):
    total = active = 0
    dimensions = defaultdict(int)
    max_shift = 0.0
    for match in decorated_results or []:
        for signal in ((match.get("autolearn_v84") or {}).get("signals") or []):
            total += 1
            policy = signal.get("dynamic_weighting") or {}
            if policy.get("active"):
                active += 1
                max_shift = max(max_shift, _num(policy.get("max_shift"), 0.0) or 0.0)
                for item in policy.get("dimensions") or []:
                    dimension = str(item.get("dimension") or "")
                    if dimension:
                        dimensions[dimension] += 1
    return {
        "version": DYNAMIC_WEIGHTS_VERSION,
        "status": "ACTIVE" if active else "SAFE_FALLBACK",
        "active_signals": active,
        "total_signals": total,
        "active_share": round(active / total, 4) if total else 0.0,
        "max_shift": round(max_shift, 4),
        "dimensions_used": dict(sorted(dimensions.items())),
        "source": "previous_model_telemetry_v84c_snapshot",
        "policy": "bounded_segment_shrinkage_no_model_reenable",
    }


def _capture_frozen(history, decorated_results, now):
    by_key = {}
    for m in decorated_results or []:
        by_key[_match_key({
            "match_id": m.get("id") or m.get("match_id"), "id": m.get("id") or m.get("match_id"),
            "p1": m.get("p1"), "p2": m.get("p2"), "scheduled_time": m.get("scheduled_time"),
            "tournament": m.get("tournament"),
        })] = m
    out = []
    captured = 0
    for entry in history or []:
        e = dict(entry)
        if e.get("autolearn_signals_v84"):
            out.append(e); continue
        if e.get("status") not in ("pending", "upcoming"):
            out.append(e); continue
        # ML is not allowed to create new Live Tennis API settlement work.
        if not (e.get("signals") or e.get("shadow_signals")):
            out.append(e); continue
        scheduled = _dt(e.get("scheduled_time"))
        if scheduled is None or scheduled <= now + timedelta(minutes=CAPTURE_CUTOFF_MINUTES):
            out.append(e); continue
        match = by_key.get(_match_key(e))
        sigs = list(((match or {}).get("autolearn_v84") or {}).get("signals") or [])
        if not sigs:
            out.append(e); continue
        sigs = _select_game_state_tracking_signals(
            sigs, MAX_TRACK_SIGNALS_PER_MATCH
        )
        generator_keys = {
            s["key"] for s in sorted(
                [s for s in sigs if _num(s.get("ensemble"), 0) >= GENERATOR_SELECT_THRESHOLD * 100],
                key=lambda x: -_num(x.get("ensemble"), 0),
            )[:GENERATOR_TOP_PER_MATCH]
        }
        frozen = []
        for s in sigs:
            frozen.append({
                "key": s.get("key"), "label": s.get("label"), "market": s.get("market"),
                "pick": s.get("pick"),
                "checkpoint": s.get("checkpoint") or _game_state_checkpoint(s),
                "line": s.get("line"), "score": s.get("ensemble"),
                "result": "pending", "source_model": "ensemble_v84",
                "game_state_tracking_version": (
                    GAME_STATE_TRACKING_VERSION if _game_state_checkpoint(s) else None
                ),
                "model_scores": {
                    "current": s.get("current"), "catboost": s.get("catboost"),
                    "tabpfn": s.get("tabpfn"), "ensemble": s.get("ensemble"),
                },
                "generator_selected": s.get("key") in generator_keys,
                "dynamic_weighting": s.get("dynamic_weighting") or {
                    "version": DYNAMIC_WEIGHTS_VERSION, "active": False,
                    "status": "SAFE_FALLBACK", "reason": "not_available",
                },
                "local_weights": s.get("local_weights") or {},
                "tracker_version": VERSION,
            })
        if frozen:
            e["autolearn_signals_v84"] = frozen
            e["autolearn_version"] = VERSION
            e["autolearn_captured_at"] = now.isoformat()
            captured += 1
        out.append(e)
    return out, captured


def tracking_stats(history, tracker_version=None):
    model_rows = defaultdict(list)
    generator_rows = []
    for e in history or []:
        for s in unique_signals(e, "autolearn_signals_v84"):
            if tracker_version is not None and str(s.get("tracker_version") or "") != str(tracker_version):
                continue
            if s.get("result") not in ("hit", "miss"):
                continue
            y = 1 if s["result"] == "hit" else 0
            scores = s.get("model_scores") or {}
            for name in ("current", "catboost", "tabpfn", "ensemble"):
                sc = _num(scores.get(name))
                if sc is not None:
                    model_rows[name].append((y, _clamp(sc / 100.0, .01, .99)))
            final = _num((s.get("adaptive_prod_v79") or {}).get("final_score"))
            if final is not None:
                model_rows["adaptive_prod"].append((y, _clamp(final / 100.0, .01, .99)))
            if s.get("generator_selected"):
                sc = _num(scores.get("ensemble"))
                if sc is not None: generator_rows.append((y, _clamp(sc / 100.0, .01, .99)))

    def summarize(pairs, select_threshold=MODEL_SELECT_THRESHOLD):
        if not pairs: return {"n": 0, "brier": None, "log_loss": None, "selected_n": 0, "accuracy": None}
        y = [x[0] for x in pairs]; p = [x[1] for x in pairs]
        chosen = [x for x in pairs if x[1] >= select_threshold]
        return {
            "n": len(pairs), "brier": round(_brier(y, p), 5), "log_loss": round(_logloss(y, p), 5),
            "selected_n": len(chosen),
            "accuracy": round(sum(x[0] for x in chosen) * 100 / len(chosen), 1) if chosen else None,
        }
    out = {name: summarize(rows) for name, rows in model_rows.items()}
    if generator_rows:
        out["generator"] = {
            "n": len(generator_rows), "selected_n": len(generator_rows),
            "accuracy": round(sum(x[0] for x in generator_rows) * 100 / len(generator_rows), 1),
            "brier": round(_brier([x[0] for x in generator_rows], [x[1] for x in generator_rows]), 5),
            "log_loss": round(_logloss([x[0] for x in generator_rows], [x[1] for x in generator_rows]), 5),
        }
    else:
        out["generator"] = {"n": 0, "selected_n": 0, "accuracy": None, "brier": None, "log_loss": None}
    return out


def _state_tab_current(state, current_rows):
    cache = state.get("tabpfn_current") or {}
    out = []
    for r in current_rows:
        value = _num(cache.get(f'{r["match_key"]}::{r["candidate_key"]}'))
        out.append(value if value is not None else None)
    return out


def run(now=None, force_retrain=False, force_tabpfn=False):
    now = now or datetime.now(timezone.utc)
    history = _read(HISTORY_PATH, [])
    results = _read(RESULTS_PATH, [])
    meta = _read(META_PATH, {})
    state = _read(STATE_PATH, {})
    dynamic_telemetry = _read(DYNAMIC_TELEMETRY_PATH, {})
    if not isinstance(history, list): history = []
    if not isinstance(results, list): results = []
    if not isinstance(meta, dict): meta = {}
    if not isinstance(state, dict): state = {}

    train_rows_all = build_training_rows(history)
    train, cal, val = chronological_split(train_rows_all)
    current_rows, _ = build_current_rows(results)
    class_count = len({r.get("target") for r in train})
    enough = len(train_rows_all) >= MIN_TRAIN_ROWS and len({r["match_key"] for r in train_rows_all}) >= MIN_TRAIN_MATCHES and class_count >= 2

    current_calibration_candidate = _fit_current_calibration(train)
    current_calibration = _gate_current_calibration(current_calibration_candidate, cal)
    raw_current_probs = [_raw_prob_from_score(r) for r in current_rows]
    current_probs = [_prob_from_score(r, current_calibration) for r in current_rows]
    cat_probs = [None] * len(current_rows)
    tab_probs = _state_tab_current(state, current_rows)
    previous_validation = state.get("validation") or {}
    previous_tracking = state.get("tracking") or {}
    previous_weights = state.get("weights") or {"current": 1.0}
    validation = previous_validation
    weights = _normalize_weights(previous_weights)
    weight_policy = state.get("weight_policy") or {"status": "bootstrap"}
    cat_status = "collecting"
    tab_status = state.get("tabpfn") or {"status": "unavailable", "reason": "not_run_yet", "model_version": "V2"}
    retrained = False

    if enough:
        due = force_retrain or _model_due(state, len(train_rows_all), now)
        try:
            if due:
                model = _train_catboost(train, cal)
                retrained = True
            else:
                model = _load_catboost()
            cat_status = "active"
            cat_probs = _predict_cat(model, current_rows)
            raw_base_cal = [_raw_prob_from_score(r) for r in cal]
            raw_base_val = [_raw_prob_from_score(r) for r in val]
            base_cal = [_prob_from_score(r, current_calibration) for r in cal]
            base_val = [_prob_from_score(r, current_calibration) for r in val]
            cat_cal = _predict_cat(model, cal)
            cat_val = _predict_cat(model, val)

            run_tab = force_tabpfn or (due and tabpfn_due(now))
            if run_tab:
                tab_result = _run_tabpfn(train, cal, val, current_rows, now)
                tab_status = {
                    "status": tab_result.get("status"), "reason": tab_result.get("reason"),
                    "model_version": "V2", "trained_at": tab_result.get("trained_at"),
                }
                if tab_result.get("status") == "ok":
                    tab_cal = [float(x) for x in tab_result.get("cal_probs") or []]
                    tab_val = [float(x) for x in tab_result.get("val_probs") or []]
                    idxs = tab_result.get("current_indices") or []
                    vals = tab_result.get("current_probs") or []
                    tab_probs = [None] * len(current_rows)
                    for idx, prob in zip(idxs, vals):
                        if 0 <= int(idx) < len(tab_probs): tab_probs[int(idx)] = float(prob)
                    state["tabpfn_current"] = {
                        f'{r["match_key"]}::{r["candidate_key"]}': p
                        for r, p in zip(current_rows, tab_probs) if p is not None
                    }
                    state["tabpfn_trained_at"] = now.isoformat()
                else:
                    tab_cal, tab_val = [], []
            else:
                # Stored challenger forecasts are still useful for unchanged current fixtures,
                # but holdout predictions are not invented on non-retrain runs.
                tab_cal, tab_val = [], []

            probs_cal = {"current": base_cal, "catboost": cat_cal}
            tab_refreshed = len(tab_cal) == len(cal) and bool(cal)
            if tab_refreshed:
                probs_cal["tabpfn"] = tab_cal
            if cal:
                weights, weight_policy = _choose_weights(
                    cal, probs_cal, previous_weights, previous_validation,
                    previous_tracking, tab_refreshed=tab_refreshed,
                    tab_cached_available=any(p is not None for p in tab_probs),
                )
            elif not weights:
                weights = {"current": 1.0}
                weight_policy = {"status": "no_calibration", "allowed": False}

            probs_val = {"current": base_val, "catboost": cat_val}
            if len(tab_val) == len(val) and val:
                probs_val["tabpfn"] = tab_val
            ens_val = ensemble_probs(probs_val, weights, len(val))
            validation = {
                "current": _metrics(val, base_val),
                "current_raw": _metrics(val, raw_base_val),
                "catboost": _metrics(val, cat_val),
                "tabpfn": _metrics(val, tab_val) if len(tab_val) == len(val) and val else (validation.get("tabpfn") or {"n": 0, "selected_n": 0, "accuracy": None, "brier": None, "log_loss": None}),
                "ensemble": _metrics(val, ens_val),
                "validation_matches": len({r["match_key"] for r in val}),
                "calibration_matches": len({r["match_key"] for r in cal}),
                "policy": "chronological_match_grouped_70_15_15_calibration_gate_on_cal",
            }
            if retrained:
                state["catboost_trained_at"] = now.isoformat()
                state["training_rows"] = len(train_rows_all)
        except Exception as exc:
            cat_status = "fallback"
            cat_probs = [None] * len(current_rows)
            weights = {"current": 1.0}
            weight_policy = {"status": "catboost_fallback", "allowed": False}
            state["last_catboost_error"] = type(exc).__name__
    else:
        weights = {"current": 1.0}
        weight_policy = {"status": "collecting", "allowed": False}

    # Ensure missing challenger probabilities do not dilute the available models.
    decorated = _decorate_results(
        results, current_rows, current_probs, cat_probs, tab_probs, weights,
        "ACTIVE" if cat_status == "active" else "COLLECTING",
        dynamic_telemetry=dynamic_telemetry,
    )
    dynamic_summary = _summarize_dynamic(decorated)
    history, captured = _capture_frozen(history, decorated, now)

    # v8.4A.2 zmienia semantykę Current Engine z raw /100 na calibrated probability.
    # Główny tracking nie miesza starych i nowych metod; all-versions zostaje tylko
    # referencją diagnostyczną.
    tracking = tracking_stats(history, tracker_version=VERSION)
    tracking_all_versions = tracking_stats(history)

    report = {
        "version": VERSION,
        "generated_at": now.isoformat(),
        "status": "ACTIVE" if cat_status == "active" else "COLLECTING",
        "models": {
            "current": {"name": "Current Engine", "status": "active"},
            "catboost": {"name": CATBOOST_NAME, "status": cat_status, "retrained": retrained},
            "tabpfn": {"name": TABPFN_NAME, **tab_status},
            "ensemble": {"name": ENSEMBLE_NAME, "status": "active" if cat_status == "active" else "fallback"},
        },
        "training": {
            "rows": len(train_rows_all), "matches": len({r["match_key"] for r in train_rows_all}),
            "train_rows": len(train), "calibration_rows": len(cal), "validation_rows": len(val),
            "minimum_rows": MIN_TRAIN_ROWS, "minimum_matches": MIN_TRAIN_MATCHES,
            "retrain_hours": RETRAIN_HOURS, "retrain_new_rows": RETRAIN_NEW_ROWS,
        },
        "weights": {k: round(float(v), 3) for k, v in weights.items()},
        "weight_policy": weight_policy,
        "dynamic_weights": dynamic_summary,
        "game_state_tracking": {
            "version": GAME_STATE_TRACKING_VERSION,
            "checkpoints": [2, 4, 6],
            "current_signals": sum(
                1 for m in decorated
                for s in ((m.get("autolearn_v84") or {}).get("signals") or [])
                if _game_state_checkpoint(s)
            ),
            "history_learning_signals": sum(
                len(e.get("game_state_learning_v84e1") or []) for e in history
            ),
            "policy": "exact_top_state_hidden_learning_bounded_reservation_pbp_only",
        },
        "current_calibration": current_calibration,
        "validation": validation,
        "tracking": tracking,
        "tracking_all_versions": tracking_all_versions,
        "generator": {
            "selection_threshold": GENERATOR_SELECT_THRESHOLD * 100,
            "policy": "quality_lock_no_forced_fill_v852",
            "logic_guard": "majority_consensus_calibration_gate_weight_cap_v84b",
            "dynamic_weight_guard": "bounded_segment_shrinkage_v84d",
            "market_policy": "existing_signals_and_existing_lines_only",
            "profile_thresholds": {
                "stable": {"strong": 78, "floor": 74, "min_average": 74},
                "balanced": {"strong": 76, "floor": 72, "min_average": 72},
                "strong": {"strong": 84, "floor": 80, "min_average": 80},
                "experimental": {"strong": 68, "floor": 62, "min_average": 62},
            },
            "captured_matches_this_run": captured,
        },
        "notes": [
            "Current Engine /100 jest siłą sygnału; kandydat Platt jest fitowany na TRAIN i dopuszczany wyłącznie przez osobny gate na CAL; VAL pozostaje finalnym holdoutem.",
            "Przy małej liczbie meczów CAL jeden model nie może dostać 100% sterowania Ensemble; działa cap + minimalny głos Current Engine.",
            "CatBoost jest meta-rankerem sygnałów, a nie zamiennikiem tenisowych modeli bazowych.",
            "TabPFN używa wyłącznie jawnie wskazanej wersji V2; nowsze non-commercial checkpointy nie są używane.",
            "Podział walidacyjny jest chronologiczny i grupowany całymi meczami, bez losowego przecieku sygnałów.",
            "Awaria ML przełącza generator na Current Engine; ML nie wykonuje żadnych dodatkowych requestów Live Tennis API.",
            "TabPFN zachowuje ostatnią zatwierdzoną wagę między retrainingami; brak świeżej predykcji dla sygnału nie rozcieńcza Ensemble.",
            "Generator może dobrać graniczny sygnał tylko w obrębie profilu i Marketability Guard; nadal nie wymusza słabych spotkań.",
            "v8.4D koryguje wagi Current/CatBoost/TabPFN per tour/nawierzchnia/rynek wyłącznie z poprzedniego snapshotu telemetryki; mała próbka wraca do wag globalnych.",
        ],
    }

    state.update({
        "version": VERSION, "updated_at": now.isoformat(), "weights": report["weights"],
        "weight_policy": weight_policy, "dynamic_weights": dynamic_summary,
        "current_calibration": current_calibration,
        "validation": validation, "tracking": tracking, "tabpfn": tab_status,
    })
    _write(RESULTS_PATH, decorated)
    _write(HISTORY_PATH, history)
    _write(REPORT_PATH, report)
    _write(STATE_PATH, state)
    meta.update({
        "autolearn_v84_version": VERSION,
        "autolearn_v84_status": report["status"],
        "autolearn_v84_updated_at": now.isoformat(),
        "autolearn_v84_training_rows": len(train_rows_all),
        "autolearn_v84_training_matches": report["training"]["matches"],
        "autolearn_v84_catboost_status": cat_status,
        "autolearn_v84_tabpfn_status": tab_status.get("status"),
        "autolearn_v84_weights": report["weights"],
        "autolearn_v84_weight_policy": weight_policy,
        "autolearn_v84_dynamic_weights": dynamic_summary,
        "autolearn_v84_dynamic_weights_version": DYNAMIC_WEIGHTS_VERSION,
        "autolearn_v84_game_state_tracking": report["game_state_tracking"],
        "autolearn_v84_current_calibration": current_calibration,
        "autolearn_v84_logic_guard": "v8.4B",
    })
    _write(META_PATH, meta)
    return report


def self_check():
    demo = []
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    for i in range(30):
        demo.append({
            "match_key": f"id:{i}", "scheduled_time": (now + timedelta(hours=i)).isoformat(),
            "candidate_key": f"set1_total|8.5|over", "market": "set1_total", "pick": "over",
            "pick_kind": "over", "line": 8.5, "label": "1S O8.5", "tour": "ATP", "surface": "HARD",
            "quality": "good", "model_confidence": 75, "base_score": 72 + (i % 4), "adaptive": 72,
            "early": 74, "serve": 70, "form": 71, "surface_model": 73, "consensus": 75,
            "support": 6, "mean_score": 72.5, "std_score": 2.0, "min_score": 70, "max_score": 75,
            "spread": 5, "consensus_votes": 4, "consensus_strong_votes": 3, "score_band": "72-79",
            "target": 1 if i % 3 else 0,
        })
    tr, cal, val = chronological_split(demo)
    assert set(r["match_key"] for r in tr).isdisjoint(r["match_key"] for r in val)
    assert len(tr) + len(cal) + len(val) == len(demo)
    current_calibration = _fit_current_calibration(tr)
    assert current_calibration.get("fit_scope") == "train_only"
    current_eval = [_prob_from_score(r, current_calibration) for r in (cal or val)]
    assert all(0.01 <= p <= 0.99 for p in current_eval)
    w = _optimize_weights(cal or val, {"current": current_eval, "catboost": [0.7] * len(cal or val)})
    assert abs(sum(w.values()) - 1.0) < 1e-9
    preserved, policy = _choose_weights(
        cal or val,
        {"current": [_prob_from_score(r) for r in (cal or val)], "catboost": [0.7] * len(cal or val)},
        {"current": 0.3, "catboost": 0.6, "tabpfn": 0.1},
        {}, {}, tab_refreshed=False,
    )
    assert abs(preserved.get("tabpfn", 0.0) - 0.1) < 1e-9
    print(json.dumps({"version": VERSION, "self_check": "PASS", "split": [len(tr), len(cal), len(val)], "weights": w, "policy": policy}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tabpfn-due", action="store_true")
    parser.add_argument("--force-retrain", action="store_true")
    parser.add_argument("--force-tabpfn", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.tabpfn_due:
        raise SystemExit(0 if tabpfn_due() else 1)
    if args.self_check:
        self_check(); return
    report = run(force_retrain=args.force_retrain, force_tabpfn=args.force_tabpfn)
    print(json.dumps({
        "version": report["version"], "status": report["status"],
        "training": report["training"], "weights": report["weights"],
        "weight_policy": report.get("weight_policy"),
        "models": report["models"], "generator": report["generator"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
