from __future__ import annotations

"""Persistent training/status artifact for the isolated NEURO SHADOW meta-model.

Reads only dedicated NEURO SHADOW history. It never writes PLAYABLE/Symphony
artifacts and never promotes a neural model automatically. Markets stay in
COLLECTING_DATA until the strict trainer gates are satisfied.
"""

import hashlib
import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from backend.neuro_shadow_history import DEFAULT_HISTORY_PATH, load_history
from backend.neuro_shadow_neural import (
    MIN_CLASS_COUNT,
    MIN_DISTINCT_MATCHES,
    MIN_SETTLED,
    SEED as NEURAL_SEED,
    VERSION as NEURAL_VERSION,
    _fit as _fit_neural,
    _forward as _forward_neural,
    _match_balanced_weights,
    _match_key,
    _standardizer,
    _time_key,
    _transform,
    train_market,
)

VERSION = "neuro-shadow-training-v9.3.11"
MODE = "SHADOW"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False
AUTO_PROMOTION = False
ORIENTATION_POLICY = "SIDE_MARKET_PLAYER_MUST_MATCH_APP_ORDER"
SIDE_MARKETS = {
    "p1_exactly_1_set": "p1",
    "p1_exactly_2_sets": "p1",
    "p1_wins_a_set": "p1",
    "p2_exactly_1_set": "p2",
    "p2_exactly_2_sets": "p2",
    "p2_wins_a_set": "p2",
}

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAINING_PATH = ROOT / "frontend" / "data" / "neuro_shadow_neural_v936.json"
PHASE7_REPORT_PATH = ROOT / "frontend" / "data" / "player_dna_phase7_calibration_walk_forward.json"
PHASE8_REPORT_PATH = ROOT / "frontend" / "data" / "neuro_shadow_phase8_challenger_walk_forward.json"

PHASE8_VERSION = "neuro-shadow-phase8-challenger-walk-forward-v1"
PHASE8_MODE = "SHADOW_PHASE8_MODEL_CLASS_COMPARISON_ONLY"
PHASE8_TRAIN_FRACTIONS = (0.55, 0.70, 0.85)
PHASE8_REQUIRED_FOLDS = 3
PHASE8_MIN_SUPPORTED_MARKETS = 6
PHASE8_FOLD_MIN_TRAIN_ROWS = 60
PHASE8_FOLD_MIN_EVAL_ROWS = 10
PHASE8_FOLD_MIN_EVAL_MATCHES = 5
PHASE8_FOLD_MIN_TRAIN_CLASS = 10
PHASE8_FEATURE_PROBABILITIES = (
    "state_probability",
    "base_probability",
    "current_probability",
    "adaptive_probability",
)
PHASE8_FEATURE_CONTEXT = (
    "best_of_5",
    "surface_hard",
    "surface_clay",
    "surface_grass",
)
PHASE8_FEATURE_NAMES = (
    *PHASE8_FEATURE_PROBABILITIES,
    *PHASE8_FEATURE_CONTEXT,
    *(f"missing_{name}" for name in PHASE8_FEATURE_PROBABILITIES),
)
PHASE8_LOGISTIC_EPOCHS = 300
PHASE8_LOGISTIC_LEARNING_RATE = 0.04
PHASE8_LOGISTIC_L2 = 0.001
PHASE8_CATBOOST_ITERATIONS = 120
PHASE8_CATBOOST_DEPTH = 4
PHASE8_CATBOOST_LEARNING_RATE = 0.04


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _name_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return " ".join(sorted(re.sub(r"[^a-z0-9]+", " ", text).split()))


def _orientation_valid(row: dict[str, Any]) -> bool:
    """Fail closed for historical side-sensitive rows captured before fixture orientation.

    Dedicated history remains append-only. This guard only decides whether a row
    is trustworthy enough to train the neural SHADOW model.
    """
    market = str(row.get("market") or "")
    side = SIDE_MARKETS.get(market)
    if side is None:
        return True
    player = _name_key(row.get("player"))
    expected = _name_key(row.get(side))
    return bool(player and expected and player == expected)


def _eligible_training_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows or [] if isinstance(row, dict) and _orientation_valid(row)]


def _group_by_market(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        market = str(row.get("market") or "")
        if market:
            grouped[market].append(row)
    return dict(grouped)


def training_fingerprint(rows: list[dict[str, Any]]) -> str:
    """Hash every trusted settled field that can affect neural training or its split.

    Pending/VOID rows do not trigger an expensive retrain. HIT/MISS evidence,
    immutable features, match grouping identity and chronological split time do.
    Historical side-market rows with inconsistent player orientation are
    quarantined before fingerprinting so they can never preserve a contaminated
    cached model artifact.
    """
    evidence = []
    for row in _eligible_training_rows(rows):
        if row.get("settlement") not in {"hit", "miss"}:
            continue
        evidence.append({
            "prediction_key": row.get("prediction_key"),
            "match_id": row.get("match_id") or row.get("id"),
            "p1": row.get("p1"),
            "p2": row.get("p2"),
            "scheduled_time": row.get("scheduled_time"),
            "created_at": row.get("created_at"),
            "market": row.get("market"),
            "settlement": row.get("settlement"),
            "probability": row.get("probability"),
            "feature_snapshot": row.get("feature_snapshot"),
        })
    evidence.sort(key=lambda row: (
        str(row.get("scheduled_time") or row.get("created_at") or ""),
        str(row.get("match_id") or ""),
        str(row.get("prediction_key") or ""),
        str(row.get("market") or ""),
        str(row.get("settlement") or ""),
    ))
    raw = json.dumps(
        {
            "trainer": VERSION,
            "neural": NEURAL_VERSION,
            "orientation_policy": ORIENTATION_POLICY,
            "evidence": evidence,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_training_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    raw_rows = [row for row in rows or [] if isinstance(row, dict)]
    eligible = _eligible_training_rows(raw_rows)
    quarantined = len(raw_rows) - len(eligible)
    grouped = _group_by_market(eligible)
    reports = {
        market: train_market(grouped[market], market)
        for market in sorted(grouped)
    }
    ready_markets = sorted(
        market for market, report in reports.items()
        if report.get("status") == "SHADOW_MODEL_READY"
    )
    ready = len(ready_markets)
    collecting = len(reports) - ready
    return {
        "version": VERSION,
        "neural_version": NEURAL_VERSION,
        "mode": MODE,
        "status": "SHADOW_READY" if ready else "COLLECTING_DATA",
        "history_rows_total": len(raw_rows),
        "history_rows": len(eligible),
        "orientation_quarantined_rows": quarantined,
        "orientation_policy": ORIENTATION_POLICY,
        "markets_seen": len(reports),
        "markets_ready": ready,
        "ready_markets": ready_markets,
        "markets_collecting": collecting,
        "markets": reports,
        "auto_promotion": False,
        "auto_promote": False,
        "production_influence": False,
        "playable_influence": False,
        "symphony_prod_influence": False,
    }



def _phase8_num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _phase8_feature_vector(row: dict[str, Any]) -> list[float] | None:
    snapshot = row.get("feature_snapshot")
    if not isinstance(snapshot, dict):
        return None
    if snapshot.get("contains_final_result") is True:
        return None
    if snapshot.get("contains_bookmaker_price") is True:
        return None
    numeric = snapshot.get("numeric")
    if not isinstance(numeric, dict):
        return None

    values: list[float] = []
    missing: list[float] = []
    for name in PHASE8_FEATURE_PROBABILITIES:
        value = _phase8_num(numeric.get(name))
        missing.append(1.0 if value is None else 0.0)
        values.append(0.5 if value is None else max(0.0, min(1.0, value)))
    for name in PHASE8_FEATURE_CONTEXT:
        value = _phase8_num(numeric.get(name))
        values.append(0.0 if value is None else value)
    values.extend(missing)
    return values


def _phase8_target(row: dict[str, Any]) -> float | None:
    settlement = row.get("settlement")
    if settlement == "hit":
        return 1.0
    if settlement == "miss":
        return 0.0
    return None


def _phase8_items(
    rows: list[dict[str, Any]],
    market: str,
) -> list[tuple[dict[str, Any], list[float], float]]:
    items = []
    for row in _eligible_training_rows(rows):
        if str(row.get("market") or "") != str(market):
            continue
        target = _phase8_target(row)
        features = _phase8_feature_vector(row)
        if target is None or features is None or not _time_key(row):
            continue
        items.append((row, features, target))
    items.sort(
        key=lambda item: (
            _time_key(item[0]),
            _match_key(item[0]),
            str(item[0].get("prediction_key") or ""),
        )
    )
    return items


def _phase8_fold_specs(
    items: list[tuple[dict[str, Any], list[float], float]],
) -> list[dict[str, Any]]:
    timestamps = sorted({_time_key(row) for row, _features, _target in items if _time_key(row)})
    if len(timestamps) < 4:
        return []

    cutoffs = []
    for fraction in PHASE8_TRAIN_FRACTIONS:
        index = max(1, min(len(timestamps) - 1, int(len(timestamps) * fraction)))
        cutoffs.append(timestamps[index])
    if len(set(cutoffs)) != PHASE8_REQUIRED_FOLDS:
        return []

    specs = []
    for index, start in enumerate(cutoffs):
        end = cutoffs[index + 1] if index + 1 < len(cutoffs) else None
        train = [item for item in items if _time_key(item[0]) < start]
        evaluation = [
            item
            for item in items
            if _time_key(item[0]) >= start
            and (end is None or _time_key(item[0]) < end)
        ]
        train_times = {_time_key(item[0]) for item in train}
        eval_times = {_time_key(item[0]) for item in evaluation}
        specs.append({
            "fold": index + 1,
            "train_fraction_target": PHASE8_TRAIN_FRACTIONS[index],
            "train_before": start,
            "eval_from": start,
            "eval_before": end,
            "train": train,
            "evaluation": evaluation,
            "same_timestamp_split": bool(train_times & eval_times),
        })
    return specs


def _phase8_sigmoid(value: float) -> float:
    if value >= 0.0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _fit_phase8_logistic(
    xs: list[list[float]],
    ys: list[float],
    weights: list[float],
) -> dict[str, Any]:
    means, scales = _standardizer(xs, weights)
    transformed = [_transform(x, means, scales) for x in xs]
    width = len(transformed[0])
    coefficients = [0.0] * width
    total_weight = sum(max(0.0, float(weight)) for weight in weights)
    weighted_positive = sum(
        max(0.0, float(weight)) * float(target)
        for weight, target in zip(weights, ys)
    )
    prior = min(1.0 - 1e-6, max(1e-6, weighted_positive / max(total_weight, 1e-12)))
    intercept = math.log(prior / (1.0 - prior))

    for _ in range(PHASE8_LOGISTIC_EPOCHS):
        grad_b = 0.0
        grad_w = [0.0] * width
        for x, target, weight in zip(transformed, ys, weights):
            w = max(0.0, float(weight))
            if w <= 0.0:
                continue
            probability = _phase8_sigmoid(
                intercept + sum(coef * value for coef, value in zip(coefficients, x))
            )
            error = (probability - target) * w
            grad_b += error
            for index, value in enumerate(x):
                grad_w[index] += error * value
        scale = 1.0 / max(total_weight, 1e-12)
        intercept -= PHASE8_LOGISTIC_LEARNING_RATE * grad_b * scale
        for index in range(width):
            gradient = grad_w[index] * scale + PHASE8_LOGISTIC_L2 * coefficients[index]
            coefficients[index] -= PHASE8_LOGISTIC_LEARNING_RATE * gradient

    return {
        "means": means,
        "scales": scales,
        "coefficients": coefficients,
        "intercept": intercept,
    }


def _predict_phase8_logistic(model: dict[str, Any], xs: list[list[float]]) -> list[float]:
    means = model["means"]
    scales = model["scales"]
    coefficients = model["coefficients"]
    intercept = float(model["intercept"])
    return [
        _phase8_sigmoid(
            intercept
            + sum(
                coef * value
                for coef, value in zip(coefficients, _transform(x, means, scales))
            )
        )
        for x in xs
    ]


def _fit_predict_phase8_catboost(
    train_x: list[list[float]],
    train_y: list[float],
    train_weights: list[float],
    eval_x: list[list[float]],
    *,
    seed: int,
) -> list[float]:
    from catboost import CatBoostClassifier

    model = CatBoostClassifier(
        iterations=PHASE8_CATBOOST_ITERATIONS,
        depth=PHASE8_CATBOOST_DEPTH,
        learning_rate=PHASE8_CATBOOST_LEARNING_RATE,
        loss_function="Logloss",
        random_seed=seed,
        verbose=False,
        allow_writing_files=False,
        thread_count=1,
        bootstrap_type="No",
        random_strength=0.0,
        l2_leaf_reg=3.0,
    )
    model.fit(train_x, train_y, sample_weight=train_weights)
    return [float(row[1]) for row in model.predict_proba(eval_x)]


def _fit_predict_phase8_neural(
    train_x: list[list[float]],
    train_y: list[float],
    train_weights: list[float],
    eval_x: list[list[float]],
    *,
    seed: int,
) -> list[float]:
    means, scales = _standardizer(train_x, train_weights)
    transformed_train = [_transform(x, means, scales) for x in train_x]
    model = _fit_neural(
        transformed_train,
        train_y,
        seed=seed,
        weights=train_weights,
    )
    return [
        float(_forward_neural(model, _transform(x, means, scales))[1])
        for x in eval_x
    ]


def _phase8_metrics(
    probabilities: list[float],
    targets: list[float],
    weights: list[float],
) -> dict[str, Any]:
    n = len(probabilities)
    if not n or len(targets) != n or len(weights) != n:
        return {
            "n": n,
            "brier": None,
            "log_loss": None,
            "accuracy_0.5": None,
            "ece_10_bin": None,
            "calibration_bins": [],
        }

    clean_weights = [max(0.0, float(weight)) for weight in weights]
    total_weight = sum(clean_weights)
    if total_weight <= 0.0:
        return {
            "n": n,
            "brier": None,
            "log_loss": None,
            "accuracy_0.5": None,
            "ece_10_bin": None,
            "calibration_bins": [],
        }

    eps = 1e-12
    brier = 0.0
    log_loss = 0.0
    accuracy = 0.0
    bins: dict[int, list[tuple[float, float, float]]] = defaultdict(list)
    for probability, target, weight in zip(probabilities, targets, clean_weights):
        p = min(1.0 - eps, max(eps, float(probability)))
        y = float(target)
        brier += weight * (p - y) ** 2
        log_loss += weight * (-(y * math.log(p) + (1.0 - y) * math.log(1.0 - p)))
        accuracy += weight * int((p >= 0.5) == bool(y))
        bins[min(9, int(p * 10))].append((p, y, weight))

    calibration = []
    ece = 0.0
    for index in range(10):
        rows = bins.get(index) or []
        if not rows:
            continue
        bucket_weight = sum(weight for _p, _y, weight in rows)
        avg_probability = sum(p * weight for p, _y, weight in rows) / bucket_weight
        hit_rate = sum(y * weight for _p, y, weight in rows) / bucket_weight
        gap = abs(avg_probability - hit_rate)
        ece += (bucket_weight / total_weight) * gap
        calibration.append({
            "from": index / 10.0,
            "to": (index + 1) / 10.0,
            "n": len(rows),
            "weight": round(bucket_weight, 6),
            "avg_probability": round(avg_probability, 6),
            "hit_rate": round(hit_rate, 6),
            "gap": round(gap, 6),
        })

    return {
        "n": n,
        "brier": round(brier / total_weight, 6),
        "log_loss": round(log_loss / total_weight, 6),
        "accuracy_0.5": round(accuracy / total_weight, 6),
        "ece_10_bin": round(ece, 6),
        "calibration_bins": calibration,
    }


def _phase8_better_on_proper_scores(
    candidate: dict[str, Any],
    reference: dict[str, Any],
) -> bool:
    return bool(
        candidate.get("brier") is not None
        and reference.get("brier") is not None
        and candidate.get("log_loss") is not None
        and reference.get("log_loss") is not None
        and float(candidate["brier"]) < float(reference["brier"])
        and float(candidate["log_loss"]) < float(reference["log_loss"])
    )


def _phase8_better_calibrated(
    candidate: dict[str, Any],
    reference: dict[str, Any],
) -> bool:
    return bool(
        candidate.get("ece_10_bin") is not None
        and reference.get("ece_10_bin") is not None
        and float(candidate["ece_10_bin"]) < float(reference["ece_10_bin"])
    )


def evaluate_phase8_market(
    rows: list[dict[str, Any]],
    market: str,
) -> dict[str, Any]:
    items = _phase8_items(rows, market)
    positives = sum(int(target == 1.0) for _row, _features, target in items)
    negatives = len(items) - positives
    distinct_matches = len({_match_key(row) for row, _features, _target in items})
    gate = {
        "min_settled": MIN_SETTLED,
        "min_class_count": MIN_CLASS_COUNT,
        "min_distinct_matches": MIN_DISTINCT_MATCHES,
        "settled": len(items),
        "hits": positives,
        "misses": negatives,
        "distinct_matches": distinct_matches,
    }
    if (
        len(items) < MIN_SETTLED
        or min(positives, negatives) < MIN_CLASS_COUNT
        or distinct_matches < MIN_DISTINCT_MATCHES
    ):
        return {
            "market": market,
            "status": "INSUFFICIENT_MARKET_SAMPLE",
            "gate": gate,
            "folds": [],
            "aggregate": {},
            "neural_review_candidate": False,
            "ensemble_review_candidate": False,
        }

    specs = _phase8_fold_specs(items)
    if len(specs) != PHASE8_REQUIRED_FOLDS:
        return {
            "market": market,
            "status": "INCOMPLETE_CHRONOLOGY",
            "gate": gate,
            "folds": [],
            "aggregate": {},
            "neural_review_candidate": False,
            "ensemble_review_candidate": False,
        }

    folds = []
    aggregate_probabilities = {
        "logistic": [],
        "catboost": [],
        "neural": [],
        "ensemble": [],
    }
    aggregate_targets: list[float] = []
    aggregate_weights: list[float] = []

    for spec in specs:
        train = spec["train"]
        evaluation = spec["evaluation"]
        train_y = [item[2] for item in train]
        eval_y = [item[2] for item in evaluation]
        train_matches = len({_match_key(item[0]) for item in train})
        eval_matches = len({_match_key(item[0]) for item in evaluation})
        train_class_min = (
            min(
                sum(int(target == 1.0) for target in train_y),
                sum(int(target == 0.0) for target in train_y),
            )
            if train_y else 0
        )
        support_ok = bool(
            len(train) >= PHASE8_FOLD_MIN_TRAIN_ROWS
            and len(evaluation) >= PHASE8_FOLD_MIN_EVAL_ROWS
            and eval_matches >= PHASE8_FOLD_MIN_EVAL_MATCHES
            and train_class_min >= PHASE8_FOLD_MIN_TRAIN_CLASS
            and len(set(eval_y)) == 2
            and spec["same_timestamp_split"] is False
        )
        fold_meta = {
            "fold": spec["fold"],
            "train_fraction_target": spec["train_fraction_target"],
            "train_before": spec["train_before"],
            "eval_from": spec["eval_from"],
            "eval_before": spec["eval_before"],
            "train_rows": len(train),
            "eval_rows": len(evaluation),
            "train_matches": train_matches,
            "eval_matches": eval_matches,
            "train_min_class_count": train_class_min,
            "same_timestamp_split": spec["same_timestamp_split"],
        }
        if not support_ok:
            folds.append({
                **fold_meta,
                "status": "FOLD_INSUFFICIENT_SAMPLE",
                "models": {},
            })
            continue

        train_x = [item[1] for item in train]
        eval_x = [item[1] for item in evaluation]
        train_weights = _match_balanced_weights(train)
        eval_weights = _match_balanced_weights(evaluation)
        seed = NEURAL_SEED + sum(ord(ch) for ch in str(market)) + int(spec["fold"])

        logistic_model = _fit_phase8_logistic(train_x, train_y, train_weights)
        logistic_p = _predict_phase8_logistic(logistic_model, eval_x)
        catboost_p = _fit_predict_phase8_catboost(
            train_x,
            train_y,
            train_weights,
            eval_x,
            seed=seed,
        )
        neural_p = _fit_predict_phase8_neural(
            train_x,
            train_y,
            train_weights,
            eval_x,
            seed=seed,
        )
        ensemble_p = [
            (logistic + catboost + neural) / 3.0
            for logistic, catboost, neural in zip(logistic_p, catboost_p, neural_p)
        ]
        predictions = {
            "logistic": logistic_p,
            "catboost": catboost_p,
            "neural": neural_p,
            "ensemble": ensemble_p,
        }
        metrics = {
            name: _phase8_metrics(probabilities, eval_y, eval_weights)
            for name, probabilities in predictions.items()
        }
        folds.append({
            **fold_meta,
            "status": "FOLD_COMPLETE",
            "same_eval_rows_all_models": True,
            "models": metrics,
            "comparison": {
                "neural_beats_logistic_proper_scores": _phase8_better_on_proper_scores(
                    metrics["neural"], metrics["logistic"]
                ),
                "neural_beats_catboost_proper_scores": _phase8_better_on_proper_scores(
                    metrics["neural"], metrics["catboost"]
                ),
                "neural_beats_logistic_calibration": _phase8_better_calibrated(
                    metrics["neural"], metrics["logistic"]
                ),
                "neural_beats_catboost_calibration": _phase8_better_calibrated(
                    metrics["neural"], metrics["catboost"]
                ),
                "ensemble_beats_all_standalone_proper_scores": all(
                    _phase8_better_on_proper_scores(metrics["ensemble"], metrics[name])
                    for name in ("logistic", "catboost", "neural")
                ),
            },
        })
        for name, probabilities in predictions.items():
            aggregate_probabilities[name].extend(probabilities)
        aggregate_targets.extend(eval_y)
        aggregate_weights.extend(eval_weights)

    complete_folds = [fold for fold in folds if fold.get("status") == "FOLD_COMPLETE"]
    if len(complete_folds) != PHASE8_REQUIRED_FOLDS:
        return {
            "market": market,
            "status": "INCOMPLETE_WALK_FORWARD",
            "gate": gate,
            "folds": folds,
            "aggregate": {},
            "complete_folds": len(complete_folds),
            "required_folds": PHASE8_REQUIRED_FOLDS,
            "neural_review_candidate": False,
            "ensemble_review_candidate": False,
        }

    aggregate = {
        name: _phase8_metrics(probabilities, aggregate_targets, aggregate_weights)
        for name, probabilities in aggregate_probabilities.items()
    }
    neural_repeatable = sum(
        int(
            (fold.get("comparison") or {}).get("neural_beats_logistic_proper_scores") is True
            and (fold.get("comparison") or {}).get("neural_beats_catboost_proper_scores") is True
        )
        for fold in complete_folds
    )
    neural_review_candidate = bool(
        neural_repeatable >= 2
        and _phase8_better_on_proper_scores(aggregate["neural"], aggregate["logistic"])
        and _phase8_better_on_proper_scores(aggregate["neural"], aggregate["catboost"])
        and _phase8_better_calibrated(aggregate["neural"], aggregate["logistic"])
        and _phase8_better_calibrated(aggregate["neural"], aggregate["catboost"])
    )
    ensemble_repeatable = sum(
        int(
            (fold.get("comparison") or {}).get("ensemble_beats_all_standalone_proper_scores")
            is True
        )
        for fold in complete_folds
    )
    ensemble_review_candidate = bool(
        ensemble_repeatable >= 2
        and all(
            _phase8_better_on_proper_scores(aggregate["ensemble"], aggregate[name])
            for name in ("logistic", "catboost", "neural")
        )
        and all(
            _phase8_better_calibrated(aggregate["ensemble"], aggregate[name])
            for name in ("logistic", "catboost", "neural")
        )
    )

    return {
        "market": market,
        "status": "WALK_FORWARD_COMPLETE",
        "gate": gate,
        "feature_names": list(PHASE8_FEATURE_NAMES),
        "complete_folds": len(complete_folds),
        "required_folds": PHASE8_REQUIRED_FOLDS,
        "folds": folds,
        "aggregate": aggregate,
        "neural_repeatable_proper_score_gain_folds": neural_repeatable,
        "ensemble_repeatable_proper_score_gain_folds": ensemble_repeatable,
        "neural_review_candidate": neural_review_candidate,
        "ensemble_review_candidate": ensemble_review_candidate,
        "runtime_switch_authorized": False,
    }


def summarize_phase8_gate(
    market_reports: dict[str, dict[str, Any]],
    phase7_report: dict[str, Any],
) -> dict[str, Any]:
    supported = {
        market: report
        for market, report in market_reports.items()
        if report.get("status") == "WALK_FORWARD_COMPLETE"
        and int(report.get("complete_folds") or 0) == PHASE8_REQUIRED_FOLDS
    }
    neural_candidates = sorted(
        market
        for market, report in supported.items()
        if report.get("neural_review_candidate") is True
    )
    ensemble_candidates = sorted(
        market
        for market, report in supported.items()
        if report.get("ensemble_review_candidate") is True
    )
    phase7_ready = bool(
        phase7_report.get("phase7_complete") is True
        and phase7_report.get("phase8_ready") is True
    )
    technical_complete = bool(
        phase7_ready
        and len(supported) >= PHASE8_MIN_SUPPORTED_MARKETS
        and all(
            all(
                fold.get("same_eval_rows_all_models") is True
                for fold in report.get("folds") or []
                if fold.get("status") == "FOLD_COMPLETE"
            )
            for report in supported.values()
        )
    )
    return {
        "phase7_prerequisite_satisfied": phase7_ready,
        "supported_markets": len(supported),
        "minimum_supported_markets": PHASE8_MIN_SUPPORTED_MARKETS,
        "supported_market_names": sorted(supported),
        "neural_review_candidates": neural_candidates,
        "ensemble_review_candidates": ensemble_candidates,
        "technical_validation_complete": technical_complete,
        "phase8_complete": technical_complete,
        "phase9_ready": technical_complete,
        "neural_global_promotion_authorized": False,
        "ensemble_global_promotion_authorized": False,
        "promotion_verdict": (
            "PER_MARKET_REVIEW_CANDIDATES_SHADOW_ONLY"
            if neural_candidates or ensemble_candidates
            else "NO_MODEL_CLASS_PROMOTION_EVIDENCE_REMAINS_SHADOW"
        ),
    }


def evaluate_phase8_challengers(
    rows: list[dict[str, Any]],
    phase7_report: dict[str, Any],
) -> dict[str, Any]:
    raw_rows = [row for row in rows or [] if isinstance(row, dict)]
    eligible = _eligible_training_rows(raw_rows)
    grouped = _group_by_market(eligible)
    reports = {
        market: evaluate_phase8_market(eligible, market)
        for market in sorted(grouped)
    }
    summary = summarize_phase8_gate(reports, phase7_report)
    return {
        "version": PHASE8_VERSION,
        "mode": PHASE8_MODE,
        "status": (
            "PHASE8_VALIDATION_COMPLETE_NO_PROMOTION"
            if summary["phase8_complete"]
            else "PHASE8_VALIDATION_INCOMPLETE_NO_PROMOTION"
        ),
        "phase": 8,
        "history_rows_total": len(raw_rows),
        "history_rows_orientation_valid": len(eligible),
        "orientation_quarantined_rows": len(raw_rows) - len(eligible),
        "markets_seen": len(reports),
        "model_classes": [
            "interpretable_logistic_baseline",
            "catboost",
            "neural_network",
            "equal_weight_ensemble",
        ],
        "feature_contract": {
            "same_feature_vector_for_logistic_catboost_nn": True,
            "feature_names": list(PHASE8_FEATURE_NAMES),
            "existing_catboost_probability_excluded_to_avoid_circular_comparison": True,
            "existing_tabpfn_probability_excluded_to_avoid_model_class_leakage": True,
            "bookmaker_price_features_forbidden": True,
            "final_result_features_forbidden": True,
            "settlement_used_only_as_target": True,
            "missing_probability_inputs_imputed_neutral_with_explicit_mask": True,
        },
        "walk_forward_contract": {
            "train_fractions": list(PHASE8_TRAIN_FRACTIONS),
            "required_folds": PHASE8_REQUIRED_FOLDS,
            "expanding_train_windows": True,
            "evaluation_windows_disjoint": True,
            "same_timestamp_groups_not_split": True,
            "split_unit": "scheduled_time_with_whole_match_grouping",
            "weighting_unit": "match",
            "same_evaluation_rows_for_all_model_classes": True,
            "hyperparameters_frozen_before_evaluation": True,
            "ensemble_is_equal_weight_no_post_hoc_tuning": True,
        },
        "models": {
            "logistic": {
                "epochs": PHASE8_LOGISTIC_EPOCHS,
                "learning_rate": PHASE8_LOGISTIC_LEARNING_RATE,
                "l2": PHASE8_LOGISTIC_L2,
            },
            "catboost": {
                "iterations": PHASE8_CATBOOST_ITERATIONS,
                "depth": PHASE8_CATBOOST_DEPTH,
                "learning_rate": PHASE8_CATBOOST_LEARNING_RATE,
                "bootstrap_type": "No",
                "random_strength": 0.0,
                "thread_count": 1,
            },
            "neural": {
                "implementation": "backend.neuro_shadow_neural canonical deterministic MLP",
                "seed_base": NEURAL_SEED,
            },
            "ensemble": {
                "weights": {
                    "logistic": 1.0 / 3.0,
                    "catboost": 1.0 / 3.0,
                    "neural": 1.0 / 3.0,
                },
                "tuned_on_holdout": False,
            },
        },
        "markets": reports,
        "summary": summary,
        "phase8_complete": summary["phase8_complete"],
        "phase9_ready": summary["phase9_ready"],
        "production_influence": False,
        "runtime_switch_enabled": False,
        "playable_influence": False,
        "symphony_prod_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "promotion_allowed_by_this_gate": False,
        "contract": {
            "neural_remains_shadow_without_out_of_sample_superiority": True,
            "model_class_comparison_uses_identical_walk_forward": True,
            "proper_scores_and_calibration_are_primary": True,
            "accuracy_is_diagnostic_only": True,
            "per_market_evidence_not_global_magic_winner": True,
            "phase8_completion_means_evaluation_complete_not_model_promotion": True,
            "phase9_may_start_without_promoting_neural": True,
        },
    }


def build_phase8_report(
    history_path: Path = DEFAULT_HISTORY_PATH,
    phase7_path: Path = PHASE7_REPORT_PATH,
    output_path: Path = PHASE8_REPORT_PATH,
) -> dict[str, Any]:
    report = evaluate_phase8_challengers(
        load_history(history_path),
        _read_json(phase7_path),
    )
    _write_json_atomic(output_path, report)
    print(json.dumps({
        "version": report.get("version"),
        "mode": report.get("mode"),
        "status": report.get("status"),
        "phase8_complete": report.get("phase8_complete"),
        "phase9_ready": report.get("phase9_ready"),
        "summary": report.get("summary"),
    }, ensure_ascii=False))
    return report


def refresh_training_artifact(
    history_path: Path = DEFAULT_HISTORY_PATH,
    training_path: Path = DEFAULT_TRAINING_PATH,
) -> dict[str, Any]:
    rows = load_history(history_path)
    fingerprint = training_fingerprint(rows)
    existing = _read_json(training_path)
    if (
        existing.get("training_fingerprint") == fingerprint
        and existing.get("version") == VERSION
        and existing.get("neural_version") == NEURAL_VERSION
        and existing.get("orientation_policy") == ORIENTATION_POLICY
        and isinstance(existing.get("markets"), dict)
    ):
        return {**existing, "training_reused": True}

    report = build_training_report(rows)
    report["training_fingerprint"] = fingerprint
    report["training_reused"] = False
    _write_json_atomic(training_path, report)
    return report
