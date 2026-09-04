from __future__ import annotations

"""Prospective SHADOW validation for the Player DNA hold-calibrated candidate.

Historical holdout and walk-forward evidence can still overstate real-world
performance. This module freezes only pre-match predictions from segments that
were repeatable in the walk-forward audit, then settles them later from the
canonical point tape. It never changes the simulator, PROD, Symfonia 2.0 or
Superbet PLAYABLE.
"""

import gzip
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.player_dna_market_backtest import _binary_probability, _labels_by_match
except ModuleNotFoundError:  # direct execution
    from player_dna_market_backtest import _binary_probability, _labels_by_match

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "data" / "derived" / "player_dna" / "point_events.jsonl.gz"
CURRENT_SIMULATION = ROOT / "frontend" / "data" / "player_dna_current_simulation.json"
WALK_FORWARD = ROOT / "frontend" / "data" / "player_dna_hold_walk_forward.json"
OUT = ROOT / "frontend" / "data" / "player_dna_prospective_validation.json"

VERSION = "player-dna-prospective-validation-v1"
MODE = "SHADOW_PROSPECTIVE_VALIDATION_ONLY"
DURATION_MARKETS = (
    "first_set_tiebreak",
    "first_set_over_8.5",
    "first_set_over_9.5",
    "first_set_over_10.5",
)
MIN_PREMATCH_LEAD_MINUTES = 5
MIN_SETTLED_FOR_SIGNAL = 150
MIN_SEGMENT_SETTLED = 30
MAX_SNAPSHOTS = 5000


def _iter_jsonl_gz(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _repeatable_segments(walk_forward: dict[str, Any], dimension: str) -> set[str]:
    if (
        not isinstance(walk_forward, dict)
        or walk_forward.get("mode") != "SHADOW_WALK_FORWARD_AUDIT_ONLY"
        or walk_forward.get("status") != "WALK_FORWARD_COMPLETE_NO_INTEGRATION"
        or walk_forward.get("signal") != "HOLD_CALIBRATION_WALK_FORWARD_ROBUST_SHADOW"
        or walk_forward.get("production_influence") is not False
        or walk_forward.get("symphony2_influence") is not False
        or walk_forward.get("superbet_playable_influence") is not False
        or walk_forward.get("auto_integrate") is not False
    ):
        return set()

    rows = ((walk_forward.get("segment_aggregate") or {}).get(dimension) or {})
    if not isinstance(rows, dict):
        return set()
    return {
        str(name).strip().lower()
        for name, row in rows.items()
        if isinstance(row, dict) and row.get("repeatable_duration_signal") is True
    }


def prospective_eligibility(
    row: dict[str, Any],
    walk_forward: dict[str, Any],
) -> dict[str, Any]:
    tours = _repeatable_segments(walk_forward, "tour")
    surfaces = _repeatable_segments(walk_forward, "surface")
    tour = str(row.get("tour") or "").strip().lower()
    surface = str(row.get("surface") or "").strip().lower()
    tour_ok = bool(tour and tour in tours)
    surface_ok = bool(surface and surface in surfaces)
    return {
        "eligible": bool(tour_ok and surface_ok),
        "tour": tour,
        "surface": surface,
        "tour_repeatable": tour_ok,
        "surface_repeatable": surface_ok,
        "supported_tours": sorted(tours),
        "supported_surfaces": sorted(surfaces),
        "policy": "tour AND surface must both have repeatable duration signal in mature walk-forward",
    }


def _market_probabilities(simulation: dict[str, Any]) -> dict[str, float]:
    out = {}
    for market in DURATION_MARKETS:
        probability = _binary_probability(simulation, market)
        if probability is not None:
            out[market] = float(probability)
    return out


def _snapshot_from_current(
    row: dict[str, Any],
    walk_forward: dict[str, Any],
    now: datetime,
    labels: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    eligibility = prospective_eligibility(row, walk_forward)
    if eligibility["eligible"] is not True:
        return None

    match_id = str(row.get("match_id") or "").strip()
    scheduled = _parse_utc(row.get("scheduled_time"))
    if not match_id or scheduled is None:
        return None
    if scheduled < now + timedelta(minutes=MIN_PREMATCH_LEAD_MINUTES):
        return None
    # Never create a prospective observation after the canonical tape already
    # knows the result.
    if match_id in labels:
        return None

    raw = row.get("simulation")
    calibrated = row.get("hold_calibrated_candidate")
    if not isinstance(raw, dict) or not isinstance(calibrated, dict):
        return None
    if calibrated.get("mode") != "SHADOW_HOLD_CALIBRATED_CANDIDATE":
        return None
    for key in ("production_influence", "symphony2_influence", "superbet_playable_influence", "auto_promote"):
        if calibrated.get(key) is not False:
            return None

    raw_probabilities = _market_probabilities(raw)
    calibrated_probabilities = _market_probabilities(calibrated)
    if set(raw_probabilities) != set(DURATION_MARKETS):
        return None
    if set(calibrated_probabilities) != set(DURATION_MARKETS):
        return None

    return {
        "match_id": match_id,
        "scheduled_time": scheduled.isoformat(),
        "captured_at": now.isoformat(),
        "captured_pre_match": True,
        "tour": eligibility["tour"],
        "surface": eligibility["surface"],
        "p1": row.get("p1"),
        "p2": row.get("p2"),
        "source_model_fingerprint_sha256": row.get("source_model_fingerprint_sha256"),
        "raw_probabilities": raw_probabilities,
        "calibrated_probabilities": calibrated_probabilities,
        "settled": False,
        "actual": None,
    }


def _settle_snapshots(
    snapshots: list[dict[str, Any]],
    labels: dict[str, dict[str, Any]],
) -> None:
    for snapshot in snapshots:
        if not isinstance(snapshot, dict) or snapshot.get("settled") is True:
            continue
        label = labels.get(str(snapshot.get("match_id") or ""))
        if not isinstance(label, dict):
            continue
        actual = {}
        complete = True
        for market in DURATION_MARKETS:
            value = label.get(market)
            if not isinstance(value, bool):
                complete = False
                break
            actual[market] = bool(value)
        if not complete:
            continue
        snapshot["settled"] = True
        snapshot["actual"] = actual


def _evaluation(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    settled = [row for row in snapshots if isinstance(row, dict) and row.get("settled") is True]
    markets = {}
    for market in DURATION_MARKETS:
        raw_error = []
        calibrated_error = []
        for row in settled:
            actual = (row.get("actual") or {}).get(market)
            raw = (row.get("raw_probabilities") or {}).get(market)
            calibrated = (row.get("calibrated_probabilities") or {}).get(market)
            if not isinstance(actual, bool) or raw is None or calibrated is None:
                continue
            y = 1.0 if actual else 0.0
            raw_error.append((float(raw) - y) ** 2)
            calibrated_error.append((float(calibrated) - y) ** 2)
        if not raw_error:
            markets[market] = {"n": 0}
            continue
        raw_brier = sum(raw_error) / len(raw_error)
        calibrated_brier = sum(calibrated_error) / len(calibrated_error)
        markets[market] = {
            "n": len(raw_error),
            "raw_brier": round(raw_brier, 6),
            "calibrated_brier": round(calibrated_brier, 6),
            "brier_gain_calibrated_vs_raw": round(raw_brier - calibrated_brier, 6),
            "improved": calibrated_brier < raw_brier,
        }

    positive = sum(1 for row in markets.values() if row.get("improved") is True)
    worst_gain = min(
        [float(row["brier_gain_calibrated_vs_raw"]) for row in markets.values() if row.get("n")]
        or [0.0]
    )
    return {
        "settled_matches": len(settled),
        "markets": markets,
        "duration_markets_improved": positive,
        "duration_markets_total": len(DURATION_MARKETS),
        "worst_market_brier_gain": round(worst_gain, 6),
    }


def _segment_evaluation(
    snapshots: list[dict[str, Any]],
    dimension: str,
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in snapshots:
        if not isinstance(row, dict) or row.get("settled") is not True:
            continue
        value = str(row.get(dimension) or "unknown").strip().lower()
        groups[value].append(row)

    out = {}
    for value, rows in sorted(groups.items()):
        report = _evaluation(rows)
        report["support_sufficient"] = int(report.get("settled_matches") or 0) >= MIN_SEGMENT_SETTLED
        out[value] = report
    return out


def build_report(
    current_simulation: dict[str, Any],
    walk_forward: dict[str, Any],
    point_rows: list[dict[str, Any]],
    previous: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    labels, label_counts = _labels_by_match(point_rows)

    previous_rows = (previous or {}).get("snapshots") if isinstance(previous, dict) else []
    snapshots = [
        dict(row)
        for row in (previous_rows if isinstance(previous_rows, list) else [])
        if isinstance(row, dict) and row.get("match_id") is not None
    ]
    by_id = {str(row.get("match_id")): row for row in snapshots}

    current_rows = current_simulation.get("matches") if isinstance(current_simulation, dict) else []
    current_rows = current_rows if isinstance(current_rows, list) else []
    eligible_current = 0
    for row in current_rows:
        if not isinstance(row, dict):
            continue
        eligibility = prospective_eligibility(row, walk_forward)
        if eligibility["eligible"] is True:
            eligible_current += 1
        match_id = str(row.get("match_id") or "").strip()
        if not match_id or match_id in by_id:
            continue
        snapshot = _snapshot_from_current(row, walk_forward, now, labels)
        if snapshot is not None:
            snapshots.append(snapshot)
            by_id[match_id] = snapshot

    _settle_snapshots(snapshots, labels)
    snapshots.sort(key=lambda row: (str(row.get("scheduled_time") or ""), str(row.get("match_id") or "")))
    if len(snapshots) > MAX_SNAPSHOTS:
        snapshots = snapshots[-MAX_SNAPSHOTS:]

    evaluation = _evaluation(snapshots)
    settled = int(evaluation.get("settled_matches") or 0)
    if settled < MIN_SETTLED_FOR_SIGNAL:
        signal = "COLLECTING_PROSPECTIVE_EVIDENCE"
    else:
        positive = int(evaluation.get("duration_markets_improved") or 0)
        worst = float(evaluation.get("worst_market_brier_gain") or 0.0)
        signal = (
            "PROSPECTIVE_DURATION_ROBUST_SHADOW"
            if positive >= 3 and worst >= -0.002
            else "PROSPECTIVE_DURATION_NOT_YET_PROVEN"
        )

    supported_tours = sorted(_repeatable_segments(walk_forward, "tour"))
    supported_surfaces = sorted(_repeatable_segments(walk_forward, "surface"))
    return {
        "version": VERSION,
        "mode": MODE,
        "status": "PROSPECTIVE_COLLECTION_ACTIVE",
        "signal": signal,
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "current_simulator_modified": False,
        "auto_integrate": False,
        "market_scope": "DURATION_MARKETS_ONLY",
        "winner_markets_promoted": False,
        "eligibility_policy": {
            "requires_walk_forward_robust": True,
            "requires_repeatable_tour": True,
            "requires_repeatable_surface": True,
            "supported_tours": supported_tours,
            "supported_surfaces": supported_surfaces,
            "minimum_pre_match_lead_minutes": MIN_PREMATCH_LEAD_MINUTES,
            "post_result_snapshot_forbidden": True,
        },
        "source": {
            "walk_forward_version": walk_forward.get("version") if isinstance(walk_forward, dict) else None,
            "walk_forward_signal": walk_forward.get("signal") if isinstance(walk_forward, dict) else None,
            "current_simulation_version": current_simulation.get("version") if isinstance(current_simulation, dict) else None,
        },
        "counts": {
            "current_simulated_matches": len(current_rows),
            "current_eligible_by_segment": eligible_current,
            "snapshots": len(snapshots),
            "settled_snapshots": settled,
            "unsettled_snapshots": sum(1 for row in snapshots if row.get("settled") is not True),
            "label_counts": label_counts,
        },
        "evaluation": evaluation,
        "segment_evaluation": {
            "tour": _segment_evaluation(snapshots, "tour"),
            "surface": _segment_evaluation(snapshots, "surface"),
        },
        "snapshots": snapshots,
    }


def build() -> dict[str, Any]:
    try:
        current = json.loads(CURRENT_SIMULATION.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        current = {}
    try:
        walk_forward = json.loads(WALK_FORWARD.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        walk_forward = {}
    try:
        previous = json.loads(OUT.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        previous = {}

    point_rows = list(_iter_jsonl_gz(POINTS) or ())
    report = build_report(current, walk_forward, point_rows, previous)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": report.get("version"),
        "status": report.get("status"),
        "signal": report.get("signal"),
        "counts": report.get("counts"),
        "supported_tours": (report.get("eligibility_policy") or {}).get("supported_tours"),
        "supported_surfaces": (report.get("eligibility_policy") or {}).get("supported_surfaces"),
        "production_influence": report.get("production_influence"),
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
