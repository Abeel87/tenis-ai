from __future__ import annotations

"""Symfonia 2.0 operator-first runtime.

The current Superbet offer is the only actionable candidate universe. Exact
state probability and existing model outputs are features of one supervised,
calibrated operator-line model; no hand-written percentage blend creates P_final.
"""

from copy import deepcopy
from datetime import datetime, timezone
from itertools import combinations
import json
import math
from pathlib import Path

try:
    from .symphony2_learning import feature_row, train_operator_line_model, VERSION as LEARNING_VERSION, FULL_SUPPORT_ROWS
    from .symphony2_state import build_outcomes, marginal_probability, joint_probability, VERSION as STATE_VERSION
    from .superbet_playable_v912 import signal_signature
except ImportError:
    from symphony2_learning import feature_row, train_operator_line_model, VERSION as LEARNING_VERSION, FULL_SUPPORT_ROWS
    from symphony2_state import build_outcomes, marginal_probability, joint_probability, VERSION as STATE_VERSION
    from superbet_playable_v912 import signal_signature

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"
RESULTS = DATA / "results.json"
HISTORY = DATA / "history.json"
CURRENT = DATA / "symphony2_current.json"
STATS = DATA / "symphony2_stats.json"
VERSION = "symphony2-runtime-6"
OPERATOR = "superbet.pl"
LINE_MARKETS = {
    "match_total", "set1_total", "set2_total", "set3_total", "total_sets",
    "match_game_handicap", "set1_game_handicap", "set2_game_handicap",
    "player_total_games", "match_total_aces", "player_aces", "player_double_faults",
}
MIN_ACTIONABLE_P = 0.55
TOP_POOL = 16


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


def _scheduled_utc(match: dict) -> datetime | None:
    raw = str(match.get("scheduled_time") or "").strip()
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_current_pre_match_fixture(match: dict, now: datetime | None = None) -> bool:
    scheduled = _scheduled_utc(match)
    if scheduled is None:
        return True
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    else:
        reference = reference.astimezone(timezone.utc)
    return scheduled > reference


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
            if raw.get("fixture_line_verified") is not True or _num(raw.get("line")) is None:
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
    market, pick = str(row.get("market") or "rynek"), str(row.get("pick") or "")
    line, player = _num(row.get("line")), str(row.get("player") or "").strip()
    parts = [market, player, pick]
    if line is not None:
        parts.append(f"{line:g}")
    return " · ".join(x for x in parts if x)


def _selection_id(row: dict) -> str:
    return "|".join(map(str, signal_signature(row)))


def _existing_evidence(merged: dict) -> dict:
    adaptive = _num((merged.get("adaptive_prod_v79") or {}).get("final_score"))
    scores = merged.get("model_scores") or {}
    return {
        "base": _num(merged.get("score")),
        "current": _num(scores.get("current"), _num(merged.get("current"))),
        "catboost": _num(scores.get("catboost"), _num(merged.get("catboost"))),
        "tabpfn": _num(scores.get("tabpfn"), _num(merged.get("tabpfn"))),
        "adaptive": adaptive,
    }


COHERENT_WINNER_MARKETS = {"match_winner", "set1_winner", "set2_winner", "set3_winner"}
COHERENT_OU_MARKETS = {
    "match_total", "set1_total", "set2_total", "set3_total", "total_sets",
    "player_total_games", "match_total_aces", "player_aces", "player_double_faults",
}


def _coherence_pick(value) -> str:
    raw = _norm(value)
    if raw in {"o", "over", "powyzej"} or raw.startswith("over "):
        return "over"
    if raw in {"u", "under", "ponizej"} or raw.startswith("under "):
        return "under"
    return raw


def _cohere_exclusive_probabilities(rows: list[dict]) -> list[dict]:
    groups = {}
    for row in rows or []:
        p = _num(row.get("operator_model_probability"))
        if p is None:
            continue
        market = _market(row.get("market"))
        if market in COHERENT_WINNER_MARKETS:
            key = ("winner", market)
        elif market in COHERENT_OU_MARKETS and _coherence_pick(row.get("pick")) in {"over", "under"}:
            line = _num(row.get("line"))
            if line is None:
                continue
            key = ("ou", market, round(line, 6), _norm(row.get("player")), int(_num(row.get("checkpoint"), 0) or 0))
        else:
            continue
        groups.setdefault(key, []).append(row)
    for key, group in groups.items():
        if key[0] == "winner":
            if len(group) != 2:
                continue
        else:
            picks = {_coherence_pick(row.get("pick")) for row in group}
            if len(group) != 2 or picks != {"over", "under"}:
                continue
        total = sum(_num(row.get("operator_model_probability"), 0.0) or 0.0 for row in group)
        if total <= 0:
            continue
        normalized = []
        for row in group:
            before = float(_num(row.get("operator_model_probability"), 0.0) or 0.0)
            normalized.append((row, before, before * 100.0 / total))
        running = 0.0
        for idx, (row, before, after) in enumerate(normalized):
            final = round(100.0 - running, 2) if idx == len(normalized) - 1 else round(after, 2)
            running += final
            row["operator_model_probability_pre_coherence"] = round(before, 2)
            row["operator_model_probability"] = final
            row["probability_coherence"] = "NORMALIZED_EXCLUSIVE_GROUP"
    return rows


def _score_offer(match: dict, model, outcomes: list[dict]) -> list[dict]:
    models = _model_index(match)
    rows = []
    for selection in _current_offer(match):
        sig = signal_signature(selection)
        merged = _merge_model_features(selection, models.get(sig))
        state_p = marginal_probability(match, selection, outcomes) if outcomes else None
        merged["state_probability"] = state_p * 100.0 if state_p is not None else -1.0
        features = feature_row(match, merged)
        diagnostics = model.predict_diagnostics(features) if model.ready else None
        learned = diagnostics["final"] if diagnostics else None
        support = diagnostics["support"] if diagnostics else 0
        rows.append({
            "selection_id": _selection_id(selection), "market": selection.get("market"), "pick": selection.get("pick"),
            "line": selection.get("line"), "checkpoint": selection.get("checkpoint"), "player": selection.get("player"),
            "label": _label(selection), "operator": OPERATOR, "operator_market_id": selection.get("market_id"),
            "operator_outcome_id": selection.get("outcome_id"),
            "fixture_line_verified": selection.get("fixture_line_verified", selection.get("market") not in LINE_MARKETS),
            "operator_line_source": selection.get("operator_line_source"),
            "operator_model_probability": round(learned * 100.0, 2) if learned is not None else None,
            "raw_model_probability": round(diagnostics["raw"] * 100.0, 2) if diagnostics else None,
            "calibrated_model_probability": round(diagnostics["calibrated"] * 100.0, 2) if diagnostics else None,
            "learning_reliability": round(diagnostics["reliability"], 4) if diagnostics else None,
            "market_calibrator_used": bool(diagnostics["market_calibrator"]) if diagnostics else False,
            "state_probability": round(state_p * 100.0, 2) if state_p is not None else None,
            "existing_model_evidence": _existing_evidence(merged), "learning_support_rows": support,
            "state_supported": state_p is not None, "learning_model_ready": model.ready,
            "probability_kind": "SUPERVISED_OPERATOR_LINE_P_HIT",
        })
    rows = _cohere_exclusive_probabilities(rows)
    rows.sort(key=lambda x: _num(x.get("operator_model_probability"), -1.0), reverse=True)
    return rows


def _quantile(values: list[float], q: float):
    xs = sorted(float(x) for x in values if _num(x) is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return round(xs[0], 3)
    pos = (len(xs) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    value = xs[lo] if lo == hi else xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)
    return round(value, 3)


def _distribution(rows: list[dict], key: str) -> dict:
    values = [_num(r.get(key)) for r in rows]
    values = [x for x in values if x is not None]
    return {"count": len(values), "min": round(min(values), 3) if values else None, "p50": _quantile(values, 0.50),
            "p90": _quantile(values, 0.90), "p95": _quantile(values, 0.95), "max": round(max(values), 3) if values else None}


def _probability_diagnostics(rows: list[dict]) -> dict:
    scored = [r for r in rows if _num(r.get("operator_model_probability")) is not None]
    zero_support = [r for r in rows if int(r.get("learning_support_rows") or 0) == 0]
    supported = [r for r in rows if int(r.get("learning_support_rows") or 0) > 0]
    per_market = {}
    for market in sorted({_market(r.get("market")) for r in rows}):
        offered_subset = [r for r in rows if _market(r.get("market")) == market]
        subset = [r for r in scored if _market(r.get("market")) == market]
        finals = [_num(r.get("operator_model_probability"), 0.0) for r in subset]
        supports = [int(r.get("learning_support_rows") or 0) for r in offered_subset]
        per_market[market] = {"offered_selections": len(offered_subset), "scored_selections": len(subset),
            "unscored_zero_support": sum(1 for r in offered_subset if int(r.get("learning_support_rows") or 0) == 0 and _num(r.get("operator_model_probability")) is None),
            "support_rows": max(supports) if supports else 0, "max_final": round(max(finals), 3) if finals else None,
            "p90_final": _quantile(finals, 0.90), "above_50": sum(1 for p in finals if p >= 50.0),
            "above_52": sum(1 for p in finals if p >= 52.0), "above_55": sum(1 for p in finals if p >= 55.0)}
    return {"offer_selections": len(rows), "scored_selections": len(scored),
        "raw_all_model_outputs": _distribution(rows, "raw_model_probability"), "raw_scored": _distribution(scored, "raw_model_probability"),
        "calibrated_scored": _distribution(scored, "calibrated_model_probability"), "final_scored": _distribution(scored, "operator_model_probability"),
        "threshold_counts": {"above_50": sum(1 for r in scored if _num(r.get("operator_model_probability"), 0.0) >= 50.0),
            "above_52": sum(1 for r in scored if _num(r.get("operator_model_probability"), 0.0) >= 52.0),
            "above_55": sum(1 for r in scored if _num(r.get("operator_model_probability"), 0.0) >= 55.0)},
        "support": {"full_support_rows": FULL_SUPPORT_ROWS, "supported_offer_selections": len(supported),
            "below_full_support": sum(1 for r in supported if int(r.get("learning_support_rows") or 0) < FULL_SUPPORT_ROWS),
            "at_full_support": sum(1 for r in supported if int(r.get("learning_support_rows") or 0) >= FULL_SUPPORT_ROWS),
            "zero_support_offer_selections": len(zero_support),
            "unscored_zero_support": sum(1 for r in zero_support if _num(r.get("operator_model_probability")) is None)}, "per_market": per_market}


def _same_market_conflict(a: dict, b: dict) -> bool:
    ma, mb = _market(a.get("market")), _market(b.get("market"))
    if ma != mb:
        return False
    if ma == "game_state":
        return _num(a.get("checkpoint"), 0) == _num(b.get("checkpoint"), 0)
    return True


def _score_pair(value):
    raw = str(value or "").strip().replace("-", ":")
    parts = raw.split(":")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _semantic_redundancy(a: dict, b: dict) -> bool:
    """Reject legs where one selection already guarantees the other.

    Example: exact match score 2:0 already guarantees under 2.5 sets. Superbet may
    allow both legs in a builder, but the second leg adds no independent condition
    and therefore must not be presented by Symphony as increasing composition value.
    Match-game totals and set-game totals are deliberately NOT treated as redundant.
    """
    for exact, other in ((a, b), (b, a)):
        if _market(exact.get("market")) != "exact_match_score" or _market(other.get("market")) != "total_sets":
            continue
        score = _score_pair(exact.get("pick"))
        line = _num(other.get("line"))
        direction = _coherence_pick(other.get("pick"))
        if score is None or line is None or direction not in {"over", "under"}:
            continue
        set_count = score[0] + score[1]
        if direction == "under" and set_count < line:
            return True
        if direction == "over" and set_count > line:
            return True
    return False


def _compatible(selection: tuple[dict, ...]) -> bool:
    for i, a in enumerate(selection):
        for b in selection[i + 1:]:
            if _same_market_conflict(a, b) or _semantic_redundancy(a, b):
                return False
    return True


def _composition_utility(selection: tuple[dict, ...], joint: float) -> float:
    ps = [max(0.001, min(0.999, _num(x.get("operator_model_probability"), 0.0) / 100.0)) for x in selection]
    n = len(ps)
    geometric = math.exp(sum(math.log(p) for p in ps) / n)
    weakest = min(ps)
    joint_equivalent = max(0.001, joint) ** (1.0 / n)
    support = min(int(x.get("learning_support_rows") or 0) for x in selection)
    support_quality = min(1.0, support / float(FULL_SUPPORT_ROWS))
    complexity_penalty = 0.008 * max(0, n - 2)
    return 100.0 * max(0.0, 0.48 * geometric + 0.22 * weakest + 0.22 * joint_equivalent + 0.08 * support_quality - complexity_penalty)


def _best_compositions(match: dict, scored: list[dict], outcomes: list[dict]) -> dict:
    pool = [x for x in scored if x.get("state_supported") is True and _num(x.get("operator_model_probability"), 0.0) >= MIN_ACTIONABLE_P * 100.0][:TOP_POOL]
    out = {}
    for n in range(2, 7):
        best = None
        for combo in combinations(pool, n):
            if not _compatible(combo):
                continue
            joint, supported_count = joint_probability(match, list(combo), outcomes)
            if joint is None or supported_count != n:
                continue
            candidate = {"legs": n, "score": round(_composition_utility(combo, joint), 2), "joint_probability": round(joint * 100.0, 3),
                "joint_status": "EXACT_SHARED_STATE", "state_version": STATE_VERSION, "selection": [dict(x) for x in combo]}
            if best is None or candidate["score"] > best["score"]:
                best = candidate
        if best:
            out[str(n)] = best
    return out


def build(results: list[dict], history: list[dict]) -> tuple[dict, dict]:
    model = train_operator_line_model(history)
    matches, all_scored = [], []
    fixture_count = selection_count = actionable_count = state_supported_count = 0
    generated_at_dt = datetime.now(timezone.utc)
    for match in results or []:
        if not isinstance(match, dict) or not _operator_context(match) or not _is_current_pre_match_fixture(match, generated_at_dt):
            continue
        outcomes = build_outcomes(match)
        scored = _score_offer(match, model, outcomes)
        all_scored.extend(scored)
        fixture_count += 1
        selection_count += len(scored)
        actionable_count += sum(1 for x in scored if _num(x.get("operator_model_probability"), 0.0) >= MIN_ACTIONABLE_P * 100.0)
        state_supported_count += sum(1 for x in scored if x.get("state_supported") is True)
        comps = _best_compositions(match, scored, outcomes) if model.ready and outcomes else {}
        matches.append({"match_key": str(match.get("match_id") if match.get("match_id") is not None else match.get("id") or ""),
            "id": match.get("match_id") if match.get("match_id") is not None else match.get("id"), "p1": match.get("p1"), "p2": match.get("p2"),
            "scheduled_time": match.get("scheduled_time"), "tour": match.get("tour"), "surface": match.get("surface"), "best_of": match.get("best_of"),
            "offer_selections": len(scored), "shared_state_outcomes": len(outcomes), "scored_selections": scored, "compositions": comps,
            "recommended_leg_count": int(max(comps.items(), key=lambda x: x[1]["score"])[0]) if comps else None})
    generated_at = generated_at_dt.isoformat()
    probability_diagnostics = _probability_diagnostics(all_scored)
    current = {"version": VERSION, "learning_version": LEARNING_VERSION, "state_version": STATE_VERSION, "generated_at": generated_at,
        "operator": OPERATOR, "architecture": "CURRENT_SUPERBET_OFFER -> SUPERVISED_EXACT_LINE_P -> SHARED_STATE_JOINT -> SYMPHONY2",
        "probability_policy": "SUPERVISED_MODEL; PER_MARKET_CALIBRATION_WHEN_VALIDATED; STATE_AND_EXISTING_MODELS_ARE_FEATURES_NOT_FIXED_WEIGHTS",
        "model_status": model.status, "matches_count": len(matches), "matches": matches}
    stats = {"version": VERSION, "generated_at": generated_at, "operator": OPERATOR, "model_status": model.status,
        "training": model.metrics or {"version": LEARNING_VERSION, "training_rows": model.trained_rows},
        "current_offer": {"verified_fixtures": fixture_count, "exact_operator_selections": selection_count,
            "state_supported_selections": state_supported_count, "selections_above_actionable_threshold": actionable_count,
            "threshold": MIN_ACTIONABLE_P * 100.0, "probability_diagnostics": probability_diagnostics},
        "joint_probability_policy": "EXACT_SHARED_STATE_ONLY", "semantic_redundancy_policy": "REDUNDANT_LEGS_REJECTED",
        "legacy_symphony_stats_used": False, "prices_used": False}
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
    return {"status": "OK", "version": VERSION, "model_status": current["model_status"], "matches": current["matches_count"],
        "training": stats.get("training"), **{k: v for k, v in stats["current_offer"].items() if k != "probability_diagnostics"},
        "probability_diagnostics": stats["current_offer"]["probability_diagnostics"]}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))