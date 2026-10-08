"""Autonomous, read-only ensemble search over prospectively frozen SHADOW evidence.

No operator odds, monetary decisions, live feeds, model promotion or PROD writes.
Validation selects a candidate; a later untouched holdout measures that selection.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"
LEDGER = DATA / "prediction_ledger_shadow.json"
SETTLEMENT = DATA / "prediction_ledger_settlement_shadow.json"
REPORT = DATA / "self_evolution_shadow.json"
MODELS = ("current", "catboost", "tabpfn")
VERSION = "self-evolution-shadow-v1"
MIN_MATCHES = (120, 40, 40)  # independent fixture identities, not row counts
MIN_SPECIALIST_MATCHES = (60, 20, 20)
MAX_SPECIALIST_MARKETS = 12
# No tour or surface inference from match names or a context digest.
MARKET_ID_PATTERN = re.compile(r"[a-z0-9_]{1,64}\Z")


def _parse_dt(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _digest(doc):
    raw = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _scores(row):
    result = []
    for name in MODELS:
        item = (row.get("model_scores") or {}).get(name) or {}
        value = item.get("value")
        if item.get("available") is not True or isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(value) or not (0 <= value <= 1):
            return None
        result.append(float(value))
    return tuple(result)


def _samples(ledger, settlement, now):
    if ledger.get("schema_version") != "prediction-ledger-shadow-v1" or settlement.get("schema_version") != "prediction-ledger-settlement-shadow-v1":
        raise ValueError("Unrecognized frozen evidence schema")
    if ledger.get("mode") != "SHADOW_ONLY" or settlement.get("mode") != "SHADOW_ONLY":
        raise ValueError("Source not SHADOW_ONLY")
    if _digest(ledger) != settlement.get("source_ledger_sha256"):
        raise ValueError("Ledger/settlement digest mismatch")
    ledger_rows = ledger.get("rows")
    settled_rows = settlement.get("rows")
    if not isinstance(ledger_rows, list) or not isinstance(settled_rows, list):
        raise ValueError("Invalid evidence rows")
    frozen = {}
    duplicates = set()
    for row in ledger_rows:
        if not isinstance(row, dict):
            continue
        pid = row.get("prediction_id")
        if not isinstance(pid, str) or not pid:
            continue
        if pid in frozen:
            duplicates.add(pid)
        frozen[pid] = row
    if duplicates:
        raise ValueError("Duplicate frozen prediction IDs")
    seen = set()
    samples = []
    excluded = Counter()
    for record in settled_rows:
        if not isinstance(record, dict):
            excluded["BAD_RECORD"] += 1
            continue
        pid = record.get("prediction_id")
        if not isinstance(pid, str) or not pid or pid in seen:
            raise ValueError("Missing/duplicate settlement prediction ID")
        seen.add(pid)
        row = frozen.get(pid)
        if row is None or any(record.get(key) != row.get(key) for key in ("match_key", "candidate_key", "scheduled_time")):
            raise ValueError("Settlement identity not in frozen ledger")
        outcome = record.get("settlement") or {}
        if outcome.get("status") != "SETTLED" or outcome.get("result") not in ("hit", "miss"):
            excluded["NOT_BINARY_VERIFIED"] += 1
            continue
        scheduled = _parse_dt(row.get("scheduled_time"))
        captured = _parse_dt(row.get("captured_at"))
        settled = _parse_dt(outcome.get("settled_at"))
        key = row.get("match_key")
        scores = _scores(row)
        if not (scheduled and captured and settled and captured < scheduled <= settled <= now):
            excluded["INVALID_CHRONOLOGY"] += 1
            continue
        if not isinstance(key, str) or not key.startswith("id:") or not key[3:].isdigit() or scores is None:
            excluded["IDENTITY_OR_SCORES_MISSING"] += 1
            continue
        if row.get("score_semantics") not in (None, "probability_0_1"):
            excluded["SCORE_SEMANTICS"] += 1
            continue
        if scheduled.date() >= now.date():
            excluded["INCOMPLETE_DAY"] += 1
            continue
        market = row.get("market")
        market = market.strip().casefold() if isinstance(market, str) else None
        if market is not None and not MARKET_ID_PATTERN.fullmatch(market):
            market = None  # Unknown market is not silently guessed from the candidate key.
        samples.append({"match_key": key, "market": market, "day": scheduled.date().isoformat(),
                        "settled_at": settled, "p": scores,
                        "y": int(outcome["result"] == "hit")})
    return samples, dict(excluded)


def _weights():
    # Deterministic bounded experiment space: 66 convex mixtures, including anchors.
    return [(a / 10, b / 10, (10 - a - b) / 10)
            for a in range(11) for b in range(11 - a)]


def _metric(samples, weights):
    """Brier score balanced across independent fixtures, not correlated market rows."""
    if not samples:
        return None
    by_match = {}
    for sample in samples:
        p = sum(weight * score for weight, score in zip(weights, sample["p"]))
        total, n = by_match.get(sample["match_key"], (0.0, 0))
        by_match[sample["match_key"]] = (total + (p - sample["y"]) ** 2, n + 1)
    return round(sum(total / n for total, n in by_match.values()) / len(by_match), 9)


def _split(samples):
    # Whole UTC fixture days, so no market from a match crosses windows.
    days = sorted({sample["day"] for sample in samples})
    if len(days) < 5:
        return None
    first = max(1, int(len(days) * 0.6))
    second = max(first + 1, int(len(days) * 0.8))
    if second >= len(days):
        return None
    split_days = (days[first], days[second])
    train = [s for s in samples if s["day"] < split_days[0] and s["settled_at"] < datetime.fromisoformat(split_days[0] + "T00:00:00+00:00")]
    validation = [s for s in samples if split_days[0] <= s["day"] < split_days[1] and s["settled_at"] < datetime.fromisoformat(split_days[1] + "T00:00:00+00:00")]
    holdout = [s for s in samples if s["day"] >= split_days[1]]
    return (train, validation, holdout, split_days)



def _market_research(train, validation, holdout):
    """Train independent market challengers on the SAME global temporal windows.

    This is descriptive SHADOW research. Holdout never selects a candidate and
    the returned weight vector cannot influence live recommendations.
    """
    grouped = {}
    for fold_name, rows in (("train", train), ("validation", validation), ("holdout", holdout)):
        for row in rows:
            market = row.get("market")
            if market is not None:
                grouped.setdefault(market, {"train": [], "validation": [], "holdout": []})[fold_name].append(row)

    all_market_ids = sorted(grouped)
    studies = []
    weights = _weights()
    baseline = (1.0, 0.0, 0.0)
    for market_id in all_market_ids[:MAX_SPECIALIST_MARKETS]:
        windows = grouped[market_id]
        sample_sizes = {
            name: {"rows": len(rows), "independent_matches": len({r["match_key"] for r in rows})}
            for name, rows in windows.items()
        }
        result = {"market": market_id, "status": "INSUFFICIENT_EVIDENCE",
                  "windows": sample_sizes, "candidate": None}
        if all(sample_sizes[name]["independent_matches"] >= MIN_SPECIALIST_MATCHES[index]
               for index, name in enumerate(("train", "validation", "holdout"))):
            # Strictly train-only ranking; validation decides among finalists.
            ranked = sorted(weights, key=lambda w: (_metric(windows["train"], w), w))
            finalist = min(ranked[:12],
                           key=lambda w: (_metric(windows["validation"], w),
                                          _metric(windows["train"], w), w))
            scores = {
                name: {"challenger_brier": _metric(rows, finalist),
                       "current_brier": _metric(rows, baseline)}
                for name, rows in windows.items()
            }
            result["status"] = "EVALUATED_SHADOW_ONLY"
            result["candidate"] = {
                "weights": dict(zip(MODELS, finalist)),
                "scores": scores,
                "validation_better_than_current": (
                    scores["validation"]["challenger_brier"] < scores["validation"]["current_brier"]
                ),
                "holdout_better_than_current": (
                    scores["holdout"]["challenger_brier"] < scores["holdout"]["current_brier"]
                ),
            }
        studies.append(result)

    return {
        "status": "EXPLORATORY_SHADOW_ONLY" if all_market_ids else "NO_VERIFIED_MARKET_LABELS",
        "market_ids_with_data": len(all_market_ids),
        "market_limit": MAX_SPECIALIST_MARKETS,
        "unexamined_market_ids": all_market_ids[MAX_SPECIALIST_MARKETS:],
        "studies": studies,
        "optimizer": "FROZEN_66_CONVEX_MIXTURES_BY_EXACT_MARKET",
        "shared_utc_cutoffs": True,
        "holdout_used_for_selection": False,
        "holdout_reuse_warning": "REPEATED_DAILY_HISTORICAL_HOLDOUT_IS_DESCRIPTIVE_NOT_PROSPECTIVE",
        "auto_promote": False,
        "bookmaker_profit_claim": False,
    }


def build_report(ledger, settlement, *, now):
    parsed_now = _parse_dt(now)
    if parsed_now is None:
        raise ValueError("now must be timezone-aware")
    samples, excluded = _samples(ledger, settlement, parsed_now)
    result = {
        "schema_version": VERSION, "mode": "SHADOW_ONLY", "generated_at": parsed_now.isoformat(),
        "source_ledger_sha256": settlement["source_ledger_sha256"],
        "source_settlement_sha256": _digest(settlement),
        "production_influence": False, "playable_influence": False, "symphony_influence": False,
        "ineed_influence": False, "auto_promote": False, "real_betting_enabled": False,
        "network_fetch_enabled": False, "optimizer": "DETERMINISTIC_CONVEX_GRID_BRIER",
        "selection_metric": "Brier (smaller is better)", "economic_roi_evaluated": False,
        "samples": len(samples), "excluded": excluded,
        "quote_provenance": {
            "status": "NO_FROZEN_EXACT_HISTORICAL_OPERATOR_QUOTES_JOINED",
            "verified_priced_actions": None,
            "eligible_roi_observations": None,
            "economic_learning_authorized": False,
            "reason": "CURRENT_OFFER_AND_BB_QUOTES_ARE_NOT_IMMUTABLE_PER_DECISION_HISTORY",
        },
        "market_research": None,
        "status": "COLLECTING_VERIFIED_HISTORY", "candidate": None,
        "windows": None,
    }
    split = _split(samples)
    if split is None:
        result["reason"] = "INSUFFICIENT_DISTINCT_COMPLETE_DAYS"
        return result
    train, val, test, split_days = split
    counts = [len({s["match_key"] for s in window}) for window in (train, val, test)]
    result["windows"] = {"train_rows": len(train), "validation_rows": len(val), "holdout_rows": len(test),
                         "train_matches": counts[0], "validation_matches": counts[1], "holdout_matches": counts[2],
                         "validation_start_day": split_days[0], "holdout_start_day": split_days[1]}
    if any(actual < minimum for actual, minimum in zip(counts, MIN_MATCHES)):
        result["reason"] = "INSUFFICIENT_INDEPENDENT_MATCHES"
        return result
    # Training explores all mixtures. Validation alone chooses among the best
    # training candidates. Holdout is read only after candidate selection.
    ranked = sorted(_weights(), key=lambda w: (_metric(train, w), w))
    shortlist = ranked[:12]
    selected = min(shortlist, key=lambda w: (_metric(val, w), _metric(train, w), w))
    baseline = (1.0, 0.0, 0.0)
    train_brier = _metric(train, selected)
    val_brier = _metric(val, selected)
    test_brier = _metric(test, selected)
    baseline_val = _metric(val, baseline)
    baseline_test = _metric(test, baseline)
    result["candidate"] = {"weights": dict(zip(MODELS, selected)),
                           "train_brier": train_brier, "validation_brier": val_brier,
                           "holdout_brier": test_brier, "current_validation_brier": baseline_val,
                           "current_holdout_brier": baseline_test,
                           "validation_delta_vs_current": round(val_brier - baseline_val, 9),
                           "holdout_delta_vs_current": round(test_brier - baseline_test, 9)}
    result["status"] = "SHADOW_EVIDENCE_POSITIVE" if val_brier < baseline_val and test_brier < baseline_test else "SHADOW_NOT_BETTER"
    result["market_research"] = _market_research(train, val, test)
    result["reason"] = "DESCRIPTIVE_RESEARCH_ONLY_NO_AUTOMATIC_PRODUCTION_PROMOTION"
    return result


def main():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    settlement = json.loads(SETTLEMENT.read_text(encoding="utf-8"))
    report = build_report(ledger, settlement, now=datetime.now(timezone.utc))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "windows": report["windows"], "candidate": report["candidate"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
