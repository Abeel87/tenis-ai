from __future__ import annotations

"""Symfonia 2.0 history, settlement and performance statistics.

The new Symphony starts its own performance history from zero. Exact archived
operator labels and the canonical final-result scorer settle its frozen legs;
legacy Symphony outcomes are never imported. This is semantic performance
evidence, not an operator ticket/payout or iNeed bankroll settlement authority.
"""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

try:
    from .signal_settlement import resolve_player_side, settle_signal_live
except ImportError:  # Direct workflow invocation: python backend/symphony2_tracker.py
    from signal_settlement import resolve_player_side, settle_signal_live

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"
CURRENT = DATA / "symphony2_current.json"
BASE_HISTORY = DATA / "history.json"
HISTORY = DATA / "symphony2_history.json"
STATS = DATA / "symphony2_stats.json"
VERSION = "symphony2-tracker-4"
TERMINAL = {"hit", "miss", "void"}


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


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _dt(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def _prematch(entry: dict) -> bool:
    captured, scheduled = _dt(entry.get("captured_at")), _dt(entry.get("scheduled_time"))
    return captured is not None and scheduled is not None and captured < scheduled


def _pick(value: Any) -> str:
    raw = _norm(value)
    aliases = {
        "o": "over", "powyzej": "over", "więcej": "over", "wiecej": "over",
        "u": "under", "ponizej": "under", "mniej": "under",
        "tak": "yes", "nie": "no",
    }
    return aliases.get(raw, raw)


def _match_id(row: dict) -> str:
    value = row.get("match_id") if row.get("match_id") is not None else row.get("id")
    if value is not None and str(value) != "":
        return str(value)
    return "|".join((_norm(row.get("p1")), _norm(row.get("p2")), str(row.get("scheduled_time") or "")[:16]))


def selection_signature(match_id: str, row: dict) -> tuple:
    return (
        str(match_id),
        _norm(row.get("market")).replace(" ", "_"),
        _pick(row.get("pick")),
        _num(row.get("line")),
        _num(row.get("checkpoint")),
        _norm(row.get("player")),
    )


def _settled_operator_index(base_history: list[dict]) -> dict[tuple, str | None]:
    out: dict[tuple, str | None] = {}
    for entry in base_history or []:
        if not isinstance(entry, dict):
            continue
        mid = _match_id(entry)
        # Neither layer may silently override a conflicting exact result.
        layers = (
            entry.get("playable_autolearn_signals_v912"),
            entry.get("playable_signals_v912"),
        )
        for rows in layers:
            if not isinstance(rows, list):
                continue
            for signal in rows:
                if not isinstance(signal, dict):
                    continue
                result = _norm(signal.get("result"))
                if result not in {"hit", "miss", "void"}:
                    continue
                sig = selection_signature(mid, signal)
                if sig in out and out[sig] != result:
                    out[sig] = None
                else:
                    out.setdefault(sig, result)
    return out


def _settlement_evidence(entry: dict, history_index: dict) -> tuple[dict | None, str | None]:
    if not _prematch(entry):
        return None, "NOT_PROVEN_PREMATCH"
    mid = str(entry.get("match_id") or "")
    if not mid.isdigit():
        return None, "NOT_EXACT_LIVE_TENNIS_MATCH_ID"
    matches = history_index.get(mid) or []
    if len(matches) != 1:
        return None, "NO_EXACT_HISTORY_MATCH" if not matches else "AMBIGUOUS_EXACT_HISTORY_MATCH"
    source = matches[0]
    scheduled = _dt(entry.get("scheduled_time"))
    if scheduled is None or scheduled != _dt(source.get("scheduled_time")):
        return None, "MATCH_SCHEDULE_CONFLICT"
    if (resolve_player_side(entry.get("p1"), source) != 1
            or resolve_player_side(entry.get("p2"), source) != 2):
        return None, "MATCH_PARTICIPANT_CONFLICT"
    if source.get("status") not in {"settled", "void"}:
        return None, "HISTORY_MATCH_NOT_TERMINAL"
    settled_at = _dt(source.get("settled_at"))
    if settled_at is None or settled_at < scheduled:
        return None, "INVALID_SETTLEMENT_TIMESTAMP"
    if not source.get("settlement_source") or not source.get("settlement_version"):
        return None, "MISSING_SETTLEMENT_PROVENANCE"
    return source, None


def _terminal_result(source: dict) -> dict | None:
    final = source.get("result")
    if not isinstance(final, dict) or final.get("status") not in {"completed", "retired", "void"}:
        return None
    if (resolve_player_side(source.get("p1"), final) != 1
            or resolve_player_side(source.get("p2"), final) != 2):
        return None
    # The canonical live result owner supplies these fields. Missing evidence
    # must not turn into the scorer's absent-set/market void semantics.
    if final.get("status") == "completed" and (not final.get("sets") or any(
        final.get(key) is None for key in
        ("winner", "number_of_sets", "total_games", "match_score", "first_set_score")
    )):
        return None
    return final


def _composition_id(match_id: str, comp: dict) -> str:
    legs = sorted(
        "|".join(map(str, selection_signature(match_id, row)))
        for row in comp.get("selection") or [] if isinstance(row, dict)
    )
    raw = f"{match_id}::{int(comp.get('legs') or len(legs))}::" + "||".join(legs)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def capture(current: dict, history_doc: dict) -> tuple[dict, int]:
    doc = dict(history_doc) if isinstance(history_doc, dict) else {}
    rows = [dict(x) for x in (doc.get("entries") or []) if isinstance(x, dict)]
    seen = {str(x.get("prediction_id")) for x in rows if x.get("prediction_id")}
    captured = 0
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()

    for match in current.get("matches") or []:
        if not isinstance(match, dict):
            continue
        scheduled = _dt(match.get("scheduled_time"))
        if scheduled is None or scheduled <= now_dt:
            continue
        n = match.get("recommended_leg_count")
        comp = (match.get("compositions") or {}).get(str(n)) if n is not None else None
        if not isinstance(comp, dict) or not comp.get("selection"):
            continue
        mid = _match_id(match)
        pid = _composition_id(mid, comp)
        if pid in seen:
            continue
        legs = []
        valid = True
        for raw in comp.get("selection") or []:
            if not isinstance(raw, dict):
                valid = False
                break
            # A history row is training/accuracy evidence. Require an explicit
            # operator-verification bit rather than treating a missing bit as OK.
            if raw.get("fixture_line_verified") is not True:
                valid = False
                break
            legs.append({
                "selection_id": raw.get("selection_id"),
                "market": raw.get("market"),
                "pick": raw.get("pick"),
                "line": raw.get("line"),
                "checkpoint": raw.get("checkpoint"),
                "player": raw.get("player"),
                "label": raw.get("label"),
                "probability": raw.get("operator_model_probability"),
                "fixture_line_verified": raw.get("fixture_line_verified"),
                "result": "pending",
            })
        if not valid or len(legs) < 2:
            continue
        dependency = comp.get("dependency_diagnostics")
        frozen_dependency = deepcopy(dependency) if isinstance(dependency, dict) else None
        rows.append({
            "prediction_id": pid,
            "version": VERSION,
            "engine_version": current.get("version"),
            "captured_at": now,
            "match_id": mid,
            "p1": match.get("p1"),
            "p2": match.get("p2"),
            "scheduled_time": match.get("scheduled_time"),
            "legs": int(comp.get("legs") or len(legs)),
            "score": comp.get("score"),
            "joint_probability": comp.get("joint_probability"),
            "joint_status": comp.get("joint_status"),
            "selection": legs,
            "dependency_diagnostics": frozen_dependency,
            "dependency_evidence_status": (
                "FROZEN_PREMATCH_EXACT_SHARED_STATE"
                if frozen_dependency is not None else "NOT_AVAILABLE"
            ),
            "result": "pending",
        })
        seen.add(pid)
        captured += 1

    doc.update({
        "version": VERSION,
        "created_from_legacy_symphony": False,
        "legacy_symphony_results_imported": False,
        "entries": rows,
    })
    return doc, captured


def settle(history_doc: dict, base_history: list[dict]) -> tuple[dict, int]:
    doc = dict(history_doc) if isinstance(history_doc, dict) else {"entries": []}
    history_index: dict[str, list[dict]] = {}
    for source in base_history or []:
        if isinstance(source, dict):
            history_index.setdefault(_match_id(source), []).append(source)
    settled = 0
    rows = []
    for raw in doc.get("entries") or []:
        if not isinstance(raw, dict):
            continue
        entry = dict(raw)
        if all(isinstance(leg, dict) and leg.get("result") in TERMINAL
               for leg in entry.get("selection") or []) and entry.get("result") in TERMINAL:
            rows.append(entry)
            continue
        mid = str(entry.get("match_id") or "")
        source, reason = _settlement_evidence(entry, history_index)
        index = _settled_operator_index([source]) if source else {}
        final = _terminal_result(source) if source else None
        legs = []
        statuses = []
        for leg_raw in entry.get("selection") or []:
            if not isinstance(leg_raw, dict):
                continue
            leg = dict(leg_raw)
            if leg.get("result") not in TERMINAL:
                signature = selection_signature(mid, leg)
                status = index.get(signature)
                owner = "archived_exact_operator_signal"
                # A conflicting archived label is unresolved, never a reason
                # to fall through and select a more convenient result.
                if signature not in index and final is not None:
                    status = settle_signal_live(leg, final)
                    owner = "signal_settlement.settle_signal_live"
                if status in TERMINAL:
                    leg.update(result=status, settlement_owner=owner,
                               settlement_source=source["settlement_source"],
                               settlement_version=source["settlement_version"],
                               settled_at=source["settled_at"])
            statuses.append(str(leg.get("result") or "pending"))
            legs.append(leg)
        entry["selection"] = legs
        if any(x not in TERMINAL for x in statuses):
            entry["settlement_pending_reason"] = reason or "NO_UNAMBIGUOUS_TERMINAL_LEG_EVIDENCE"
        else:
            entry.pop("settlement_pending_reason", None)
        # A loss is operationally terminal as soon as one leg misses, but its
        # remaining legs still need evidence for complete performance analysis.
        # Never rewrite an archived terminal outcome or its original timestamp.
        if entry.get("result") in TERMINAL:
            rows.append(entry)
            continue
        non_void = [x for x in statuses if x != "void"]
        if non_void and all(x == "hit" for x in non_void) and all(x in {"hit", "void"} for x in statuses):
            entry["result"] = "hit"
            entry["settled_at"] = source["settled_at"] if source else datetime.now(timezone.utc).isoformat()
            settled += 1
        elif any(x == "miss" for x in statuses):
            entry["result"] = "miss"
            entry["settled_at"] = source["settled_at"] if source else datetime.now(timezone.utc).isoformat()
            settled += 1
        elif statuses and all(x == "void" for x in statuses):
            entry["result"] = "void"
            entry["settled_at"] = source["settled_at"] if source else datetime.now(timezone.utc).isoformat()
            settled += 1
        rows.append(entry)
    doc["entries"] = rows
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return doc, settled


def _brier(observations: list[tuple[float, int]]) -> float | None:
    if not observations:
        return None
    return sum((float(probability) - int(target)) ** 2 for probability, target in observations) / len(observations)


def _decile_label(value: float) -> str:
    bounded = max(0.0, min(1.0, float(value)))
    index = min(9, int(bounded * 10.0))
    lo = index / 10.0
    hi = (index + 1) / 10.0
    return f"{lo:.1f}-{hi:.1f}"


def _calibration_summary(observations: list[tuple[float, int]]) -> dict:
    if not observations:
        return {
            "settled": 0,
            "hits": 0,
            "misses": 0,
            "observed_hit_rate": None,
            "mean_predicted_probability": None,
            "brier": None,
        }
    hits = sum(int(target) for _, target in observations)
    mean_probability = sum(float(probability) for probability, _ in observations) / len(observations)
    return {
        "settled": len(observations),
        "hits": hits,
        "misses": len(observations) - hits,
        "observed_hit_rate": round(100.0 * hits / len(observations), 3),
        "mean_predicted_probability": round(100.0 * mean_probability, 3),
        "brier": round(float(_brier(observations)), 6),
    }


def _dependency_settlement_calibration(entries: list[dict]) -> dict:
    composition_observations: list[tuple[float, int]] = []
    pair_observations: list[dict] = []
    excluded: dict[str, int] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if not _prematch(entry):
            excluded["NOT_PROVEN_PREMATCH"] = excluded.get("NOT_PROVEN_PREMATCH", 0) + 1
            continue
        result = str(entry.get("result") or "")
        joint_probability = _num(entry.get("joint_probability"))
        leg_results = [leg.get("result") for leg in entry.get("selection") or [] if isinstance(leg, dict)]
        complete_binary = (len(leg_results) == _num(entry.get("legs"))
                           and len(leg_results) >= 2
                           and all(x in {"hit", "miss"} for x in leg_results))
        if not complete_binary:
            reason = "VOID_LEGS" if "void" in leg_results else "UNRESOLVED_LEGS"
            excluded[reason] = excluded.get(reason, 0) + 1
        if (complete_binary and result in {"hit", "miss"}
                and joint_probability is not None and 0 <= joint_probability <= 100):
            composition_observations.append((
                max(0.0, min(1.0, float(joint_probability) / 100.0)),
                1 if result == "hit" else 0,
            ))

        diagnostics = entry.get("dependency_diagnostics")
        if not isinstance(diagnostics, dict):
            continue
        legs = {
            str(leg.get("selection_id")): leg
            for leg in (entry.get("selection") or [])
            if isinstance(leg, dict) and leg.get("selection_id") is not None
        }
        for pair in diagnostics.get("pairs") or []:
            if not isinstance(pair, dict):
                continue
            left = legs.get(str(pair.get("left_selection_id")))
            right = legs.get(str(pair.get("right_selection_id")))
            if not isinstance(left, dict) or not isinstance(right, dict):
                continue
            left_result = str(left.get("result") or "")
            right_result = str(right.get("result") or "")
            if left_result not in {"hit", "miss"} or right_result not in {"hit", "miss"}:
                continue
            pair_joint = _num(pair.get("exact_pair_joint_probability"))
            redundancy = _num(pair.get("redundancy_score"))
            conflict = _num(pair.get("conflict_score"))
            if pair_joint is None or not 0 <= pair_joint <= 100:
                continue
            probability = max(0.0, min(1.0, float(pair_joint) / 100.0))
            target = 1 if left_result == "hit" and right_result == "hit" else 0
            pair_observations.append({
                "probability": probability,
                "target": target,
                "redundancy_score": redundancy,
                "conflict_score": conflict,
            })

    redundancy_bins: dict[str, list[tuple[float, int]]] = {}
    for row in pair_observations:
        score = row.get("redundancy_score")
        if score is None:
            continue
        label = _decile_label(float(score))
        redundancy_bins.setdefault(label, []).append((row["probability"], row["target"]))

    return {
        "status": "PROSPECTIVE_SETTLEMENT_CALIBRATION_DIAGNOSTIC_ONLY",
        "prospective_only": True,
        "threshold_selection_enabled": False,
        "ranking_influence": False,
        "composition_joint": _calibration_summary(composition_observations),
        "exact_pair_joint": _calibration_summary([
            (row["probability"], row["target"])
            for row in pair_observations
        ]),
        "by_redundancy_decile": {
            label: _calibration_summary(rows)
            for label, rows in sorted(redundancy_bins.items())
        },
        "pair_outcome_policy": "BOTH_LEGS_MUST_BE_SETTLED_HIT_OR_MISS; HIT_ONLY_IF_BOTH_HIT; VOID_OR_PENDING_EXCLUDED",
        "composition_outcome_policy": "PROVEN_PREMATCH; ALL_LEGS_HIT_OR_MISS; VOID_OR_PENDING_EXCLUDED",
        "composition_excluded_by_reason": excluded,
        "score_source": "FROZEN_PREMATCH_EXACT_SHARED_STATE",
    }


def performance_stats(history_doc: dict) -> dict:
    entries = [x for x in (history_doc.get("entries") or []) if isinstance(x, dict)]
    settled = [x for x in entries if x.get("result") in {"hit", "miss"}]
    hits = sum(1 for x in settled if x.get("result") == "hit")
    legs = [
        leg for entry in entries for leg in (entry.get("selection") or [])
        if isinstance(leg, dict) and leg.get("result") in {"hit", "miss"}
    ]
    leg_hits = sum(1 for x in legs if x.get("result") == "hit")
    by_legs = {}
    for n in range(2, 7):
        subset = [x for x in settled if int(x.get("legs") or 0) == n]
        h = sum(1 for x in subset if x.get("result") == "hit")
        by_legs[str(n)] = {
            "settled": len(subset), "hits": h, "misses": len(subset) - h,
            "accuracy": round(100.0 * h / len(subset), 2) if subset else None,
        }

    diagnostic_entries = [
        x for x in entries
        if isinstance(x.get("dependency_diagnostics"), dict)
    ]
    diagnostic_settled = [
        x for x in diagnostic_entries
        if x.get("result") in {"hit", "miss"}
    ]
    diagnostic_pairs = sum(
        len((x.get("dependency_diagnostics") or {}).get("pairs") or [])
        for x in diagnostic_entries
    )
    diagnostic_settled_pairs = sum(
        len((x.get("dependency_diagnostics") or {}).get("pairs") or [])
        for x in diagnostic_settled
    )
    return {
        "history_version": VERSION,
        "predictions_total": len(entries),
        "predictions_pending": sum(1 for x in entries if x.get("result") == "pending"),
        "compositions_settled": len(settled),
        "compositions_hits": hits,
        "compositions_misses": len(settled) - hits,
        "compositions_with_unresolved_legs": sum(
            any(isinstance(leg, dict) and leg.get("result") not in TERMINAL
                for leg in entry.get("selection") or []) for entry in entries
        ),
        "composition_accuracy": round(100.0 * hits / len(settled), 2) if settled else None,
        "legs_settled": len(legs),
        "legs_hits": leg_hits,
        "legs_misses": len(legs) - leg_hits,
        "leg_accuracy": round(100.0 * leg_hits / len(legs), 2) if legs else None,
        "by_leg_count": by_legs,
        "dependency_evidence": {
            "predictions_with_frozen_diagnostics": len(diagnostic_entries),
            "settled_predictions_with_frozen_diagnostics": len(diagnostic_settled),
            "pair_observations_frozen": diagnostic_pairs,
            "settled_pair_observations": diagnostic_settled_pairs,
            "prospective_only": True,
            "threshold_calibration_enabled": False,
            "ranking_influence": False,
            "settlement_calibration": _dependency_settlement_calibration(entries),
        },
        "legacy_symphony_stats_used": False,
    }


def run() -> dict:
    current = _read(CURRENT, {})
    base_history = _read(BASE_HISTORY, [])
    old_history = _read(HISTORY, {})
    if not isinstance(current, dict):
        raise RuntimeError("symphony2_current.json invalid")
    if not isinstance(base_history, list):
        raise RuntimeError("history.json invalid")

    history_doc, captured = capture(current, old_history)
    history_doc, settled = settle(history_doc, base_history)
    _write(HISTORY, history_doc)

    stats = _read(STATS, {})
    if not isinstance(stats, dict):
        stats = {}
    stats["performance"] = performance_stats(history_doc)
    stats["tracker_version"] = VERSION
    stats["updated_at"] = datetime.now(timezone.utc).isoformat()
    stats["legacy_symphony_stats_used"] = False
    _write(STATS, stats)

    return {
        "status": "OK", "version": VERSION,
        "captured": captured, "settled": settled,
        **stats["performance"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
