from __future__ import annotations

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
    "ensemble": "Ensemble",
    "generator": "Generator AI",
}
MODEL_ORDER = list(MODEL_LABELS)


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
        "tour": str(entry.get("tour") or "N/D").upper(),
        "surface": str(entry.get("surface") or "N/D").upper(),
        "market": str(signal.get("market") or "other").lower(),
        "candidate_key": _key(signal),
        "model": model,
        "score": max(1.0, min(99.0, sc)),
        "target": 1 if result == "hit" else 0,
        "odds": _odds(signal),
        "generator_selected": bool(generator_selected),
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

        for signal in entry.get("signals") or []:
            if not isinstance(signal, dict):
                continue
            src = str(signal.get("source_model") or "adaptive").lower()
            if src in ("legacy", "adaptive"):
                add(_row(entry, signal, "adaptive"))

        for signal in entry.get("learning_signals_v79b") or []:
            if not isinstance(signal, dict):
                continue
            src = str(signal.get("source_model") or "").lower()
            if src in ("early", "serve", "form", "surface", "consensus", "adaptive"):
                add(_row(entry, signal, src))

        for signal in entry.get("autolearn_signals_v84") or []:
            if not isinstance(signal, dict):
                continue
            if str(signal.get("result") or "") not in ("hit", "miss"):
                continue
            scores = signal.get("model_scores") or {}
            for model in ("current", "catboost", "tabpfn", "ensemble"):
                sc = _num(scores.get(model))
                if sc is not None:
                    add(_row(entry, signal, model, score=sc))
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
        for signal in entry.get("signals") or []:
            if not isinstance(signal, dict) or str(signal.get("result") or "") not in ("hit", "miss"):
                continue
            src = str(signal.get("source_model") or "adaptive").lower()
            if src in ("legacy", "adaptive"):
                sc = _score(signal)
                if sc is not None:
                    by_candidate[_key(signal)]["adaptive"] = (sc, signal)
        for signal in entry.get("learning_signals_v79b") or []:
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

        for signal in entry.get("autolearn_signals_v84") or []:
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
        "top_segments_30d": top_segments(segments30),
        "agreement": agreement_stats(history),
        "notes": [
            "Accuracy modeli bazowych jest liczona na rozliczonych, zamrożonych sygnałach; próg wyboru to 65/100.",
            "Brier/log-loss dla modeli bazowych używa score/100 jako proxy confidence; pełna probabilistyczna kalibracja pozostaje domeną Current/CatBoost/TabPFN/Ensemble.",
            "Generator ma własny licznik tylko dla sygnałów oznaczonych generator_selected.",
            "ROI jest liczone wyłącznie tam, gdzie historia zawiera rzeczywisty kurs dziesiętny; brak kursu pozostaje N/D.",
            "Segmenty ATP/WTA/CH/ITF, nawierzchnia i rynek są raportowane osobno i nie zmieniają jeszcze wag produkcyjnych.",
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
    })
    _write(META_PATH, meta)
    return report


def self_check():
    now = datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc)
    history = [{
        "match_key": "id:1", "status": "settled", "scheduled_time": "2026-08-23T10:00:00+00:00",
        "tour": "ATP", "surface": "HARD",
        "signals": [{"key": "set1_total|8.5|over", "market": "set1_total", "pick": "over", "score": 72, "result": "hit", "source_model": "adaptive"}],
        "learning_signals_v79b": [
            {"key": "set1_total|8.5|over", "market": "set1_total", "pick": "over", "score": 75, "result": "hit", "source_model": "early"},
            {"key": "set1_total|8.5|over", "market": "set1_total", "pick": "over", "score": 73, "result": "hit", "source_model": "serve"},
        ],
        "autolearn_signals_v84": [{
            "key": "set1_total|8.5|over", "market": "set1_total", "pick": "over", "result": "hit",
            "model_scores": {"current": 71, "catboost": 76, "tabpfn": 74, "ensemble": 74},
            "generator_selected": True,
        }],
    }]
    report = build_report(history, now=now)
    assert report["version"] == VERSION
    assert report["scopes"]["30d"]["by_model"]["adaptive"]["accuracy"] == 100.0
    assert report["scopes"]["30d"]["by_model"]["generator"]["selected_n"] == 1
    assert report["segments_30d"]["tour"]["ATP"]["early"]["selected_n"] == 1
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
