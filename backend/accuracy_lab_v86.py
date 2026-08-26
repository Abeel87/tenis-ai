from __future__ import annotations

import bisect
import gc
import json
import math
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

VERSION = "v8.6-shadow"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
HISTORY_PATH = OUT / "history.json"
AUTOLearn_REPORT = OUT / "autolearn_v84.json"
REPORT_PATH = OUT / "accuracy_lab_v86.json"
DB_PATH = ROOT / "data" / "tennis.db"

PRODUCTION_MODE = "shadow_only"
GLOBAL_THRESHOLD = 0.65
MIN_SEGMENT_CAL = 20
MIN_SEGMENT_VAL = 10


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
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


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(value)))


def _norm(value):
    return " ".join(str(value or "").strip().casefold().split())


def _brier(y, p):
    pairs = [(int(yy), float(pp)) for yy, pp in zip(y, p) if pp is not None]
    if not pairs:
        return None
    return sum((pp - yy) ** 2 for yy, pp in pairs) / len(pairs)


def _logloss(y, p):
    pairs = [(int(yy), float(pp)) for yy, pp in zip(y, p) if pp is not None]
    if not pairs:
        return None
    total = 0.0
    for yy, pp in pairs:
        pp = _clamp(pp, 1e-6, 1 - 1e-6)
        total += -(yy * math.log(pp) + (1 - yy) * math.log(1 - pp))
    return total / len(pairs)


def _metrics(rows, probs, threshold=GLOBAL_THRESHOLD):
    usable = [(r, float(p)) for r, p in zip(rows or [], probs or []) if p is not None and r.get("target") in (0, 1)]
    if not usable:
        return {"n": 0, "coverage": 0.0, "brier": None, "log_loss": None, "selected_n": 0, "accuracy": None}
    y = [int(r["target"]) for r, _ in usable]
    pp = [p for _, p in usable]
    selected = [(r, p) for r, p in usable if p >= threshold]
    hits = sum(int(r["target"]) for r, _ in selected)
    return {
        "n": len(usable),
        "coverage": round(len(usable) / max(1, len(rows or [])), 4),
        "brier": round(_brier(y, pp), 5),
        "log_loss": round(_logloss(y, pp), 5),
        "selected_n": len(selected),
        "selected_coverage": round(len(selected) / max(1, len(usable)), 4),
        "accuracy": round(100.0 * hits / len(selected), 1) if selected else None,
        "threshold": round(threshold * 100, 1),
    }


def _wilson_lower(hits: int, n: int, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    phat = hits / n
    den = 1.0 + z * z / n
    center = phat + z * z / (2.0 * n)
    margin = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n)
    return max(0.0, (center - margin) / den)


def _choose_threshold(rows, probs, minimum_selected=12, minimum_coverage=0.20):
    usable = [(r, float(p)) for r, p in zip(rows or [], probs or []) if p is not None and r.get("target") in (0, 1)]
    if not usable:
        return None
    n = len(usable)
    min_n = max(int(minimum_selected), int(math.ceil(n * minimum_coverage)))
    best = None
    for pct in range(55, 91):
        threshold = pct / 100.0
        selected = [(r, p) for r, p in usable if p >= threshold]
        if len(selected) < min_n:
            continue
        hits = sum(int(r["target"]) for r, _ in selected)
        accuracy = hits / len(selected)
        lower = _wilson_lower(hits, len(selected))
        # Wilson lower bound is primary: it punishes tiny, lucky samples.
        score = (lower, accuracy, len(selected), -threshold)
        if best is None or score > best[0]:
            best = (score, threshold, hits, len(selected))
    if best is None:
        return None
    _, threshold, hits, selected_n = best
    return {
        "threshold": threshold,
        "selected_n": selected_n,
        "accuracy": hits / selected_n,
        "wilson95_lower": _wilson_lower(hits, selected_n),
        "coverage": selected_n / n,
    }


def _market_threshold_lab(cal_rows, cal_probs, val_rows, val_probs):
    cal_by = defaultdict(lambda: ([], []))
    val_by = defaultdict(lambda: ([], []))
    for r, p in zip(cal_rows, cal_probs):
        if p is not None:
            cal_by[str(r.get("market") or "other")][0].append(r)
            cal_by[str(r.get("market") or "other")][1].append(p)
    for r, p in zip(val_rows, val_probs):
        if p is not None:
            val_by[str(r.get("market") or "other")][0].append(r)
            val_by[str(r.get("market") or "other")][1].append(p)

    out = {}
    for market, (cr, cp) in cal_by.items():
        vr, vp = val_by.get(market, ([], []))
        if len(cr) < MIN_SEGMENT_CAL or len(vr) < MIN_SEGMENT_VAL:
            continue
        chosen = _choose_threshold(cr, cp)
        if not chosen:
            continue
        base = _metrics(vr, vp, GLOBAL_THRESHOLD)
        test = _metrics(vr, vp, chosen["threshold"])
        delta = None
        if base.get("accuracy") is not None and test.get("accuracy") is not None:
            delta = round(test["accuracy"] - base["accuracy"], 1)
        out[market] = {
            "cal_n": len(cr),
            "val_n": len(vr),
            "chosen_threshold": round(chosen["threshold"] * 100, 1),
            "cal_selected_n": chosen["selected_n"],
            "cal_wilson95_lower": round(chosen["wilson95_lower"] * 100, 1),
            "baseline_65_val": base,
            "candidate_val": test,
            "accuracy_delta_pp": delta,
            "shadow_recommendation": bool(
                delta is not None and delta >= 2.0 and (test.get("selected_n") or 0) >= MIN_SEGMENT_VAL
            ),
        }
    return out


def _elo_expected(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def _elo_update(winner: float, loser: float, k: float = 32.0):
    expected = _elo_expected(winner, loser)
    delta = k * (1.0 - expected)
    return winner + delta, loser - delta


class EloIndex:
    """Strict pre-date Elo lookup: same-day results are never visible to a historical fixture."""

    def __init__(self):
        self.overall: dict[str, tuple[list[int], list[float]]] = {}
        self.surface: dict[tuple[str, str], tuple[list[int], list[float]]] = {}

    @staticmethod
    def _append(store, key, day: int, rating: float):
        dates, vals = store.setdefault(key, ([], []))
        dates.append(day)
        vals.append(float(rating))

    @staticmethod
    def _before(store, key, day: int, default=1500.0):
        pair = store.get(key)
        if not pair:
            return float(default)
        dates, vals = pair
        pos = bisect.bisect_left(dates, day) - 1
        return float(vals[pos]) if pos >= 0 else float(default)

    def overall_before(self, player_key: str, day: int):
        return self._before(self.overall, player_key, day)

    def surface_before(self, player_key: str, surface: str, day: int):
        return self._before(self.surface, (player_key, surface), day)


def _build_elo_index(long_df, key_fn) -> EloIndex:
    import pandas as pd

    idx = EloIndex()
    if long_df is None or long_df.empty:
        return idx
    x = long_df.copy()
    x["date"] = pd.to_datetime(x.get("date"), errors="coerce")
    x = x[(x.get("won") == 1.0) & x["date"].notna()].copy()
    x = x.sort_values(["date", "player", "opponent"])

    ratings = defaultdict(lambda: 1500.0)
    surface_ratings = defaultdict(lambda: 1500.0)
    seen = set()
    for _, row in x.iterrows():
        winner = key_fn(row.get("player"))
        loser = key_fn(row.get("opponent"))
        if not winner or not loser:
            continue
        day = int(row["date"].normalize().toordinal())
        surface = str(row.get("surface") or "").lower() or "unknown"
        dedupe = (day, surface, tuple(sorted((winner, loser))))
        if dedupe in seen:
            continue
        seen.add(dedupe)

        rw, rl = ratings[winner], ratings[loser]
        sw, sl = surface_ratings[(winner, surface)], surface_ratings[(loser, surface)]
        rw2, rl2 = _elo_update(rw, rl, 32.0)
        sw2, sl2 = _elo_update(sw, sl, 36.0)
        ratings[winner], ratings[loser] = rw2, rl2
        surface_ratings[(winner, surface)], surface_ratings[(loser, surface)] = sw2, sl2
        idx._append(idx.overall, winner, day, rw2)
        idx._append(idx.overall, loser, day, rl2)
        idx._append(idx.surface, (winner, surface), day, sw2)
        idx._append(idx.surface, (loser, surface), day, sl2)
    return idx


def _fixture_day(value):
    try:
        text = str(value or "")[:10]
        return datetime.fromisoformat(text).date()
    except Exception:
        return None


def _pick_side(row, entry):
    pick = _norm(row.get("pick"))
    p1 = _norm(entry.get("p1"))
    p2 = _norm(entry.get("p2"))
    if pick and pick == p1:
        return "p1"
    if pick and pick == p2:
        return "p2"
    if pick in ("over", "under"):
        return pick
    if ":" in str(row.get("pick") or ""):
        return "state"
    return "other"


def _safe_profile_metric(profile, name, default=0.0):
    v = _num((profile or {}).get(name))
    return float(v) if v is not None else float(default)


def _direct_feature_rows(rows, entries_by_key, long_df, elo_index, key_fn, player_profile_fn, surface_priors_fn):
    import pandas as pd

    out = []
    profile_cache = {}
    prior_cache = {}
    for row in rows:
        entry = entries_by_key.get(row.get("match_key")) or {}
        day = _fixture_day(entry.get("scheduled_time") or row.get("scheduled_time"))
        surface = str(entry.get("surface") or row.get("surface") or "").lower()
        p1 = str(entry.get("p1") or "")
        p2 = str(entry.get("p2") or "")
        if day:
            # Critical anti-leak rule for historical training: exclude the fixture's calendar day.
            cutoff = pd.Timestamp(day - timedelta(days=1))
            prior_key = (surface, cutoff.date().isoformat())
            if prior_key not in prior_cache:
                prior_cache[prior_key] = surface_priors_fn(long_df, surface, cutoff)
            priors = prior_cache[prior_key]
            for player in (p1, p2):
                ck = (key_fn(player), surface, cutoff.date().isoformat())
                if ck not in profile_cache:
                    profile_cache[ck] = player_profile_fn(long_df, player, surface, cutoff, priors)
            a = profile_cache.get((key_fn(p1), surface, cutoff.date().isoformat()), {})
            b = profile_cache.get((key_fn(p2), surface, cutoff.date().isoformat()), {})
            ordinal = day.toordinal()
        else:
            a, b, ordinal = {}, {}, 1

        arank = _safe_profile_metric(a, "rank", 500.0)
        brank = _safe_profile_metric(b, "rank", 500.0)
        ahold = _safe_profile_metric(a, "hold_rate", 0.72)
        bhold = _safe_profile_metric(b, "hold_rate", 0.72)
        abreak = _safe_profile_metric(a, "break_rate", 0.28)
        bbreak = _safe_profile_metric(b, "break_rate", 0.28)
        aspw = _safe_profile_metric(a, "serve_points_won", 0.60)
        bspw = _safe_profile_metric(b, "serve_points_won", 0.60)
        arpw = _safe_profile_metric(a, "return_points_won", 0.40)
        brpw = _safe_profile_metric(b, "return_points_won", 0.40)
        aelo = elo_index.overall_before(key_fn(p1), ordinal) if day else 1500.0
        belo = elo_index.overall_before(key_fn(p2), ordinal) if day else 1500.0
        aselo = elo_index.surface_before(key_fn(p1), surface, ordinal) if day else 1500.0
        bselo = elo_index.surface_before(key_fn(p2), surface, ordinal) if day else 1500.0

        out.append({
            "target": int(row.get("target")) if row.get("target") in (0, 1) else None,
            "market": str(row.get("market") or "other"),
            "pick_kind": str(row.get("pick_kind") or "other"),
            "pick_side": _pick_side(row, entry),
            "tour": str(entry.get("tour") or row.get("tour") or "N/D").upper(),
            "surface": str(entry.get("surface") or row.get("surface") or "N/D").upper(),
            "quality": str(entry.get("quality") or row.get("quality") or "N/D"),
            "line": _num(row.get("line"), -1.0),
            "rank_log_ratio": math.log((brank + 30.0) / (arank + 30.0)),
            "p1_hold": ahold, "p2_hold": bhold, "hold_diff": ahold - bhold,
            "p1_break": abreak, "p2_break": bbreak, "break_diff": abreak - bbreak,
            "p1_spw": aspw, "p2_spw": bspw, "spw_diff": aspw - bspw,
            "p1_rpw": arpw, "p2_rpw": brpw, "rpw_diff": arpw - brpw,
            "p1_serve_vs_p2_return": 0.58 * aspw + 0.42 * (1.0 - brpw),
            "p2_serve_vs_p1_return": 0.58 * bspw + 0.42 * (1.0 - arpw),
            "p1_first_serve_won": _safe_profile_metric(a, "first_serve_won", 0.62),
            "p2_first_serve_won": _safe_profile_metric(b, "first_serve_won", 0.62),
            "p1_second_serve_won": _safe_profile_metric(a, "second_serve_won", 0.50),
            "p2_second_serve_won": _safe_profile_metric(b, "second_serve_won", 0.50),
            "fatigue_diff": _safe_profile_metric(a, "fatigue_load", 0.0) - _safe_profile_metric(b, "fatigue_load", 0.0),
            "surface_matches_diff": _safe_profile_metric(a, "surface_matches", 0.0) - _safe_profile_metric(b, "surface_matches", 0.0),
            "data_confidence_min": min(_safe_profile_metric(a, "data_confidence", 0.0), _safe_profile_metric(b, "data_confidence", 0.0)),
            "elo_diff": aelo - belo,
            "surface_elo_diff": aselo - bselo,
            "elo_p1": aelo, "elo_p2": belo,
            "surface_elo_p1": aselo, "surface_elo_p2": bselo,
            "direct_data_quality": "ready" if (a.get("matches", 0) >= 5 and b.get("matches", 0) >= 5) else "sparse",
        })
    return out


DIRECT_CATEGORICAL = ["market", "pick_kind", "pick_side", "tour", "surface", "quality", "direct_data_quality"]
DIRECT_NUMERIC = [
    "line", "rank_log_ratio", "p1_hold", "p2_hold", "hold_diff", "p1_break", "p2_break", "break_diff",
    "p1_spw", "p2_spw", "spw_diff", "p1_rpw", "p2_rpw", "rpw_diff", "p1_serve_vs_p2_return",
    "p2_serve_vs_p1_return", "p1_first_serve_won", "p2_first_serve_won", "p1_second_serve_won",
    "p2_second_serve_won", "fatigue_diff", "surface_matches_diff", "data_confidence_min", "elo_diff",
    "surface_elo_diff", "elo_p1", "elo_p2", "surface_elo_p1", "surface_elo_p2",
]


def _direct_frame(rows):
    import pandas as pd

    data = []
    for r in rows:
        x = {c: _num(r.get(c), 0.0) for c in DIRECT_NUMERIC}
        x.update({c: str(r.get(c) or "N/D") for c in DIRECT_CATEGORICAL})
        data.append(x)
    return pd.DataFrame(data, columns=DIRECT_NUMERIC + DIRECT_CATEGORICAL)


def _fit_direct_catboost(train_rows, cal_rows, val_rows):
    if len(train_rows) < 80 or len({r.get("target") for r in train_rows}) < 2:
        return None, [], [], {"status": "insufficient_training_data"}
    try:
        from catboost import CatBoostClassifier
    except ModuleNotFoundError:
        return None, [], [], {"status": "missing_catboost"}

    X_train = _direct_frame(train_rows)
    X_cal = _direct_frame(cal_rows)
    X_val = _direct_frame(val_rows)
    y_train = [int(r["target"]) for r in train_rows]
    y_cal = [int(r["target"]) for r in cal_rows]

    model = CatBoostClassifier(
        iterations=320,
        depth=5,
        learning_rate=0.035,
        l2_leaf_reg=6.0,
        loss_function="Logloss",
        random_seed=42,
        verbose=False,
        allow_writing_files=False,
        thread_count=2,
    )
    fit_kwargs: dict[str, Any] = {"cat_features": DIRECT_CATEGORICAL}
    if len(cal_rows) >= 30 and len(set(y_cal)) >= 2:
        fit_kwargs.update({"eval_set": (X_cal, y_cal), "use_best_model": True, "early_stopping_rounds": 45})
    model.fit(X_train, y_train, **fit_kwargs)

    def prob(X):
        return [] if X.empty else [float(v[1]) for v in model.predict_proba(X)]

    cal_probs = prob(X_cal)
    val_probs = prob(X_val)
    info = {
        "status": "ok",
        "features": len(DIRECT_NUMERIC) + len(DIRECT_CATEGORICAL),
        "numeric_features": len(DIRECT_NUMERIC),
        "categorical_features": len(DIRECT_CATEGORICAL),
        "best_iteration": int(model.get_best_iteration()) if model.get_best_iteration() is not None else None,
    }
    return model, cal_probs, val_probs, info


def _native_tabpfn_frame(rows, numeric, categorical):
    import pandas as pd

    data = []
    for r in rows:
        x = {c: _num(r.get(c), 0.0) for c in numeric}
        x.update({c: str(r.get(c) or "N/D") for c in categorical})
        data.append(x)
    return pd.DataFrame(data, columns=[*numeric, *categorical])


def _run_native_tabpfn(train, cal, val, numeric, categorical, cap: int, n_estimators: int):
    from tabpfn import TabPFNClassifier
    from tabpfn.constants import ModelVersion

    use_train = train[-cap:] if cap and len(train) > cap else list(train)
    X_train = _native_tabpfn_frame(use_train, numeric, categorical)
    X_cal = _native_tabpfn_frame(cal, numeric, categorical)
    X_val = _native_tabpfn_frame(val, numeric, categorical)
    cat_indices = [len(numeric) + i for i in range(len(categorical))]
    y_train = [int(r["target"]) for r in use_train]

    clf = TabPFNClassifier.create_default_for_version(
        ModelVersion.V2,
        n_estimators=n_estimators,
        device="cpu",
        show_progress_bar=False,
        random_state=42,
    )
    # v8.6 experiment: preserve categoricals and let TabPFN's own preprocessing handle them.
    clf.categorical_features_indices = cat_indices
    clf.fit(X_train, y_train)

    def prob(X):
        return [] if X.empty else [float(v[1]) for v in clf.predict_proba(X)]

    cal_probs = prob(X_cal)
    val_probs = prob(X_val)
    info = {
        "status": "ok",
        "train_rows": len(use_train),
        "n_estimators": n_estimators,
        "external_one_hot": False,
        "categorical_features_indices": cat_indices,
    }
    del clf
    gc.collect()
    return cal_probs, val_probs, info


def _segment_value(row, fields):
    return "|".join(str(row.get(f) or "N/D") for f in fields)


def _segment_champions(rows, probs_by_model, fields, min_n):
    groups = defaultdict(list)
    for i, r in enumerate(rows):
        groups[_segment_value(r, fields)].append(i)
    out = {}
    for segment, indices in groups.items():
        if len(indices) < min_n:
            continue
        candidates = []
        for model, probs in probs_by_model.items():
            pairs = [(rows[i], probs[i]) for i in indices if i < len(probs) and probs[i] is not None]
            if len(pairs) < max(10, int(0.80 * len(indices))):
                continue
            y = [int(r["target"]) for r, _ in pairs]
            pp = [float(p) for _, p in pairs]
            b = _brier(y, pp)
            ll = _logloss(y, pp)
            if b is not None:
                candidates.append((b, ll if ll is not None else 99.0, model, len(pairs)))
        if candidates:
            candidates.sort()
            b, ll, model, n = candidates[0]
            out[segment] = {"model": model, "cal_n": n, "brier": round(b, 5), "log_loss": round(ll, 5)}
    return out


def _router_lab(cal_rows, val_rows, cal_probs_by_model, val_probs_by_model):
    if not cal_probs_by_model or "current" not in cal_probs_by_model:
        return None

    global_candidates = []
    for model, probs in cal_probs_by_model.items():
        m = _metrics(cal_rows, probs)
        if m.get("n", 0) >= max(20, int(0.8 * len(cal_rows))) and m.get("brier") is not None:
            global_candidates.append((m["brier"], m.get("log_loss") or 99.0, model))
    global_candidates.sort()
    global_model = global_candidates[0][2] if global_candidates else "current"

    levels = [
        (("market", "tour", "surface"), 25),
        (("market", "tour"), 30),
        (("market",), 40),
    ]
    maps = [(fields, _segment_champions(cal_rows, cal_probs_by_model, fields, min_n)) for fields, min_n in levels]

    routed = []
    selected_models = defaultdict(int)
    for i, row in enumerate(val_rows):
        chosen = None
        for fields, mapping in maps:
            item = mapping.get(_segment_value(row, fields))
            if item:
                chosen = item["model"]
                break
        chosen = chosen or global_model
        probs = val_probs_by_model.get(chosen) or []
        p = probs[i] if i < len(probs) else None
        if p is None:
            chosen = "current"
            p = (val_probs_by_model.get("current") or [None] * len(val_rows))[i]
        selected_models[chosen] += 1
        routed.append(p)

    return {
        "global_cal_champion": global_model,
        "segment_levels": [
            {"fields": list(fields), "segments": mapping} for fields, mapping in maps
        ],
        "validation": _metrics(val_rows, routed),
        "validation_model_usage": dict(sorted(selected_models.items())),
        "policy": "calibration_only_champion_selection_hierarchical_fallback_validation_untouched",
    }


def main():
    now = datetime.now(timezone.utc)
    history = _read(HISTORY_PATH, [])
    previous_auto = _read(AUTOLearn_REPORT, {})
    if not history:
        _write(REPORT_PATH, {
            "version": VERSION, "generated_at": now.isoformat(), "status": "UNAVAILABLE",
            "production_mode": PRODUCTION_MODE, "reason": "missing_history",
        })
        return

    # Lazy imports keep pytest/basic runtime independent from optional TabPFN.
    from autolearn_v84 import (
        CATEGORICAL_FEATURES,
        NUMERIC_FEATURES,
        _fit_current_calibration,
        _gate_current_calibration,
        _match_key,
        _prob_from_score,
        build_training_rows,
        chronological_split,
    )
    from model import _key, _surface_priors, player_profile

    rows = build_training_rows(history)
    train, cal, val = chronological_split(rows)
    if len(train) < 40 or not cal or not val:
        _write(REPORT_PATH, {
            "version": VERSION, "generated_at": now.isoformat(), "status": "UNAVAILABLE",
            "production_mode": PRODUCTION_MODE, "reason": "insufficient_chronological_split",
            "rows": len(rows), "train": len(train), "cal": len(cal), "val": len(val),
        })
        return

    calibration = _gate_current_calibration(_fit_current_calibration(train), cal)
    current_cal = [_prob_from_score(r, calibration) for r in cal]
    current_val = [_prob_from_score(r, calibration) for r in val]
    current_metrics = {"calibration": _metrics(cal, current_cal), "validation": _metrics(val, current_val)}
    threshold_lab = _market_threshold_lab(cal, current_cal, val, current_val)

    entries_by_key = {_match_key(e): e for e in history if isinstance(e, dict)}
    long_df = None
    direct = {"status": "unavailable", "reason": "missing_tennis_db"}
    direct_cal: list[float] = []
    direct_val: list[float] = []
    if DB_PATH.exists():
        try:
            import pandas as pd
            with sqlite3.connect(DB_PATH) as con:
                long_df = pd.read_sql_query("SELECT * FROM player_matches", con)
            long_df["date"] = pd.to_datetime(long_df.get("date"), errors="coerce")
            elo = _build_elo_index(long_df, _key)
            dtrain = _direct_feature_rows(train, entries_by_key, long_df, elo, _key, player_profile, _surface_priors)
            dcal = _direct_feature_rows(cal, entries_by_key, long_df, elo, _key, player_profile, _surface_priors)
            dval = _direct_feature_rows(val, entries_by_key, long_df, elo, _key, player_profile, _surface_priors)
            _, direct_cal, direct_val, dinfo = _fit_direct_catboost(dtrain, dcal, dval)
            direct = {
                **dinfo,
                "anti_leak_cutoff": "strictly_before_fixture_calendar_day",
                "elo": "overall_plus_surface_standard_elo_shadow_feature",
                "serve_return_interactions": True,
                "calibration": _metrics(cal, direct_cal) if direct_cal else None,
                "validation": _metrics(val, direct_val) if direct_val else None,
            }
        except Exception as exc:
            direct = {"status": "error", "reason": type(exc).__name__, "detail": str(exc)[:400]}

    partial = {
        "version": VERSION,
        "generated_at": now.isoformat(),
        "status": "ACTIVE_PARTIAL",
        "production_mode": PRODUCTION_MODE,
        "production_changed": False,
        "training": {"rows": len(rows), "matches": len({r.get('match_key') for r in rows}), "train": len(train), "cal": len(cal), "val": len(val)},
        "current": current_metrics,
        "market_thresholds_shadow": threshold_lab,
        "direct_tennis_catboost": direct,
        "tabpfn_native_ab": {"status": "pending_or_optional"},
        "router_shadow": None,
        "latest_production_tabpfn_snapshot": ((previous_auto.get("validation") or {}).get("tabpfn")),
        "notes": [
            "Shadow-only: no production signal, weight or threshold is modified.",
            "Market thresholds are selected on CAL and evaluated only on untouched VAL.",
            "Direct Tennis ML uses raw player profiles, surface Elo and opponent serve/return interaction features.",
            "Historical direct features use only matches strictly before the fixture calendar day to avoid same-day target leakage.",
        ],
    }
    _write(REPORT_PATH, partial)

    cal_models: dict[str, list[float]] = {"current": current_cal}
    val_models: dict[str, list[float]] = {"current": current_val}
    if direct_cal and direct_val:
        cal_models["direct_catboost"] = direct_cal
        val_models["direct_catboost"] = direct_val

    tab_report: dict[str, Any] = {"status": "unavailable", "reason": "tabpfn_not_installed_this_run", "variants": {}}
    try:
        import tabpfn  # noqa: F401
        variants = [("native_300_e1", 300, 1), ("native_600_e4", 600, 4)]
        if os.getenv("V86_EXTENDED", "0") == "1":
            variants.append(("native_full_e8", max(800, len(train)), 8))
        tab_report = {"status": "ok", "variants": {}}
        for name, cap, estimators in variants:
            try:
                cp, vp, info = _run_native_tabpfn(train, cal, val, NUMERIC_FEATURES, CATEGORICAL_FEATURES, cap, estimators)
                tab_report["variants"][name] = {
                    **info,
                    "calibration": _metrics(cal, cp),
                    "validation": _metrics(val, vp),
                }
                cal_models[name] = cp
                val_models[name] = vp
            except Exception as exc:
                tab_report["variants"][name] = {
                    "status": "error", "reason": type(exc).__name__, "detail": str(exc)[:400],
                    "train_cap": cap, "n_estimators": estimators,
                }
    except ModuleNotFoundError:
        pass

    router = _router_lab(cal, val, cal_models, val_models)
    final = {
        **partial,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ACTIVE",
        "tabpfn_native_ab": tab_report,
        "router_shadow": router,
        "models_available_for_router": sorted(cal_models),
        "promotion_gate": {
            "status": "shadow_only",
            "rule": "no automatic production promotion; require repeated VAL/tracking win in Brier/log-loss and non-worse accuracy",
        },
    }
    _write(REPORT_PATH, final)
    print(json.dumps({
        "status": final["status"],
        "current_val": current_metrics["validation"],
        "direct_val": (direct or {}).get("validation"),
        "tabpfn": tab_report,
        "router_val": (router or {}).get("validation"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
