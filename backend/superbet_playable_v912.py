from __future__ import annotations

"""Tenis AI v9.1.2 — global Superbet PLAYABLE projection.

Core models stay independent and keep their raw internal ladders. This module is
used only *after* the core/AutoLearn prediction work:

- ``inject`` adds verified real Superbet selections to the current AutoLearn
  signal stream before Player Intelligence / SHADOW current scoring, so those
  models can score the same real operator lines;
- ``project`` runs after model guards and turns frontend-facing result ladders
  into a PLAYABLE view, filters SHADOW feeds, freezes separate operator-aware
  history layers, and publishes separate PLAYABLE statistics.

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
        if isinstance(row, dict) and row.get("operator_available") is not False:
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
        return True
    market = _market(signal.get("market"))
    if market not in STRICT_MARKETS:
        return False
    return signal_signature(signal) in operator_availability(match)


def _operator_meta(row: dict, available: dict | None = None) -> dict:
    out = dict(row)
    out.update({
        "operator": OPERATOR,
        "operator_available": True,
        "operator_line_verified": True,
        "operator_line_source": "oddspapi_superbet_pl",
        "operator_playable": True,
        "operator_projection_version": VERSION,
    })
    if isinstance(available, dict):
        out["operator_market_id"] = available.get("market_id")
        out["operator_outcome_id"] = available.get("outcome_id")
        out["operator_main_line"] = bool(available.get("main_line", False))
    return out


def _injected_signal(row: dict, available: dict | None = None) -> dict:
    out = _operator_meta(row, available)
    score = _num(out.get("score"), _num(out.get("symphony_raw_probability")))
    if score is not None:
        out.setdefault("current", round(score, 1))
        # AutoLearn itself did not score a newly-created operator line. Keep a
        # fallback only so downstream generic SHADOW feature builders can inspect
        # the line; statistics explicitly do not count it as a learned ensemble.
        out.setdefault("ensemble", round(score, 1))
        out["operator_projection_fallback"] = True
        out["ensemble_score_kind"] = "current_model_fallback_not_learned_ensemble"
    out.setdefault("support", 0)
    out.setdefault("dynamic_weighting", {
        "version": VERSION,
        "active": False,
        "status": "OPERATOR_LINE_CURRENT_FALLBACK",
        "reason": "real_line_was_not_in_original_autolearn_candidate_grid",
    })
    out.setdefault("local_weights", {"current": 1.0})
    return out


def inject_match(match: dict) -> tuple[dict, dict]:
    """Add real operator lines after AutoLearn, without deleting raw diagnostics."""
    m = dict(match)
    if not operator_context_active(m):
        return m, {"active": False, "added": 0, "verified_existing": 0}

    available = operator_availability(m)
    model_signals = operator_model_signals(m)
    auto = dict(m.get("autolearn_v84") or {})
    rows = [dict(x) for x in (auto.get("signals") or []) if isinstance(x, dict)]
    seen = set()
    verified_existing = 0

    for i, row in enumerate(rows):
        sig = signal_signature(row)
        seen.add(sig)
        if sig in available:
            verified_existing += 1
            row = _operator_meta(row, available[sig])
            if sig in model_signals:
                row["operator_model_probability"] = _num(model_signals[sig].get("score"))
            rows[i] = row
        elif _market(row.get("market")) in STRICT_MARKETS:
            row["operator_playable"] = False
            row["operator_projection_version"] = VERSION
            row["operator_note"] = "raw_analysis_only_not_in_current_superbet_offer"
            rows[i] = row

    added = 0
    for sig, row in model_signals.items():
        if sig in seen:
            continue
        rows.append(_injected_signal(row, available.get(sig)))
        seen.add(sig)
        added += 1

    auto["signals"] = rows
    old_by_key = auto.get("by_key") or {}
    by_key = dict(old_by_key) if isinstance(old_by_key, dict) else {}
    for row in rows:
        key = str(row.get("key") or "")
        if key:
            previous = by_key.get(key)
            by_key[key] = {**(previous if isinstance(previous, dict) else {}), **row}
    auto["by_key"] = by_key
    auto["superbet_playable_v912"] = {
        "active": True,
        "operator": OPERATOR,
        "verified_existing": verified_existing,
        "operator_lines_added_for_downstream_models": added,
        "raw_signals_preserved_for_diagnostics": True,
        "prices_used": False,
    }
    m["autolearn_v84"] = auto
    return m, {"active": True, "added": added, "verified_existing": verified_existing}


def inject_results(results: list[dict]) -> tuple[list[dict], dict]:
    out = []
    active = added = existing = 0
    for raw in results or []:
        if not isinstance(raw, dict):
            continue
        row, info = inject_match(raw)
        active += int(info["active"])
        added += int(info["added"])
        existing += int(info["verified_existing"])
        out.append(row)
    return out, {"matches_active": active, "signals_added": added, "verified_existing": existing}


def _signals_by_market(match: dict) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in (match.get("superbet_market_v91") or {}).get("model_signals") or []:
        if isinstance(row, dict) and row.get("operator_line_verified") is True:
            groups[_market(row.get("market"))].append(row)
    return groups


def _player_map(rows: list[dict]) -> dict:
    out = {}
    for row in rows:
        score = _num(row.get("score"))
        pick = row.get("pick")
        if score is not None and pick:
            out[str(pick)] = round(score, 1)
    return out


def _ou_map(rows: list[dict]) -> dict:
    out = {}
    for row in rows:
        line, score = _num(row.get("line")), _num(row.get("score"))
        pick = _pick(row.get("pick"), _market(row.get("market")))
        if line is None or score is None or pick not in {"over", "under"}:
            continue
        key = f"{line:.1f}"
        out.setdefault(key, {})[pick] = round(score, 1)
    return dict(sorted(out.items(), key=lambda kv: float(kv[0])))


def _score_map(rows: list[dict]) -> dict:
    out = {}
    for row in rows:
        score = _num(row.get("score"))
        pick = row.get("pick")
        if score is not None and pick:
            out[str(pick).replace("-", ":")] = round(score, 1)
    return out


def _state_map(rows: list[dict]) -> dict:
    out = {}
    for row in rows:
        cp = int(_num(row.get("checkpoint"), 0) or 0)
        score = _num(row.get("score"))
        pick = row.get("pick")
        if cp in {2, 4, 6} and score is not None and pick:
            out.setdefault(str(cp), {})[str(pick).replace("-", ":")] = round(score, 1)
    return out


def _total_sets_display(rows: list[dict]) -> dict:
    out = {}
    for row in rows:
        line, score = _num(row.get("line")), _num(row.get("score"))
        pick = _pick(row.get("pick"), "total_sets")
        if line is None or score is None or pick not in {"over", "under"}:
            continue
        out[f"{'OVER' if pick == 'over' else 'UNDER'} {line:g}"] = round(score, 1)
    return out


def _serve_props_analysis_only(match: dict) -> dict | None:
    props = match.get("serve_props_v72")
    if not isinstance(props, dict):
        return props
    out = dict(props)
    for side in ("p1", "p2"):
        block = out.get(side)
        if not isinstance(block, dict):
            continue
        sb = dict(block)
        for field in ("aces", "double_faults"):
            mb = sb.get(field)
            if not isinstance(mb, dict):
                continue
            x = dict(mb)
            if isinstance(x.get("lines"), dict) and x.get("lines"):
                x.setdefault("analysis_lines", x.get("lines"))
            x["lines"] = {}
            x["operator_lines_verified"] = False
            x["display_note"] = "średnia modelowa; brak indywidualnych player props w zweryfikowanym feedzie Superbet"
            sb[field] = x
        out[side] = sb
    out["operator_projection_version"] = VERSION
    out["operator_player_props_actionable"] = False
    return out


def project_match_for_display(match: dict) -> tuple[dict, dict]:
    m = dict(match)
    if not operator_context_active(m):
        m["superbet_playable_v912"] = {
            "version": VERSION, "active": False, "status": "NO_VERIFIED_OPERATOR_MATCH",
            "raw_analysis_preserved": True,
        }
        return m, {"active": False, "suppressed": 0, "playable": 0}

    groups = _signals_by_market(m)
    raw_total = 0
    for field in ("match_win", "first_set_win", "second_set_win", "third_set_win", "over_under", "match_over_under", "exact_first_set", "exact_match_score", "game_states", "total_sets"):
        value = m.get(field)
        if isinstance(value, dict):
            raw_total += len(value)

    m["match_win"] = _player_map(groups.get("match_winner", [])) or None
    m["first_set_win"] = _player_map(groups.get("set1_winner", [])) or None
    m["second_set_win"] = _player_map(groups.get("set2_winner", [])) or None
    m["third_set_win"] = _player_map(groups.get("set3_winner", [])) or None
    m["over_under"] = _ou_map(groups.get("set1_total", [])) or None
    m["match_over_under"] = _ou_map(groups.get("match_total", [])) or None
    m["exact_first_set"] = _score_map(groups.get("set1_exact_score", [])) or None
    m["exact_match_score"] = _score_map(groups.get("exact_match_score", [])) or None
    m["game_states"] = _state_map(groups.get("game_state", [])) or None
    m["total_sets"] = _total_sets_display(groups.get("total_sets", [])) or None

    # Current OddsPapi Free feed does not expose individual tennis player props.
    # Keep means/diagnostics, but never display model-made ace/DF ladders as bets.
    has_individual_props = bool(groups.get("player_aces") or groups.get("player_double_faults"))
    if not has_individual_props:
        m["serve_props_v72"] = _serve_props_analysis_only(m)

    auto = dict(m.get("autolearn_v84") or {})
    if isinstance(auto.get("signals"), list):
        playable = [dict(x) for x in auto["signals"] if isinstance(x, dict) and is_operator_playable_signal(m, x)]
        auto["analysis_signals_v912"] = [
            dict(x) for x in auto["signals"]
            if isinstance(x, dict) and not is_operator_playable_signal(m, x)
        ]
        auto["signals"] = playable
        auto["by_key"] = {str(x.get("key")): x for x in playable if x.get("key")}
        auto["operator_view"] = "PLAYABLE_SUPERBET_ONLY"
        m["autolearn_v84"] = auto

    playable_count = sum(len(v) for v in groups.values())
    suppressed = max(0, raw_total - playable_count)
    m["superbet_playable_v912"] = {
        "version": VERSION,
        "active": True,
        "status": "PLAYABLE_SUPERBET_ONLY",
        "operator": OPERATOR,
        "playable_model_signals": playable_count,
        "raw_display_groups": raw_total,
        "suppressed_raw_groups_estimate": suppressed,
        "prices_used": False,
        "raw_models_trained_unchanged": True,
    }
    return m, {"active": True, "suppressed": suppressed, "playable": playable_count}


def _match_key(row: dict) -> str:
    mid = row.get("match_id") if row.get("match_id") is not None else row.get("id")
    if mid is not None and str(mid) != "":
        return f"id:{mid}"
    return "|".join([
        _name_key(row.get("p1")), _name_key(row.get("p2")),
        str(row.get("scheduled_time") or "")[:10], _norm(row.get("tournament")),
    ])


def _result_index(results: list[dict]) -> dict:
    return {_match_key(m): m for m in results if isinstance(m, dict)}


def _filter_shadow_feed(data, results_index: dict):
    if isinstance(data, list):
        rows = []
        for raw in data:
            if not isinstance(raw, dict):
                continue
            row = dict(raw)
            match = results_index.get(_match_key(row))
            if match and operator_context_active(match):
                sigs = [dict(x) for x in (row.get("signals") or []) if isinstance(x, dict) and is_operator_playable_signal(match, x)]
                row["signals"] = sigs
                row["operator_view"] = "PLAYABLE_SUPERBET_ONLY"
            rows.append(row)
        return rows
    if isinstance(data, dict) and isinstance(data.get("matches"), list):
        out = dict(data)
        matches = []
        counts = defaultdict(int)
        for raw in data.get("matches") or []:
            if not isinstance(raw, dict):
                continue
            row = dict(raw)
            match = results_index.get(_match_key(row))
            if match and operator_context_active(match):
                sigs = [dict(x) for x in (row.get("signals") or []) if isinstance(x, dict) and is_operator_playable_signal(match, x)]
                row["signals"] = sigs
                row["operator_view"] = "PLAYABLE_SUPERBET_ONLY"
            for signal in row.get("signals") or []:
                for model_id in (signal.get("scores") or {}):
                    counts[str(model_id)] += 1
            if row.get("signals"):
                matches.append(row)
        out["matches"] = matches
        out["matches_count"] = len(matches)
        if counts:
            out["model_signal_counts"] = dict(sorted(counts.items()))
        out["operator_projection"] = {
            "version": VERSION, "view": "PLAYABLE_SUPERBET_ONLY", "prices_used": False,
        }
        return out
    return data


def _history_signal(row: dict, source_model: str, score=None) -> dict:
    out = {
        "id": str(row.get("key") or "|".join(map(str, signal_signature(row)))),
        "key": row.get("key"),
        "label": row.get("label"),
        "market": _market(row.get("market")),
        "pick": row.get("pick"),
        "line": row.get("line"),
        "checkpoint": row.get("checkpoint"),
        "player": row.get("player"),
        "score": round(float(score if score is not None else _num(row.get("score"), 0.0)), 1),
        "result": "pending",
        "source_model": source_model,
        "operator": OPERATOR,
        "operator_playable": True,
        "operator_line_verified": True,
        "operator_projection_version": VERSION,
    }
    return {k: v for k, v in out.items() if v is not None}


def _freeze_history_layers(history: list[dict], results: list[dict], shadow_center: dict) -> tuple[list[dict], dict]:
    rindex = _result_index(results)
    sindex = {_match_key(m): m for m in (shadow_center.get("matches") or []) if isinstance(m, dict)} if isinstance(shadow_center, dict) else {}
    captured_base = captured_auto = captured_shadow = captured_lab = 0
    out = []

    for raw in history or []:
        if not isinstance(raw, dict):
            continue
        e = dict(raw)
        if e.get("status") not in ("pending", "upcoming"):
            out.append(e)
            continue
        match = rindex.get(_match_key(e))
        if not match or not operator_context_active(match):
            out.append(e)
            continue

        if not e.get("playable_signals_v912"):
            rows = []
            for signal in (match.get("superbet_market_v91") or {}).get("model_signals") or []:
                market = _market(signal.get("market"))
                score = _num(signal.get("score"))
                if market in SETTLE_SUPPORTED and score is not None and score >= GREEN_THRESHOLD:
                    rows.append(_history_signal(signal, "current_prod", score))
            if rows:
                e["playable_signals_v912"] = rows
                e["playable_captured_at_v912"] = e.get("captured_at") or datetime.now(timezone.utc).isoformat()
                captured_base += len(rows)

        if not e.get("playable_shadow_lab_v912"):
            rows = []
            for signal in (match.get("superbet_market_v91") or {}).get("model_signals") or []:
                market = _market(signal.get("market"))
                score = _num(signal.get("score"))
                if market in SETTLE_SUPPORTED and score is not None and SHADOW_MIN_THRESHOLD <= score < GREEN_THRESHOLD:
                    rows.append(_history_signal(signal, "shadow_lab_v78e6", score))
            if rows:
                e["playable_shadow_lab_v912"] = rows
                captured_lab += len(rows)

        if not e.get("playable_autolearn_signals_v912"):
            rows = []
            for signal in ((match.get("autolearn_v84") or {}).get("signals") or []):
                if not isinstance(signal, dict) or not is_operator_playable_signal(match, signal):
                    continue
                market = _market(signal.get("market"))
                if market not in SETTLE_SUPPORTED:
                    continue
                ensemble = _num(signal.get("ensemble"))
                current = _num(signal.get("current"), _num(signal.get("score")))
                row = _history_signal(signal, "ensemble_v84", ensemble if ensemble is not None else current)
                row["model_scores"] = {
                    "current": current,
                    "catboost": _num(signal.get("catboost")),
                    "tabpfn": _num(signal.get("tabpfn")),
                    "ensemble": ensemble,
                }
                row["ensemble_fallback_only"] = bool(signal.get("operator_projection_fallback"))
                adaptive = signal.get("adaptive_prod_v79")
                if isinstance(adaptive, dict):
                    row["adaptive_prod_v79"] = adaptive
                rows.append(row)
            if rows:
                e["playable_autolearn_signals_v912"] = rows
                captured_auto += len(rows)

        if not e.get("playable_shadow_models_v912"):
            sm = sindex.get(_match_key(e))
            rows = []
            for signal in (sm.get("signals") or []) if isinstance(sm, dict) else []:
                if _market(signal.get("market")) not in SETTLE_SUPPORTED:
                    continue
                for model_id, value in (signal.get("scores") or {}).items():
                    score = _num(value)
                    if score is None or score < SHADOW_MIN_THRESHOLD:
                        continue
                    row = _history_signal(signal, str(model_id), score)
                    rows.append(row)
            if rows:
                e["playable_shadow_models_v912"] = rows
                captured_shadow += len(rows)

        out.append(e)
    return out, {
        "base": captured_base, "shadow_lab": captured_lab,
        "autolearn": captured_auto, "shadow_models": captured_shadow,
    }


def _summary(rows: list[dict], threshold: float) -> dict:
    selected = [r for r in rows if r.get("result") in {"hit", "miss"} and _num(r.get("score"), -1) >= threshold]
    hits = sum(1 for r in selected if r.get("result") == "hit")
    return {
        "settled": len(selected),
        "hits": hits,
        "misses": len(selected) - hits,
        "accuracy": round(100.0 * hits / len(selected), 1) if selected else None,
        "threshold": threshold,
    }


def _playable_stats(history: list[dict], results: list[dict], shadow_center: dict, projection_info: dict) -> dict:
    base_rows = []
    shadow_lab_rows = []
    auto_models: dict[str, list[dict]] = defaultdict(list)
    shadow_models: dict[str, list[dict]] = defaultdict(list)

    for e in history or []:
        if not isinstance(e, dict):
            continue
        base_rows.extend(x for x in (e.get("playable_signals_v912") or []) if isinstance(x, dict))
        shadow_lab_rows.extend(x for x in (e.get("playable_shadow_lab_v912") or []) if isinstance(x, dict))
        for row in e.get("playable_autolearn_signals_v912") or []:
            if not isinstance(row, dict) or row.get("result") not in {"hit", "miss"}:
                continue
            result = row.get("result")
            scores = row.get("model_scores") or {}
            for model_id in ("current", "catboost", "tabpfn", "ensemble"):
                score = _num(scores.get(model_id))
                if score is None:
                    continue
                if model_id == "ensemble" and row.get("ensemble_fallback_only"):
                    continue
                auto_models[model_id].append({"result": result, "score": score})
            adaptive = row.get("adaptive_prod_v79") or {}
            score = _num(adaptive.get("final_score")) if isinstance(adaptive, dict) else None
            if score is not None:
                auto_models["adaptive_prod"].append({"result": result, "score": score})
        for row in e.get("playable_shadow_models_v912") or []:
            if not isinstance(row, dict):
                continue
            shadow_models[str(row.get("source_model") or "shadow")].append(row)

    verified = sum(1 for m in results if isinstance(m, dict) and operator_context_active(m))
    model_ready = sum(1 for m in results if isinstance(m, dict) and m.get("model_ready"))
    verified_model_ready = sum(1 for m in results if isinstance(m, dict) and m.get("model_ready") and operator_context_active(m))
    current_playable = sum(
        1 for m in results if isinstance(m, dict) and operator_context_active(m)
        for s in ((m.get("superbet_market_v91") or {}).get("model_signals") or [])
        if isinstance(s, dict) and _num(s.get("score"), -1) >= GREEN_THRESHOLD
    )
    shadow_counts = shadow_center.get("model_signal_counts") if isinstance(shadow_center, dict) else {}

    models = {
        "current_prod": _summary(base_rows, GREEN_THRESHOLD),
        "shadow_lab_v78e6": _summary(shadow_lab_rows, SHADOW_MIN_THRESHOLD),
    }
    for model_id, rows in sorted(auto_models.items()):
        models[f"autolearn_{model_id}"] = _summary(rows, MODEL_SELECT_THRESHOLD)
    for model_id, rows in sorted(shadow_models.items()):
        models[f"shadow_{model_id}"] = _summary(rows, MODEL_SELECT_THRESHOLD)

    return {
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "operator": OPERATOR,
        "mode": "PLAYABLE_SUPERBET_ONLY",
        "prices_used": False,
        "current": {
            "model_ready_matches": model_ready,
            "verified_superbet_matches": verified,
            "verified_model_ready_matches": verified_model_ready,
            "verified_match_coverage": round(verified_model_ready / model_ready, 4) if model_ready else 0.0,
            "playable_green_signals": current_playable,
            "shadow_model_signal_counts": shadow_counts if isinstance(shadow_counts, dict) else {},
            "suppressed_raw_display_estimate": int(projection_info.get("suppressed", 0)),
        },
        "models": models,
        "contract": {
            "raw_model_training_unchanged": True,
            "playable_stats_use_only_frozen_operator_verified_signals": True,
            "legacy_history_without_operator_snapshot_excluded": True,
            "unavailable_lines_never_count_as_playable_miss_or_hit": True,
            "bookmaker_prices_not_used": True,
            "sample_starts_with_version": VERSION,
        },
    }


def _update_meta(mode: str, info: dict) -> None:
    meta = _read(META, {})
    meta = meta if isinstance(meta, dict) else {}
    meta["superbet_playable_v912"] = {
        "version": VERSION,
        "mode": mode,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "prices_used": False,
        **info,
    }
    _write(META, meta)


def inject() -> dict:
    rows = _read(RESULTS, [])
    rows = rows if isinstance(rows, list) else []
    injected, info = inject_results(rows)
    _write(RESULTS, injected)
    _update_meta("inject", info)
    return {"status": "OK", "version": VERSION, "mode": "inject", **info}


def project() -> dict:
    rows = _read(RESULTS, [])
    rows = rows if isinstance(rows, list) else []
    projected = []
    active = suppressed = playable = 0
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        row, info = project_match_for_display(raw)
        active += int(info["active"])
        suppressed += int(info["suppressed"])
        playable += int(info["playable"])
        projected.append(row)
    _write(RESULTS, projected)

    rindex = _result_index(projected)
    shadow_current = _filter_shadow_feed(_read(SHADOW_CURRENT, []), rindex)
    shadow_center = _filter_shadow_feed(_read(SHADOW_CENTER, {}), rindex)
    _write(SHADOW_CURRENT, shadow_current)
    _write(SHADOW_CENTER, shadow_center)

    history = _read(HISTORY, [])
    history = history if isinstance(history, list) else []
    history, captured = _freeze_history_layers(history, projected, shadow_center if isinstance(shadow_center, dict) else {})
    _write(HISTORY, history)

    pinfo = {"matches_active": active, "suppressed": suppressed, "playable": playable}
    stats = _playable_stats(history, projected, shadow_center if isinstance(shadow_center, dict) else {}, pinfo)
    _write(STATS, stats)
    _update_meta("project", {**pinfo, "history_captured": captured})
    return {
        "status": "OK", "version": VERSION, "mode": "project",
        **pinfo, "history_captured": captured,
        "playable_stats_models": len(stats.get("models") or {}),
    }


def main():
    mode = str(sys.argv[1] if len(sys.argv) > 1 else "project").strip().casefold()
    if mode == "inject":
        result = inject()
    elif mode == "project":
        result = project()
    else:
        raise SystemExit("usage: superbet_playable_v912.py [inject|project]")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
