from __future__ import annotations

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

VERSION = "v8.4A"
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
TABPFN_TRAIN_CAP = 300
TABPFN_CURRENT_CAP = 300
TABPFN_TIMEOUT_SECONDS = 150

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
    for signal in entry.get("signals") or []:
        if not isinstance(signal, dict):
            continue
        src = str(signal.get("source_model") or "adaptive")
        if src == "legacy": src = "adaptive"
        grouped[_candidate_key(signal)][src] = signal
    for signal in entry.get("learning_signals_v79b") or []:
        if not isinstance(signal, dict):
            continue
        src = str(signal.get("source_model") or "specialist")
        grouped[_candidate_key(signal)][src] = signal
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


def _prob_from_score(row):
    return _clamp(_num(row.get("base_score"), 50.0) / 100.0, 0.01, 0.99)


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


def _decorate_results(results, current_rows, current_probs, cat_probs, tab_probs, weights, status="COLLECTING"):
    per_match = defaultdict(list)
    ensemble = ensemble_probs({"current": current_probs, "catboost": cat_probs, "tabpfn": tab_probs}, weights, len(current_rows))
    for i, row in enumerate(current_rows):
        tab = tab_probs[i] if i < len(tab_probs) else None
        cat = cat_probs[i] if i < len(cat_probs) else None
        item = {
            "key": row["candidate_key"], "label": row["label"], "market": row["market"],
            "pick": row["pick"], "line": None if row["line"] == -1 else row["line"],
            "current": round(current_probs[i] * 100, 1),
            "catboost": round(cat * 100, 1) if cat is not None else None,
            "tabpfn": round(tab * 100, 1) if tab is not None else None,
            "ensemble": round(ensemble[i] * 100, 1),
            "support": int(row["support"]),
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
        m["autolearn_v84"] = {
            "version": VERSION,
            "status": status if sigs else "COLLECTING",
            "weights": {k: round(v, 3) for k, v in weights.items()},
            "signals": sigs,
            "by_key": {x["key"]: x for x in sigs},
            "note": "ML rankuje wyłącznie istniejące sygnały/linie; nie tworzy nowych rynków.",
        }
        out.append(m)
    return out


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
        sigs = [s for s in sigs if _num(s.get("ensemble"), 0) >= 55.0][:MAX_TRACK_SIGNALS_PER_MATCH]
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
                "pick": s.get("pick"), "line": s.get("line"), "score": s.get("ensemble"),
                "result": "pending", "source_model": "ensemble_v84",
                "model_scores": {
                    "current": s.get("current"), "catboost": s.get("catboost"),
                    "tabpfn": s.get("tabpfn"), "ensemble": s.get("ensemble"),
                },
                "generator_selected": s.get("key") in generator_keys,
                "tracker_version": VERSION,
            })
        if frozen:
            e["autolearn_signals_v84"] = frozen
            e["autolearn_version"] = VERSION
            e["autolearn_captured_at"] = now.isoformat()
            captured += 1
        out.append(e)
    return out, captured


def tracking_stats(history):
    model_rows = defaultdict(list)
    generator_rows = []
    for e in history or []:
        for s in e.get("autolearn_signals_v84") or []:
            if s.get("result") not in ("hit", "miss"):
                continue
            y = 1 if s["result"] == "hit" else 0
            scores = s.get("model_scores") or {}
            for name in ("current", "catboost", "tabpfn", "ensemble"):
                sc = _num(scores.get(name))
                if sc is not None:
                    model_rows[name].append((y, _clamp(sc / 100.0, .01, .99)))
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
    return [(_num(cache.get(f'{r["match_key"]}::{r["candidate_key"]}')) or None) for r in current_rows]


def run(now=None, force_retrain=False, force_tabpfn=False):
    now = now or datetime.now(timezone.utc)
    history = _read(HISTORY_PATH, [])
    results = _read(RESULTS_PATH, [])
    meta = _read(META_PATH, {})
    state = _read(STATE_PATH, {})
    if not isinstance(history, list): history = []
    if not isinstance(results, list): results = []
    if not isinstance(meta, dict): meta = {}
    if not isinstance(state, dict): state = {}

    train_rows_all = build_training_rows(history)
    train, cal, val = chronological_split(train_rows_all)
    current_rows, _ = build_current_rows(results)
    class_count = len({r.get("target") for r in train})
    enough = len(train_rows_all) >= MIN_TRAIN_ROWS and len({r["match_key"] for r in train_rows_all}) >= MIN_TRAIN_MATCHES and class_count >= 2

    current_probs = [_prob_from_score(r) for r in current_rows]
    cat_probs = [None] * len(current_rows)
    tab_probs = _state_tab_current(state, current_rows)
    validation = state.get("validation") or {}
    weights = state.get("weights") or {"current": 1.0}
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
            base_cal = [_prob_from_score(r) for r in cal]
            base_val = [_prob_from_score(r) for r in val]
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
            if len(tab_cal) == len(cal) and cal:
                probs_cal["tabpfn"] = tab_cal
            if cal:
                weights = _optimize_weights(cal, probs_cal)
            elif not weights:
                weights = {"current": 1.0}

            probs_val = {"current": base_val, "catboost": cat_val}
            if len(tab_val) == len(val) and val:
                probs_val["tabpfn"] = tab_val
            ens_val = ensemble_probs(probs_val, weights, len(val))
            validation = {
                "current": _metrics(val, base_val),
                "catboost": _metrics(val, cat_val),
                "tabpfn": _metrics(val, tab_val) if len(tab_val) == len(val) and val else (validation.get("tabpfn") or {"n": 0, "selected_n": 0, "accuracy": None, "brier": None, "log_loss": None}),
                "ensemble": _metrics(val, ens_val),
                "validation_matches": len({r["match_key"] for r in val}),
                "calibration_matches": len({r["match_key"] for r in cal}),
                "policy": "chronological_match_grouped_70_15_15",
            }
            if retrained:
                state["catboost_trained_at"] = now.isoformat()
                state["training_rows"] = len(train_rows_all)
        except Exception as exc:
            cat_status = "fallback"
            cat_probs = [None] * len(current_rows)
            weights = {"current": 1.0}
            state["last_catboost_error"] = type(exc).__name__
    else:
        weights = {"current": 1.0}

    # Ensure missing challenger probabilities do not dilute the available models.
    decorated = _decorate_results(results, current_rows, current_probs, cat_probs, tab_probs, weights, "ACTIVE" if cat_status == "active" else "COLLECTING")
    history, captured = _capture_frozen(history, decorated, now)
    tracking = tracking_stats(history)

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
        "validation": validation,
        "tracking": tracking,
        "generator": {
            "selection_threshold": GENERATOR_SELECT_THRESHOLD * 100,
            "policy": "quality_first_no_forced_fill",
            "market_policy": "existing_signals_and_existing_lines_only",
            "captured_matches_this_run": captured,
        },
        "notes": [
            "CatBoost jest meta-rankerem sygnałów, a nie zamiennikiem tenisowych modeli bazowych.",
            "TabPFN używa wyłącznie jawnie wskazanej wersji V2; nowsze non-commercial checkpointy nie są używane.",
            "Podział walidacyjny jest chronologiczny i grupowany całymi meczami, bez losowego przecieku sygnałów.",
            "Awaria ML przełącza generator na Current Engine; ML nie wykonuje żadnych dodatkowych requestów Live Tennis API.",
        ],
    }

    state.update({
        "version": VERSION, "updated_at": now.isoformat(), "weights": report["weights"],
        "validation": validation, "tabpfn": tab_status,
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
    w = _optimize_weights(cal or val, {"current": [_prob_from_score(r) for r in (cal or val)], "catboost": [0.7] * len(cal or val)})
    assert abs(sum(w.values()) - 1.0) < 1e-9
    print(json.dumps({"version": VERSION, "self_check": "PASS", "split": [len(tr), len(cal), len(val)], "weights": w}, indent=2))


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
        "models": report["models"], "generator": report["generator"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
