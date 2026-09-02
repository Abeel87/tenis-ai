from __future__ import annotations

"""Tenis AI v9.1.2 — global Superbet PLAYABLE projection.

Core models stay independent and keep their raw internal ladders. This module is
used only *after* the core/AutoLearn prediction work:

- ``inject`` adds verified real Superbet selections to the current AutoLearn
  signal stream before Player Intelligence / SHADOW current scoring, so those
  models can score the same real operator lines;
- ``project`` runs after model guards and turns frontend-facing result ladders
  into a PLAYABLE view, derives operator-filtered SHADOW evidence in memory,
  freezes separate operator-aware history layers, and publishes separate
  PLAYABLE statistics without rewriting the RAW SHADOW feeds.

Bookmaker prices are never read here and operator availability never becomes a
training target.
"""

import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
RESULTS = OUT / "results.json"
HISTORY = OUT / "history.json"
SHADOW_CURRENT = OUT / "shadow_current.json"
SHADOW_CENTER = OUT / "shadow_signals_v894.json"
STATS = OUT / "superbet_playable_stats_v912.json"
META = OUT / "meta.json"

VERSION = "v9.1.2"
OPERATOR = "superbet.pl"
GREEN_THRESHOLD = 72.0
MODEL_SELECT_THRESHOLD = 68.0
SHADOW_MIN_THRESHOLD = 55.0

STRICT_MARKETS = {
    "match_winner", "set1_winner", "set2_winner", "set3_winner",
    "match_total", "set1_total", "set2_total", "set3_total", "total_sets",
    "set1_exact_score", "exact_match_score", "game_state", "set1_tiebreak",
    "match_game_handicap", "set1_game_handicap", "set2_game_handicap",
    "player_total_games", "match_total_aces", "most_aces",
    "player_aces", "player_double_faults", "most_double_faults", "most_aces_plus_df",
}
LINE_MARKETS = {
    "match_total", "set1_total", "set2_total", "set3_total", "total_sets",
    "match_game_handicap", "set1_game_handicap", "set2_game_handicap",
    "player_total_games", "match_total_aces", "player_aces", "player_double_faults",
}
PLAYER_MARKETS = {"player_total_games", "player_aces", "player_double_faults"}
WINNER_MARKETS = {"match_winner", "set1_winner", "set2_winner", "set3_winner", "most_aces", "most_double_faults", "most_aces_plus_df"}
SETTLE_SUPPORTED = {
    "match_winner", "set1_winner", "set2_winner", "set3_winner",
    "match_total", "set1_total", "total_sets", "set1_exact_score", "exact_match_score",
}
ALIASES = {
    "match_win": "match_winner",
    "first_set_win": "set1_winner", "set1_win": "set1_winner",
    "second_set_win": "set2_winner", "set2_win": "set2_winner",
    "third_set_win": "set3_winner", "set3_win": "set3_winner",
    "exact_set1": "set1_exact_score", "exact_first_set": "set1_exact_score",
    "exact_match": "exact_match_score",
    "state2": "game_state", "state4": "game_state", "state6": "game_state",
}


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
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


def _norm(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9:.+\-]+", " ", text).casefold()
    return " ".join(text.split())


def _name_key(value) -> str:
    return " ".join(sorted(re.sub(r"[^a-z0-9]+", " ", _norm(value)).split()))


def _market(value) -> str:
    raw = _norm(value).replace(" ", "_")
    return ALIASES.get(raw, raw)


def _pick(value, market: str) -> str:
    raw = _norm(value)
    if market in WINNER_MARKETS:
        return _name_key(value)
    if market in {"set1_exact_score", "exact_match_score", "game_state"}:
        m = re.search(r"(\d+)\s*[:\-]\s*(\d+)", str(value or ""))
        return f"{int(m.group(1))}:{int(m.group(2))}" if m else raw
    if raw in {"o", "over", "powyzej"}:
        return "over"
    if raw in {"u", "under", "ponizej"}:
        return "under"
    return raw


def signal_signature(signal: dict):
    market = _market(signal.get("market"))
    line = _num(signal.get("line")) if market in LINE_MARKETS else None
    checkpoint = int(_num(signal.get("checkpoint"), 0) or 0) if market == "game_state" else 0
    player = _name_key(signal.get("player")) if market in PLAYER_MARKETS else ""
    return (
        market,
        _pick(signal.get("pick"), market),
        round(float(line), 6) if line is not None else None,
        checkpoint,
        player,
    )


def operator_context_active(match: dict) -> bool:
    ctx = match.get("superbet_market_v91") or {}
    return bool(
        isinstance(ctx, dict)
        and ctx.get("operator_verified") is True
        and ctx.get("status") == "VERIFIED"
        and isinstance(ctx.get("canonical_selections"), list)
    )


def operator_availability(match: dict) -> dict:
    ctx = match.get("superbet_market_v91") or {}
    out = {}
    if not operator_context_active(match):
        return out
    for row in ctx.get("canonical_selections") or []:
        if not isinstance(row, dict) or row.get("operator_available") is False:
            continue
        market = _market(row.get("market"))
        # A line market without explicit fixture-line verification is diagnostic
        # context only. It must never become PLAYABLE through a malformed/legacy
        # canonical selection.
        if market in LINE_MARKETS and row.get("operator_line_verified") is not True:
            continue
        out[signal_signature(row)] = row
    return out


def operator_model_signals(match: dict) -> dict:
    ctx = match.get("superbet_market_v91") or {}
    out = {}
    if not operator_context_active(match):
        return out
    for row in ctx.get("model_signals") or []:
        if isinstance(row, dict) and row.get("operator_line_verified") is True:
            out[signal_signature(row)] = row
    return out


def is_operator_playable_signal(match: dict, signal: dict) -> bool:
    if not operator_context_active(match):
        return False
    market = _market(signal.get("market"))
    if market not in STRICT_MARKETS:
        return False
    return signal_signature(signal) in operator_availability(match)


def _copy_signal(signal: dict) -> dict:
    out = dict(signal)
    out["market"] = _market(signal.get("market"))
    if out["market"] in LINE_MARKETS:
        out["line"] = _num(signal.get("line"))
    if out["market"] == "game_state":
        out["checkpoint"] = int(_num(signal.get("checkpoint"), 0) or 0)
    return out


def _model_probability_fallback(match: dict, operator_signal: dict):
    market = _market(operator_signal.get("market"))
    pick = operator_signal.get("pick")
    line = _num(operator_signal.get("line"))
    try:
        if market == "match_winner":
            return _lookup_player(match.get("match_win"), pick)
        if market == "set1_winner":
            return _lookup_player(match.get("first_set_win"), pick)
        if market == "set2_winner":
            return _lookup_player(match.get("second_set_win"), pick)
        if market == "set3_winner":
            return _lookup_player(match.get("third_set_win"), pick)
        if market == "set1_total":
            return _lookup_ou(match.get("over_under"), line, pick)
        if market == "match_total":
            return _lookup_ou(match.get("match_over_under"), line, pick)
        if market == "set1_exact_score":
            return _lookup_exact(match.get("exact_first_set"), pick)
        if market == "exact_match_score":
            return _lookup_exact(match.get("exact_match_score"), pick)
        if market == "game_state":
            cp = str(int(_num(operator_signal.get("checkpoint"), 0) or 0))
            return _lookup_exact((match.get("game_states") or {}).get(cp), pick)
    except Exception:
        return None
    return None


def _lookup_player(block, pick):
    if not isinstance(block, dict):
        return None
    target = _name_key(pick)
    for name, value in block.items():
        if _name_key(name) == target:
            return _num(value)
    return None


def _lookup_ou(block, line, pick):
    if not isinstance(block, dict) or line is None:
        return None
    for key in (f"{float(line):.1f}", f"{float(line):g}", str(line)):
        row = block.get(key)
        if isinstance(row, dict):
            return _num(row.get(str(pick).lower()))
    return None


def _lookup_exact(block, pick):
    if not isinstance(block, dict):
        return None
    target = str(pick or "").replace("-", ":")
    for key, value in block.items():
        if str(key).replace("-", ":") == target:
            return _num(value)
    return None


def _current_autolearn_signals(match: dict):
    auto = match.get("autolearn_v84") or {}
    return [dict(x) for x in (auto.get("signals") or []) if isinstance(x, dict)]


def inject_match(match: dict) -> dict:
    m = dict(match)
    auto = dict(m.get("autolearn_v84") or {})
    current = _current_autolearn_signals(m)
    availability = operator_availability(m)
    model_signals = operator_model_signals(m)
    by_sig = {signal_signature(s): dict(s) for s in current}

    for sig, signal in list(by_sig.items()):
        if _market(signal.get("market")) in STRICT_MARKETS:
            signal["operator_playable"] = sig in availability
            signal["operator"] = OPERATOR if signal["operator_playable"] else None
            row = availability.get(sig)
            if row:
                signal["operator_line_verified"] = row.get("operator_line_verified") is True
                signal["operator_line_source"] = row.get("operator_line_source")
            by_sig[sig] = signal

    for sig, operator_signal in model_signals.items():
        if sig not in availability:
            continue
        existing = by_sig.get(sig)
        if existing:
            existing["operator_playable"] = True
            existing["operator"] = OPERATOR
            existing["operator_line_verified"] = True
            existing["operator_line_source"] = operator_signal.get("operator_line_source")
            by_sig[sig] = existing
            continue
        fallback = _model_probability_fallback(m, operator_signal)
        if fallback is None:
            continue
        item = _copy_signal(operator_signal)
        item.update({
            "key": operator_signal.get("key") or "|".join(str(x) for x in sig),
            "label": operator_signal.get("label") or str(operator_signal.get("market") or ""),
            "current": round(float(fallback), 1),
            "catboost": None,
            "tabpfn": None,
            "ensemble": round(float(fallback), 1),
            "support": 0,
            "local_weights": {"current": 1.0},
            "dynamic_weighting": {
                "version": "v8.4D", "active": False, "status": "SAFE_FALLBACK",
                "reason": "operator_line_not_in_candidate_grid",
            },
            "operator_playable": True,
            "operator": OPERATOR,
            "operator_line_verified": True,
            "operator_line_source": operator_signal.get("operator_line_source"),
            "operator_projection_fallback": True,
            "ensemble_score_kind": "current_model_fallback_not_learned_ensemble",
        })
        by_sig[sig] = item

    signals = sorted(
        by_sig.values(),
        key=lambda s: (-float(_num(s.get("ensemble"), _num(s.get("score"), 0.0)) or 0.0), str(s.get("key") or "")),
    )
    auto["signals"] = signals
    auto["by_key"] = {str(s.get("key")): s for s in signals if s.get("key")}
    auto["superbet_playable_projection"] = {
        "version": VERSION,
        "operator": OPERATOR,
        "operator_context_active": operator_context_active(m),
        "available_selections": len(availability),
        "operator_scored_selections": len(model_signals),
        "prices_used": False,
    }
    m["autolearn_v84"] = auto
    return m


def _score(signal: dict):
    for key in ("final_score", "ensemble", "score", "shadow_score", "value"):
        value = _num(signal.get(key))
        if value is not None:
            return value
    return None


def _playable_signals(match: dict, limit=None):
    rows = []
    for signal in _current_autolearn_signals(match):
        if not is_operator_playable_signal(match, signal):
            continue
        item = dict(signal)
        item["operator_playable"] = True
        item["operator"] = OPERATOR
        rows.append(item)
    rows.sort(key=lambda s: (-float(_score(s) or 0.0), str(s.get("key") or "")))
    return rows[:limit] if limit else rows


def _project_ladder(block: dict, market: str, availability: dict, player=None):
    if not isinstance(block, dict):
        return {}
    out = {}
    for key, value in block.items():
        if market in LINE_MARKETS:
            line = _num(key)
            if line is None:
                continue
            sides = value if isinstance(value, dict) else {}
            projected = {}
            for pick, score in sides.items():
                probe = {"market": market, "pick": pick, "line": line, "player": player}
                if signal_signature(probe) in availability:
                    projected[pick] = score
            if projected:
                out[str(key)] = projected
        else:
            probe = {"market": market, "pick": key, "player": player}
            if signal_signature(probe) in availability:
                out[key] = value
    return out


def project_match_for_display(match: dict) -> dict:
    m = dict(match)
    availability = operator_availability(m)
    if not availability:
        m["superbet_playable_v912"] = {
            "version": VERSION, "operator": OPERATOR, "status": "NO_VERIFIED_OPERATOR_CONTEXT",
            "playable": False, "playable_count": 0, "signals": [], "prices_used": False,
        }
        return m

    m["match_win"] = _project_ladder(m.get("match_win"), "match_winner", availability)
    m["first_set_win"] = _project_ladder(m.get("first_set_win"), "set1_winner", availability)
    m["second_set_win"] = _project_ladder(m.get("second_set_win"), "set2_winner", availability)
    m["third_set_win"] = _project_ladder(m.get("third_set_win"), "set3_winner", availability)
    m["over_under"] = _project_ladder(m.get("over_under"), "set1_total", availability)
    m["match_over_under"] = _project_ladder(m.get("match_over_under"), "match_total", availability)
    m["exact_first_set"] = _project_ladder(m.get("exact_first_set"), "set1_exact_score", availability)
    m["exact_match_score"] = _project_ladder(m.get("exact_match_score"), "exact_match_score", availability)

    signals = _playable_signals(m)
    m["superbet_playable_v912"] = {
        "version": VERSION, "operator": OPERATOR,
        "status": "PLAYABLE" if signals else "VERIFIED_NO_MODEL_SIGNAL",
        "playable": bool(signals), "playable_count": len(signals), "signals": signals,
        "prices_used": False,
    }
    return m


def _history_signal(signal: dict, source: str):
    row = {
        "key": signal.get("key"), "label": signal.get("label"),
        "market": _market(signal.get("market")), "pick": signal.get("pick"),
        "line": _num(signal.get("line")), "checkpoint": signal.get("checkpoint"),
        "player": signal.get("player"), "result": "pending",
        "source_model": source, "operator": OPERATOR,
        "operator_playable": True,
        "operator_line_verified": signal.get("operator_line_verified") is True,
        "operator_line_source": signal.get("operator_line_source"),
        "tracker_version": VERSION,
    }
    score = _score(signal)
    if score is not None:
        row["score"] = round(float(score), 1)
    return row


def _copy_result_layers(entry: dict, signals: list[dict], key: str, source: str):
    if entry.get(key):
        return entry
    entry[key] = [_history_signal(s, source) for s in signals]
    return entry


def _find_current_match(entry: dict, matches: list[dict]):
    mid = entry.get("match_id") or entry.get("id")
    if mid is not None:
        for m in matches:
            if str(m.get("id") or m.get("match_id") or "") == str(mid):
                return m
    p1, p2 = _name_key(entry.get("p1")), _name_key(entry.get("p2"))
    date = str(entry.get("scheduled_time") or "")[:10]
    for m in matches:
        if {_name_key(m.get("p1")), _name_key(m.get("p2"))} == {p1, p2} and str(m.get("scheduled_time") or "")[:10] == date:
            return m
    return None


def freeze_playable_history(history: list[dict], matches: list[dict]):
    out = []
    for raw in history:
        e = dict(raw)
        if e.get("status") not in {"pending", "upcoming"}:
            out.append(e)
            continue
        match = _find_current_match(e, matches)
        if not match:
            out.append(e)
            continue
        playable = _playable_signals(match)
        if playable:
            e = _copy_result_layers(e, playable, "playable_autolearn_signals_v912", "ensemble_v84_superbet")
        out.append(e)
    return out


def _shadow_models_from_match(match: dict):
    out = []
    pi = match.get("player_intelligence_v85") or {}
    for signal in ((match.get("autolearn_v84") or {}).get("signals") or []):
        if not is_operator_playable_signal(match, signal):
            continue
        details = signal.get("player_intelligence_v85") or {}
        if _num(details.get("shadow_score")) is not None:
            item = _copy_signal(signal)
            item["score"] = details.get("shadow_score")
            item["source_model"] = "player_intelligence_v85"
            out.append(item)
    return out


def _filter_shadow_feed(feed: dict, matches_by_id: dict) -> dict:
    source = feed if isinstance(feed, dict) else {}
    result = {k: v for k, v in source.items() if k not in {"matches", "matches_count", "model_signal_counts"}}
    kept = []
    counts = defaultdict(int)
    for row in source.get("matches") or []:
        if not isinstance(row, dict):
            continue
        match = None
        mid = row.get("id") or row.get("match_id")
        if mid is not None:
            match = matches_by_id.get(str(mid))
        if not match:
            # A PLAYABLE-only projection must never preserve an unmatched RAW row.
            continue
        signals = []
        for signal in row.get("signals") or []:
            if not isinstance(signal, dict) or not is_operator_playable_signal(match, signal):
                continue
            item = dict(signal)
            item["operator_playable"] = True
            item["operator"] = OPERATOR
            signals.append(item)
            source_model = str(item.get("source_model") or row.get("source_model") or "shadow")
            counts[source_model] += 1
        if not signals:
            continue
        item = dict(row)
        item["signals"] = signals
        kept.append(item)
    result["matches"] = kept
    result["matches_count"] = len(kept)
    result["model_signal_counts"] = dict(sorted(counts.items()))
    result["projection"] = "PLAYABLE_SUPERBET_ONLY"
    return result


def _history_stats(history):
    totals = defaultdict(lambda: {"n": 0, "hits": 0, "misses": 0})
    for entry in history or []:
        for layer in ("playable_autolearn_signals_v912", "playable_shadow_models_v912"):
            for signal in entry.get(layer) or []:
                result = signal.get("result")
                if result not in {"hit", "miss"}:
                    continue
                key = (layer, _market(signal.get("market")))
                totals[key]["n"] += 1
                totals[key]["hits"] += int(result == "hit")
                totals[key]["misses"] += int(result == "miss")
    return {
        f"{layer}:{market}": {
            **row,
            "accuracy": round(100.0 * row["hits"] / row["n"], 1) if row["n"] else None,
        }
        for (layer, market), row in sorted(totals.items())
    }


def inject():
    results = _read(RESULTS, [])
    results = [inject_match(m) for m in results if isinstance(m, dict)] if isinstance(results, list) else []
    _write(RESULTS, results)
    return {"version": VERSION, "matches": len(results), "operator": OPERATOR}


def project():
    results = _read(RESULTS, [])
    history = _read(HISTORY, [])
    raw_shadow_current = _read(SHADOW_CURRENT, {})
    raw_shadow_center = _read(SHADOW_CENTER, {})
    if not isinstance(results, list): results = []
    if not isinstance(history, list): history = []

    projected_results = [project_match_for_display(m) for m in results if isinstance(m, dict)]
    matches_by_id = {
        str(m.get("id") or m.get("match_id")): m
        for m in projected_results
        if m.get("id") is not None or m.get("match_id") is not None
    }
    history = freeze_playable_history(history, projected_results)
    shadow_current = _filter_shadow_feed(raw_shadow_current, matches_by_id)
    shadow_center = _filter_shadow_feed(raw_shadow_center, matches_by_id)
    stats = {
        "version": VERSION,
        "operator": OPERATOR,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matches": sum(1 for m in projected_results if (m.get("superbet_playable_v912") or {}).get("playable")),
        "signals": sum(int((m.get("superbet_playable_v912") or {}).get("playable_count") or 0) for m in projected_results),
        "history": _history_stats(history),
        "shadow_current": {
            "matches": shadow_current.get("matches_count", 0),
            "model_signal_counts": shadow_current.get("model_signal_counts", {}),
        },
        "shadow_center": {
            "matches": shadow_center.get("matches_count", 0),
            "model_signal_counts": shadow_center.get("model_signal_counts", {}),
        },
    }
    _write(RESULTS, projected_results)
    _write(HISTORY, history)
    _write(STATS, stats)
    meta = _read(META, {})
    if not isinstance(meta, dict): meta = {}
    meta["superbet_playable_v912"] = {
        "version": VERSION, "operator": OPERATOR,
        "matches": stats["matches"], "signals": stats["signals"],
        "updated_at": stats["generated_at"],
    }
    _write(META, meta)
    return stats


def main():
    mode = str(sys.argv[1] if len(sys.argv) > 1 else "project").strip().casefold()
    if mode == "inject": result = inject()
    elif mode == "project": result = project()
    else: raise SystemExit("usage: superbet_playable.py [inject|project]")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
