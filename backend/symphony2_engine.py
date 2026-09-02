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
    from .superbet_playable import signal_signature
except ImportError:
    from symphony2_learning import feature_row, train_operator_line_model, VERSION as LEARNING_VERSION, FULL_SUPPORT_ROWS
    from symphony2_state import build_outcomes, marginal_probability, joint_probability, VERSION as STATE_VERSION
    from superbet_playable import signal_signature

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
PLAYER_MARKETS = {"player_total_games", "player_aces", "player_double_faults"}


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


def _num(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _match_key(match: dict) -> str:
    return str(match.get("id") or match.get("event_id") or f"{match.get('p1','')}|{match.get('p2','')}|{match.get('date','')}")


def _market_key(row: dict) -> str:
    market, pick, line, checkpoint, player = signal_signature(row)
    return f"{market}|{pick}|{line if line is not None else ''}|{checkpoint or ''}|{player or ''}"


def _selection_payload(row: dict) -> dict:
    return {
        "market": row.get("market"),
        "pick": row.get("pick"),
        "line": row.get("line"),
        "checkpoint": row.get("checkpoint"),
        "player": row.get("player"),
    }


def _candidate_rows(match: dict) -> list[dict]:
    ctx = match.get("superbet_market_v91") or {}
    if not isinstance(ctx, dict) or ctx.get("operator_verified") is not True or ctx.get("status") != "VERIFIED":
        return []
    rows = []
    for row in ctx.get("model_signals") or []:
        if not isinstance(row, dict) or row.get("operator_line_verified") is not True:
            continue
        rows.append(deepcopy(row))
    return rows


def _score_candidates(match: dict, model, outcomes) -> list[dict]:
    rows = []
    for row in _candidate_rows(match):
        features = feature_row(match, row)
        p_model, support = model.predict(features, market=str(row.get("market") or ""))
        p_state = marginal_probability(outcomes, row)
        if p_model is None:
            continue
        item = deepcopy(row)
        item["operator_model_probability"] = round(100.0 * p_model, 4)
        item["state_probability"] = round(100.0 * p_state, 4) if p_state is not None else None
        item["probability_kind"] = "SUPERVISED_OPERATOR_LINE_P_HIT"
        item["learning_support_rows"] = int(support)
        item["learning_version"] = LEARNING_VERSION
        item["state_version"] = STATE_VERSION
        item["symphony2_version"] = VERSION
        rows.append(item)
    return rows


def _cohere_exclusive_probabilities(rows: list[dict]) -> list[dict]:
    groups = {}
    for row in rows:
        market = str(row.get("market") or "")
        if market not in {"match_winner", "set1_winner", "set2_winner", "set3_winner"}:
            continue
        groups.setdefault(market, []).append(row)
    for group in groups.values():
        probs = [_num(row.get("operator_model_probability")) for row in group]
        if len(group) != 2 or any(p is None for p in probs):
            continue
        total = sum(probs)
        if total <= 0:
            continue
        for row, p in zip(group, probs):
            row["operator_model_probability"] = round(100.0 * p / total, 4)
    return rows


def _compatible(a: dict, b: dict) -> bool:
    if _market_key(a) == _market_key(b):
        return False
    # Exact shared-state validation is authoritative for semantic compatibility.
    return True


def _compositions(match: dict, scored: list[dict], outcomes) -> dict:
    result = {}
    for size in (2, 3):
        best = None
        for combo in combinations(scored, size):
            if any(not _compatible(a, b) for a, b in combinations(combo, 2)):
                continue
            joint = joint_probability(outcomes, list(combo))
            if joint is None:
                continue
            payload = {
                "selections": [_selection_payload(row) for row in combo],
                "joint_probability": round(100.0 * joint, 4),
                "joint_status": "EXACT_SHARED_STATE",
            }
            if best is None or payload["joint_probability"] > best["joint_probability"]:
                best = payload
        if best:
            result[str(size)] = best
    return result


def build():
    matches = _read(RESULTS, [])
    history = _read(HISTORY, [])
    matches = matches if isinstance(matches, list) else []
    history = history if isinstance(history, list) else []
    model = train_operator_line_model(history)
    output = []
    for match in matches:
        if not isinstance(match, dict):
            continue
        candidates = _candidate_rows(match)
        if not candidates:
            continue
        outcomes = build_outcomes(match)
        scored = _cohere_exclusive_probabilities(_score_candidates(match, model, outcomes))
        if not scored:
            continue
        output.append({
            "match_key": _match_key(match),
            "p1": match.get("p1"),
            "p2": match.get("p2"),
            "date": match.get("date"),
            "scored_selections": scored,
            "compositions": _compositions(match, scored, outcomes),
        })
    doc = {
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "operator": OPERATOR,
        "architecture": "CURRENT_SUPERBET_OFFER -> SUPERVISED_EXACT_LINE_P -> SHARED_STATE_JOINT -> SYMPHONY2",
        "probability_policy": "SUPERVISED_MODEL; PER_MARKET_CALIBRATION_WHEN_VALIDATED; STATE_AND_EXISTING_MODELS_ARE_FEATURES_NOT_FIXED_WEIGHTS",
        "model_status": model.status,
        "matches_count": len(output),
        "matches": output,
    }
    _write(CURRENT, doc)
    return doc


def main():
    doc = build()
    print(json.dumps({"matches": doc.get("matches_count"), "model": doc.get("model_status")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
