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
IMMUTABLE_SNAPSHOT_FIELDS = (
    "match_id",
    "scheduled_time",
    "captured_at",
    "captured_pre_match",
    "tour",
    "surface",
    "p1",
    "p2",
    "source_model_fingerprint_sha256",
    "raw_probabilities",
    "calibrated_probabilities",
)


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
    now: datetime,
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
        snapshot["settled_at"] = now.isoformat()


def _unsettled_diagnostics(
    snapshots: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    buckets = {
        "upcoming": 0,
        "due_within_6h": 0,
        "overdue_6_24h": 0,
        "overdue_24_72h": 0,
        "overdue_gt_72h": 0,
        "unparseable_schedule": 0,
    }
    overdue = []
    for row in snapshots:
        if not isinstance(row, dict) or row.get("settled") is True:
            continue
        scheduled = _parse_utc(row.get("scheduled_time"))
        if scheduled is None:
            buckets["unparseable_schedule"] += 1
            continue
        delta_hours = (now - scheduled).total_seconds() / 3600.0
        if delta_hours < 0:
            buckets["upcoming"] += 1
            continue
        if delta_hours <= 6:
            buckets["due_within_6h"] += 1
        elif delta_hours <= 24:
            buckets["overdue_6_24h"] += 1
        elif delta_hours <= 72:
            buckets["overdue_24_72h"] += 1
        else:
            buckets["overdue_gt_72h"] += 1
        if delta_hours > 6:
            overdue.append({
                "match_id": row.get("match_id"),
                "scheduled_time": row.get("scheduled_time"),
                "hours_since_scheduled": round(delta_hours, 2),
                "p1": row.get("p1"),
                "p2": row.get("p2"),
            })
    overdue.sort(key=lambda row: float(row.get("hours_since_scheduled") or 0), reverse=True)
    return {
        "meaning": "operational age of frozen unsettled snapshots; overdue does not imply cancellation",
        "buckets": buckets,
        "overdue_samples": overdue[:10],
    }


def _settlement_latency_summary(
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    latencies = []
    for row in snapshots:
        if not isinstance(row, dict) or row.get("settled") is not True:
            continue
        scheduled = _parse_utc(row.get("scheduled_time"))
        settled_at = _parse_utc(row.get("settled_at"))
        if scheduled is None or settled_at is None:
            continue
        latencies.append((settled_at - scheduled).total_seconds() / 3600.0)
    latencies.sort()
    if not latencies:
        return {
            "n": 0,
            "median_hours": None,
            "p90_hours": None,
            "max_hours": None,
            "negative_latency_count": 0,
            "meaning": "time from frozen scheduled start to first workflow observation of complete canonical labels",
        }

    def percentile(values: list[float], p: float) -> float:
        if len(values) == 1:
            return values[0]
        position = (len(values) - 1) * p
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        fraction = position - lower
        return values[lower] + (values[upper] - values[lower]) * fraction

    mid = len(latencies) // 2
    median = (
        latencies[mid]
        if len(latencies) % 2
        else (latencies[mid - 1] + latencies[mid]) / 2.0
    )
    return {
        "n": len(latencies),
        "median_hours": round(median, 3),
        "p90_hours": round(percentile(latencies, 0.9), 3),
        "max_hours": round(max(latencies), 3),
        "negative_latency_count": sum(1 for value in latencies if value < 0),
        "meaning": "time from frozen scheduled start to first workflow observation of complete canonical labels",
    }


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


def _ledger_integrity(
    previous_snapshots: list[dict[str, Any]],
    current_snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    """Audit that prospective evidence can only grow or settle, never be rewritten."""

    def _index(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[str]]:
        indexed: dict[str, dict[str, Any]] = {}
        duplicates: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            match_id = str(row.get("match_id") or "").strip()
            if not match_id:
                continue
            if match_id in indexed:
                duplicates.append(match_id)
                continue
            indexed[match_id] = row
        return indexed, sorted(set(duplicates))

    previous_by_id, duplicate_previous_ids = _index(previous_snapshots)
    current_by_id, duplicate_current_ids = _index(current_snapshots)

    missing_previous_ids = sorted(set(previous_by_id) - set(current_by_id))
    rewritten_prediction_ids = []
    settlement_regression_ids = []
    settled_actual_rewrite_ids = []
    settled_at_rewrite_ids = []
    newly_settled_ids = []

    for match_id, old in previous_by_id.items():
        new = current_by_id.get(match_id)
        if not isinstance(new, dict):
            continue

        if any(old.get(field) != new.get(field) for field in IMMUTABLE_SNAPSHOT_FIELDS):
            rewritten_prediction_ids.append(match_id)

        old_settled = old.get("settled") is True
        new_settled = new.get("settled") is True
        if old_settled and not new_settled:
            settlement_regression_ids.append(match_id)
        if old_settled and new_settled and old.get("actual") != new.get("actual"):
            settled_actual_rewrite_ids.append(match_id)
        if old_settled and new_settled and old.get("settled_at") != new.get("settled_at"):
            settled_at_rewrite_ids.append(match_id)
        if not old_settled and new_settled:
            newly_settled_ids.append(match_id)

    new_snapshot_ids = sorted(set(current_by_id) - set(previous_by_id))
    preserved_ids = sorted(set(previous_by_id) & set(current_by_id))
    problems = (
        duplicate_previous_ids
        or duplicate_current_ids
        or missing_previous_ids
        or rewritten_prediction_ids
        or settlement_regression_ids
        or settled_actual_rewrite_ids
        or settled_at_rewrite_ids
    )

    return {
        "status": "LEDGER_INTEGRITY_OK" if not problems else "LEDGER_INTEGRITY_VIOLATION",
        "prediction_rewrite_forbidden": True,
        "settlement_regression_forbidden": True,
        "settled_actual_rewrite_forbidden": True,
        "settled_at_rewrite_forbidden": True,
        "snapshot_drop_forbidden_before_retention_cap": True,
        "retention_cap": MAX_SNAPSHOTS,
        "previous_snapshot_count": len(previous_by_id),
        "current_snapshot_count_before_retention": len(current_by_id),
        "preserved_snapshots": len(preserved_ids),
        "new_snapshots": len(new_snapshot_ids),
        "newly_settled": len(newly_settled_ids),
        "rewritten_predictions": len(rewritten_prediction_ids),
        "settlement_regressions": len(settlement_regression_ids),
        "settled_actual_rewrites": len(settled_actual_rewrite_ids),
        "settled_at_rewrites": len(settled_at_rewrite_ids),
        "missing_previous_snapshots": len(missing_previous_ids),
        "duplicate_previous_match_ids": len(duplicate_previous_ids),
        "duplicate_current_match_ids": len(duplicate_current_ids),
        "violation_samples": {
            "missing_previous": missing_previous_ids[:10],
            "rewritten_predictions": rewritten_prediction_ids[:10],
            "settlement_regressions": settlement_regression_ids[:10],
            "settled_actual_rewrites": settled_actual_rewrite_ids[:10],
            "settled_at_rewrites": settled_at_rewrite_ids[:10],
            "duplicate_previous": duplicate_previous_ids[:10],
            "duplicate_current": duplicate_current_ids[:10],
        },
    }


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
    previous_snapshots = [
        row
        for row in (previous_rows if isinstance(previous_rows, list) else [])
        if isinstance(row, dict) and row.get("match_id") is not None
    ]
    snapshots = [dict(row) for row in previous_snapshots]
    by_id = {str(row.get("match_id")): row for row in snapshots}

    current_rows = current_simulation.get("matches") if isinstance(current_simulation, dict) else []
    current_rows = current_rows if isinstance(current_rows, list) else []
    eligible_current = 0
    schedule_drifts = []
    for row in current_rows:
        if not isinstance(row, dict):
            continue
        eligibility = prospective_eligibility(row, walk_forward)
        if eligibility["eligible"] is True:
            eligible_current += 1
        match_id = str(row.get("match_id") or "").strip()
        if not match_id:
            continue
        if match_id in by_id:
            frozen_time = _parse_utc(by_id[match_id].get("scheduled_time"))
            current_time = _parse_utc(row.get("scheduled_time"))
            if frozen_time is not None and current_time is not None:
                drift_minutes = (current_time - frozen_time).total_seconds() / 60.0
                if abs(drift_minutes) >= 1.0:
                    schedule_drifts.append({
                        "match_id": match_id,
                        "frozen_scheduled_time": frozen_time.isoformat(),
                        "current_scheduled_time": current_time.isoformat(),
                        "drift_minutes": round(drift_minutes, 2),
                    })
            continue
        snapshot = _snapshot_from_current(row, walk_forward, now, labels)
        if snapshot is not None:
            snapshots.append(snapshot)
            by_id[match_id] = snapshot

    _settle_snapshots(snapshots, labels, now)

    integrity = _ledger_integrity(previous_snapshots, snapshots)
    if integrity.get("status") != "LEDGER_INTEGRITY_OK":
        raise RuntimeError(
            "Player DNA prospective ledger integrity violation: "
            + json.dumps(integrity, ensure_ascii=False, sort_keys=True)
        )

    snapshots.sort(key=lambda row: (str(row.get("scheduled_time") or ""), str(row.get("match_id") or "")))
    before_retention = len(snapshots)
    if len(snapshots) > MAX_SNAPSHOTS:
        snapshots = snapshots[-MAX_SNAPSHOTS:]
    integrity["pruned_by_retention"] = before_retention - len(snapshots)
    integrity["current_snapshot_count_after_retention"] = len(snapshots)

    evaluation = _evaluation(snapshots)
    unsettled_diagnostics = _unsettled_diagnostics(snapshots, now)
    settlement_latency = _settlement_latency_summary(snapshots)
    settlement_observability = {
        "unsettled": unsettled_diagnostics,
        "settlement_latency": settlement_latency,
        "schedule_drift": {
            "count": len(schedule_drifts),
            "meaning": "current schedule differs from immutable frozen prospective schedule; snapshot is never rewritten",
            "samples": sorted(
                schedule_drifts,
                key=lambda row: abs(float(row.get("drift_minutes") or 0)),
                reverse=True,
            )[:10],
        },
    }
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
        "ledger_integrity": integrity,
        "settlement_observability": settlement_observability,
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
        "ledger_integrity": report.get("ledger_integrity"),
        "settlement_observability": report.get("settlement_observability"),
        "production_influence": report.get("production_influence"),
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
