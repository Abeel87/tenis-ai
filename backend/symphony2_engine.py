from __future__ import annotations

"""Symfonia 2.0 operator-first runtime.

Current Superbet selections are the candidate universe. MODEL/RAW may provide
features, but it may never introduce a line into the actionable universe.
"""

from copy import deepcopy
from datetime import datetime, timezone
from itertools import combinations
import json
import math
from pathlib import Path

try:
    from .symphony2_learning import feature_row, train_operator_line_model, VERSION as LEARNING_VERSION
    from .superbet_playable_v912 import signal_signature
except ImportError:
    from symphony2_learning import feature_row, train_operator_line_model, VERSION as LEARNING_VERSION
    from superbet_playable_v912 import signal_signature

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"
RESULTS = DATA / "results.json"
HISTORY = DATA / "history.json"
CURRENT = DATA / "symphony2_current.json"
STATS = DATA / "symphony2_stats.json"
VERSION = "symphony2-runtime-1"
OPERATOR = "superbet.pl"
LINE_MARKETS = {
    "match_total", "set1_total", "set2_total", "set3_total", "total_sets",
    "match_game_handicap", "set1_game_handicap", "set2_game_handicap",
    "player_total_games", "match_total_aces", "player_aces", "player_double_faults",
}
MIN_ACTIONABLE_P = 0.55
TOP_POOL = 14


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
    return " ".join(str(value or "").strip().casefold().split())


def _market(value) -> str:
    return _norm(value).replace(" ", "_")


def _operator_context(match: dict) -> dict | None:
    ctx = match.get("superbet_market_v91")
    if not isinstance(ctx, dict):
        return None
    if ctx.get("operator_verified") is not True or ctx.get("status") != "VERIFIED":
        return None
    return ctx


def _current_offer(match: dict) -> list[dict]:
    ctx = _operator_context(match)
    if not ctx:
        return []
    out = []
    for raw in ctx.get("canonical_selections") or []:
        if not isinstance(raw, dict) or raw.get("operator_available") is False:
            continue
        market = _market(raw.get("market"))
        if market in LINE_MARKETS:
            # Symfonia 2 does not accept catalogue/global/model-line evidence.
            if raw.get("fixture_line_verified") is not True:
                continue
            if _num(raw.get("line")) is None:
                continue
        row = dict(raw)
        row["market"] = market
        out.append(row)
    return out


def _model_index(match: dict) -> dict:
    ctx = _operator_context(match) or {}
    out = {}
    for raw in ctx.get("model_signals") or []:
        if not isinstance(raw, dict) or raw.get("operator_line_verified") is not True:
            continue
        out[signal_signature(raw)] = raw
    return out


def _merge_model_features(selection: dict, model_row: dict | None) -> dict:
    out = dict(selection)
    if not isinstance(model_row, dict):
        return out
    for key in ("score", "current", "catboost", "tabpfn", "model_scores", "adaptive_prod_v79"):
        if model_row.get(key) is not None:
            out[key] = deepcopy(model_row.get(key))
    return out


def _label(row: dict) -> str:
    if row.get("label"):
        return str(row["label"])
    market = str(row.get("market") or "rynek")
    pick = str(row.get("pick") or "")
    line = _num(row.get("line"))
    player = str(row.get("player") or "").strip()
    parts = [market, player, pick]
    if line is not None:
        parts.append(f"{line:g}")
    return " · ".join(x for x in parts if x)


def _selection_id(row: dict) -> str:
    return "|".join(map(str, signal_signature(row)))


def _score_offer(match: dict, model) -> list[dict]:
    models = _model_index(match)
    rows = []
    for selection in _current_offer(match):
        sig = signal_signature(selection)
        merged = _merge_model_features(selection, models.get(sig))
        features = feature_row(match, merged)
        p = model.predict(features) if model.ready else None
        row = {
            "selection_id": _selection_id(selection),
            "market": selection.get("market"),
            "pick": selection.get("pick"),
            "line": selection.get("line"),
            "checkpoint": selection.get("checkpoint"),
            "player": selection.get("player"),
            "label": _label(selection),
            "operator": OPERATOR,
            "operator_market_id": selection.get("market_id"),
            "operator_outcome_id": selection.get("outcome_id"),
            "fixture_line_verified": selection.get("fixture_line_verified", selection.get("market") not in LINE_MARKETS),
            "operator_line_source": selection.get("operator_line_source"),
            "operator_model_probability": round(p * 100.0, 2) if p is not None else None,
            "base_model_score": _num(merged.get("score")),
            "learning_model_ready": model.ready,
        }
        rows.append(row)
    rows.sort(key=lambda x: (_num(x.get("operator_model_probability"), -1.0), _num(x.get("base_model_score"), -1.0)), reverse=True)
    return rows


def _same_market_conflict(a: dict, b: dict) -> bool:
    ma, mb = _market(a.get("market")), _market(b.get("market"))
    if ma != mb:
        return False
    if ma == "game_state":
        return _num(a.get("checkpoint"), 0) == _num(b.get("checkpoint"), 0)
    # A bookmaker builder normally does not need two legs from one exact market
    # family; forbidding this also prevents trivial nested O20.5 + O21.5 stacks.
    return True


def _compatible(selection: tuple[dict, ...]) -> bool:
    for i, a in enumerate(selection):
        for b in selection[i + 1:]:
            if _same_market_conflict(a, b):
                return False
    return True


def _composition_score(selection: tuple[dict, ...]) -> tuple[float, float]:
    ps = [max(0.001, min(0.999, _num(x.get("operator_model_probability"), 0.0) / 100.0)) for x in selection]
    if not ps or any(p <= 0.0 for p in ps):
        return 0.0, 0.0
    geometric = math.exp(sum(math.log(p) for p in ps) / len(ps))
    weakest = min(ps)
    # Ranking utility only. It is deliberately NOT called joint probability.
    utility = 100.0 * (0.72 * geometric + 0.28 * weakest)
    independent_product = math.prod(ps) * 100.0
    return utility, independent_product


def _best_compositions(scored: list[dict]) -> dict:
    pool = [x for x in scored if _num(x.get("operator_model_probability"), 0.0) >= MIN_ACTIONABLE_P * 100.0][:TOP_POOL]
    out = {}
    for n in range(2, 7):
        best = None
        for combo in combinations(pool, n):
            if not _compatible(combo):
                continue
            utility, independent = _composition_score(combo)
            candidate = {
                "legs": n,
                "score": round(utility, 2),
                "independent_product_reference": round(independent, 3),
                "joint_probability": None,
                "joint_status": "PENDING_EXACT_SHARED_STATE_ENGINE",
                "selection": [dict(x) for x in combo],
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate
        if best:
            out[str(n)] = best
    return out


def build(results: list[dict], history: list[dict]) -> tuple[dict, dict]:
    model = train_operator_line_model(history)
    matches = []
    fixture_count = selection_count = actionable_count = 0
    for match in results or []:
        if not isinstance(match, dict) or not _operator_context(match):
            continue
        scored = _score_offer(match, model)
        fixture_count += 1
        selection_count += len(scored)
        actionable_count += sum(1 for x in scored if _num(x.get("operator_model_probability"), 0.0) >= MIN_ACTIONABLE_P * 100.0)
        comps = _best_compositions(scored) if model.ready else {}
        matches.append({
            "match_key": str(match.get("match_id") if match.get("match_id") is not None else match.get("id") or ""),
            "id": match.get("match_id") if match.get("match_id") is not None else match.get("id"),
            "p1": match.get("p1"), "p2": match.get("p2"),
            "scheduled_time": match.get("scheduled_time"),
            "tour": match.get("tour"), "surface": match.get("surface"), "best_of": match.get("best_of"),
            "offer_selections": len(scored),
            "scored_selections": scored,
            "compositions": comps,
            "recommended_leg_count": int(max(comps.items(), key=lambda x: x[1]["score"])[0]) if comps else None,
        })

    current = {
        "version": VERSION,
        "learning_version": LEARNING_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "operator": OPERATOR,
        "architecture": "CURRENT_SUPERBET_OFFER -> EXACT_SELECTION_SCORE -> SYMPHONY2",
        "model_status": model.status,
        "matches_count": len(matches),
        "matches": matches,
    }
    stats = {
        "version": VERSION,
        "generated_at": current["generated_at"],
        "operator": OPERATOR,
        "model_status": model.status,
        "training": model.metrics or {"version": LEARNING_VERSION, "training_rows": model.trained_rows},
        "current_offer": {
            "verified_fixtures": fixture_count,
            "exact_operator_selections": selection_count,
            "selections_above_actionable_threshold": actionable_count,
            "threshold": MIN_ACTIONABLE_P * 100.0,
        },
        "legacy_symphony_stats_used": False,
        "prices_used": False,
    }
    return current, stats


def run() -> dict:
    results = _read(RESULTS, [])
    history = _read(HISTORY, [])
    if not isinstance(results, list) or not results:
        raise RuntimeError("results.json missing/empty")
    if not isinstance(history, list):
        raise RuntimeError("history.json invalid")
    current, stats = build(results, history)
    _write(CURRENT, current)
    _write(STATS, stats)
    return {
        "status": "OK",
        "version": VERSION,
        "model_status": current["model_status"],
        "matches": current["matches_count"],
        **stats["current_offer"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
