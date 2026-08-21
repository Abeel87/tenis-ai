from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt

MIN_SAMPLE = 10
MEDIUM_SAMPLE = 20
STRONG_SAMPLE = 50


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _line(value):
    v = _num(value)
    return None if v is None else f"{v:.1f}"


def signal_key(signal: dict) -> str:
    market = str(signal.get("market") or "other")
    pick = str(signal.get("pick") or "").lower()
    if market in ("set1_total", "match_total"):
        return f"{market}|{_line(signal.get('line')) or '?'}|{pick}"
    if market == "game_state":
        return f"{market}|{signal.get('checkpoint') or '?'}|{pick}"
    return market


def _wilson(hits: int, total: int):
    if total <= 0:
        return None
    z = 1.96
    p = hits / total
    den = 1 + z * z / total
    center = (p + z * z / (2 * total)) / den
    half = z * sqrt((p * (1 - p) + z * z / (4 * total)) / total) / den
    return [
        round(max(0.0, center - half) * 100, 1),
        round(min(1.0, center + half) * 100, 1),
    ]


def _evidence(total: int) -> str:
    if total < MIN_SAMPLE:
        return "N/D"
    if total < MEDIUM_SAMPLE:
        return "MALA"
    if total < STRONG_SAMPLE:
        return "OK"
    return "MOCNA"


def _summary(rows):
    hits = sum(1 for _, s in rows if s.get("result") == "hit")
    total = len(rows)
    accuracy = round(hits * 100 / total, 1) if total else None
    return {
        "settled": total,
        "hits": hits,
        "misses": total - hits,
        "accuracy": accuracy,
        "ci95": _wilson(hits, total),
        "evidence": _evidence(total),
        "usable": total >= MIN_SAMPLE,
        "display_accuracy": accuracy if total >= MIN_SAMPLE else None,
    }


def _settled(entries, predicate=None):
    out = []
    for entry in entries or []:
        if predicate is not None and not predicate(entry):
            continue
        for signal in entry.get("signals") or []:
            if signal.get("result") in ("hit", "miss"):
                out.append((entry, signal))
    return out


def _group(rows, key_fn):
    groups = {}
    for pair in rows:
        groups.setdefault(key_fn(*pair), []).append(pair)
    return {key: _summary(value) for key, value in sorted(groups.items())}


def build_calibration_report(entries: list[dict], current_version: str) -> dict:
    current = _settled(entries, lambda e: e.get("model_version") == current_version)
    legacy = _settled(entries, lambda e: e.get("model_version") != current_version)
    return {
        "version": "v7.8D",
        "current_model_version": current_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "min_sample": MIN_SAMPLE,
        "medium_sample": MEDIUM_SAMPLE,
        "strong_sample": STRONG_SAMPLE,
        "score_semantics": {
            "adaptive": "model_estimate_not_guarantee",
            "specialist_models": "strength_0_100_not_probability",
        },
        "current": {
            "overall": _summary(current),
            "by_key": _group(current, lambda e, s: signal_key(s)),
            "by_market": _group(current, lambda e, s: s.get("market") or "other"),
            "by_tour": _group(current, lambda e, s: str(e.get("tour") or "N/D").upper()),
        },
        "legacy_reference": {
            "reference_only": True,
            "overall": _summary(legacy),
            "by_key": _group(legacy, lambda e, s: signal_key(s)),
            "by_version": _group(legacy, lambda e, s: e.get("model_version") or "N/D"),
        },
        "all_versions_diagnostic": _summary(current + legacy),
    }


def _green_signals(match: dict, threshold: float = 72.0):
    out = []

    def add_binary(field, market, label):
        for pick, value in (match.get(field) or {}).items():
            v = _num(value)
            if v is not None and v >= threshold:
                out.append({"market": market, "label": label, "pick": str(pick), "score": round(v, 1)})

    add_binary("match_win", "match_winner", "Zwycięzca meczu")
    add_binary("first_set_win", "set1_winner", "Zwycięzca 1. seta")
    add_binary("second_set_win", "set2_winner", "Zwycięzca 2. seta")
    add_binary("third_set_win", "set3_winner", "Zwycięzca 3. seta")
    add_binary("total_sets", "total_sets", "Liczba setów")
    add_binary("exact_match_score", "exact_match", "Dokładny wynik meczu")

    for line, sides in (match.get("over_under") or {}).items():
        for side in ("over", "under"):
            v = _num((sides or {}).get(side))
            if v is not None and v >= threshold:
                out.append({
                    "market": "set1_total", "label": f"1. set · {side.upper()} {line}",
                    "pick": side, "line": _num(line), "score": round(v, 1),
                })

    for line, sides in (match.get("match_over_under") or {}).items():
        for side in ("over", "under"):
            v = _num((sides or {}).get(side))
            if v is not None and v >= threshold:
                out.append({
                    "market": "match_total", "label": f"Mecz · {side.upper()} {line}",
                    "pick": side, "line": _num(line), "score": round(v, 1),
                })

    for pick, value in (match.get("exact_first_set") or {}).items():
        v = _num(value)
        if v is not None and v >= threshold:
            out.append({
                "market": "exact_set1", "label": "Dokładny wynik 1. seta",
                "pick": str(pick), "score": round(v, 1),
            })

    return sorted(out, key=lambda s: (-s["score"], s["label"], s["pick"]))


def _decorate(signal: dict, report: dict) -> dict:
    key = signal_key(signal)
    cur = ((report.get("current") or {}).get("by_key") or {}).get(key) or _summary([])
    legacy = ((report.get("legacy_reference") or {}).get("by_key") or {}).get(key) or _summary([])
    return {**signal, "calibration_key": key, "current": cur, "legacy_reference": legacy}


def add_calibration_to_matches(matches: list[dict], report: dict, threshold: float = 72.0) -> list[dict]:
    out = []
    for match in matches or []:
        m = dict(match)
        rows = [_decorate(s, report) for s in _green_signals(m, threshold)]
        usable = sum(1 for row in rows if (row.get("current") or {}).get("usable"))
        m["calibration_v78d"] = {
            "version": "v7.8D",
            "current_model_version": report.get("current_model_version"),
            "status": "READY" if usable else "COLLECTING",
            "min_sample": report.get("min_sample", MIN_SAMPLE),
            "usable_signals": usable,
            "signals": rows[:12],
            "legacy_reference_only": True,
            "note": "Wynik modelu i historyczna trafnosc to dwie rozne rzeczy.",
        }
        out.append(m)
    return out
