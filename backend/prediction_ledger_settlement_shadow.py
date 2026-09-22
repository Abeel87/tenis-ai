from __future__ import annotations

"""Exact terminal settlement evidence for the prospective prediction ledger.

This module is SHADOW-only and additive. It never mutates the immutable
pre-selection ledger and never performs network access. Terminal match evidence
comes only from the canonical settled history owner and candidate resolution is
delegated to the existing shared signal settlement scorer.
"""

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from . import prediction_ledger_shadow
    from . import signal_settlement
except ImportError:
    import prediction_ledger_shadow
    import signal_settlement

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"
LEDGER = DATA / "prediction_ledger_shadow.json"
HISTORY = DATA / "history.json"
SELECTION = DATA / "prediction_ledger_selection_shadow.json"
OUT = DATA / "prediction_ledger_settlement_shadow.json"

SCHEMA_VERSION = "prediction-ledger-settlement-shadow-v1"
MODE = "SHADOW_ONLY"
BINARY_RESULTS = {"hit", "miss"}
TERMINAL_RESULTS = {"hit", "miss", "void"}
TERMINAL_MATCH_STATUSES = {"completed", "retired", "void"}


def _read(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _nd(reason: str, *, detail: str | None = None) -> dict[str, Any]:
    out = {
        "status": "N/D",
        "result": None,
        "reason": reason,
        "settlement_owner": "signal_settlement",
        "terminal_result_owner": "live_history_settle",
    }
    if detail:
        out["detail"] = detail
    return out


def _ledger_is_prematch(row: dict[str, Any]) -> bool:
    captured = _parse_dt(row.get("captured_at"))
    scheduled = _parse_dt(row.get("scheduled_time"))
    return bool(captured and scheduled and captured < scheduled)


def _exact_live_match_key(row: dict[str, Any]) -> str | None:
    key = str(row.get("match_key") or "").strip()
    if not key.startswith("id:"):
        return None
    token = key[3:]
    if not token.isdigit():
        return None
    return key


def _history_exact_key(entry: dict[str, Any]) -> str | None:
    key = str(entry.get("match_key") or "").strip()
    mid = entry.get("match_id")
    if not key.startswith("id:") or mid is None:
        return None
    if key != f"id:{mid}":
        return None
    if not str(mid).isdigit():
        return None
    return key


def _history_index(history: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for raw in history or []:
        if not isinstance(raw, dict):
            continue
        key = _history_exact_key(raw)
        if key is None:
            continue
        out.setdefault(key, []).append(raw)
    return out


def _selection_index(selection_doc: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], set[str]]:
    rows = selection_doc.get("rows") if isinstance(selection_doc, dict) else []
    index: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        prediction_id = str(raw.get("prediction_id") or "").strip()
        if not prediction_id:
            continue
        if prediction_id in index:
            duplicates.add(prediction_id)
            continue
        index[prediction_id] = raw
    return index, duplicates


def _selection_population_facts(
    prediction_id: str,
    selection_index: dict[str, dict[str, Any]],
    selection_duplicates: set[str],
) -> dict[str, Any]:
    if prediction_id in selection_duplicates:
        return {
            "ALL": True,
            "PLAYABLE": None,
            "SYMPHONY_SELECTED": None,
            "INEED_SELECTED": None,
            "status": "N/D",
            "reason": "AMBIGUOUS_SELECTION_SIDECAR_IDENTITY",
        }
    row = selection_index.get(prediction_id)
    if row is None:
        return {
            "ALL": True,
            "PLAYABLE": None,
            "SYMPHONY_SELECTED": None,
            "INEED_SELECTED": None,
            "status": "N/D",
            "reason": "NO_EXACT_SELECTION_SIDECAR_ROW",
        }
    facts = row.get("facts") or {}
    playable = facts.get("playable") or {}
    symphony = facts.get("symphony_selected") or {}
    ineed = facts.get("ineed_selected") or {}
    return {
        "ALL": True,
        "PLAYABLE": True if playable.get("value") is True else None,
        "SYMPHONY_SELECTED": True if symphony.get("value") is True else None,
        "INEED_SELECTED": True if ineed.get("value") is True else None,
        "status": "EXACT_SELECTION_ROW",
        "playable_status": playable.get("status") or "N/D",
        "symphony_status": symphony.get("status") or "N/D",
        "ineed_status": ineed.get("status") or "N/D",
    }


def _common_models_available(row: dict[str, Any]) -> bool:
    scores = row.get("model_scores") or {}
    return all((scores.get(name) or {}).get("available") is True for name in ("current", "catboost", "tabpfn"))


def _signal_from_ledger(row: dict[str, Any]) -> dict[str, Any] | None:
    market = str(row.get("market") or "").strip()
    pick = row.get("pick")
    if not market or pick is None:
        return None
    return {
        "market": market,
        "pick": pick,
        "line": row.get("line"),
        "checkpoint": row.get("checkpoint"),
        "player": row.get("player"),
    }


def _settlement_fact(
    row: dict[str, Any],
    history_index: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if not _ledger_is_prematch(row):
        return _nd("LEDGER_NOT_VALID_PREMATCH_EVIDENCE")

    match_key = _exact_live_match_key(row)
    if match_key is None:
        return _nd("LEDGER_MATCH_KEY_NOT_EXACT_LIVE_TENNIS_ID")

    evidence = history_index.get(match_key) or []
    if not evidence:
        return _nd("NO_EXACT_HISTORY_MATCH")
    if len(evidence) != 1:
        return _nd("AMBIGUOUS_EXACT_HISTORY_MATCH", detail=f"matches={len(evidence)}")

    entry = evidence[0]
    ledger_scheduled = _parse_dt(row.get("scheduled_time"))
    history_scheduled = _parse_dt(entry.get("scheduled_time"))
    if ledger_scheduled is None or history_scheduled is None or ledger_scheduled != history_scheduled:
        return _nd("EXACT_MATCH_ID_SCHEDULE_CONFLICT")

    final = entry.get("result")
    if not isinstance(final, dict) or final.get("status") not in TERMINAL_MATCH_STATUSES:
        return _nd("EXACT_HISTORY_MATCH_NOT_TERMINAL")
    if entry.get("status") not in {"settled", "void"}:
        return _nd("EXACT_HISTORY_ENTRY_NOT_SETTLED")

    settled_at = _parse_dt(entry.get("settled_at"))
    if settled_at is None:
        return _nd("MISSING_SETTLED_AT_PROVENANCE")
    if settled_at < ledger_scheduled:
        return _nd("SETTLEMENT_TIMESTAMP_PRECEDES_MATCH_START")

    source = str(entry.get("settlement_source") or "").strip()
    version = str(entry.get("settlement_version") or "").strip()
    if not source or not version:
        return _nd("MISSING_SETTLEMENT_PROVENANCE")

    signal = _signal_from_ledger(row)
    if signal is None:
        return _nd("MISSING_LEDGER_SELECTION_DIMENSION")

    resolved = signal_settlement.settle_signal_live(signal, final)
    if resolved == "unverifiable":
        return _nd("CANONICAL_SCORER_UNVERIFIABLE")
    if resolved not in TERMINAL_RESULTS:
        return _nd("CANONICAL_SCORER_NON_TERMINAL_RESULT", detail=str(resolved))

    return {
        "status": "SETTLED",
        "result": resolved,
        "reason": None,
        "settled_at": settled_at.isoformat(),
        "settlement_source": source,
        "settlement_version": version,
        "terminal_match_status": final.get("status"),
        "settlement_owner": "signal_settlement.settle_signal_live",
        "terminal_result_owner": "live_history_settle",
        "exact_match_key": match_key,
    }


def _probability(row: dict[str, Any], name: str) -> float | None:
    score = ((row.get("model_scores") or {}).get(name) or {})
    if score.get("available") is not True:
        return None
    value = score.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    p = float(value)
    if not math.isfinite(p) or p < 0.0 or p > 1.0:
        return None
    return p


def _calibration_bins_10(scored: list[tuple[float, int]]) -> list[dict[str, Any]]:
    """Return descriptive fixed decile calibration bins; never a promotion score."""
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(10)]
    for probability, label in scored:
        index = min(9, int(probability * 10.0))
        buckets[index].append((probability, label))
    out: list[dict[str, Any]] = []
    for index, bucket in enumerate(buckets):
        n = len(bucket)
        out.append({
            "index": index,
            "lower_inclusive": round(index / 10.0, 1),
            "upper": round((index + 1) / 10.0, 1),
            "upper_inclusive": index == 9,
            "n": n,
            "mean_probability": round(sum(p for p, _ in bucket) / n, 6) if n else None,
            "observed_hit_rate": round(sum(y for _, y in bucket) / n, 6) if n else None,
        })
    return out


def _model_metrics(records: list[dict[str, Any]], model: str) -> dict[str, Any]:
    scored: list[tuple[float, int]] = []
    for record in records:
        result = (record.get("settlement") or {}).get("result")
        if result not in BINARY_RESULTS:
            continue
        p = _probability(record.get("ledger") or {}, model)
        if p is None:
            continue
        scored.append((p, 1 if result == "hit" else 0))
    if not scored:
        return {
            "n": 0,
            "binary_accuracy_at_0_5": None,
            "brier": None,
            "log_loss": None,
            "mean_probability": None,
            "calibration_bins_10": _calibration_bins_10([]),
        }
    n = len(scored)
    correct = sum(1 for p, y in scored if (p >= 0.5) == bool(y))
    brier = sum((p - y) ** 2 for p, y in scored) / n
    eps = 1e-15
    log_loss = -sum(y * math.log(max(eps, min(1.0 - eps, p))) + (1 - y) * math.log(max(eps, min(1.0 - eps, 1.0 - p))) for p, y in scored) / n
    return {
        "n": n,
        "binary_accuracy_at_0_5": round(correct / n, 6),
        "brier": round(brier, 6),
        "log_loss": round(log_loss, 6),
        "mean_probability": round(sum(p for p, _ in scored) / n, 6),
        "calibration_bins_10": _calibration_bins_10(scored),
    }


def _in_population(record: dict[str, Any], population: str) -> bool:
    facts = record.get("population_facts") or {}
    if population == "ALL":
        return True
    if population == "PLAYABLE":
        return facts.get("PLAYABLE") is True
    if population == "SYMPHONY_SELECTED":
        return facts.get("SYMPHONY_SELECTED") is True
    if population == "PLAYABLE_AND_SYMPHONY":
        return facts.get("PLAYABLE") is True and facts.get("SYMPHONY_SELECTED") is True
    return False


def _common_binary_records(records: list[dict[str, Any]], population: str) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if _in_population(record, population)
        and record.get("common_current_catboost_tabpfn") is True
        and (record.get("settlement") or {}).get("result") in BINARY_RESULTS
    ]


def _binary_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n": len(records),
        "hit_rate": round(sum(1 for r in records if (r.get("settlement") or {}).get("result") == "hit") / len(records), 6) if records else None,
        "models": {
            name: _model_metrics(records, name)
            for name in ("current", "catboost", "tabpfn")
        },
    }


def _market_reports(records: list[dict[str, Any]], population: str) -> dict[str, Any]:
    binary = _common_binary_records(records, population)
    markets = sorted({str(record.get("market") or "N/D") for record in binary})
    return {
        market: _binary_report([record for record in binary if str(record.get("market") or "N/D") == market])
        for market in markets
    }


def _scheduled_utc_day(record: dict[str, Any]) -> str | None:
    parsed = _parse_dt(record.get("scheduled_time"))
    return parsed.date().isoformat() if parsed is not None else None


def _temporal_walk_forward(records: list[dict[str, Any]], population: str, *, as_of: datetime) -> dict[str, Any]:
    """Descriptive expanding-window audit over complete UTC schedule days.

    Frozen probabilities are never retrained, recalibrated or selected from the
    training window. Prior days exist only to prove strict chronology and sample
    growth; every test window is the next disjoint UTC day.
    """
    binary = _common_binary_records(records, population)
    dated = [(record, _scheduled_utc_day(record)) for record in binary]
    eligible = [(record, day) for record, day in dated if day is not None]
    as_of_day = as_of.astimezone(timezone.utc).date().isoformat()
    complete = [(record, day) for record, day in eligible if day < as_of_day]
    incomplete = [(record, day) for record, day in eligible if day >= as_of_day]
    dates = sorted({day for _, day in complete})
    folds: list[dict[str, Any]] = []
    for index, test_day in enumerate(dates[1:], start=1):
        test_start = datetime.fromisoformat(test_day + "T00:00:00+00:00")
        train_candidates = [record for record, day in complete if day < test_day]
        train = [
            record
            for record in train_candidates
            if (_parse_dt((record.get("settlement") or {}).get("settled_at")) or as_of) < test_start
        ]
        train_late_labels = len(train_candidates) - len(train)
        test = [record for record, day in complete if day == test_day]
        train_match_keys = {str(record.get("match_key") or "") for record in train}
        test_match_keys = {str(record.get("match_key") or "") for record in test}
        folds.append({
            "fold": index,
            "train_start_date": dates[0],
            "train_end_date": dates[index - 1],
            "test_date": test_day,
            "train_rows": len(train),
            "train_rows_excluded_late_settlement": train_late_labels,
            "test_rows": len(test),
            "match_key_overlap": len(train_match_keys & test_match_keys),
            "test_metrics": _binary_report(test),
            "test_markets": {
                market: _binary_report([record for record in test if str(record.get("market") or "N/D") == market])
                for market in sorted({str(record.get("market") or "N/D") for record in test})
            },
        })
    return {
        "status": "CHRONOLOGICAL_FOLDS_AVAILABLE" if folds else "INSUFFICIENT_DISTINCT_UTC_DATES",
        "policy": "EXPANDING_PRIOR_COMPLETE_UTC_DAYS_TO_NEXT_COMPLETE_UTC_DAY",
        "frozen_predictions_only": True,
        "retraining_enabled": False,
        "recalibration_enabled": False,
        "ranking_enabled": False,
        "promotion_enabled": False,
        "as_of_utc_date": as_of_day,
        "distinct_complete_utc_dates": dates,
        "undated_binary_rows": len(dated) - len(eligible),
        "incomplete_or_future_utc_day_binary_rows": len(incomplete),
        "fold_count": len(folds),
        "folds": folds,
    }


def _population_report(records: list[dict[str, Any]], population: str, *, as_of: datetime) -> dict[str, Any]:
    rows = [r for r in records if _in_population(r, population)]
    common = [r for r in rows if r.get("common_current_catboost_tabpfn") is True]
    binary = _common_binary_records(records, population)
    void = [r for r in common if (r.get("settlement") or {}).get("result") == "void"]
    report = _binary_report(binary)
    return {
        "rows": len(rows),
        "common_model_rows": len(common),
        "common_binary_settled_rows": len(binary),
        "common_void_rows": len(void),
        "hit_rate": report["hit_rate"],
        "models": report["models"],
        "market_reports": _market_reports(records, population),
        "temporal_walk_forward": _temporal_walk_forward(records, population, as_of=as_of),
    }


def build_sidecar(
    ledger_doc: dict[str, Any],
    history: list[dict[str, Any]],
    selection_doc: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    if not isinstance(ledger_doc, dict) or ledger_doc.get("schema_version") != prediction_ledger_shadow.SCHEMA_VERSION:
        raise ValueError("prediction ledger schema mismatch")
    rows = ledger_doc.get("rows")
    if not isinstance(rows, list):
        raise ValueError("prediction ledger rows must be a list")

    parsed_now = _parse_dt(now)
    if parsed_now is None:
        raise ValueError("generation time must be valid")

    history_index = _history_index(history)
    selection_index, selection_duplicates = _selection_index(selection_doc)
    records: list[dict[str, Any]] = []

    for raw in rows:
        if not isinstance(raw, dict):
            continue
        prediction_id = str(raw.get("prediction_id") or "").strip()
        settlement = _settlement_fact(raw, history_index)
        populations = _selection_population_facts(prediction_id, selection_index, selection_duplicates)
        records.append({
            "prediction_id": prediction_id or None,
            "match_key": raw.get("match_key"),
            "candidate_key": raw.get("candidate_key"),
            "market": raw.get("market"),
            "scheduled_time": raw.get("scheduled_time"),
            "ledger_captured_at": raw.get("captured_at"),
            "common_current_catboost_tabpfn": _common_models_available(raw),
            "population_facts": populations,
            "settlement": settlement,
            "ledger": raw,
        })

    # Keep model score snapshots only in the immutable source ledger. The sidecar
    # references them by prediction_id and drops the temporary copy before write.
    output_rows = [
        {k: v for k, v in record.items() if k != "ledger"}
        for record in records
    ]

    result_counts = {name: 0 for name in ("hit", "miss", "void", "N/D")}
    for record in records:
        fact = record.get("settlement") or {}
        result = fact.get("result")
        if result in TERMINAL_RESULTS:
            result_counts[str(result)] += 1
        else:
            result_counts["N/D"] += 1

    population_reports = {
        population: _population_report(records, population, as_of=parsed_now)
        for population in ("ALL", "PLAYABLE", "SYMPHONY_SELECTED", "PLAYABLE_AND_SYMPHONY")
    }
    common_binary = population_reports["ALL"]["common_binary_settled_rows"]

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "generated_at": parsed_now.isoformat(),
        "source_ledger_schema_version": ledger_doc.get("schema_version"),
        "source_ledger_sha256": _canonical_sha256(ledger_doc),
        "source_selection_schema_version": selection_doc.get("schema_version") if isinstance(selection_doc, dict) else None,
        "source_selection_sha256": _canonical_sha256(selection_doc) if isinstance(selection_doc, dict) and selection_doc else None,
        "settlement_contract": "EXACT_LIVE_TENNIS_MATCH_ID_AND_EXACT_SCHEDULE_THEN_CANONICAL_SIGNAL_SCORER",
        "absence_semantics": "N/D_NOT_FALSE",
        "network_fetch_enabled": False,
        "source_ledger_mutated": False,
        "rows": output_rows,
        "summary": {
            "rows": len(output_rows),
            "settlement_results": result_counts,
            "exact_history_match_keys": len(history_index),
            "common_current_catboost_tabpfn": population_reports["ALL"]["common_model_rows"],
            "common_binary_settled": common_binary,
            "common_void": population_reports["ALL"]["common_void_rows"],
            "common_set_status": "HAS_SETTLED_COMMON_ROWS" if common_binary else "NO_SETTLED_COMMON_ROWS",
            "population_reports": population_reports,
        },
        "metric_contract": {
            "binary_results": ["hit", "miss"],
            "void_excluded_from_binary_metrics": True,
            "common_intersection_required": ["current", "catboost", "tabpfn"],
            "calibration_bins": 10,
            "calibration_is_descriptive_only": True,
            "market_reports_are_descriptive_only": True,
            "temporal_policy": "EXPANDING_PRIOR_COMPLETE_UTC_DAYS_TO_NEXT_COMPLETE_UTC_DAY",
            "temporal_retraining_enabled": False,
            "temporal_recalibration_enabled": False,
            "ranking_enabled": False,
            "automatic_winner_selection_enabled": False,
            "minimum_sample_gate_defined": False,
        },
        "owner_contract": {
            "terminal_match_owner": "backend/live_history_settle.py",
            "candidate_scorer_owner": "backend/signal_settlement.py::settle_signal_live",
            "ledger_owner": "backend/prediction_ledger_shadow.py",
            "selection_population_owner": "backend/prediction_ledger_selection_shadow.py",
        },
        "production_influence": False,
        "runtime_gating_enabled": False,
        "learning_consumer_enabled": False,
        "telemetry_consumer_enabled": False,
        "auto_promote": False,
    }


def main() -> int:
    ledger_doc = _read(LEDGER, {})
    history = _read(HISTORY, [])
    selection_doc = _read(SELECTION, {})
    doc = build_sidecar(
        ledger_doc,
        history if isinstance(history, list) else [],
        selection_doc if isinstance(selection_doc, dict) else {},
        now=datetime.now(timezone.utc),
    )
    _write(OUT, doc)
    print(json.dumps(doc.get("summary") or {}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
