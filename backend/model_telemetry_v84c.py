from __future__ import annotations

try:
    from .history_sampling import unique_signals
except ImportError:
    from history_sampling import unique_signals

import argparse
import json
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
HISTORY_PATH = OUT / "history.json"
REPORT_PATH = OUT / "model_telemetry_v84c.json"
META_PATH = OUT / "meta.json"

VERSION = "v8.4C"
SELECT_THRESHOLD = 65.0
MIN_SEGMENT_SAMPLE = 5

TREND_VERSION = "v8.4E2"
TREND_COMPARE_MIN = 8
TREND_COMPARE_MAX = 20
TREND_SERIES_WINDOW = 8
TREND_SERIES_POINTS = 24

MODEL_LABELS = {
    "adaptive": "Adaptive",
    "early": "Early Hold",
    "serve": "Serve/Return",
    "form": "Form",
    "surface": "Surface",
    "consensus": "Consensus",
    "current": "Current Engine",
    "catboost": "CatBoost",
    "tabpfn": "TabPFN-2",
    "ensemble": "RAW Ensemble",
    "adaptive_prod": "FINAL Adaptive PROD",
    "dynamic": "Dynamic Ensemble v8.4D",
    "generator": "Ensemble selector proxy",
}
MODEL_ORDER = list(MODEL_LABELS)
PROD_DYNAMIC_MODELS = {"current", "catboost", "tabpfn"}
# PROD telemetry must never mix scoring semantics from older AutoLearn trackers.
# v8.4B is the current frozen-snapshot regime (calibrated Current / bounded ensemble).
AUTOLEARN_TRACKER_VERSION = "v8.4B"


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


def _dt(value):
    try:
        d = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _clamp(value, lo=0.01, hi=0.99):
    return max(lo, min(hi, float(value)))


def _norm_text(value) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()
    return "_".join(re.sub(r"[^a-z0-9.]+", " ", value).split())


def _key(signal: dict) -> str:
    market = str(signal.get("market") or "other").lower()
    market = {
        "match_win": "match_winner",
        "set1_win": "set1_winner",
        "set2_win": "set2_winner",
        "set3_win": "set3_winner",
    }.get(market, market)
    pick = _norm_text(signal.get("pick"))
    line = _num(signal.get("line"))
    checkpoint = signal.get("checkpoint")
    if market in ("set1_total", "match_total"):
        return f"{market}|{line:.1f}|{pick}" if line is not None else f"{market}|?|{pick}"
    if market == "game_state":
        return f"game_state|{checkpoint if checkpoint is not None else '?'}|{pick}"
    return f"{market}|{pick}"


def _score(signal: dict):
    for name in ("score", "value", "v"):
        value = _num(signal.get(name))
        if value is not None:
            return max(1.0, min(99.0, value))
    return None


def _odds(signal: dict):
    for name in ("odds", "decimal_odds", "price"):
        value = _num(signal.get(name))
        if value is not None and value > 1.0:
            return value
    return None


def _checkpoint(signal: dict):
    value = signal.get("checkpoint")
    if value is None:
        market = str(signal.get("market") or "").lower()
        if market.startswith("state") and market != "game_state":
            value = market.replace("state", "", 1)
    if value is None:
        parts = str(signal.get("key") or signal.get("signal_key") or "").split("|")
        if len(parts) >= 2 and parts[0] in ("state", "game_state"):
            value = parts[1]
    try:
        cp = int(value)
    except (TypeError, ValueError):
        return None
    return cp if cp in (2, 4, 6) else None


def _row(entry: dict, signal: dict, model: str, score=None, generator_selected=False):
    result = str(signal.get("result") or "")
    if result not in ("hit", "miss"):
        return None
    sc = _num(score if score is not None else _score(signal))
    if sc is None:
        return None
    return {
        "match_key": str(entry.get("match_key") or entry.get("match_id") or ""),
        "scheduled_time": entry.get("scheduled_time"),
        "autolearn_captured_at": entry.get("autolearn_captured_at"),
        "tracker_version": signal.get("tracker_version"),
        "tour": str(entry.get("tour") or "N/D").upper(),
        "surface": str(entry.get("surface") or "N/D").upper(),
        "market": str(signal.get("market") or "other").lower(),
        "candidate_key": _key(signal),
        "model": model,
        "score": max(1.0, min(99.0, sc)),
        "target": 1 if result == "hit" else 0,
        "odds": _odds(signal),
        "generator_selected": bool(generator_selected),
        "checkpoint": _checkpoint(signal),
    }


def collect_rows(history: list[dict]) -> list[dict]:
    rows = []
    seen = set()

    def add(row):
        if not row:
            return
        sig = (row["match_key"], row["model"], row["candidate_key"], row["target"])
        if sig in seen:
            return
        seen.add(sig)
        rows.append(row)

    for entry in history or []:
        if not isinstance(entry, dict) or entry.get("status") not in ("settled", "void"):
            continue

        for signal in unique_signals(entry, "signals"):
            if not isinstance(signal, dict):
                continue
            src = str(signal.get("source_model") or "adaptive").lower()
            if src in ("legacy", "adaptive"):
                add(_row(entry, signal, "adaptive"))

        for signal in unique_signals(entry, "learning_signals_v79b"):
            if not isinstance(signal, dict):
                continue
            src = str(signal.get("source_model") or "").lower()
            if src in ("early", "serve", "form", "surface", "consensus", "adaptive"):
                add(_row(entry, signal, src))

        for signal in unique_signals(entry, "autolearn_signals_v84"):
            if not isinstance(signal, dict):
                continue
            if str(signal.get("result") or "") not in ("hit", "miss"):
                continue
            scores = signal.get("model_scores") or {}
            for model in ("current", "catboost", "tabpfn", "ensemble"):
                sc = _num(scores.get(model))
                if sc is not None:
                    add(_row(entry, signal, model, score=sc))
            prod = signal.get("adaptive_prod_v79") or {}
            final = _num(prod.get("final_score"))
            if final is not None:
                add(_row(entry, signal, "adaptive_prod", score=final))
            dyn = signal.get("dynamic_weighting") or {}
            if dyn.get("active"):
                sc = _num(scores.get("ensemble"))
                if sc is not None:
                    add(_row(entry, signal, "dynamic", score=sc))
            if signal.get("generator_selected"):
                sc = _num(scores.get("ensemble"))
                if sc is not None:
                    add(_row(entry, signal, "generator", score=sc, generator_selected=True))

    rows.sort(key=lambda r: (str(r.get("scheduled_time") or ""), r["match_key"], r["model"], r["candidate_key"]))
    return rows


def _brier(rows):
    if not rows:
        return None
    return sum((_clamp(r["score"] / 100.0) - r["target"]) ** 2 for r in rows) / len(rows)


def _logloss(rows):
    if not rows:
        return None
    total = 0.0
    for r in rows:
        p = _clamp(r["score"] / 100.0)
        y = r["target"]
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / len(rows)


def summarize(rows: list[dict], model=None) -> dict:
    selected = list(rows) if model == "generator" else [r for r in rows if r["score"] >= SELECT_THRESHOLD]
    hits = sum(r["target"] for r in selected)
    misses = len(selected) - hits
    all_hits = sum(r["target"] for r in rows)
    odds_rows = [r for r in selected if _num(r.get("odds")) is not None and r["odds"] > 1.0]
    profit = sum((r["odds"] - 1.0) if r["target"] else -1.0 for r in odds_rows)
    return {
        "n": len(rows),
        "selected_n": len(selected),
        "hits": hits,
        "misses": misses,
        "accuracy": round(hits * 100.0 / len(selected), 1) if selected else None,
        "all_accuracy": round(all_hits * 100.0 / len(rows), 1) if rows else None,
        "avg_score": round(sum(r["score"] for r in rows) / len(rows), 1) if rows else None,
        "brier": round(_brier(rows), 5) if rows else None,
        "log_loss": round(_logloss(rows), 5) if rows else None,
        "odds_n": len(odds_rows),
        "roi": round(profit * 100.0 / len(odds_rows), 1) if odds_rows else None,
        "roi_status": "available" if odds_rows else "N/D — brak zapisanych kursów",
        "threshold": None if model == "generator" else SELECT_THRESHOLD,
    }


def _selected_for_trend(rows: list[dict], model=None) -> list[dict]:
    ordered = sorted(
        list(rows or []),
        key=lambda r: (str(r.get("scheduled_time") or ""), str(r.get("match_key") or ""), str(r.get("candidate_key") or "")),
    )
    if model == "generator":
        return ordered
    return [r for r in ordered if _num(r.get("score"), 0.0) >= SELECT_THRESHOLD]


def _trend_series(selected: list[dict]) -> list[dict]:
    n = len(selected)
    if n < 5:
        return []
    window = min(TREND_SERIES_WINDOW, n)
    start = max(window, n - TREND_SERIES_POINTS + 1)
    out = []
    for end in range(start, n + 1):
        sample = selected[end - window:end]
        hits = sum(int(r.get("target") or 0) for r in sample)
        out.append({
            "index": end,
            "at": sample[-1].get("scheduled_time"),
            "n": len(sample),
            "accuracy": round(hits * 100.0 / len(sample), 1),
            "brier": round(_brier(sample), 5),
        })
    return out[-TREND_SERIES_POINTS:]


def trend_summary(rows: list[dict], model=None) -> dict:
    selected = _selected_for_trend(rows, model=model)
    n = len(selected)
    base = {
        "version": TREND_VERSION,
        "status": "collecting",
        "selected_n": n,
        "compare_window": 0,
        "recent_accuracy": None,
        "previous_accuracy": None,
        "accuracy_delta_pp": None,
        "recent_brier": None,
        "previous_brier": None,
        "brier_delta": None,
        "sample_strength": "collecting",
        "series": _trend_series(selected),
    }
    half = min(TREND_COMPARE_MAX, n // 2)
    if half < TREND_COMPARE_MIN:
        return base

    previous = selected[-2 * half:-half]
    recent = selected[-half:]
    prev_hits = sum(int(r.get("target") or 0) for r in previous)
    recent_hits = sum(int(r.get("target") or 0) for r in recent)
    prev_acc = prev_hits * 100.0 / len(previous)
    recent_acc = recent_hits * 100.0 / len(recent)
    prev_brier = _brier(previous)
    recent_brier = _brier(recent)
    acc_delta = recent_acc - prev_acc
    brier_delta = recent_brier - prev_brier

    if (acc_delta >= 4.0 and brier_delta <= 0.012) or (brier_delta <= -0.020 and acc_delta >= -2.0):
        status = "rising"
    elif (acc_delta <= -4.0 and brier_delta >= -0.012) or (brier_delta >= 0.020 and acc_delta <= 2.0):
        status = "falling"
    elif abs(acc_delta) < 4.0 and abs(brier_delta) < 0.020:
        status = "stable"
    else:
        status = "watch"

    return {
        **base,
        "status": status,
        "compare_window": half,
        "recent_accuracy": round(recent_acc, 1),
        "previous_accuracy": round(prev_acc, 1),
        "accuracy_delta_pp": round(acc_delta, 1),
        "recent_brier": round(recent_brier, 5),
        "previous_brier": round(prev_brier, 5),
        "brier_delta": round(brier_delta, 5),
        "sample_strength": "strong" if half >= 15 else "medium",
    }


QUALITY_LOCK_V852_CUTOVER = datetime(2026, 8, 25, 9, 55, 27, tzinfo=timezone.utc)
QUALITY_LOCK_MODELS = ("current", "catboost", "tabpfn", "ensemble", "generator")


def build_quality_lock_v852(rows: list[dict]) -> dict:
    grouped = defaultdict(list)
    for r in rows or []:
        grouped[str(r.get("model") or "")].append(r)

    out = {"cutover": "2026-08-25T09:55:27Z"}
    for model in QUALITY_LOCK_MODELS:
        m_rows = grouped.get(model, [])
        if model == "generator":
            sel_rows = list(m_rows)
        else:
            sel_rows = [r for r in m_rows if _num(r.get("score"), 0.0) >= SELECT_THRESHOLD]

        before = []
        since = []
        unknown_n = 0
        for r in sel_rows:
            cap = r.get("autolearn_captured_at")
            d = _dt(cap) if cap else None
            if d is None:
                unknown_n += 1
            elif d < QUALITY_LOCK_V852_CUTOVER:
                before.append(r)
            else:
                since.append(r)

        def _sec(sub_rows):
            n = len(sub_rows)
            if n == 0:
                return {"selected_n": 0, "accuracy": None, "brier": None}
            hits = sum(r["target"] for r in sub_rows)
            return {
                "selected_n": n,
                "accuracy": round(hits * 100.0 / n, 1),
                "brier": round(_brier(sub_rows), 5),
            }

        out[model] = {
            "before_v852": _sec(before),
            "since_v852": _sec(since),
            "unknown_capture_time_n": unknown_n,
        }
    return out


def model_trends(rows: list[dict]) -> dict:
    grouped = defaultdict(list)
    for row in rows or []:
        grouped[str(row.get("model") or "")].append(row)
    return {
        "version": TREND_VERSION,
        "basis": "last_settled_selected_predictions",
        "compare_min_each_side": TREND_COMPARE_MIN,
        "compare_max_each_side": TREND_COMPARE_MAX,
        "models": {
            model: trend_summary(grouped.get(model, []), model=model)
            for model in MODEL_ORDER
        },
        "quality_lock_v852": build_quality_lock_v852(rows),
    }


def game_state_progress(history: list[dict]) -> dict:
    buckets = {cp: {"tracked": 0, "settled": 0, "hits": 0, "misses": 0, "void": 0, "rows": []} for cp in (2, 4, 6)}
    seen = set()

    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        match_key = str(entry.get("match_key") or entry.get("match_id") or entry.get("id") or "")
        hidden = [s for s in (entry.get("game_state_learning_v84e1") or []) if isinstance(s, dict)]
        source = hidden
        if not source:
            source = [
                s for s in (unique_signals(entry, "autolearn_signals_v84"))
                if isinstance(s, dict) and _checkpoint(s) in (2, 4, 6)
            ]

        for signal in source:
            cp = _checkpoint(signal)
            if cp not in buckets:
                continue
            sig_id = (match_key, cp)
            if sig_id in seen:
                continue
            seen.add(sig_id)
            b = buckets[cp]
            b["tracked"] += 1
            result = str(signal.get("result") or "").lower()
            if result in ("hit", "miss"):
                b["settled"] += 1
                b["hits"] += int(result == "hit")
                b["misses"] += int(result == "miss")
                score = _score(signal)
                b["rows"].append({
                    "scheduled_time": entry.get("scheduled_time"),
                    "score": score if score is not None else 65.0,
                    "target": 1 if result == "hit" else 0,
                    "model": "generator",
                    "match_key": match_key,
                    "candidate_key": f"game_state|{cp}",
                    "market": "game_state",
                    "tour": str(entry.get("tour") or "N/D").upper(),
                    "surface": str(entry.get("surface") or "N/D").upper(),
                    "odds": None,
                    "checkpoint": cp,
                })
            elif result == "void":
                b["void"] += 1

    checkpoints = {}
    for cp, b in buckets.items():
        settled = b["settled"]
        checkpoints[str(cp)] = {
            "tracked": b["tracked"],
            "settled": settled,
            "hits": b["hits"],
            "misses": b["misses"],
            "void": b["void"],
            "waiting_pbp": max(0, b["tracked"] - settled - b["void"]),
            "accuracy": round(b["hits"] * 100.0 / settled, 1) if settled else None,
            "trend": trend_summary(b["rows"], model="generator"),
        }

    return {
        "version": TREND_VERSION,
        "policy": "exact_checkpoint_pbp_only_monitoring",
        "total_tracked": sum(x["tracked"] for x in checkpoints.values()),
        "total_settled": sum(x["settled"] for x in checkpoints.values()),
        "checkpoints": checkpoints,
    }


def _scope_rows(rows: list[dict], now: datetime, days=None):
    if days is None:
        return list(rows)
    cutoff = now - timedelta(days=days)
    out = []
    for r in rows:
        d = _dt(r.get("scheduled_time"))
        if d is not None and cutoff <= d <= now + timedelta(days=1):
            out.append(r)
    return out


def _prod_safe_dynamic_rows(rows: list[dict]) -> list[dict]:
    """Only current-regime, prediction-time-verifiable ML rows may influence PROD weights."""
    out = []
    for row in rows or []:
        if str(row.get("model") or "") not in PROD_DYNAMIC_MODELS:
            continue
        if str(row.get("tracker_version") or "") != AUTOLEARN_TRACKER_VERSION:
            continue
        scheduled = _dt(row.get("scheduled_time"))
        captured = _dt(row.get("autolearn_captured_at"))
        if scheduled is None or captured is None or captured >= scheduled:
            continue
        out.append(row)
    return out


def model_metrics(rows: list[dict]) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["model"]].append(row)
    return {
        model: {
            "label": MODEL_LABELS[model],
            **summarize(grouped.get(model, []), model=model),
        }
        for model in MODEL_ORDER
    }


def segment_metrics(rows: list[dict]) -> dict:
    out = {"tour": {}, "surface": {}, "market": {}}
    for dimension in out:
        values = sorted({str(r.get(dimension) or "N/D") for r in rows})
        for value in values:
            subset = [r for r in rows if str(r.get(dimension) or "N/D") == value]
            out[dimension][value] = model_metrics(subset)
    return out


def _agreement_bucket(scores: list[float], threshold=65.0) -> str:
    vals = [float(x) for x in scores if _num(x) is not None]
    if len(vals) < 2:
        return "insufficient"
    spread = max(vals) - min(vals)
    strong = sum(v >= threshold for v in vals)
    if strong >= max(2, math.ceil(len(vals) * 0.67)) and spread <= 12:
        return "strong_consensus"
    if spread >= 18:
        return "conflict"
    if strong >= 2:
        return "majority"
    return "weak"


def agreement_stats(history: list[dict]) -> dict:
    specialist = defaultdict(list)
    ml = defaultdict(list)

    for entry in history or []:
        if not isinstance(entry, dict) or entry.get("status") not in ("settled", "void"):
            continue

        by_candidate = defaultdict(dict)
        for signal in unique_signals(entry, "signals"):
            if not isinstance(signal, dict) or str(signal.get("result") or "") not in ("hit", "miss"):
                continue
            src = str(signal.get("source_model") or "adaptive").lower()
            if src in ("legacy", "adaptive"):
                sc = _score(signal)
                if sc is not None:
                    by_candidate[_key(signal)]["adaptive"] = (sc, signal)
        for signal in unique_signals(entry, "learning_signals_v79b"):
            if not isinstance(signal, dict) or str(signal.get("result") or "") not in ("hit", "miss"):
                continue
            src = str(signal.get("source_model") or "").lower()
            if src in ("early", "serve", "form", "surface", "consensus"):
                sc = _score(signal)
                if sc is not None:
                    by_candidate[_key(signal)][src] = (sc, signal)

        for _, sources in by_candidate.items():
            if len(sources) < 2:
                continue
            signal = next(iter(sources.values()))[1]
            bucket = _agreement_bucket([x[0] for x in sources.values()])
            specialist[bucket].append({"target": 1 if signal.get("result") == "hit" else 0})

        for signal in unique_signals(entry, "autolearn_signals_v84"):
            if not isinstance(signal, dict) or str(signal.get("result") or "") not in ("hit", "miss"):
                continue
            scores = signal.get("model_scores") or {}
            vals = [_num(scores.get(k)) for k in ("current", "catboost", "tabpfn")]
            vals = [v for v in vals if v is not None]
            if len(vals) < 2:
                continue
            bucket = _agreement_bucket(vals)
            ml[bucket].append({"target": 1 if signal.get("result") == "hit" else 0})

    def finish(grouped):
        order = ("strong_consensus", "majority", "weak", "conflict", "insufficient")
        out = {}
        for name in order:
            rr = grouped.get(name, [])
            hits = sum(x["target"] for x in rr)
            out[name] = {
                "n": len(rr),
                "hits": hits,
                "misses": len(rr) - hits,
                "accuracy": round(hits * 100.0 / len(rr), 1) if rr else None,
            }
        return out

    return {"specialists": finish(specialist), "ml": finish(ml)}


def top_segments(segments: dict) -> list[dict]:
    ranked = []
    for dimension, values in (segments or {}).items():
        for value, models in (values or {}).items():
            for model, stats in (models or {}).items():
                if int(stats.get("selected_n") or 0) < MIN_SEGMENT_SAMPLE or stats.get("accuracy") is None:
                    continue
                ranked.append({
                    "dimension": dimension,
                    "value": value,
                    "model": model,
                    "label": MODEL_LABELS.get(model, model),
                    "selected_n": stats.get("selected_n"),
                    "accuracy": stats.get("accuracy"),
                    "brier": stats.get("brier"),
                    "roi": stats.get("roi"),
                })
    ranked.sort(key=lambda x: (-float(x["accuracy"]), float(x["brier"] or 9), -int(x["selected_n"])))
    return ranked[:12]


def build_report(history: list[dict], now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    rows = collect_rows(history)
    all_rows = _scope_rows(rows, now)
    rows30 = _scope_rows(rows, now, 30)
    rows7 = _scope_rows(rows, now, 7)
    segments30 = segment_metrics(rows30)
    prod_safe_rows30 = _prod_safe_dynamic_rows(rows30)
    prod_safe_segments30 = segment_metrics(prod_safe_rows30)
    trends = model_trends(all_rows)
    game_state = game_state_progress(history)
    return {
        "version": VERSION,
        "generated_at": now.isoformat(),
        "status": "ACTIVE",
        "selection_threshold": SELECT_THRESHOLD,
        "models": MODEL_LABELS,
        "scopes": {
            "7d": {"rows": len(rows7), "by_model": model_metrics(rows7)},
            "30d": {"rows": len(rows30), "by_model": model_metrics(rows30)},
            "all": {"rows": len(all_rows), "by_model": model_metrics(all_rows)},
        },
        "segments_30d": segments30,
        "prod_safe_rows_30d": len(prod_safe_rows30),
        "prod_safe_segments_30d": prod_safe_segments30,
        "prod_safe_policy": "current_catboost_tabpfn_only_current_tracker_with_capture_before_scheduled_time",
        "prod_safe_autolearn_tracker_version": AUTOLEARN_TRACKER_VERSION,
        "top_segments_30d": top_segments(segments30),
        "agreement": agreement_stats(history),
        "trends_v84e2": trends,
        "game_state_progress_v84e2": game_state,
        "notes": [
            "Accuracy modeli bazowych jest liczona na rozliczonych, zamrożonych sygnałach; próg wyboru to 65/100.",
            "Brier/log-loss używa score/100 jako proxy confidence. FINAL to ocena kandydata, nie znormalizowany rozkład przeciwstawnych zdarzeń.",
            "Generator to proxy selektora dla generator_selected, nie trafność zapisanych par. Rzeczywiste pary są liczone w Moje scenariusze.",
            "ROI jest liczone wyłącznie tam, gdzie historia zawiera rzeczywisty kurs dziesiętny; brak kursu pozostaje N/D.",
            "Pełne segmenty 30d pozostają diagnostyczne; PROD Dynamic Weights używa wyłącznie bieżącego reżimu AutoLearn z potwierdzonym capture przed startem meczu.",
        ],
    }


def run(now=None):
    history = _read(HISTORY_PATH, [])
    meta = _read(META_PATH, {})
    if not isinstance(history, list):
        history = []
    if not isinstance(meta, dict):
        meta = {}
    report = build_report(history, now=now)
    _write(REPORT_PATH, report)
    meta.update({
        "model_telemetry_version": VERSION,
        "model_telemetry_status": report["status"],
        "model_telemetry_updated_at": report["generated_at"],
        "model_telemetry_rows_30d": report["scopes"]["30d"]["rows"],
        "model_telemetry_prod_safe_rows_30d": report["prod_safe_rows_30d"],
        "model_telemetry_prod_safe_autolearn_tracker_version": AUTOLEARN_TRACKER_VERSION,
        "model_trend_version": TREND_VERSION,
        "model_trend_status": "ACTIVE",
        "model_trend_game_state_settled": report["game_state_progress_v84e2"]["total_settled"],
    })
    _write(META_PATH, meta)
    return report


def self_check():
    now = datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc)
    history = [{
        "match_key": "id:1", "status": "settled", "scheduled_time": "2026-08-23T10:00:00+00:00",
        "autolearn_captured_at": "2026-08-23T08:00:00+00:00",
        "tour": "ATP", "surface": "HARD",
        "signals": [{"key": "set1_total|8.5|over", "market": "set1_total", "pick": "over", "score": 72, "result": "hit", "source_model": "adaptive"}],
        "learning_signals_v79b": [
            {"key": "set1_total|8.5|over", "market": "set1_total", "pick": "over", "score": 75, "result": "hit", "source_model": "early"},
            {"key": "set1_total|8.5|over", "market": "set1_total", "pick": "over", "score": 73, "result": "hit", "source_model": "serve"},
        ],
        "autolearn_signals_v84": [{
            "key": "set1_total|8.5|over", "market": "set1_total", "pick": "over", "result": "hit",
            "tracker_version": AUTOLEARN_TRACKER_VERSION,
            "model_scores": {"current": 71, "catboost": 76, "tabpfn": 74, "ensemble": 74},
            "generator_selected": True,
        }],
    }]
    report = build_report(history, now=now)
    assert report["version"] == VERSION
    assert report["scopes"]["30d"]["by_model"]["adaptive"]["accuracy"] == 100.0
    assert report["scopes"]["30d"]["by_model"]["generator"]["selected_n"] == 1
    assert report["segments_30d"]["tour"]["ATP"]["early"]["selected_n"] == 1
    assert report["prod_safe_segments_30d"]["tour"]["ATP"]["current"]["selected_n"] == 1
    assert report["agreement"]["specialists"]["strong_consensus"]["n"] == 1
    assert report["agreement"]["ml"]["strong_consensus"]["n"] == 1
    print(json.dumps({"version": VERSION, "self_check": "PASS"}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    report = run()
    print(json.dumps({
        "version": report["version"],
        "status": report["status"],
        "rows_30d": report["scopes"]["30d"]["rows"],
        "top_segments": report["top_segments_30d"][:3],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
