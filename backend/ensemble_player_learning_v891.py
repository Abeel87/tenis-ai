from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

try:
    from .player_model_shadow_v89 import build_training_rows, _prob, _num, _match_key
except ImportError:
    from player_model_shadow_v89 import build_training_rows, _prob, _num, _match_key

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
RESULTS_PATH = OUT / "results.json"
HISTORY_PATH = OUT / "history.json"
TELEMETRY_PATH = OUT / "model_telemetry_v84c.json"
REPORT_PATH = OUT / "ensemble_player_learning_v891.json"
META_PATH = OUT / "meta.json"

VERSION = "v8.9.1"
MODE = "SHADOW"
SELECT_THRESHOLD = 0.65
MIN_ROWS = 100
MIN_MATCHES = 30
MIN_HOLDOUT_ROWS = 30
MIN_HOLDOUT_MATCHES = 8
ALPHA_GRID = tuple(round(i * 0.025, 3) for i in range(19))  # 0.00 .. 0.45
QUALITY_CAPS = {"HIGH": 0.45, "MEDIUM": 0.32, "LOW": 0.18, "N/D": 0.06}

# Each local estimate is shrunk toward the global alpha. More specific scopes need
# more evidence before they are allowed to move the blend strongly.
SCOPE_CONFIG = (
    ("market", ("market",), 28, 70.0, 1.00),
    ("surface", ("surface",), 32, 85.0, 0.85),
    ("quality", ("pi_quality",), 24, 65.0, 1.00),
    ("market_surface", ("market", "surface"), 42, 110.0, 1.35),
    ("market_quality", ("market", "pi_quality"), 38, 95.0, 1.30),
    ("surface_quality", ("surface", "pi_quality"), 42, 105.0, 1.15),
)


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _brier(y, p):
    if not y or len(y) != len(p):
        return None
    return sum((float(pi) - float(yi)) ** 2 for yi, pi in zip(y, p)) / len(y)


def _logloss(y, p):
    if not y or len(y) != len(p):
        return None
    total = 0.0
    for yi, pi in zip(y, p):
        pi = max(1e-6, min(1 - 1e-6, float(pi)))
        total += -(yi * math.log(pi) + (1 - yi) * math.log(1 - pi))
    return total / len(y)


def _usable(rows):
    out = []
    for row in rows or []:
        if row.get("target") not in (0, 1):
            continue
        if _prob(row.get("ensemble_score")) is None or _prob(row.get("player_probability")) is None:
            continue
        out.append(row)
    return out


def _blend(row: dict, alpha: float) -> float:
    ensemble = _prob(row.get("ensemble_score"))
    player = _prob(row.get("player_probability"))
    if ensemble is None:
        return player if player is not None else 0.5
    if player is None:
        return ensemble
    a = max(0.0, min(0.45, float(alpha)))
    return max(0.01, min(0.99, ensemble * (1.0 - a) + player * a))


def _metrics(rows, probs) -> dict:
    if not rows or len(rows) != len(probs):
        return {"n": 0, "selected_n": 0, "accuracy": None, "brier": None, "log_loss": None}
    y = [int(r["target"]) for r in rows]
    selected = [(yy, pp) for yy, pp in zip(y, probs) if pp >= SELECT_THRESHOLD]
    return {
        "n": len(rows),
        "selected_n": len(selected),
        "accuracy": round(100 * sum(yy for yy, _ in selected) / len(selected), 1) if selected else None,
        "brier": round(_brier(y, probs), 5),
        "log_loss": round(_logloss(y, probs), 5),
        "avg_probability": round(100 * mean(probs), 1) if probs else None,
    }


def _split_by_match(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    grouped = defaultdict(list)
    times = {}
    for row in rows:
        grouped[row["match_key"]].append(row)
        times[row["match_key"]] = str(row.get("scheduled_time") or "")
    keys = sorted(grouped, key=lambda k: (times.get(k, ""), k))
    if len(keys) < 2:
        return rows, []
    cut = max(1, int(len(keys) * 0.80))
    if cut >= len(keys):
        cut = len(keys) - 1
    train_keys = set(keys[:cut])
    holdout_keys = set(keys[cut:])
    return (
        [r for r in rows if r["match_key"] in train_keys],
        [r for r in rows if r["match_key"] in holdout_keys],
    )


def _fit_alpha(rows: list[dict]) -> tuple[float, dict]:
    rows = _usable(rows)
    if not rows:
        return 0.0, {"n": 0, "matches": 0, "brier": None, "log_loss": None}
    y = [int(r["target"]) for r in rows]
    best = None
    for alpha in ALPHA_GRID:
        probs = [_blend(r, alpha) for r in rows]
        brier = _brier(y, probs)
        loss = _logloss(y, probs)
        # Brier is primary. Log-loss breaks ties; then prefer the smaller alpha.
        score = (round(brier, 10), round(loss, 10), alpha)
        if best is None or score < best[0]:
            best = (score, alpha, brier, loss)
    alpha = float(best[1])
    return alpha, {
        "n": len(rows),
        "matches": len({r["match_key"] for r in rows}),
        "brier": round(best[2], 5),
        "log_loss": round(best[3], 5),
    }


def _scope_key(row: dict, fields: tuple[str, ...]) -> str:
    return "||".join(str(row.get(f) or "N/D").upper() for f in fields)


def learn_policy(train_rows: list[dict]) -> dict:
    train_rows = _usable(train_rows)
    global_alpha, global_fit = _fit_alpha(train_rows)
    scopes = {}

    for scope_name, fields, min_n, shrink_n, specificity in SCOPE_CONFIG:
        groups = defaultdict(list)
        for row in train_rows:
            groups[_scope_key(row, fields)].append(row)
        records = {}
        for key, group in groups.items():
            matches = len({r["match_key"] for r in group})
            if len(group) < min_n or matches < 6:
                continue
            raw_alpha, fit = _fit_alpha(group)
            row_rel = len(group) / (len(group) + shrink_n)
            match_rel = matches / (matches + 14.0)
            reliability = math.sqrt(row_rel * match_rel)
            shrunk = global_alpha + reliability * (raw_alpha - global_alpha)
            records[key] = {
                "fields": list(fields),
                "n": len(group),
                "matches": matches,
                "raw_alpha": round(raw_alpha, 4),
                "alpha": round(max(0.0, min(0.45, shrunk)), 4),
                "reliability": round(reliability, 4),
                "specificity_weight": specificity,
                "train_brier_at_raw_alpha": fit.get("brier"),
                "train_log_loss_at_raw_alpha": fit.get("log_loss"),
            }
        scopes[scope_name] = {
            "fields": list(fields),
            "min_n": min_n,
            "shrink_n": shrink_n,
            "specificity_weight": specificity,
            "segments": records,
        }

    return {
        "version": VERSION,
        "method": "hierarchical_segment_blend",
        "train_scope": "chronological_first_80pct_matches_only",
        "global_alpha": round(global_alpha, 4),
        "global_fit": global_fit,
        "quality_caps": QUALITY_CAPS,
        "alpha_grid": list(ALPHA_GRID),
        "scopes": scopes,
    }


def alpha_for_row(row: dict, policy: dict) -> tuple[float, list[dict]]:
    global_alpha = float(policy.get("global_alpha") or 0.0)
    weighted = global_alpha
    total_weight = 1.0
    sources = [{"scope": "global", "alpha": round(global_alpha, 4), "weight": 1.0}]

    config_by_name = {name: (fields, specificity) for name, fields, _, _, specificity in SCOPE_CONFIG}
    for scope_name, scope in (policy.get("scopes") or {}).items():
        if scope_name not in config_by_name:
            continue
        fields, specificity = config_by_name[scope_name]
        key = _scope_key(row, fields)
        rec = (scope.get("segments") or {}).get(key)
        if not rec:
            continue
        reliability = float(rec.get("reliability") or 0.0)
        weight = reliability * float(specificity)
        if weight <= 0:
            continue
        alpha = float(rec.get("alpha") or global_alpha)
        weighted += alpha * weight
        total_weight += weight
        sources.append({
            "scope": scope_name,
            "key": key,
            "alpha": round(alpha, 4),
            "weight": round(weight, 4),
            "n": rec.get("n"),
        })

    alpha = weighted / total_weight if total_weight else global_alpha
    quality = str(row.get("pi_quality") or "N/D").upper()
    cap = float(QUALITY_CAPS.get(quality, QUALITY_CAPS["N/D"]))
    alpha = min(alpha, cap)

    coverage = _num(row.get("feature_coverage"))
    if coverage is not None:
        coverage = max(0.0, min(1.0, coverage))
        alpha *= 0.65 + 0.35 * coverage

    alpha = max(0.0, min(0.45, alpha))
    return alpha, sources


def predict_rows(rows: list[dict], policy: dict) -> tuple[list[dict], list[float], list[float]]:
    usable, probs, alphas = [], [], []
    for row in _usable(rows):
        alpha, _ = alpha_for_row(row, policy)
        usable.append(row)
        alphas.append(alpha)
        probs.append(_blend(row, alpha))
    return usable, probs, alphas


def _field_metrics(rows: list[dict], field: str) -> dict:
    usable, probs = [], []
    for row in rows:
        p = _prob(row.get(field))
        if p is None:
            continue
        usable.append(row)
        probs.append(p)
    return _metrics(usable, probs)


def _baselines(rows: list[dict]) -> dict:
    return {
        "ensemble": _field_metrics(rows, "ensemble_score"),
        "fixed_ensemble_player_formula": _field_metrics(rows, "ensemble_player_shadow"),
        "player_formula": _field_metrics(rows, "player_probability"),
        "catboost": _field_metrics(rows, "catboost_score"),
    }


def _segments(rows: list[dict], probs: list[float], field: str) -> dict:
    grouped = defaultdict(lambda: ([], []))
    for row, prob in zip(rows, probs):
        key = str(row.get(field) or "N/D").upper()
        grouped[key][0].append(row)
        grouped[key][1].append(prob)
    return {key: _metrics(pair[0], pair[1]) for key, pair in grouped.items() if len(pair[0]) >= 5}


def _gate(candidate: dict, baselines: dict, holdout_matches: int) -> dict:
    fixed = baselines.get("fixed_ensemble_player_formula") or {}
    ensemble = baselines.get("ensemble") or {}
    reference_name = "fixed_ensemble_player_formula" if fixed.get("brier") is not None else "ensemble"
    reference = fixed if reference_name.startswith("fixed") else ensemble

    if candidate.get("n", 0) < 50 or holdout_matches < 12 or reference.get("brier") is None:
        return {
            "status": "collecting",
            "production_influence": False,
            "auto_promotion": False,
            "comparison_baseline": reference_name,
            "reason": "need_more_holdout_data",
        }

    cb, rb = candidate.get("brier"), reference.get("brier")
    cl, rl = candidate.get("log_loss"), reference.get("log_loss")
    ca, ra = candidate.get("accuracy"), reference.get("accuracy")
    brier_gain = None if cb is None or rb is None else rb - cb
    loss_gain = None if cl is None or rl is None else rl - cl
    acc_delta = None if ca is None or ra is None else ca - ra

    promising = (
        brier_gain is not None and brier_gain >= 0.001
        and loss_gain is not None and loss_gain >= -0.002
        and (acc_delta is None or acc_delta >= -1.0)
    )
    strong = (
        promising
        and brier_gain is not None and brier_gain >= 0.003
        and loss_gain is not None and loss_gain >= 0.002
        and (acc_delta is None or acc_delta >= 0.0)
    )
    return {
        "status": "strong_candidate" if strong else ("promising" if promising else "watch"),
        "production_influence": False,
        "auto_promotion": False,
        "comparison_baseline": reference_name,
        "brier_gain": round(brier_gain, 5) if brier_gain is not None else None,
        "log_loss_gain": round(loss_gain, 5) if loss_gain is not None else None,
        "accuracy_delta_pp": round(acc_delta, 1) if acc_delta is not None else None,
        "reason": "shadow_only_manual_gate",
    }


def _current_context(match: dict, signal: dict) -> dict | None:
    pi = signal.get("player_intelligence_v85") or {}
    player = _num(pi.get("probability"))
    ensemble = _num(pi.get("ensemble_base"))
    if player is None or ensemble is None:
        return None
    features = signal.get("player_model_features_v89") or {}
    return {
        "market": str(signal.get("market") or "other").lower(),
        "surface": str(match.get("surface") or "N/D").upper(),
        "tour": str(match.get("tour") or "N/D").upper(),
        "pi_quality": str(pi.get("quality") or features.get("pi_quality") or "N/D").upper(),
        "feature_coverage": _num(features.get("feature_coverage"), 0.0),
        "ensemble_score": ensemble,
        "player_probability": player,
    }


def decorate_current(results: list[dict], policy: dict) -> tuple[list[dict], int]:
    out = []
    scored = 0
    for m0 in results or []:
        m = dict(m0)
        auto = dict(m.get("autolearn_v84") or {})
        signals = [dict(s) for s in (auto.get("signals") or [])]
        for signal in signals:
            row = _current_context(m, signal)
            if not row:
                continue
            alpha, sources = alpha_for_row(row, policy)
            ensemble = _prob(row.get("ensemble_score"))
            player = _prob(row.get("player_probability"))
            learned = _blend(row, alpha)
            signal["ensemble_player_learning_v891"] = {
                "version": VERSION,
                "mode": MODE,
                "score": round(learned * 100, 1),
                "alpha_player": round(alpha, 4),
                "alpha_ensemble": round(1.0 - alpha, 4),
                "ensemble_base": round(ensemble * 100, 1) if ensemble is not None else None,
                "player_probability": round(player * 100, 1) if player is not None else None,
                "delta_vs_ensemble_pp": round((learned - ensemble) * 100, 1) if ensemble is not None else None,
                "quality": row.get("pi_quality"),
                "policy_sources": sources[:7],
                "production_influence": False,
            }
            scored += 1
        auto["signals"] = signals
        auto["by_key"] = {str(s.get("key")): s for s in signals if s.get("key")}
        m["autolearn_v84"] = auto
        if scored:
            m["ensemble_player_learning_v891"] = {
                "version": VERSION,
                "mode": MODE,
                "production_influence": False,
            }
        out.append(m)
    return out, scored


def run(now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    results = _read(RESULTS_PATH, [])
    history = _read(HISTORY_PATH, [])
    telemetry = _read(TELEMETRY_PATH, {})
    meta = _read(META_PATH, {})
    if not isinstance(results, list): results = []
    if not isinstance(history, list): history = []
    if not isinstance(telemetry, dict): telemetry = {}
    if not isinstance(meta, dict): meta = {}

    rows = _usable(build_training_rows(history))
    train, holdout = _split_by_match(rows)
    train_matches = len({r["match_key"] for r in train})
    holdout_matches = len({r["match_key"] for r in holdout})
    enough = (
        len(train) >= MIN_ROWS
        and train_matches >= MIN_MATCHES
        and len(holdout) >= MIN_HOLDOUT_ROWS
        and holdout_matches >= MIN_HOLDOUT_MATCHES
    )

    policy = learn_policy(train) if train else learn_policy([])
    learned_metrics = {"n": 0, "selected_n": 0, "accuracy": None, "brier": None, "log_loss": None}
    baselines = _baselines(holdout)
    segments = {"market": {}, "surface": {}, "quality": {}}
    alpha_summary = {"avg": None, "min": None, "max": None}
    gate = {
        "status": "collecting",
        "production_influence": False,
        "auto_promotion": False,
        "reason": "minimum_training_sample_not_reached",
    }
    current_scored = 0

    if enough:
        usable_holdout, learned_probs, holdout_alphas = predict_rows(holdout, policy)
        learned_metrics = _metrics(usable_holdout, learned_probs)
        segments = {
            "market": _segments(usable_holdout, learned_probs, "market"),
            "surface": _segments(usable_holdout, learned_probs, "surface"),
            "quality": _segments(usable_holdout, learned_probs, "pi_quality"),
        }
        if holdout_alphas:
            alpha_summary = {
                "avg": round(mean(holdout_alphas), 4),
                "min": round(min(holdout_alphas), 4),
                "max": round(max(holdout_alphas), 4),
            }
        gate = _gate(learned_metrics, baselines, holdout_matches)
        full_policy = learn_policy(rows)
        results, current_scored = decorate_current(results, full_policy)
    else:
        full_policy = policy

    report = {
        "version": VERSION,
        "generated_at": now.isoformat(),
        "mode": MODE,
        "status": "ACTIVE_SHADOW" if enough else "COLLECTING",
        "production_influence": False,
        "auto_promotion": False,
        "training": {
            "rows_total": len(rows),
            "matches_total": len({r["match_key"] for r in rows}),
            "train_rows": len(train),
            "train_matches": train_matches,
            "holdout_rows": len(holdout),
            "holdout_matches": holdout_matches,
            "chronological_match_split": "80/20",
            "leakage_policy": "policy_fit_train_only_holdout_untouched",
        },
        "policy": policy,
        "full_runtime_policy": full_policy,
        "holdout": {
            "ensemble_player_learning": learned_metrics,
            "baselines": baselines,
            "alpha_summary": alpha_summary,
            "segments": segments,
        },
        "gate": gate,
        "current_scored_signals": current_scored,
        "note": (
            "Ensemble + Player Learning uczy udziału Player Intelligence z historii, rynku, nawierzchni i jakości profilu. "
            "Działa wyłącznie w SHADOW i nie zmienia Ensemble, Generatora, Adaptive PROD ani final_score."
        ),
    }

    telemetry["ensemble_player_learning_v891"] = report
    meta.update({
        "ensemble_player_learning_v891_version": VERSION,
        "ensemble_player_learning_v891_mode": MODE,
        "ensemble_player_learning_v891_status": report["status"],
        "ensemble_player_learning_v891_training_rows": len(rows),
        "ensemble_player_learning_v891_holdout_rows": len(holdout),
        "ensemble_player_learning_v891_current_scored": current_scored,
        "ensemble_player_learning_v891_production_influence": False,
        "ensemble_player_learning_v891_updated_at": now.isoformat(),
    })

    _write(RESULTS_PATH, results)
    _write(REPORT_PATH, report)
    _write(TELEMETRY_PATH, telemetry)
    _write(META_PATH, meta)
    return {
        "status": report["status"],
        "training_rows": len(rows),
        "holdout_rows": len(holdout),
        "global_alpha": policy.get("global_alpha"),
        "holdout_accuracy": learned_metrics.get("accuracy"),
        "holdout_brier": learned_metrics.get("brier"),
        "gate": gate.get("status"),
        "current_scored": current_scored,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
