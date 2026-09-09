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
    from .symphony2_state import (
        VERSION as STATE_VERSION,
        build_outcomes,
        build_player_dna_shared_outcomes,
        joint_probability,
        marginal_probability,
        player_dna_joint_probability,
        player_dna_marginal_probability,
        phase9_shared_state_contract,
    )
    from .superbet_playable import signal_signature
except ImportError:
    from symphony2_learning import feature_row, train_operator_line_model, VERSION as LEARNING_VERSION, FULL_SUPPORT_ROWS
    from symphony2_state import (
        VERSION as STATE_VERSION,
        build_outcomes,
        build_player_dna_shared_outcomes,
        joint_probability,
        marginal_probability,
        player_dna_joint_probability,
        player_dna_marginal_probability,
        phase9_shared_state_contract,
    )
    from superbet_playable import signal_signature

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"
RESULTS = DATA / "results.json"
HISTORY = DATA / "history.json"
CURRENT = DATA / "symphony2_current.json"
STATS = DATA / "symphony2_stats.json"
PHASE9_REPORT = DATA / "symphony2_phase9_player_dna_shared_state.json"
PHASE10_OUT = DATA / "symphony2_phase10_bet_builder_dependency.json"
VERSION = "symphony2-runtime-6"
PHASE10_VERSION = "symphony2-phase10-bet-builder-dependency-v1"
PHASE10_MODE = "SHADOW_BET_BUILDER_DEPENDENCY_DIAGNOSTIC_ONLY"
PHASE10_EXACT_EPS = 1e-12
OPERATOR = "superbet.pl"
LINE_MARKETS = {
    "match_total", "set1_total", "set2_total", "set3_total", "total_sets",
    "match_game_handicap", "set1_game_handicap", "set2_game_handicap", "set3_game_handicap", "set_handicap",
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
        return False
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
    if (
        ctx.get("operator") != OPERATOR
        or ctx.get("operator_verified") is not True
        or ctx.get("status") != "VERIFIED"
        or ctx.get("suspended") is True
    ):
        return None
    return ctx


def _current_offer(match: dict) -> list[dict]:
    ctx = _operator_context(match)
    if not ctx:
        return []
    out = []
    for raw in ctx.get("canonical_selections") or []:
        if not isinstance(raw, dict) or raw.get("operator_available") is not True:
            continue
        market = _market(raw.get("market"))
        if market in LINE_MARKETS:
            if (
                raw.get("operator_line_verified") is not True
                or raw.get("fixture_line_verified") is not True
                or _num(raw.get("line")) is None
            ):
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


def _pav_non_increasing(values: list[float]) -> list[float]:
    """Least-squares monotone projection for an OVER probability ladder."""
    blocks: list[dict] = []
    for idx, value in enumerate(values):
        blocks.append({"start": idx, "end": idx, "sum": float(value), "weight": 1})
        while len(blocks) >= 2:
            left, right = blocks[-2], blocks[-1]
            left_mean = left["sum"] / left["weight"]
            right_mean = right["sum"] / right["weight"]
            if left_mean >= right_mean - 1e-12:
                break
            blocks[-2:] = [{
                "start": left["start"], "end": right["end"],
                "sum": left["sum"] + right["sum"],
                "weight": left["weight"] + right["weight"],
            }]
    out = [0.0] * len(values)
    for block in blocks:
        mean = block["sum"] / block["weight"]
        for idx in range(block["start"], block["end"] + 1):
            out[idx] = mean
    return out


def _cohere_ou_line_ladders(rows: list[dict]) -> list[dict]:
    """Project complete exact O/U ladders onto the nearest monotone model ladder.

    The supervised/calibrated probabilities remain the only source of the published
    marginal P. This step corrects only impossible cross-line inversions: OVER may
    stay flat or decrease as the line rises, and UNDER remains its exact complement.
    Shared-state probabilities are not blended back into P after prediction.
    """
    ladders: dict[tuple, dict[float, dict[str, dict]]] = {}
    for row in rows or []:
        market = _market(row.get("market"))
        pick = _coherence_pick(row.get("pick"))
        line = _num(row.get("line"))
        if market not in COHERENT_OU_MARKETS or pick not in {"over", "under"} or line is None:
            continue
        if _num(row.get("operator_model_probability")) is None:
            continue
        key = (market, _norm(row.get("player")), int(_num(row.get("checkpoint"), 0) or 0))
        ladders.setdefault(key, {}).setdefault(round(line, 6), {})[pick] = row

    for line_map in ladders.values():
        complete = [(line, pair) for line, pair in sorted(line_map.items()) if set(pair) == {"over", "under"}]
        if len(complete) < 2:
            continue
        over_values = [float(_num(pair["over"].get("operator_model_probability"), 0.0) or 0.0) for _, pair in complete]
        projected = _pav_non_increasing(over_values)
        for (_, pair), over_p in zip(complete, projected):
            over_final = round(max(0.01, min(99.99, over_p)), 2)
            under_final = round(100.0 - over_final, 2)
            for pick, final in (("over", over_final), ("under", under_final)):
                row = pair[pick]
                before = round(float(_num(row.get("operator_model_probability"), 0.0) or 0.0), 2)
                if abs(before - final) > 0.005:
                    row["operator_model_probability_pre_line_coherence"] = before
                    row["operator_model_probability"] = final
                    row["probability_coherence"] = "MONOTONIC_OU_LADDER"
                    row["line_coherence_source"] = "SUPERVISED_MONOTONIC_PROJECTION"
    return rows


def _score_offer(
    match: dict,
    model,
    outcomes: list[dict],
    phase9_outcomes: list[dict] | None = None,
) -> list[dict]:
    models = _model_index(match)
    rows = []
    for selection in _current_offer(match):
        sig = signal_signature(selection)
        merged = _merge_model_features(selection, models.get(sig))
        state_p = marginal_probability(match, selection, outcomes) if outcomes else None
        phase9_p = (
            player_dna_marginal_probability(match, selection, phase9_outcomes)
            if phase9_outcomes
            else None
        )
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
            "player_dna_shared_state_probability_shadow": (
                round(phase9_p * 100.0, 2) if phase9_p is not None else None
            ),
            "player_dna_shared_state_supported_shadow": phase9_p is not None,
            "existing_model_evidence": _existing_evidence(merged), "learning_support_rows": support,
            "state_supported": state_p is not None, "learning_model_ready": model.ready,
            "probability_kind": "SUPERVISED_OPERATOR_LINE_P_HIT",
        })
    rows = _cohere_exclusive_probabilities(rows)
    rows = _cohere_ou_line_ladders(rows)
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


def _composition_dependency_diagnostics(
    match: dict,
    selection: tuple[dict, ...],
    joint: float,
    outcomes: list[dict],
) -> dict:
    """Describe exact shared-state dependence without changing composition rank.

    The diagnostics are intentionally threshold-free. They expose conditional
    state survival and pairwise overlap so future redundancy/conflict gates can
    be calibrated from evidence instead of hand-picked rules.
    """
    legs = list(selection)
    marginals: list[float | None] = [
        marginal_probability(match, leg, outcomes)
        for leg in legs
    ]
    per_leg = []
    for index, leg in enumerate(legs):
        others = legs[:index] + legs[index + 1:]
        if not others:
            others_joint = 1.0
        elif len(others) == 1:
            others_joint = marginal_probability(match, others[0], outcomes)
        else:
            others_joint, supported = joint_probability(match, others, outcomes)
            if supported != len(others):
                others_joint = None

        conditional = (
            float(joint) / float(others_joint)
            if others_joint is not None and float(others_joint) > 0.0
            else None
        )
        if conditional is not None:
            conditional = max(0.0, min(1.0, conditional))
        marginal = marginals[index]
        lift = (
            conditional / float(marginal)
            if conditional is not None and marginal is not None and float(marginal) > 0.0
            else None
        )
        information = (
            -math.log(conditional)
            if conditional is not None and conditional > 0.0
            else None
        )
        per_leg.append({
            "selection_id": _selection_id(leg),
            "label": leg.get("label") or _label(leg),
            "state_marginal_probability": round(float(marginal) * 100.0, 3) if marginal is not None else None,
            "joint_without_leg_probability": round(float(others_joint) * 100.0, 3) if others_joint is not None else None,
            "conditional_probability_given_other_legs": round(conditional * 100.0, 3) if conditional is not None else None,
            "conditional_lift_vs_marginal": round(lift, 6) if lift is not None else None,
            "conditional_information_nats": round(information, 6) if information is not None else None,
            "marginal_information_gain_nats": round(information, 6) if information is not None else None,
            "joint_mass_removed_by_leg_pp": round((float(others_joint) - float(joint)) * 100.0, 3)
            if others_joint is not None else None,
        })

    pairs = []
    for left_index, right_index in combinations(range(len(legs)), 2):
        left = legs[left_index]
        right = legs[right_index]
        pair_joint, supported = joint_probability(match, [left, right], outcomes)
        left_p = marginals[left_index]
        right_p = marginals[right_index]
        smaller = (
            min(float(left_p), float(right_p))
            if left_p is not None and right_p is not None
            else None
        )
        overlap = (
            float(pair_joint) / smaller
            if pair_joint is not None and smaller is not None and smaller > 0.0
            else None
        )
        if overlap is not None:
            overlap = max(0.0, min(1.0, overlap))
        independence = (
            float(left_p) * float(right_p)
            if left_p is not None and right_p is not None
            else None
        )
        lift = (
            float(pair_joint) / independence
            if pair_joint is not None and independence is not None and independence > 0.0
            else None
        )
        pair_exact = pair_joint is not None and supported == 2
        redundancy_score = overlap if pair_exact else None
        conflict_score = (1.0 - overlap) if pair_exact and overlap is not None else None
        pairs.append({
            "left_selection_id": _selection_id(left),
            "right_selection_id": _selection_id(right),
            "exact_pair_joint_probability": round(float(pair_joint) * 100.0, 3)
            if pair_exact else None,
            "overlap_of_smaller_leg": round(overlap, 6) if overlap is not None and pair_exact else None,
            "redundancy_score": round(redundancy_score, 6) if redundancy_score is not None else None,
            "conflict_score": round(conflict_score, 6) if conflict_score is not None else None,
            "score_semantics": "NORMALIZED_EXACT_PAIR_OVERLAP_AXIS",
            "lift_vs_independence": round(lift, 6) if lift is not None and pair_exact else None,
        })

    weakest_supervised = min(
        legs,
        key=lambda leg: _num(leg.get("operator_model_probability"), 101.0),
    )
    state_candidates = [
        (leg, marginal)
        for leg, marginal in zip(legs, marginals)
        if marginal is not None
    ]
    weakest_state = min(state_candidates, key=lambda item: item[1])[0] if state_candidates else None

    per_leg_by_id = {row["selection_id"]: row for row in per_leg}
    weakest_supervised_id = _selection_id(weakest_supervised)
    weakest_state_id = _selection_id(weakest_state) if weakest_state is not None else None
    weakest_supervised_impact = per_leg_by_id.get(weakest_supervised_id, {}).get("joint_mass_removed_by_leg_pp")
    weakest_state_impact = (
        per_leg_by_id.get(weakest_state_id, {}).get("joint_mass_removed_by_leg_pp")
        if weakest_state_id is not None else None
    )
    return {
        "status": "EXACT_SHARED_STATE_DIAGNOSTIC_ONLY",
        "ranking_influence": False,
        "threshold_classification_enabled": False,
        "joint_probability": round(float(joint) * 100.0, 3),
        "weakest_supervised_leg_selection_id": weakest_supervised_id,
        "weakest_supervised_leg_joint_mass_removed_pp": weakest_supervised_impact,
        "weakest_state_leg_selection_id": weakest_state_id,
        "weakest_state_leg_joint_mass_removed_pp": weakest_state_impact,
        "dependency_score_semantics": {
            "redundancy_score": "exact_pair_joint / min(pair_marginals); 1 means full containment",
            "conflict_score": "1 - redundancy_score; 1 means zero shared exact state mass",
            "marginal_information_gain_nats": "-log(P(leg | all other legs))",
            "thresholds_enabled": False,
        },
        "per_leg": per_leg,
        "pairs": pairs,
    }




def _phase10_dependency_diagnostics(
    match: dict,
    selections: list[dict] | tuple[dict, ...],
    phase9_outcomes: list[dict],
) -> dict:
    """Exact dependency diagnostics from one Player DNA shared state-space.

    This is deliberately diagnostic-only. Scores are continuous and no
    arbitrary threshold turns them into runtime reject/accept decisions.
    """
    legs = list(selections)
    if len(legs) < 2 or not phase9_outcomes:
        return {
            "status": "UNSUPPORTED_OR_EMPTY",
            "legs": len(legs),
            "ranking_influence": False,
            "threshold_classification_enabled": False,
        }

    marginals = [
        player_dna_marginal_probability(match, leg, phase9_outcomes)
        for leg in legs
    ]
    joint, supported = player_dna_joint_probability(
        match,
        legs,
        phase9_outcomes,
    )
    if (
        joint is None
        or supported != len(legs)
        or any(value is None for value in marginals)
    ):
        return {
            "status": "UNSUPPORTED_OR_EMPTY",
            "legs": len(legs),
            "supported_legs": supported,
            "ranking_influence": False,
            "threshold_classification_enabled": False,
        }

    exact_joint = float(joint)
    per_leg = []
    for index, leg in enumerate(legs):
        others = legs[:index] + legs[index + 1:]
        if len(others) == 1:
            others_joint = player_dna_marginal_probability(
                match,
                others[0],
                phase9_outcomes,
            )
        else:
            others_joint, others_supported = player_dna_joint_probability(
                match,
                others,
                phase9_outcomes,
            )
            if others_supported != len(others):
                others_joint = None

        conditional = (
            exact_joint / float(others_joint)
            if others_joint is not None and float(others_joint) > PHASE10_EXACT_EPS
            else None
        )
        if conditional is not None:
            conditional = max(0.0, min(1.0, conditional))
        marginal = float(marginals[index])
        lift = (
            conditional / marginal
            if conditional is not None and marginal > PHASE10_EXACT_EPS
            else None
        )
        information = (
            -math.log(conditional)
            if conditional is not None and conditional > PHASE10_EXACT_EPS
            else None
        )
        removed = (
            float(others_joint) - exact_joint
            if others_joint is not None
            else None
        )
        per_leg.append({
            "selection_id": _selection_id(leg),
            "label": leg.get("label") or _label(leg),
            "market": _market(leg.get("market")),
            "state_marginal_probability": round(marginal * 100.0, 6),
            "joint_without_leg_probability": (
                round(float(others_joint) * 100.0, 6)
                if others_joint is not None
                else None
            ),
            "conditional_probability_given_other_legs": (
                round(conditional * 100.0, 6)
                if conditional is not None
                else None
            ),
            "conditional_zero": bool(
                conditional is not None
                and conditional <= PHASE10_EXACT_EPS
            ),
            "conditional_lift_vs_marginal": (
                round(lift, 9) if lift is not None else None
            ),
            "marginal_information_gain_nats": (
                round(information, 9) if information is not None else None
            ),
            "joint_mass_removed_by_leg_pp": (
                round(max(0.0, removed) * 100.0, 6)
                if removed is not None
                else None
            ),
        })

    pairs = []
    for left_index, right_index in combinations(range(len(legs)), 2):
        left = legs[left_index]
        right = legs[right_index]
        pair_joint, pair_supported = player_dna_joint_probability(
            match,
            [left, right],
            phase9_outcomes,
        )
        left_p = float(marginals[left_index])
        right_p = float(marginals[right_index])
        pair_exact = pair_joint is not None and pair_supported == 2
        smaller = min(left_p, right_p)
        overlap = (
            float(pair_joint) / smaller
            if pair_exact and smaller > PHASE10_EXACT_EPS
            else None
        )
        if overlap is not None:
            overlap = max(0.0, min(1.0, overlap))
        independence = left_p * right_p
        lift = (
            float(pair_joint) / independence
            if pair_exact and independence > PHASE10_EXACT_EPS
            else None
        )
        exact_containment = bool(
            pair_exact
            and abs(float(pair_joint) - smaller) <= PHASE10_EXACT_EPS
        )
        exact_conflict = bool(
            pair_exact and float(pair_joint) <= PHASE10_EXACT_EPS
        )
        pairs.append({
            "left_selection_id": _selection_id(left),
            "right_selection_id": _selection_id(right),
            "left_market": _market(left.get("market")),
            "right_market": _market(right.get("market")),
            "exact_pair_joint_probability": (
                round(float(pair_joint) * 100.0, 6)
                if pair_exact
                else None
            ),
            "independence_product_probability": round(
                independence * 100.0,
                6,
            ),
            "joint_minus_independence_pp": (
                round((float(pair_joint) - independence) * 100.0, 6)
                if pair_exact
                else None
            ),
            "redundancy_score": (
                round(overlap, 9) if overlap is not None else None
            ),
            "conflict_score": (
                round(1.0 - overlap, 9) if overlap is not None else None
            ),
            "lift_vs_independence": (
                round(lift, 9) if lift is not None else None
            ),
            "exact_containment": exact_containment,
            "exact_conflict": exact_conflict,
            "runtime_semantic_redundancy": _semantic_redundancy(left, right),
        })

    state_candidates = [
        (leg, float(marginal))
        for leg, marginal in zip(legs, marginals)
    ]
    weakest_leg, weakest_marginal = min(
        state_candidates,
        key=lambda item: item[1],
    )
    weakest_id = _selection_id(weakest_leg)
    per_leg_by_id = {row["selection_id"]: row for row in per_leg}
    weakest_impact = (
        per_leg_by_id.get(weakest_id, {}).get(
            "joint_mass_removed_by_leg_pp"
        )
    )

    redundancy_rows = [
        row for row in pairs if row.get("redundancy_score") is not None
    ]
    conflict_rows = [
        row for row in pairs if row.get("conflict_score") is not None
    ]
    strongest_redundancy = (
        max(redundancy_rows, key=lambda row: row["redundancy_score"])
        if redundancy_rows else None
    )
    strongest_conflict = (
        max(conflict_rows, key=lambda row: row["conflict_score"])
        if conflict_rows else None
    )

    return {
        "status": "EXACT_PLAYER_DNA_DEPENDENCY_DIAGNOSTIC",
        "mode": PHASE10_MODE,
        "legs": len(legs),
        "joint_probability": round(exact_joint * 100.0, 6),
        "joint_source": "PLAYER_DNA_SINGLE_WHOLE_MATCH_SHARED_STATE",
        "independence_product_forbidden_as_joint": True,
        "weakest_state_leg_selection_id": weakest_id,
        "weakest_state_leg_marginal_probability": round(
            weakest_marginal * 100.0,
            6,
        ),
        "weakest_state_leg_joint_mass_removed_pp": weakest_impact,
        "strongest_redundancy_pair": strongest_redundancy,
        "strongest_conflict_pair": strongest_conflict,
        "per_leg": per_leg,
        "pairs": pairs,
        "dependency_score_semantics": {
            "redundancy_score": (
                "exact_pair_joint / min(pair_marginals); "
                "1 means mathematical containment"
            ),
            "conflict_score": (
                "1 - redundancy_score; 1 means zero shared exact state mass"
            ),
            "marginal_information_gain_nats": (
                "-log(P(leg | all other legs)); null only for zero/undefined "
                "conditional probability"
            ),
            "weakest_leg_impact": (
                "joint probability mass removed by the lowest-marginal leg"
            ),
            "thresholds_enabled": False,
        },
        "ranking_influence": False,
        "operator_model_probability_influence": False,
        "recommended_leg_count_influence": False,
        "production_influence": False,
        "playable_influence": False,
        "auto_promote": False,
        "threshold_classification_enabled": False,
    }


def _phase10_operator_price_reaction_experiment() -> dict:
    return {
        "status": "NOT_AVAILABLE_NO_OBSERVED_BUILDER_PRICE_DELTAS",
        "observed_builder_price_delta_rows": 0,
        "used_as_truth_label": False,
        "used_for_model_training": False,
        "used_for_ranking": False,
        "gate_required": False,
        "policy": (
            "If exact Bet Builder price-change observations are collected later, "
            "compare them descriptively with shared-state dependence only; "
            "operator price is never a ground-truth outcome label."
        ),
    }


def _phase10_shadow_dependency_summary(
    match: dict,
    scored: list[dict],
    phase9_outcomes: list[dict],
) -> dict:
    supported = [
        row
        for row in scored
        if row.get("player_dna_shared_state_supported_shadow") is True
    ]
    # Keep runtime cost bounded: one representative pair and one triple from
    # the already probability-sorted exact Superbet offer.
    pair_report = None
    triple_report = None
    for combo in combinations(supported[:6], 2):
        candidate = _phase10_dependency_diagnostics(
            match,
            combo,
            phase9_outcomes,
        )
        if candidate.get("status") == "EXACT_PLAYER_DNA_DEPENDENCY_DIAGNOSTIC":
            pair_report = candidate
            break
    for combo in combinations(supported[:6], 3):
        candidate = _phase10_dependency_diagnostics(
            match,
            combo,
            phase9_outcomes,
        )
        if candidate.get("status") == "EXACT_PLAYER_DNA_DEPENDENCY_DIAGNOSTIC":
            triple_report = candidate
            break

    return {
        "mode": PHASE10_MODE,
        "status": (
            "SHADOW_DEPENDENCY_DIAGNOSTICS_AVAILABLE"
            if pair_report is not None
            else "SHADOW_DEPENDENCY_DIAGNOSTICS_UNAVAILABLE"
        ),
        "supported_offer_selections": len(supported),
        "representative_pair": pair_report,
        "representative_triple": triple_report,
        "operator_price_reaction_experiment": (
            _phase10_operator_price_reaction_experiment()
        ),
        "ranking_influence": False,
        "operator_model_probability_influence": False,
        "recommended_leg_count_influence": False,
        "production_influence": False,
        "playable_influence": False,
        "auto_promote": False,
    }


def evaluate_phase10_gate(phase9_report: dict) -> dict:
    match = {
        "p1": "Phase10 A",
        "p2": "Phase10 B",
        "best_of": 3,
        "service_model": {"p1_hold": 0.78, "p2_hold": 0.74},
        "first_set_win": {"Phase10 A": 0.56, "Phase10 B": 0.44},
        "second_set_win": {"Phase10 A": 0.55, "Phase10 B": 0.45},
        "third_set_win": {"Phase10 A": 0.54, "Phase10 B": 0.46},
    }
    states = build_player_dna_shared_outcomes(match)
    phase9_ready = bool(
        phase9_report.get("phase9_complete") is True
        and phase9_report.get("phase10_ready") is True
    )

    correlated_legs = [
        {"market": "set1_winner", "pick": "Phase10 A"},
        {"market": "set2_total", "pick": "over", "line": 8.5},
        {"market": "match_winner", "pick": "Phase10 A"},
    ]
    redundant_legs = [
        {"market": "exact_match_score", "pick": "2:0"},
        {"market": "total_sets", "pick": "under", "line": 2.5},
    ]
    conflict_legs = [
        {"market": "exact_match_score", "pick": "2:0"},
        {"market": "total_sets", "pick": "over", "line": 2.5},
    ]

    correlated = _phase10_dependency_diagnostics(
        match,
        correlated_legs,
        states,
    )
    redundant = _phase10_dependency_diagnostics(
        match,
        redundant_legs,
        states,
    )
    conflict = _phase10_dependency_diagnostics(
        match,
        conflict_legs,
        states,
    )

    correlated_pairs = correlated.get("pairs") or []
    redundancy_pair = (redundant.get("pairs") or [{}])[0]
    conflict_pair = (conflict.get("pairs") or [{}])[0]
    exact_metrics_complete = bool(
        correlated.get("status")
        == "EXACT_PLAYER_DNA_DEPENDENCY_DIAGNOSTIC"
        and len(correlated.get("per_leg") or []) == 3
        and correlated_pairs
        and correlated.get("joint_probability") is not None
        and correlated.get("weakest_state_leg_selection_id")
        and all(
            row.get("conditional_probability_given_other_legs") is not None
            and row.get("joint_mass_removed_by_leg_pp") is not None
            for row in correlated.get("per_leg") or []
        )
        and any(
            row.get("marginal_information_gain_nats") is not None
            for row in correlated.get("per_leg") or []
        )
    )
    redundancy_identified = bool(
        redundant.get("status")
        == "EXACT_PLAYER_DNA_DEPENDENCY_DIAGNOSTIC"
        and redundancy_pair.get("exact_containment") is True
        and abs(float(redundancy_pair.get("redundancy_score") or 0.0) - 1.0)
        <= 1e-9
    )
    conflict_identified = bool(
        conflict.get("status")
        == "EXACT_PLAYER_DNA_DEPENDENCY_DIAGNOSTIC"
        and conflict_pair.get("exact_conflict") is True
        and abs(float(conflict_pair.get("conflict_score") or 0.0) - 1.0)
        <= 1e-9
    )
    independence_not_used = bool(
        correlated.get("independence_product_forbidden_as_joint") is True
        and any(
            abs(float(row.get("joint_minus_independence_pp") or 0.0)) > 1e-6
            for row in correlated_pairs
        )
    )
    isolation = all(
        correlated.get(key) is False
        for key in (
            "ranking_influence",
            "operator_model_probability_influence",
            "recommended_leg_count_influence",
            "production_influence",
            "playable_influence",
            "auto_promote",
            "threshold_classification_enabled",
        )
    )
    price_experiment = _phase10_operator_price_reaction_experiment()
    price_policy_safe = bool(
        price_experiment.get("used_as_truth_label") is False
        and price_experiment.get("used_for_model_training") is False
        and price_experiment.get("used_for_ranking") is False
    )
    complete = bool(
        phase9_ready
        and states
        and exact_metrics_complete
        and redundancy_identified
        and conflict_identified
        and independence_not_used
        and isolation
        and price_policy_safe
    )

    return {
        "version": PHASE10_VERSION,
        "mode": PHASE10_MODE,
        "status": (
            "PHASE10_DEPENDENCY_DIAGNOSTICS_COMPLETE_NO_PROMOTION"
            if complete
            else "PHASE10_DEPENDENCY_DIAGNOSTICS_INCOMPLETE_NO_PROMOTION"
        ),
        "phase": 10,
        "phase9_prerequisite_satisfied": phase9_ready,
        "phase10_complete": complete,
        "phase11_ready": complete,
        "evidence": {
            "shared_state_outcomes": len(states),
            "correlated_three_leg": correlated,
            "exact_redundancy_case": redundant,
            "exact_conflict_case": conflict,
            "exact_metrics_complete": exact_metrics_complete,
            "redundancy_identified": redundancy_identified,
            "conflict_identified": conflict_identified,
            "independence_product_not_used_as_joint": independence_not_used,
        },
        "operator_price_reaction_experiment": price_experiment,
        "promotion_allowed_by_this_gate": False,
        "production_influence": False,
        "runtime_ranking_influence": False,
        "operator_model_probability_influence": False,
        "recommended_leg_count_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
    }


def build_phase10_gate() -> dict:
    phase9 = _read(PHASE9_REPORT, {})
    report = evaluate_phase10_gate(
        phase9 if isinstance(phase9, dict) else {}
    )
    _write(PHASE10_OUT, report)
    print(json.dumps({
        "version": report.get("version"),
        "status": report.get("status"),
        "phase10_complete": report.get("phase10_complete"),
        "phase11_ready": report.get("phase11_ready"),
        "price_experiment": report.get(
            "operator_price_reaction_experiment"
        ),
    }, ensure_ascii=False))
    return report


def _phase9_shadow_shared_state_diagnostics(
    match: dict,
    scored: list[dict],
    phase9_outcomes: list[dict],
) -> dict:
    contract = phase9_shared_state_contract()
    supported_rows = [
        row
        for row in scored
        if row.get("player_dna_shared_state_supported_shadow") is True
    ]
    pool = supported_rows[:TOP_POOL]
    pairs = []
    cross_family_exact = 0

    def family(market: str) -> str:
        market = _market(market)
        if market.startswith("set1_"):
            return "set1"
        if market.startswith("set2_"):
            return "set2"
        return "match"

    for left, right in combinations(pool, 2):
        if not _compatible((left, right)):
            continue
        left_market = _market(left.get("market"))
        right_market = _market(right.get("market"))
        left_family = family(left_market)
        right_family = family(right_market)
        if left_family == right_family:
            continue

        joint, supported = player_dna_joint_probability(
            match,
            [left, right],
            phase9_outcomes,
        )
        if joint is None or supported != 2:
            continue
        left_p = player_dna_marginal_probability(match, left, phase9_outcomes)
        right_p = player_dna_marginal_probability(match, right, phase9_outcomes)
        if left_p is None or right_p is None:
            continue
        independent = float(left_p) * float(right_p)
        cross_family_exact += 1
        pairs.append({
            "left_selection_id": _selection_id(left),
            "right_selection_id": _selection_id(right),
            "left_market": left_market,
            "right_market": right_market,
            "left_family": left_family,
            "right_family": right_family,
            "left_marginal_probability": round(float(left_p) * 100.0, 3),
            "right_marginal_probability": round(float(right_p) * 100.0, 3),
            "exact_joint_probability": round(float(joint) * 100.0, 3),
            "independence_product_probability": round(independent * 100.0, 3),
            "joint_minus_independence_pp": round(
                (float(joint) - independent) * 100.0,
                3,
            ),
            "joint_source": "PLAYER_DNA_SINGLE_WHOLE_MATCH_SHARED_STATE",
        })

    return {
        "mode": contract["mode"],
        "status": (
            "SHADOW_SHARED_STATE_AVAILABLE"
            if phase9_outcomes
            else "SHADOW_SHARED_STATE_UNAVAILABLE"
        ),
        "shared_state_outcomes": len(phase9_outcomes),
        "shared_state_probability_mass": round(
            sum(float(row.get("prob") or 0.0) for row in phase9_outcomes),
            12,
        ),
        "supported_offer_selections": len(supported_rows),
        "cross_family_exact_pairs": cross_family_exact,
        "cross_family_pairs": pairs,
        "contract": contract,
        "ranking_influence": False,
        "operator_model_probability_influence": False,
        "recommended_leg_count_influence": False,
        "production_influence": False,
        "playable_influence": False,
    }


def _best_compositions(match: dict, scored: list[dict], outcomes: list[dict]) -> dict:
    pool = [x for x in scored if x.get("state_supported") is True and _num(x.get("operator_model_probability"), 0.0) >= MIN_ACTIONABLE_P * 100.0][:TOP_POOL]
    out = {}
    for n in range(2, 7):
        best = None
        best_combo = None
        best_joint = None
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
                best_combo = combo
                best_joint = joint
        if best and best_combo is not None and best_joint is not None:
            best["dependency_diagnostics"] = _composition_dependency_diagnostics(
                match, best_combo, best_joint, outcomes
            )
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
        phase9_outcomes = build_player_dna_shared_outcomes(match)
        scored = _score_offer(match, model, outcomes, phase9_outcomes)
        all_scored.extend(scored)
        fixture_count += 1
        selection_count += len(scored)
        actionable_count += sum(1 for x in scored if _num(x.get("operator_model_probability"), 0.0) >= MIN_ACTIONABLE_P * 100.0)
        state_supported_count += sum(1 for x in scored if x.get("state_supported") is True)
        comps = _best_compositions(match, scored, outcomes) if model.ready and outcomes else {}
        phase9_shadow = _phase9_shadow_shared_state_diagnostics(
            match,
            scored,
            phase9_outcomes,
        )
        phase10_shadow = _phase10_shadow_dependency_summary(
            match,
            scored,
            phase9_outcomes,
        )
        matches.append({"match_key": str(match.get("match_id") if match.get("match_id") is not None else match.get("id") or ""),
            "id": match.get("match_id") if match.get("match_id") is not None else match.get("id"), "p1": match.get("p1"), "p2": match.get("p2"),
            "scheduled_time": match.get("scheduled_time"), "tour": match.get("tour"), "surface": match.get("surface"), "best_of": match.get("best_of"),
            "offer_selections": len(scored), "shared_state_outcomes": len(outcomes), "scored_selections": scored, "compositions": comps,
            "phase9_player_dna_shared_state_shadow": phase9_shadow,
            "phase10_bet_builder_dependency_shadow": phase10_shadow,
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
        "composition_dependency_diagnostics_policy": "EXACT_SHARED_STATE_DIAGNOSTIC_ONLY_NO_RANKING_INFLUENCE",
        "phase9_player_dna_shared_state_policy": "SHADOW_ONLY; CROSS_FAMILY_EXACT_JOINT; NO_RANKING_OR_P_FINAL_INFLUENCE",
        "phase10_dependency_policy": "SHADOW_ONLY; EXACT_JOINT_CONDITIONAL_REDUNDANCY_CONFLICT_INFORMATION; NO_RANKING_OR_P_FINAL_INFLUENCE",
        "line_coherence_policy": "COMPLETE_OU_PAIRS_ONLY; OVER_NON_INCREASING; UNDER_COMPLEMENT; SUPERVISED_MONOTONIC_PROJECTION_ONLY",
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
