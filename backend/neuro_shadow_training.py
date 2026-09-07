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
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path
from typing import Any

from backend.neuro_shadow_history import DEFAULT_HISTORY_PATH, load_history
from backend.neuro_shadow_neural import VERSION as NEURAL_VERSION, train_market
from backend.neuro_shadow_state import CANDIDATE_CAPTURE_READY_MARKETS

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
PHASE8_OUT = ROOT / "frontend" / "data" / "neuro_shadow_phase8_challenger_walk_forward.json"

PHASE8_VERSION = "neuro-shadow-phase8-challenger-walk-forward-v1"
PHASE8_MODE = "SHADOW_PHASE8_CHALLENGER_WALK_FORWARD_ONLY"
PHASE8_TRAIN_FRACTIONS = (0.55, 0.70, 0.85)
PHASE8_REQUIRED_FOLDS = 3
PHASE8_MIN_TRAIN_MATCHES = 50
PHASE8_MIN_EVAL_MATCHES = 15
PHASE8_MIN_EVAL_ROWS = 100
PHASE8_MIN_TRAIN_CLASS_ROWS = 40
PHASE8_MIN_EVAL_CLASS_ROWS = 10
PHASE8_CATBOOST_ITERATIONS = 120
PHASE8_NN_EPOCHS = 250
PHASE8_NN_HIDDEN = 6
PHASE8_SEED = 938
PHASE8_EPS = 1e-6
PHASE8_TRACKS = (
    "state_reference",
    "logistic_baseline",
    "catboost",
    "neural_network",
    "ensemble",
)
PHASE8_LEARNED_TRACKS = (
    "logistic_baseline",
    "catboost",
    "neural_network",
    "ensemble",
)
PHASE8_MARKETS = tuple(sorted(CANDIDATE_CAPTURE_READY_MARKETS))


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



def _phase8_parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _phase8_match_id(row: dict[str, Any]) -> str:
    value = row.get("match_id") if row.get("match_id") is not None else row.get("id")
    return str(value).strip() if value is not None else ""


def _phase8_target(row: dict[str, Any]) -> int | None:
    settlement = row.get("settlement")
    if settlement == "hit":
        return 1
    if settlement == "miss":
        return 0
    return None


def _phase8_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _phase8_eligible_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in _eligible_training_rows(rows):
        target = _phase8_target(row)
        match_id = _phase8_match_id(row)
        scheduled = _phase8_parse_time(row.get("scheduled_time"))
        market = str(row.get("market") or "").strip()
        snapshot = row.get("feature_snapshot")
        numeric = snapshot.get("numeric") if isinstance(snapshot, dict) else None
        state_probability = (
            _phase8_number(numeric.get("state_probability"))
            if isinstance(numeric, dict)
            else None
        )
        if (
            target is None
            or not match_id
            or scheduled is None
            or market not in PHASE8_MARKETS
            or state_probability is None
        ):
            continue
        if isinstance(snapshot, dict):
            if snapshot.get("contains_final_result") is True:
                continue
            if snapshot.get("contains_bookmaker_price") is True:
                continue
        if row.get("mode") not in {None, MODE}:
            continue
        if row.get("operator_playable") not in {None, False}:
            continue
        out.append({
            "row": row,
            "match_id": match_id,
            "scheduled_time": scheduled,
            "market": market,
            "target": target,
        })
    out.sort(key=lambda item: (
        item["scheduled_time"],
        item["match_id"],
        str(item["row"].get("prediction_key") or ""),
    ))
    return out


def _phase8_fold_specs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    match_times: dict[str, datetime] = {}
    for item in records:
        match_id = item["match_id"]
        scheduled = item["scheduled_time"]
        previous = match_times.get(match_id)
        if previous is not None and previous != scheduled:
            raise ValueError(f"Phase-8 conflicting scheduled_time for match {match_id}")
        match_times[match_id] = scheduled

    ordered = sorted(match_times.items(), key=lambda item: (item[1], item[0]))
    if len(ordered) < 4:
        return []

    cutoffs = []
    n = len(ordered)
    for fraction in PHASE8_TRAIN_FRACTIONS:
        index = max(1, min(n - 1, int(n * fraction)))
        cutoffs.append(ordered[index][1])
    if not (cutoffs[0] < cutoffs[1] < cutoffs[2]):
        return []

    specs = []
    for index, start in enumerate(cutoffs):
        end = cutoffs[index + 1] if index + 1 < len(cutoffs) else None
        train_ids = {
            match_id
            for match_id, scheduled in match_times.items()
            if scheduled < start
        }
        eval_ids = {
            match_id
            for match_id, scheduled in match_times.items()
            if scheduled >= start and (end is None or scheduled < end)
        }
        train_times = {match_times[mid] for mid in train_ids}
        eval_times = {match_times[mid] for mid in eval_ids}
        specs.append({
            "fold": index + 1,
            "train_fraction_target": PHASE8_TRAIN_FRACTIONS[index],
            "train_before": start,
            "eval_from": start,
            "eval_before": end,
            "train_ids": train_ids,
            "eval_ids": eval_ids,
            "same_timestamp_split": bool(train_times & eval_times),
        })
    return specs


def _phase8_surface_flags(row: dict[str, Any], numeric: dict[str, Any]) -> tuple[float, float, float]:
    hard = _phase8_number(numeric.get("surface_hard"))
    clay = _phase8_number(numeric.get("surface_clay"))
    grass = _phase8_number(numeric.get("surface_grass"))
    if hard is not None and clay is not None and grass is not None:
        return hard, clay, grass
    surface = str(row.get("surface") or "").strip().casefold()
    return (
        1.0 if surface == "hard" else 0.0,
        1.0 if surface == "clay" else 0.0,
        1.0 if surface == "grass" else 0.0,
    )


def phase8_feature_names() -> list[str]:
    names = [
        "state_probability",
        "state_logit",
        "best_of_5",
        "surface_hard",
        "surface_clay",
        "surface_grass",
    ]
    names.extend(f"market_intercept::{market}" for market in PHASE8_MARKETS)
    names.extend(f"market_state_logit::{market}" for market in PHASE8_MARKETS)
    return names


def _phase8_feature_vector(item: dict[str, Any]) -> list[float]:
    row = item["row"]
    snapshot = row.get("feature_snapshot") or {}
    numeric = snapshot.get("numeric") or {}
    state_probability = _phase8_number(numeric.get("state_probability"))
    if state_probability is None:
        raise ValueError("Phase-8 row lost state_probability after eligibility gate")
    p = min(1.0 - PHASE8_EPS, max(PHASE8_EPS, state_probability))
    state_logit = math.log(p / (1.0 - p))
    best_of_5 = _phase8_number(numeric.get("best_of_5"))
    if best_of_5 is None:
        best_of_5 = 0.0
    hard, clay, grass = _phase8_surface_flags(row, numeric)
    market = item["market"]
    intercepts = [1.0 if market == name else 0.0 for name in PHASE8_MARKETS]
    slopes = [state_logit if market == name else 0.0 for name in PHASE8_MARKETS]
    return [
        p,
        state_logit,
        float(best_of_5),
        float(hard),
        float(clay),
        float(grass),
        *intercepts,
        *slopes,
    ]


def _phase8_match_balanced_weights(records: list[dict[str, Any]]):
    import numpy as np

    if not records:
        return np.asarray([], dtype=float)
    counts: dict[str, int] = defaultdict(int)
    for item in records:
        counts[item["match_id"]] += 1
    scale = len(records) / max(1, len(counts))
    return np.asarray([
        scale / counts[item["match_id"]]
        for item in records
    ], dtype=float)


def _phase8_sigmoid(values):
    import numpy as np

    values = np.asarray(values, dtype=float)
    out = np.empty_like(values)
    positive = values >= 0.0
    out[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exp_values = np.exp(values[~positive])
    out[~positive] = exp_values / (1.0 + exp_values)
    return out


def _phase8_metrics(probabilities, targets, weights) -> dict[str, Any]:
    import numpy as np

    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(targets, dtype=float)
    w = np.asarray(weights, dtype=float)
    if len(p) == 0 or len(p) != len(y) or len(p) != len(w):
        return {
            "n": 0,
            "accuracy": None,
            "brier": None,
            "log_loss": None,
            "ece_10_bin": None,
            "calibration_bins": [],
        }
    p = np.clip(p, PHASE8_EPS, 1.0 - PHASE8_EPS)
    w = np.maximum(w, 0.0)
    total_weight = float(w.sum())
    if total_weight <= 0.0:
        return {
            "n": int(len(p)),
            "accuracy": None,
            "brier": None,
            "log_loss": None,
            "ece_10_bin": None,
            "calibration_bins": [],
        }
    accuracy = float(np.sum(w * ((p >= 0.5) == (y >= 0.5))) / total_weight)
    brier = float(np.sum(w * np.square(p - y)) / total_weight)
    log_loss = float(
        np.sum(w * (-(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))))
        / total_weight
    )

    bins = []
    ece = 0.0
    for index in range(10):
        lo = index / 10.0
        hi = (index + 1) / 10.0
        mask = (p >= lo) & (p < hi if index < 9 else p <= hi)
        if not bool(mask.any()):
            continue
        bw = w[mask]
        bin_weight = float(bw.sum())
        if bin_weight <= 0.0:
            continue
        mean_probability = float(np.sum(bw * p[mask]) / bin_weight)
        observed_rate = float(np.sum(bw * y[mask]) / bin_weight)
        gap = abs(mean_probability - observed_rate)
        ece += (bin_weight / total_weight) * gap
        bins.append({
            "bin": index,
            "lo": lo,
            "hi": hi,
            "n": int(mask.sum()),
            "weight": round(bin_weight, 8),
            "mean_probability": round(mean_probability, 8),
            "observed_rate": round(observed_rate, 8),
            "gap": round(gap, 8),
        })

    return {
        "n": int(len(p)),
        "accuracy": round(accuracy, 8),
        "brier": round(brier, 8),
        "log_loss": round(log_loss, 8),
        "ece_10_bin": round(float(ece), 8),
        "calibration_bins": bins,
    }


def _phase8_fit_logistic(train_x, train_y, train_weights, eval_x):
    import numpy as np

    x = np.asarray(train_x, dtype=float)
    y = np.asarray(train_y, dtype=float)
    w = np.asarray(train_weights, dtype=float)
    xe = np.asarray(eval_x, dtype=float)
    xa = np.column_stack([np.ones(len(x)), x])
    xea = np.column_stack([np.ones(len(xe)), xe])
    beta = np.zeros(xa.shape[1], dtype=float)
    regularization = np.ones_like(beta)
    regularization[0] = 0.0
    l2 = 1e-3

    for _ in range(80):
        p = _phase8_sigmoid(xa @ beta)
        curvature = np.maximum(p * (1.0 - p), 1e-8)
        gradient = xa.T @ (w * (y - p)) - l2 * regularization * beta
        hessian = xa.T @ ((w * curvature)[:, None] * xa)
        hessian += l2 * np.diag(regularization)
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hessian, gradient, rcond=None)[0]
        beta += step
        if float(np.max(np.abs(step))) < 1e-8:
            break
    return _phase8_sigmoid(xea @ beta)


def _phase8_fit_catboost(
    train_x,
    train_y,
    train_weights,
    eval_x,
    *,
    iterations: int,
    seed: int,
):
    from catboost import CatBoostClassifier

    model = CatBoostClassifier(
        iterations=int(iterations),
        depth=4,
        learning_rate=0.04,
        loss_function="Logloss",
        l2_leaf_reg=5.0,
        bootstrap_type="No",
        random_strength=0.0,
        random_seed=int(seed),
        thread_count=1,
        verbose=False,
        allow_writing_files=False,
    )
    model.fit(train_x, train_y, sample_weight=train_weights)
    return model.predict_proba(eval_x)[:, 1]


def _phase8_fit_neural(
    train_x,
    train_y,
    train_weights,
    eval_x,
    *,
    epochs: int,
    seed: int,
):
    import numpy as np

    x = np.asarray(train_x, dtype=float)
    y = np.asarray(train_y, dtype=float)
    w = np.asarray(train_weights, dtype=float)
    xe = np.asarray(eval_x, dtype=float)

    total_weight = float(w.sum())
    normalized_weights = w / total_weight
    means = np.sum(normalized_weights[:, None] * x, axis=0)
    variance = np.sum(normalized_weights[:, None] * np.square(x - means), axis=0)
    scales = np.maximum(np.sqrt(variance), 1e-6)
    xs = (x - means) / scales
    xes = (xe - means) / scales

    rng = np.random.default_rng(int(seed))
    width = xs.shape[1]
    hidden = PHASE8_NN_HIDDEN
    w1 = rng.normal(0.0, 1.0 / math.sqrt(max(1, width)), size=(width, hidden))
    b1 = np.zeros(hidden, dtype=float)
    w2 = rng.normal(0.0, 1.0 / math.sqrt(max(1, hidden)), size=hidden)
    b2 = np.zeros(1, dtype=float)

    params = [w1, b1, w2, b2]
    first_moment = [np.zeros_like(param) for param in params]
    second_moment = [np.zeros_like(param) for param in params]
    beta1 = 0.9
    beta2 = 0.999
    adam_eps = 1e-8
    learning_rate = 0.025
    l2 = 5e-4

    for epoch in range(1, int(epochs) + 1):
        hidden_values = np.tanh(xs @ w1 + b1)
        probabilities = _phase8_sigmoid(hidden_values @ w2 + b2[0])
        dz2 = (probabilities - y) * normalized_weights

        grad_w2 = hidden_values.T @ dz2 + l2 * w2
        grad_b2 = np.asarray([float(dz2.sum())], dtype=float)
        dhidden = dz2[:, None] * w2[None, :]
        dz1 = dhidden * (1.0 - np.square(hidden_values))
        grad_w1 = xs.T @ dz1 + l2 * w1
        grad_b1 = dz1.sum(axis=0)
        gradients = [grad_w1, grad_b1, grad_w2, grad_b2]

        for index, (param, gradient) in enumerate(zip(params, gradients)):
            first_moment[index] = beta1 * first_moment[index] + (1.0 - beta1) * gradient
            second_moment[index] = beta2 * second_moment[index] + (1.0 - beta2) * np.square(gradient)
            m_hat = first_moment[index] / (1.0 - beta1 ** epoch)
            v_hat = second_moment[index] / (1.0 - beta2 ** epoch)
            param -= learning_rate * m_hat / (np.sqrt(v_hat) + adam_eps)

    eval_hidden = np.tanh(xes @ w1 + b1)
    return _phase8_sigmoid(eval_hidden @ w2 + b2[0])


def _phase8_row_key(item: dict[str, Any]) -> str:
    row = item["row"]
    prediction_key = str(row.get("prediction_key") or "").strip()
    if prediction_key:
        return prediction_key
    return "|".join([
        item["match_id"],
        item["market"],
        str(row.get("pick") or ""),
        str(row.get("line") or ""),
        str(row.get("player") or ""),
    ])


def _phase8_per_market_metrics(
    records: list[dict[str, Any]],
    predictions: dict[str, Any],
) -> dict[str, Any]:
    import numpy as np

    out = {}
    for market in sorted({item["market"] for item in records}):
        indexes = [index for index, item in enumerate(records) if item["market"] == market]
        subset = [records[index] for index in indexes]
        weights = _phase8_match_balanced_weights(subset)
        targets = np.asarray([item["target"] for item in subset], dtype=float)
        market_tracks = {}
        for track in PHASE8_TRACKS:
            values = np.asarray(predictions[track], dtype=float)[indexes]
            market_tracks[track] = _phase8_metrics(values, targets, weights)
        out[market] = {
            "rows": len(subset),
            "matches": len({item["match_id"] for item in subset}),
            "tracks": market_tracks,
        }
    return out


def _phase8_gain(candidate: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    def gain(metric: str) -> float | None:
        left = candidate.get(metric)
        right = reference.get(metric)
        if left is None or right is None:
            return None
        return round(float(right) - float(left), 8)

    brier_gain = gain("brier")
    log_loss_gain = gain("log_loss")
    ece_gain = gain("ece_10_bin")
    return {
        "brier_gain": brier_gain,
        "log_loss_gain": log_loss_gain,
        "ece_gain": ece_gain,
        "better_on_brier_and_log_loss": bool(
            brier_gain is not None
            and log_loss_gain is not None
            and brier_gain > 0.0
            and log_loss_gain > 0.0
        ),
        "calibration_not_worse": bool(ece_gain is not None and ece_gain >= 0.0),
    }


def evaluate_phase8_challengers(
    rows: list[dict[str, Any]],
    phase7_report: dict[str, Any],
    *,
    catboost_iterations: int = PHASE8_CATBOOST_ITERATIONS,
    nn_epochs: int = PHASE8_NN_EPOCHS,
) -> dict[str, Any]:
    import numpy as np

    phase7_ready = bool(
        phase7_report.get("phase7_complete") is True
        and phase7_report.get("phase8_ready") is True
    )
    base = {
        "version": PHASE8_VERSION,
        "neural_version": NEURAL_VERSION,
        "mode": PHASE8_MODE,
        "phase": 8,
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "playable_influence": False,
        "symphony_prod_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "promotion_allowed_by_this_gate": False,
        "phase7_prerequisite_satisfied": phase7_ready,
        "comparison_contract": {
            "same_raw_rows_all_tracks": True,
            "same_fold_membership_all_tracks": True,
            "expanding_train_windows": True,
            "disjoint_future_eval_windows": True,
            "same_timestamp_matches_never_split": True,
            "stable_match_id_grouping_only": True,
            "match_balanced_weighting_all_tracks": True,
            "shared_feature_family_all_learned_tracks": True,
            "state_probability_is_untrained_reference": True,
            "logistic_baseline_has_market_fixed_effects_and_market_state_slopes": True,
            "catboost_trained_from_same_phase8_features": True,
            "neural_network_trained_from_same_phase8_features": True,
            "ensemble_is_fixed_equal_weight_mean_no_holdout_tuning": True,
            "upstream_catboost_probability_not_used_as_feature": True,
            "bookmaker_price_not_used_as_feature": True,
            "final_result_not_used_as_feature": True,
            "phase8_completion_is_not_model_promotion": True,
        },
        "feature_contract": {
            "shared_feature_names": phase8_feature_names(),
            "market_universe": list(PHASE8_MARKETS),
            "excluded_probability_features": [
                "base_probability",
                "current_probability",
                "catboost_probability",
                "tabpfn_probability",
                "adaptive_probability",
            ],
            "bookmaker_price_excluded": True,
            "settlement_used_only_as_target": True,
        },
        "fold_policy": {
            "train_fractions": list(PHASE8_TRAIN_FRACTIONS),
            "evaluation_fraction_windows": [[0.55, 0.70], [0.70, 0.85], [0.85, 1.0]],
            "required_folds": PHASE8_REQUIRED_FOLDS,
            "min_train_matches": PHASE8_MIN_TRAIN_MATCHES,
            "min_eval_matches": PHASE8_MIN_EVAL_MATCHES,
            "min_eval_rows": PHASE8_MIN_EVAL_ROWS,
            "min_train_class_rows": PHASE8_MIN_TRAIN_CLASS_ROWS,
            "min_eval_class_rows": PHASE8_MIN_EVAL_CLASS_ROWS,
        },
        "model_config": {
            "logistic_baseline": {
                "kind": "WEIGHTED_LOGISTIC_CALIBRATION_WITH_MARKET_FIXED_EFFECTS",
                "l2": 1e-3,
            },
            "catboost": {
                "iterations": int(catboost_iterations),
                "depth": 4,
                "learning_rate": 0.04,
                "bootstrap_type": "No",
                "random_strength": 0.0,
                "thread_count": 1,
            },
            "neural_network": {
                "architecture": "ONE_HIDDEN_LAYER_TANH_LOGISTIC",
                "hidden_units": PHASE8_NN_HIDDEN,
                "epochs": int(nn_epochs),
                "optimizer": "FULL_BATCH_ADAM",
                "match_balanced": True,
            },
            "ensemble": {
                "members": ["logistic_baseline", "catboost", "neural_network"],
                "weights": [1 / 3, 1 / 3, 1 / 3],
                "tuned_on_eval": False,
            },
        },
    }

    if not phase7_ready:
        return {
            **base,
            "status": "PHASE8_BLOCKED_PHASE7_PREREQUISITE",
            "phase8_complete": False,
            "phase9_ready": False,
            "nn_promotion_evidence_sufficient": False,
            "promotion_verdict": "NN_REMAINS_SHADOW_CHALLENGER",
            "folds": [],
            "aggregate": {},
        }

    records = _phase8_eligible_rows(rows)
    specs = _phase8_fold_specs(records)
    counts = {
        "history_rows_total": len([row for row in rows if isinstance(row, dict)]),
        "eligible_settled_rows": len(records),
        "eligible_matches": len({item["match_id"] for item in records}),
        "eligible_markets": len({item["market"] for item in records}),
        "fold_specs": len(specs),
    }
    if len(specs) != PHASE8_REQUIRED_FOLDS:
        return {
            **base,
            "status": "PHASE8_INCOMPLETE_NO_PROMOTION",
            "phase8_complete": False,
            "phase9_ready": False,
            "nn_promotion_evidence_sufficient": False,
            "promotion_verdict": "NN_REMAINS_SHADOW_CHALLENGER",
            "counts": counts,
            "folds": [],
            "aggregate": {},
        }

    folds = []
    aggregate_records: list[dict[str, Any]] = []
    aggregate_predictions = {track: [] for track in PHASE8_TRACKS}

    for spec in specs:
        train_records = [item for item in records if item["match_id"] in spec["train_ids"]]
        eval_records = [item for item in records if item["match_id"] in spec["eval_ids"]]
        train_targets = np.asarray([item["target"] for item in train_records], dtype=float)
        eval_targets = np.asarray([item["target"] for item in eval_records], dtype=float)
        train_matches = len({item["match_id"] for item in train_records})
        eval_matches = len({item["match_id"] for item in eval_records})
        train_hits = int(train_targets.sum()) if len(train_targets) else 0
        train_misses = len(train_targets) - train_hits
        eval_hits = int(eval_targets.sum()) if len(eval_targets) else 0
        eval_misses = len(eval_targets) - eval_hits
        support_sufficient = bool(
            train_matches >= PHASE8_MIN_TRAIN_MATCHES
            and eval_matches >= PHASE8_MIN_EVAL_MATCHES
            and len(eval_records) >= PHASE8_MIN_EVAL_ROWS
            and min(train_hits, train_misses) >= PHASE8_MIN_TRAIN_CLASS_ROWS
            and min(eval_hits, eval_misses) >= PHASE8_MIN_EVAL_CLASS_ROWS
            and spec["same_timestamp_split"] is False
        )

        fold_meta = {
            "fold": spec["fold"],
            "train_fraction_target": spec["train_fraction_target"],
            "train_before": spec["train_before"].isoformat(),
            "eval_from": spec["eval_from"].isoformat(),
            "eval_before": spec["eval_before"].isoformat() if spec["eval_before"] else None,
            "train_rows": len(train_records),
            "eval_rows": len(eval_records),
            "train_matches": train_matches,
            "eval_matches": eval_matches,
            "train_hits": train_hits,
            "train_misses": train_misses,
            "eval_hits": eval_hits,
            "eval_misses": eval_misses,
            "same_timestamp_split": spec["same_timestamp_split"],
            "support_sufficient": support_sufficient,
            "eval_prediction_key_fingerprint_sha256": hashlib.sha256(
                "\n".join(sorted(_phase8_row_key(item) for item in eval_records)).encode("utf-8")
            ).hexdigest(),
        }
        if not support_sufficient:
            folds.append({
                **fold_meta,
                "status": "FOLD_INCOMPLETE",
                "reason": "INSUFFICIENT_SHARED_SUPPORT",
                "metrics": {},
                "per_market": {},
            })
            continue

        train_x = np.asarray([_phase8_feature_vector(item) for item in train_records], dtype=float)
        eval_x = np.asarray([_phase8_feature_vector(item) for item in eval_records], dtype=float)
        train_weights = _phase8_match_balanced_weights(train_records)
        eval_weights = _phase8_match_balanced_weights(eval_records)
        state_reference = np.asarray([
            min(
                1.0 - PHASE8_EPS,
                max(
                    PHASE8_EPS,
                    float((item["row"].get("feature_snapshot") or {}).get("numeric", {}).get("state_probability")),
                ),
            )
            for item in eval_records
        ], dtype=float)
        logistic = _phase8_fit_logistic(
            train_x,
            train_targets,
            train_weights,
            eval_x,
        )
        catboost = _phase8_fit_catboost(
            train_x,
            train_targets,
            train_weights,
            eval_x,
            iterations=catboost_iterations,
            seed=PHASE8_SEED + int(spec["fold"]),
        )
        neural = _phase8_fit_neural(
            train_x,
            train_targets,
            train_weights,
            eval_x,
            epochs=nn_epochs,
            seed=PHASE8_SEED + 100 + int(spec["fold"]),
        )
        ensemble = (logistic + catboost + neural) / 3.0
        predictions = {
            "state_reference": state_reference,
            "logistic_baseline": logistic,
            "catboost": catboost,
            "neural_network": neural,
            "ensemble": ensemble,
        }
        metrics = {
            track: _phase8_metrics(predictions[track], eval_targets, eval_weights)
            for track in PHASE8_TRACKS
        }
        if any(int((metrics.get(track) or {}).get("n") or 0) != len(eval_records) for track in PHASE8_TRACKS):
            raise ValueError(f"Phase-8 track coverage drift in fold {spec['fold']}")

        nn_vs_logistic = _phase8_gain(
            metrics["neural_network"],
            metrics["logistic_baseline"],
        )
        nn_vs_state = _phase8_gain(
            metrics["neural_network"],
            metrics["state_reference"],
        )
        best_by_brier = min(
            PHASE8_LEARNED_TRACKS,
            key=lambda track: float(metrics[track]["brier"]),
        )
        best_by_log_loss = min(
            PHASE8_LEARNED_TRACKS,
            key=lambda track: float(metrics[track]["log_loss"]),
        )
        folds.append({
            **fold_meta,
            "status": "FOLD_COMPLETE",
            "metrics": metrics,
            "per_market": _phase8_per_market_metrics(eval_records, predictions),
            "nn_vs_logistic": nn_vs_logistic,
            "nn_vs_state_reference": nn_vs_state,
            "best_challenger_by_brier": best_by_brier,
            "best_challenger_by_log_loss": best_by_log_loss,
        })

        aggregate_records.extend(eval_records)
        for track in PHASE8_TRACKS:
            aggregate_predictions[track].extend(float(value) for value in predictions[track])

    completed = [fold for fold in folds if fold.get("status") == "FOLD_COMPLETE"]
    technical_complete = bool(
        len(folds) == PHASE8_REQUIRED_FOLDS
        and len(completed) == PHASE8_REQUIRED_FOLDS
        and all(fold.get("support_sufficient") is True for fold in completed)
    )

    aggregate = {}
    nn_promotion_evidence_sufficient = False
    promotion_verdict = "NN_REMAINS_SHADOW_CHALLENGER"
    if aggregate_records:
        aggregate_targets = np.asarray([item["target"] for item in aggregate_records], dtype=float)
        aggregate_weights = _phase8_match_balanced_weights(aggregate_records)
        aggregate_metrics = {
            track: _phase8_metrics(
                aggregate_predictions[track],
                aggregate_targets,
                aggregate_weights,
            )
            for track in PHASE8_TRACKS
        }
        aggregate_per_market = _phase8_per_market_metrics(
            aggregate_records,
            aggregate_predictions,
        )
        nn_vs_logistic = _phase8_gain(
            aggregate_metrics["neural_network"],
            aggregate_metrics["logistic_baseline"],
        )
        nn_vs_state = _phase8_gain(
            aggregate_metrics["neural_network"],
            aggregate_metrics["state_reference"],
        )
        positive_folds = sum(
            1
            for fold in completed
            if (fold.get("nn_vs_logistic") or {}).get("better_on_brier_and_log_loss") is True
        )
        best_by_brier = min(
            PHASE8_LEARNED_TRACKS,
            key=lambda track: float(aggregate_metrics[track]["brier"]),
        )
        best_by_log_loss = min(
            PHASE8_LEARNED_TRACKS,
            key=lambda track: float(aggregate_metrics[track]["log_loss"]),
        )
        nn_promotion_evidence_sufficient = bool(
            technical_complete
            and nn_vs_logistic.get("better_on_brier_and_log_loss") is True
            and nn_vs_logistic.get("calibration_not_worse") is True
            and nn_vs_state.get("better_on_brier_and_log_loss") is True
            and positive_folds >= 2
        )
        if nn_promotion_evidence_sufficient:
            promotion_verdict = "NN_EVIDENCE_READY_FOR_AUDIT_REVIEW"

        aggregate = {
            "rows": len(aggregate_records),
            "matches": len({item["match_id"] for item in aggregate_records}),
            "metrics": aggregate_metrics,
            "per_market": aggregate_per_market,
            "nn_vs_logistic": nn_vs_logistic,
            "nn_vs_state_reference": nn_vs_state,
            "nn_better_than_logistic_brier_log_loss_folds": positive_folds,
            "best_challenger_by_brier": best_by_brier,
            "best_challenger_by_log_loss": best_by_log_loss,
            "eval_prediction_key_fingerprint_sha256": hashlib.sha256(
                "\n".join(sorted(_phase8_row_key(item) for item in aggregate_records)).encode("utf-8")
            ).hexdigest(),
        }

    return {
        **base,
        "status": (
            "PHASE8_CHALLENGER_EVALUATION_COMPLETE_NO_PROMOTION"
            if technical_complete
            else "PHASE8_INCOMPLETE_NO_PROMOTION"
        ),
        "counts": counts,
        "folds": folds,
        "aggregate": aggregate,
        "technical_validation_complete": technical_complete,
        "phase8_complete": technical_complete,
        "phase9_ready": technical_complete,
        "nn_promotion_evidence_sufficient": nn_promotion_evidence_sufficient,
        "promotion_verdict": promotion_verdict,
        "policy": {
            "nn_is_challenger_not_default_winner": True,
            "best_oos_track_is_reported_not_activated": True,
            "phase8_completion_does_not_require_nn_to_win": True,
            "nn_requires_oos_brier_log_loss_and_calibration_gain_before_review": True,
            "two_of_three_positive_folds_required_for_nn_review": True,
            "promotion_remains_separate_phase14_process": True,
        },
    }


def build_phase8_gate(
    history_path: Path = DEFAULT_HISTORY_PATH,
    phase7_path: Path = PHASE7_REPORT_PATH,
    output_path: Path = PHASE8_OUT,
) -> dict[str, Any]:
    rows = load_history(history_path)
    phase7 = _read_json(phase7_path)
    report = evaluate_phase8_challengers(rows, phase7)
    _write_json_atomic(output_path, report)
    print(json.dumps({
        "version": report.get("version"),
        "mode": report.get("mode"),
        "status": report.get("status"),
        "phase8_complete": report.get("phase8_complete"),
        "phase9_ready": report.get("phase9_ready"),
        "promotion_verdict": report.get("promotion_verdict"),
        "aggregate": {
            "rows": (report.get("aggregate") or {}).get("rows"),
            "matches": (report.get("aggregate") or {}).get("matches"),
            "best_brier": (report.get("aggregate") or {}).get("best_challenger_by_brier"),
            "best_log_loss": (report.get("aggregate") or {}).get("best_challenger_by_log_loss"),
            "nn_positive_folds": (report.get("aggregate") or {}).get(
                "nn_better_than_logistic_brier_log_loss_folds"
            ),
        },
    }, ensure_ascii=False))
    return report
