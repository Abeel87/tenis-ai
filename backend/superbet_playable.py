from __future__ import annotations

"""Canonical Superbet PLAYABLE projection.

MODEL/RAW remains the source of model analysis. This module never rewrites raw
model ladders or AutoLearn signals. It derives a separate, fail-closed operator
projection from the current verified Superbet context and may freeze that
projection into dedicated PLAYABLE history layers.

Contract:
    DATA/MODEL RAW -> SYMPHONY / model analysis -> verified Superbet offer -> PLAYABLE

Bookmaker availability is never a training target and bookmaker prices are not
used here.
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
WINNER_MARKETS = {
    "match_winner", "set1_winner", "set2_winner", "set3_winner",
    "most_aces", "most_double_faults", "most_aces_plus_df",
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
    if raw in {"o", "over", "powyzej"} or raw.startswith("over "):
        return "over"
    if raw in {"u", "under", "ponizej"} or raw.startswith("under "):
        return "under"
    if raw in {"tak", "yes"}:
        return "yes"
    if raw in {"nie", "no"}:
        return "no"
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
        and ctx.get("suspended") is not True
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
        if not isinstance(row, dict):
            continue
        market = _market(row.get("market"))
        if market in LINE_MARKETS and row.get("operator_line_verified") is not True:
            continue
        out[signal_signature(row)] = row
    return out


def is_operator_playable_signal(match: dict, signal: dict) -> bool:
    if not operator_context_active(match) or not isinstance(signal, dict):
        return False
    if _market(signal.get("market")) not in STRICT_MARKETS:
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
    side = _pick(pick, "match_total")
    for key in (f"{float(line):.1f}", f"{float(line):g}", str(line)):
        row = block.get(key)
        if isinstance(row, dict):
            return _num(row.get(side))
    return None


def _lookup_exact(block, pick):
    if not isinstance(block, dict):
        return None
    target = str(pick or "").replace("-", ":")
    for key, value in block.items():
        if str(key).replace("-", ":") == target:
            return _num(value)
    return None


def _model_probability_fallback(match: dict, operator_signal: dict):
    market = _market(operator_signal.get("market"))
    pick = operator_signal.get("pick")
    line = _num(operator_signal.get("line"))
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
    return None


def _score(signal: dict):
    for key in ("final_score", "ensemble", "score", "current", "shadow_score", "value"):
        value = _num(signal.get(key))
        if value is not None:
            return value
    return None


def _current_autolearn_signals(match: dict) -> list[dict]:
    auto = match.get("autolearn_v84") or {}
    return [dict(x) for x in (auto.get("signals") or []) if isinstance(x, dict)]


def _projection_signals(match: dict) -> list[dict]:
    """Build PLAYABLE without mutating RAW AutoLearn/model ladders."""
    availability = operator_availability(match)
    if not availability:
        return []

    out: dict[tuple, dict] = {}
    for raw in _current_autolearn_signals(match):
        sig = signal_signature(raw)
        available = availability.get(sig)
        if available is None:
            continue
        item = dict(raw)
        item.update({
            "operator": OPERATOR,
            "operator_playable": True,
            "operator_line_verified": available.get("operator_line_verified") is True
            if _market(raw.get("market")) in LINE_MARKETS else True,
            "operator_line_source": available.get("operator_line_source"),
            "operator_projection_version": VERSION,
            "operator_projection_fallback": False,
        })
        out[sig] = item

    for sig, operator_signal in operator_model_signals(match).items():
        if sig not in availability or sig in out:
            continue
        score = _num(operator_signal.get("score"))
        if score is None:
            score = _model_probability_fallback(match, operator_signal)
        if score is None:
            continue
        item = _copy_signal(operator_signal)
        item.update({
            "key": operator_signal.get("key") or "|".join(str(x) for x in sig),
            "label": operator_signal.get("label") or str(operator_signal.get("market") or ""),
            "score": round(float(score), 1),
            "current": round(float(score), 1),
            "ensemble": None,
            "catboost": None,
            "tabpfn": None,
            "support": 0,
            "source_model": "current_operator_projection",
            "operator": OPERATOR,
            "operator_playable": True,
            "operator_line_verified": True,
            "operator_line_source": operator_signal.get("operator_line_source"),
            "operator_projection_version": VERSION,
            "operator_projection_fallback": True,
            "ensemble_score_kind": "not_learned_ensemble",
        })
        out[sig] = item

    rows = list(out.values())
    rows.sort(key=lambda s: (-float(_score(s) or 0.0), str(s.get("key") or "")))
    return rows


def inject_match(match: dict) -> tuple[dict, dict]:
    """Backward-compatible entrypoint; only attaches a separate PLAYABLE layer."""
    m = dict(match)
    signals = _projection_signals(m)
    m["superbet_playable_v912"] = {
        "version": VERSION,
        "operator": OPERATOR,
        "status": "PLAYABLE" if signals else (
            "VERIFIED_NO_MODEL_SIGNAL" if operator_context_active(m) else "NO_VERIFIED_OPERATOR_CONTEXT"
        ),
        "playable": bool(signals),
        "playable_count": len(signals),
        "signals": signals,
        "prices_used": False,
        "raw_model_fields_preserved": True,
    }
    info = {
        "active": operator_context_active(m),
        "playable": len(signals),
        "raw_preserved": True,
    }
    return m, info


def project_match_for_display(match: dict) -> tuple[dict, dict]:
    """Attach PLAYABLE metadata while preserving every MODEL/RAW field."""
    return inject_match(match)


def _history_signal(signal: dict, source: str):
    row = {
        "key": signal.get("key"),
        "label": signal.get("label"),
        "market": _market(signal.get("market")),
        "pick": signal.get("pick"),
        "line": _num(signal.get("line")),
        "checkpoint": signal.get("checkpoint"),
        "player": signal.get("player"),
        "result": "pending",
        "source_model": source,
        "operator": OPERATOR,
        "operator_playable": True,
        "operator_line_verified": signal.get("operator_line_verified") is True,
        "operator_line_source": signal.get("operator_line_source"),
        "tracker_version": VERSION,
    }
    score = _score(signal)
    if score is not None:
        row["score"] = round(float(score), 1)
    return {k: v for k, v in row.items() if v is not None}


def _match_key(row: dict) -> str:
    mid = row.get("match_id") if row.get("match_id") is not None else row.get("id")
    if mid is not None and str(mid) != "":
        return f"id:{mid}"
    return "|".join([
        _name_key(row.get("p1")), _name_key(row.get("p2")),
        str(row.get("scheduled_time") or "")[:10], _norm(row.get("tournament")),
    ])


def freeze_playable_history(history: list[dict], matches: list[dict]):
    current = {_match_key(m): m for m in matches if isinstance(m, dict)}
    out = []
    for raw in history or []:
        if not isinstance(raw, dict):
            continue
        entry = dict(raw)
        if entry.get("status") not in {"pending", "upcoming"} or entry.get("playable_autolearn_signals_v912"):
            out.append(entry)
            continue
        match = current.get(_match_key(entry))
        signals = ((match or {}).get("superbet_playable_v912") or {}).get("signals") or []
        if signals:
            entry["playable_autolearn_signals_v912"] = [
                _history_signal(s, "superbet_playable_projection") for s in signals
            ]
            entry["playable_captured_at_v912"] = datetime.now(timezone.utc).isoformat()
        out.append(entry)
    return out


def _filter_shadow_feed(feed, matches_by_key: dict):
    """Derive a PLAYABLE-only SHADOW view in memory. Never write it back to RAW."""
    if isinstance(feed, list):
        rows = []
        for raw in feed:
            if not isinstance(raw, dict):
                continue
            match = matches_by_key.get(_match_key(raw))
            if not match:
                continue
            signals = [
                dict(s) for s in (raw.get("signals") or [])
                if isinstance(s, dict) and is_operator_playable_signal(match, s)
            ]
            if signals:
                item = dict(raw)
                item["signals"] = signals
                rows.append(item)
        return rows

    source = feed if isinstance(feed, dict) else {}
    result = {k: v for k, v in source.items() if k not in {"matches", "matches_count", "model_signal_counts"}}
    kept = []
    counts = defaultdict(int)
    for raw in source.get("matches") or []:
        if not isinstance(raw, dict):
            continue
        match = matches_by_key.get(_match_key(raw))
        if not match:
            continue
        signals = []
        for signal in raw.get("signals") or []:
            if not isinstance(signal, dict) or not is_operator_playable_signal(match, signal):
                continue
            item = dict(signal)
            item["operator_playable"] = True
            item["operator"] = OPERATOR
            signals.append(item)
            model_id = str(item.get("source_model") or raw.get("source_model") or "shadow")
            counts[model_id] += 1
        if signals:
            item = dict(raw)
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
        for signal in entry.get("playable_autolearn_signals_v912") or []:
            result = signal.get("result")
            if result not in {"hit", "miss"}:
                continue
            key = _market(signal.get("market"))
            totals[key]["n"] += 1
            totals[key]["hits"] += int(result == "hit")
            totals[key]["misses"] += int(result == "miss")
    return {
        market: {
            **row,
            "accuracy": round(100.0 * row["hits"] / row["n"], 1) if row["n"] else None,
        }
        for market, row in sorted(totals.items())
    }


def inject():
    results = _read(RESULTS, [])
    projected = []
    active = playable = 0
    for raw in results if isinstance(results, list) else []:
        if not isinstance(raw, dict):
            continue
        row, info = inject_match(raw)
        projected.append(row)
        active += int(info["active"])
        playable += int(info["playable"])
    _write(RESULTS, projected)
    return {
        "version": VERSION,
        "operator": OPERATOR,
        "matches_active": active,
        "playable_signals": playable,
        "raw_preserved": True,
    }


def project():
    results = _read(RESULTS, [])
    history = _read(HISTORY, [])
    raw_shadow_current = _read(SHADOW_CURRENT, {})
    raw_shadow_center = _read(SHADOW_CENTER, {})
    if not isinstance(results, list):
        results = []
    if not isinstance(history, list):
        history = []

    projected_results = []
    for raw in results:
        if isinstance(raw, dict):
            row, _ = project_match_for_display(raw)
            projected_results.append(row)

    matches_by_key = {_match_key(m): m for m in projected_results}
    history = freeze_playable_history(history, projected_results)
    shadow_current = _filter_shadow_feed(raw_shadow_current, matches_by_key)
    shadow_center = _filter_shadow_feed(raw_shadow_center, matches_by_key)

    stats = {
        "version": VERSION,
        "operator": OPERATOR,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matches": sum(1 for m in projected_results if (m.get("superbet_playable_v912") or {}).get("playable")),
        "signals": sum(int((m.get("superbet_playable_v912") or {}).get("playable_count") or 0) for m in projected_results),
        "history": _history_stats(history),
        "shadow_current": {
            "matches": len(shadow_current) if isinstance(shadow_current, list) else shadow_current.get("matches_count", 0),
            "model_signal_counts": {} if isinstance(shadow_current, list) else shadow_current.get("model_signal_counts", {}),
        },
        "shadow_center": {
            "matches": len(shadow_center) if isinstance(shadow_center, list) else shadow_center.get("matches_count", 0),
            "model_signal_counts": {} if isinstance(shadow_center, list) else shadow_center.get("model_signal_counts", {}),
        },
        "contract": {
            "raw_model_fields_preserved": True,
            "raw_autolearn_preserved": True,
            "raw_shadow_files_preserved": True,
            "operator_filter_fail_closed": True,
            "prices_used": False,
        },
    }

    # Only the additive PLAYABLE layer is persisted into results. RAW model
    # ladders and AutoLearn remain byte-for-byte equivalent in substance.
    _write(RESULTS, projected_results)
    _write(HISTORY, history)
    _write(STATS, stats)

    meta = _read(META, {})
    if not isinstance(meta, dict):
        meta = {}
    meta["superbet_playable_v912"] = {
        "version": VERSION,
        "operator": OPERATOR,
        "matches": stats["matches"],
        "signals": stats["signals"],
        "raw_preserved": True,
        "updated_at": stats["generated_at"],
    }
    _write(META, meta)
    return stats


def main():
    mode = str(sys.argv[1] if len(sys.argv) > 1 else "project").strip().casefold()
    if mode == "inject":
        result = inject()
    elif mode == "project":
        result = project()
    else:
        raise SystemExit("usage: superbet_playable.py [inject|project]")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
