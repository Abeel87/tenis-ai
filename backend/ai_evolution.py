from __future__ import annotations

"""Autonomous SHADOW-only challenger search over frozen tennis predictions."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, time, timezone
import hashlib
import json
import math
from pathlib import Path
import random

try:
    from . import prediction_ledger_settlement_shadow as settlement
    from . import prediction_ledger_shadow as ledger_owner
except ImportError:
    import prediction_ledger_settlement_shadow as settlement
    import prediction_ledger_shadow as ledger_owner

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"
MODELS = ("current", "catboost", "tabpfn")
SCHEMA = "ai-evolution-shadow-v1"
SEED = 20261008


def _dt(value):
    return settlement._parse_dt(value)


def _probabilities(row):
    if row.get("score_semantics") != "probability_0_1":
        return None
    values = []
    for model in MODELS:
        score = (row.get("model_scores") or {}).get(model) or {}
        p = score.get("value")
        if score.get("available") is not True or isinstance(p, bool) or not isinstance(p, (int, float)):
            return None
        if not math.isfinite(p) or not 0 <= p <= 1:
            return None
        values.append(float(p))
    return tuple(values)


def _extract(frozen, history, now):
    if not isinstance(frozen, dict) or frozen.get("schema_version") != ledger_owner.SCHEMA_VERSION:
        raise ValueError("Frozen prediction-ledger schema mismatch")
    if not isinstance(frozen.get("rows"), list) or not isinstance(history, list):
        raise ValueError("Missing frozen ledger or canonical history")
    if frozen.get("mode") != "SHADOW_ONLY":
        raise ValueError("Expected SHADOW_ONLY frozen ledger")
    index = settlement._history_index(history)
    counts = Counter(str(r.get("prediction_id")) for r in frozen["rows"]
                     if isinstance(r, dict) and r.get("prediction_id"))
    signatures = Counter((str(r.get("match_key")), str(r.get("candidate_key")),
                          str(r.get("scheduled_time"))) for r in frozen["rows"] if isinstance(r, dict))
    rejected = Counter()
    rows = []
    for raw in frozen["rows"]:
        if not isinstance(raw, dict):
            rejected["INVALID_ROW"] += 1
            continue
        pid = str(raw.get("prediction_id") or "")
        signature = (str(raw.get("match_key")), str(raw.get("candidate_key")),
                     str(raw.get("scheduled_time")))
        if not pid or counts[pid] != 1 or signatures[signature] != 1:
            rejected["AMBIGUOUS_IDENTITY"] += 1
            continue
        captured, scheduled = _dt(raw.get("captured_at")), _dt(raw.get("scheduled_time"))
        if raw.get("mode") != "SHADOW_ONLY" or not captured or not scheduled or captured >= scheduled:
            rejected["NOT_FROZEN_PREMATCH"] += 1
            continue
        if scheduled.date() >= now.date():
            rejected["INCOMPLETE_UTC_DAY"] += 1
            continue
        if not str(raw.get("match_key") or "").startswith("id:"):
            rejected["NO_EXACT_MATCH_ID"] += 1
            continue
        ps = _probabilities(raw)
        if ps is None:
            rejected["NO_COMMON_PROBABILITY"] += 1
            continue
        fact = settlement._settlement_fact(raw, index)
        if fact.get("status") != "SETTLED" or fact.get("result") not in ("hit", "miss"):
            rejected["NO_EXACT_BINARY_SETTLEMENT"] += 1
            continue
        settled_at = _dt(fact.get("settled_at"))
        if not settled_at or settled_at > now:
            rejected["SETTLEMENT_AFTER_AS_OF"] += 1
            continue
        rows.append({"prediction_id": pid, "match_key": raw["match_key"],
                     "day": scheduled.date().isoformat(), "settled_at": settled_at,
                     "p": ps, "y": int(fact["result"] == "hit")})
    rows.sort(key=lambda x: (x["day"], x["match_key"], x["prediction_id"]))
    return rows, dict(sorted(rejected.items()))


def _partition(rows):
    days = sorted({r["day"] for r in rows})
    if len(days) < 5:
        return None
    a = max(1, int(len(days) * .6))
    b = max(a + 1, int(len(days) * .8))
    if b >= len(days):
        return None
    dev_day, test_day = days[a], days[b]
    dev_cutoff = datetime.combine(datetime.fromisoformat(dev_day).date(), time.min, timezone.utc)
    test_cutoff = datetime.combine(datetime.fromisoformat(test_day).date(), time.min, timezone.utc)
    folds = {
        "train": [r for r in rows if r["day"] < dev_day and r["settled_at"] < dev_cutoff],
        "validation": [r for r in rows if dev_day <= r["day"] < test_day and r["settled_at"] < test_cutoff],
        "holdout": [r for r in rows if r["day"] >= test_day],
    }
    return folds, {"validation_starts_utc": dev_day, "holdout_starts_utc": test_day,
                   "training_settled_before": dev_cutoff.isoformat(),
                   "validation_settled_before": test_cutoff.isoformat(),
                   "policy": "CHRONOLOGICAL_UTC_MATCH_DAYS_SETTLEMENT_EMBARGO"}


def _sizes(rows):
    return {"predictions": len(rows), "matches": len({r["match_key"] for r in rows}),
            "days": len({r["day"] for r in rows})}


def _brier(rows, weights):
    if not rows:
        return None
    by_match = defaultdict(lambda: [0.0, 0])
    for row in rows:
        p = sum(w * v for w, v in zip(weights, row["p"]))
        entry = by_match[row["match_key"]]
        entry[0] += (p - row["y"]) ** 2
        entry[1] += 1
    return sum(total / n for total, n in by_match.values()) / len(by_match)


def _normalize(ws):
    ws = [max(0.0, float(w)) for w in ws]
    s = sum(ws)
    return tuple(w / s for w in ws) if s else (1 / 3,) * 3


def _evolve(train, validation):
    rng = random.Random(SEED)
    pool = {(1., 0., 0.), (0., 1., 0.), (0., 0., 1.), (1 / 3,) * 3}
    pool.update(_normalize([rng.random() for _ in MODELS]) for _ in range(16))
    generations = []
    for gen in range(8):
        ranked = sorted(pool, key=lambda w: (_brier(train, w), w))
        elite = ranked[:8]
        generations.append({"generation": gen + 1, "best_train_brier": round(_brier(train, elite[0]), 8),
                            "evaluated_candidates": len(pool)})
        for _ in range(20):
            parent = elite[rng.randrange(len(elite))]
            pool.add(_normalize([w + rng.gauss(0, .15) for w in parent]))
    finalists = sorted(pool, key=lambda w: (_brier(train, w), w))[:12]
    winner = min(finalists, key=lambda w: (_brier(validation, w), w))
    return winner, generations, len(pool)


def build_report(frozen_ledger, canonical_history, *, now=None,
                 min_predictions=(120, 40, 40), min_matches=(30, 10, 10)):
    now = _dt(now or datetime.now(timezone.utc))
    if now is None:
        raise ValueError("Invalid as-of time")
    rows, rejected = _extract(frozen_ledger, canonical_history, now)
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps([row["prediction_id"], row["day"], row["p"], row["y"]],
                                 separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    report = {
        "schema_version": SCHEMA, "mode": "SHADOW_ONLY", "generated_at": now.isoformat(),
        "input_contract": {"ledger": ledger_owner.SCHEMA_VERSION,
                           "settlement_owner": "prediction_ledger_settlement_shadow._settlement_fact",
                           "population": "ALL_COMMON_CURRENT_CATBOOST_TABPFN",
                           "eligible_rows_sha256": digest.hexdigest(),
                           "eligible_predictions": len(rows), "rejected_reasons": rejected},
        "production_influence": False, "playable_influence": False,
        "ineed_influence": False, "real_betting_enabled": False, "auto_promote": False,
        "verified_operator_odds": False, "roi": None,
        "objective": "FIXTURE_BALANCED_BRIER_NOT_BETTING_PROFIT",
        "weights_are_shadow_only": True,
    }
    partition = _partition(rows)
    if partition is None:
        return {**report, "status": "INSUFFICIENT_EVIDENCE",
                "reason": "AT_LEAST_FIVE_DISTINCT_SETTLED_DAYS_REQUIRED",
                "folds": None, "challenger": None}
    folds, time_contract = partition
    counts = {name: _sizes(value) for name, value in folds.items()}
    report["folds"] = counts
    report["time_contract"] = time_contract
    if any(counts[name]["predictions"] < min_predictions[i] or
           counts[name]["matches"] < min_matches[i]
           for i, name in enumerate(("train", "validation", "holdout"))):
        return {**report, "status": "INSUFFICIENT_EVIDENCE",
                "reason": "MINIMUM_PREDICTIONS_OR_DISTINCT_MATCHES_NOT_MET", "challenger": None}
    winner, trace, searched = _evolve(folds["train"], folds["validation"])
    evals = {}
    for name, samples in folds.items():
        b0 = _brier(samples, (1., 0., 0.))
        b1 = _brier(samples, winner)
        evals[name] = {"current_brier": round(b0, 8), "challenger_brier": round(b1, 8),
                       "challenger_minus_current": round(b1 - b0, 8)}
    return {**report, "status": "TRAINED_SHADOW_ONLY",
            "challenger": {
                "model_weights": dict(zip(MODELS, [round(w, 8) for w in winner])),
                "selection_policy": "TRAIN_SEARCH_VALIDATION_SELECT_HOLDOUT_OBSERVE",
                "search_seed": SEED, "candidate_count": searched, "generations": trace,
                "evaluation": evals,
                "validation_better_than_current": evals["validation"]["challenger_minus_current"] < 0,
                "holdout_better_than_current": evals["holdout"]["challenger_minus_current"] < 0,
                "automatic_production_promotion": False,
            }}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DATA / "prediction_ledger_shadow.json")
    parser.add_argument("--history", type=Path, default=DATA / "history.json")
    parser.add_argument("--output", type=Path, default=Path("ai-evolution-shadow.json"))
    args = parser.parse_args()
    with args.ledger.open(encoding="utf-8") as f:
        frozen = json.load(f)
    with args.history.open(encoding="utf-8") as f:
        history = json.load(f)
    report = build_report(frozen, history)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(args.output.suffix + ".tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(args.output)
    print(json.dumps({"status": report["status"], "folds": report.get("folds"),
                      "weights": report["challenger"]["model_weights"] if report.get("challenger") else None}))


if __name__ == "__main__":
    main()
