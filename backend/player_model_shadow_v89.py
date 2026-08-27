from __future__ import annotations

import json
import math
import unicodedata
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev

try:
    from .player_intelligence_v85 import (
        _load_long_df as _load_pi_long_df,
        build_profile as _build_pi_profile,
        _matchup_summary as _pi_matchup_summary,
        _surface as _pi_surface,
    )
except ImportError:
    from player_intelligence_v85 import (
        _load_long_df as _load_pi_long_df,
        build_profile as _build_pi_profile,
        _matchup_summary as _pi_matchup_summary,
        _surface as _pi_surface,
    )

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
CACHE = ROOT / "data" / "cache" / "player_model_shadow_v89"
RESULTS_PATH = OUT / "results.json"
HISTORY_PATH = OUT / "history.json"
TELEMETRY_PATH = OUT / "model_telemetry_v84c.json"
REPORT_PATH = OUT / "player_model_shadow_v89.json"
META_PATH = OUT / "meta.json"

VERSION = "v8.9"
MODE = "SHADOW"
SELECT_THRESHOLD = 0.65
MIN_TRAIN_ROWS = 80
MIN_TRAIN_MATCHES = 20
MIN_HOLDOUT_ROWS = 20
MIN_HOLDOUT_MATCHES = 5

PROFILE_INDEXES = ("serve", "return", "form", "mental", "early", "rank_strength", "overall")
PROFILE_METRICS = (
    "hold_rate", "break_rate", "serve_points_won", "return_points_won",
    "first_set_won", "won",
)

BASE_NUMERIC_FEATURES = (
    "current_score", "catboost_score", "tabpfn_score", "ensemble_score",
    "adaptive_prod_score", "player_probability", "ensemble_player_shadow",
    "support_score", "pi_vs_ensemble", "line", "checkpoint",
    "pi_quality_rank", "feature_coverage", "best_of",
)
PROFILE_NUMERIC_FEATURES = tuple(
    f"{side}_{name}"
    for side in ("p1", "p2")
    for name in (
        *PROFILE_INDEXES,
        *PROFILE_METRICS,
        "sample_matches", "l5_n", "l10_n", "l20_n",
        "coverage", "fallback_used",
    )
)
EDGE_NUMERIC_FEATURES = (
    "overall_edge_p1", "serve_edge_p1", "return_edge_p1", "form_edge_p1",
    "overall_edge_for_pick", "serve_edge_for_pick", "return_edge_for_pick", "form_edge_for_pick",
    "overall_edge_abs", "serve_edge_abs", "return_edge_abs", "form_edge_abs",
)
NUMERIC_FEATURES = BASE_NUMERIC_FEATURES + PROFILE_NUMERIC_FEATURES + EDGE_NUMERIC_FEATURES
CATEGORICAL_FEATURES = ("market", "pick_kind", "tour", "surface", "pi_quality", "pick_side")
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES


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


def _prob(value):
    x = _num(value)
    if x is None:
        return None
    if x > 1:
        x /= 100.0
    return max(0.01, min(0.99, x))


def _norm(value) -> str:
    s = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def _match_key(entry: dict) -> str:
    mid = entry.get("match_id") if entry.get("match_id") is not None else entry.get("id")
    if mid is not None and str(mid) != "":
        return f"id:{mid}"
    return "|".join([
        _norm(entry.get("p1")), _norm(entry.get("p2")),
        str(entry.get("scheduled_time") or "")[:10], _norm(entry.get("tournament")),
    ])


def _canonical_market(value) -> str:
    x = str(value or "").lower()
    return {
        "match_win": "match_winner",
        "set1_win": "set1_winner",
        "set2_win": "set2_winner",
        "set3_win": "set3_winner",
    }.get(x, x or "other")


def _pick_kind(signal: dict) -> str:
    market = _canonical_market(signal.get("market"))
    pick = str(signal.get("pick") or "").lower()
    if pick in ("over", "under"):
        return pick
    if market == "game_state" or market.startswith("state"):
        return "state"
    if "winner" in market:
        return "player"
    return "other"


def _quality_rank(value) -> int:
    return {"N/D": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(str(value or "N/D").upper(), 0)


def _idx(profile: dict, name: str):
    return _num(((profile or {}).get("indexes") or {}).get(name))


def _metric(profile: dict, name: str, window="10"):
    metrics = ((((profile or {}).get("windows") or {}).get(str(window)) or {}).get("metrics") or {})
    return _num((metrics.get(name) or {}).get("adjusted"))


def _sample(profile: dict, window: int) -> float:
    return float(((((profile or {}).get("windows") or {}).get(str(window)) or {}).get("sample_matches")) or 0)


def _pick_side(match: dict, signal: dict) -> tuple[str, float]:
    pick = _norm(signal.get("pick"))
    p1, p2 = _norm(match.get("p1")), _norm(match.get("p2"))
    if pick and pick == p1:
        return "p1", 1.0
    if pick and pick == p2:
        return "p2", -1.0
    return "neutral", 0.0


def feature_snapshot(match: dict, signal: dict) -> dict:
    """Freeze pre-match Player Intelligence features for later learning.

    This snapshot is descriptive only. It never edits Ensemble/final_score.
    """
    pi = match.get("player_intelligence_v85") or {}
    profiles = pi.get("profiles") or {}
    p1, p2 = profiles.get("p1") or {}, profiles.get("p2") or {}
    matchup = pi.get("matchup") or {}
    side, direction = _pick_side(match, signal)
    q = str(matchup.get("quality") or "N/D").upper()

    out = {
        "schema": "pi85-ml1",
        "pick_side": side,
        "pi_quality": q,
        "pi_quality_rank": _quality_rank(q),
        "best_of": _num(matchup.get("best_of"), _num(match.get("best_of"), 0.0)),
    }
    present = total = 0
    for prefix, profile in (("p1", p1), ("p2", p2)):
        for name in PROFILE_INDEXES:
            total += 1
            value = _idx(profile, name)
            if value is not None:
                present += 1
            out[f"{prefix}_{name}"] = value
        for name in PROFILE_METRICS:
            total += 1
            value = _metric(profile, name)
            if value is not None:
                present += 1
            out[f"{prefix}_{name}"] = value
        out[f"{prefix}_sample_matches"] = _num(profile.get("sample_matches"), 0.0)
        out[f"{prefix}_l5_n"] = _sample(profile, 5)
        out[f"{prefix}_l10_n"] = _sample(profile, 10)
        out[f"{prefix}_l20_n"] = _sample(profile, 20)
        out[f"{prefix}_coverage"] = _num(profile.get("coverage"))
        out[f"{prefix}_fallback_used"] = 1.0 if profile.get("fallback_used") else 0.0

    edge_map = {
        "overall": "edge_p1",
        "serve": "serve_edge_p1",
        "return": "return_edge_p1",
        "form": "form_edge_p1",
    }
    for short, source in edge_map.items():
        value = _num(matchup.get(source))
        out[f"{short}_edge_p1"] = value
        out[f"{short}_edge_abs"] = abs(value) if value is not None else None
        out[f"{short}_edge_for_pick"] = value * direction if value is not None and direction else 0.0

    out["feature_coverage"] = round(present / total, 4) if total else 0.0
    return out


def _signal_scores(auto_signal: dict) -> dict:
    scores = auto_signal.get("model_scores") or {}
    def score(name):
        return _num(scores.get(name), _num(auto_signal.get(name)))
    prod = auto_signal.get("adaptive_prod_v79") or {}
    return {
        "current_score": score("current"),
        "catboost_score": score("catboost"),
        "tabpfn_score": score("tabpfn"),
        "ensemble_score": score("ensemble"),
        "adaptive_prod_score": _num(prod.get("final_score"), _num(auto_signal.get("adaptive_prod"))),
    }


def _row(entry: dict, pi_signal: dict, auto_signal: dict, target=None) -> dict | None:
    pp = _num(pi_signal.get("player_probability"))
    ensemble_player = _num(pi_signal.get("shadow_score"))
    ensemble_base = _num(pi_signal.get("ensemble_base"))
    if pp is None or ensemble_base is None:
        return None

    snap = pi_signal.get("ml_features_v89") or {}
    scores = _signal_scores(auto_signal)
    market = _canonical_market(pi_signal.get("market") or auto_signal.get("market"))
    line = _num(pi_signal.get("line"), _num(auto_signal.get("line"), -1.0))
    checkpoint = _num(pi_signal.get("checkpoint"), _num(auto_signal.get("checkpoint"), -1.0))
    q = str(pi_signal.get("quality") or snap.get("pi_quality") or "N/D").upper()

    row = {
        "match_key": _match_key(entry),
        "scheduled_time": entry.get("scheduled_time"),
        "candidate_key": str(pi_signal.get("key") or auto_signal.get("key") or ""),
        "target": target,
        "market": market,
        "pick_kind": _pick_kind(pi_signal or auto_signal),
        "tour": str(entry.get("tour") or "N/D").upper(),
        "surface": str(entry.get("surface") or "N/D").upper(),
        "pi_quality": q,
        "pick_side": str(snap.get("pick_side") or "neutral"),
        "player_probability": pp,
        "ensemble_player_shadow": ensemble_player,
        "support_score": _num(pi_signal.get("support_score"), 0.0),
        "pi_vs_ensemble": pp - ensemble_base,
        "line": line,
        "checkpoint": checkpoint,
        "pi_quality_rank": _quality_rank(q),
        "feature_coverage": _num(snap.get("feature_coverage"), 0.0),
        "best_of": _num(snap.get("best_of"), 0.0),
        **scores,
    }
    if row["ensemble_score"] is None:
        row["ensemble_score"] = ensemble_base
    for name in PROFILE_NUMERIC_FEATURES + EDGE_NUMERIC_FEATURES:
        row[name] = _num(snap.get(name))
    return row


def freeze_feature_snapshots(history: list[dict], results: list[dict]) -> tuple[list[dict], int]:
    """Add PI feature vectors to already-frozen pending signals only.

    The Player Intelligence capture step already enforces the pre-match cutoff.
    We only enrich those frozen rows; we never generate a forecast after kickoff.
    """
    current = {_match_key(m): m for m in results or []}
    changed = 0
    out = []
    for e0 in history or []:
        e = dict(e0)
        rows = e.get("player_intelligence_signals_v85") or []
        if not rows:
            out.append(e)
            continue
        match = current.get(_match_key(e))
        if not match:
            out.append(e)
            continue
        current_by_key = {
            str(s.get("key")): s
            for s in ((match.get("autolearn_v84") or {}).get("signals") or [])
            if s.get("key")
        }
        enriched = []
        for p0 in rows:
            p = dict(p0)
            if not p.get("ml_features_v89"):
                sig = current_by_key.get(str(p.get("key")))
                if sig and (sig.get("player_intelligence_v85") or {}).get("probability") is not None:
                    p["ml_features_v89"] = feature_snapshot(match, sig)
                    p["ml_features_version"] = VERSION
                    changed += 1
            enriched.append(p)
        e["player_intelligence_signals_v85"] = enriched
        out.append(e)
    return out, changed


def backfill_historical_feature_snapshots(history: list[dict]) -> tuple[list[dict], int, int]:
    """Rebuild missing PI feature vectors using only information available before each match.

    build_profile() applies an as-of cutoff (< match date), so this is a leakage-safe
    historical reconstruction from the existing local player DB/cache. Once written
    into history the snapshot is reused on every later run.
    """
    needs = []
    for entry in history or []:
        rows = entry.get("player_intelligence_signals_v85") or []
        if any(
            isinstance(p, dict)
            and p.get("result") in ("hit", "miss")
            and not p.get("ml_features_v89")
            for p in rows
        ):
            needs.append(entry)
    if not needs:
        return history, 0, 0

    df = _load_pi_long_df()
    if df is None or getattr(df, "empty", True):
        return history, 0, len(needs)

    rebuilt = skipped = 0
    profile_cache = {}
    out = []
    for e0 in history or []:
        e = dict(e0)
        rows = e.get("player_intelligence_signals_v85") or []
        missing = [
            p for p in rows
            if isinstance(p, dict)
            and p.get("result") in ("hit", "miss")
            and not p.get("ml_features_v89")
        ]
        if not missing:
            out.append(e)
            continue

        scheduled = e.get("scheduled_time")
        p1_name, p2_name = str(e.get("p1") or ""), str(e.get("p2") or "")
        surface = _pi_surface(e.get("surface"))
        if not scheduled or not p1_name or not p2_name:
            skipped += 1
            out.append(e)
            continue

        sides = {}
        try:
            for side, name in (("p1", p1_name), ("p2", p2_name)):
                ck = (_norm(name), surface, str(scheduled)[:10])
                profile = profile_cache.get(ck)
                if profile is None:
                    early = (((e.get("early_hold_v7") or {}).get(side) or {}).get("ehs"))
                    profile = _build_pi_profile(df, name, surface, scheduled, early)
                    profile_cache[ck] = profile
                sides[side] = profile
            matchup = _pi_matchup_summary(sides["p1"], sides["p2"], e.get("best_of"))
            reconstructed_match = {
                "p1": p1_name,
                "p2": p2_name,
                "surface": surface,
                "best_of": e.get("best_of"),
                "player_intelligence_v85": {
                    "version": "v8.5",
                    "mode": "HISTORICAL_RECONSTRUCTION",
                    "profiles": sides,
                    "matchup": matchup,
                },
            }
            enriched = []
            for p0 in rows:
                p = dict(p0)
                if p.get("result") in ("hit", "miss") and not p.get("ml_features_v89"):
                    signal = {
                        "key": p.get("key"),
                        "market": p.get("market"),
                        "pick": p.get("pick"),
                        "line": p.get("line"),
                        "checkpoint": p.get("checkpoint"),
                    }
                    p["ml_features_v89"] = feature_snapshot(reconstructed_match, signal)
                    p["ml_features_version"] = VERSION
                    p["ml_features_origin"] = "historical_asof_rebuild"
                    rebuilt += 1
                enriched.append(p)
            e["player_intelligence_signals_v85"] = enriched
        except Exception:
            skipped += 1
        out.append(e)
    return out, rebuilt, skipped


def build_training_rows(history: list[dict]) -> list[dict]:
    rows = []
    seen = set()
    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        auto = {
            str(s.get("key")): s
            for s in (entry.get("autolearn_signals_v84") or [])
            if isinstance(s, dict) and s.get("key")
        }
        for p in entry.get("player_intelligence_signals_v85") or []:
            if not isinstance(p, dict) or p.get("result") not in ("hit", "miss"):
                continue
            key = str(p.get("key") or "")
            sig = auto.get(key) or {}
            row = _row(entry, p, sig, 1 if p.get("result") == "hit" else 0)
            if not row:
                continue
            dedupe = (row["match_key"], row["candidate_key"], row["target"])
            if dedupe in seen:
                continue
            seen.add(dedupe)
            rows.append(row)
    rows.sort(key=lambda r: (str(r.get("scheduled_time") or ""), r["match_key"], r["candidate_key"]))
    return rows


def split_by_match(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    grouped = defaultdict(list)
    times = {}
    for row in rows:
        grouped[row["match_key"]].append(row)
        times[row["match_key"]] = str(row.get("scheduled_time") or "")
    keys = sorted(grouped, key=lambda k: (times.get(k, ""), k))
    if len(keys) < 2:
        return rows, []
    cut = max(1, int(len(keys) * 0.80))
    if cut >= len(keys):
        cut = len(keys) - 1
    train_keys = set(keys[:cut])
    holdout_keys = set(keys[cut:])
    return (
        [r for r in rows if r["match_key"] in train_keys],
        [r for r in rows if r["match_key"] in holdout_keys],
    )


def _frame(rows: list[dict]):
    import pandas as pd
    data = []
    for r in rows:
        x = {}
        for name in NUMERIC_FEATURES:
            value = _num(r.get(name))
            x[name] = float("nan") if value is None else value
        for name in CATEGORICAL_FEATURES:
            x[name] = str(r.get(name) or "N/D")
        data.append(x)
    return pd.DataFrame(data, columns=FEATURE_COLUMNS)


def _fit(rows: list[dict]):
    from catboost import CatBoostClassifier

    if not rows:
        return None
    y = [int(r["target"]) for r in rows]
    if len(set(y)) < 2:
        return None
    X = _frame(rows)
    cat_idx = [FEATURE_COLUMNS.index(c) for c in CATEGORICAL_FEATURES]
    model = CatBoostClassifier(
        iterations=240,
        depth=5,
        learning_rate=0.04,
        loss_function="Logloss",
        eval_metric="Logloss",
        random_seed=89,
        l2_leaf_reg=6.0,
        random_strength=0.5,
        verbose=False,
        allow_writing_files=False,
        thread_count=2,
    )
    model.fit(X, y, cat_features=cat_idx, verbose=False)
    return model


def _predict(model, rows: list[dict]) -> list[float]:
    if model is None or not rows:
        return []
    X = _frame(rows)
    return [float(x[1]) for x in model.predict_proba(X)]


def _brier(y, p):
    if not y or len(y) != len(p):
        return None
    return sum((float(pi) - float(yi)) ** 2 for yi, pi in zip(y, p)) / len(y)


def _logloss(y, p):
    if not y or len(y) != len(p):
        return None
    total = 0.0
    for yi, pi in zip(y, p):
        pi = max(1e-6, min(1 - 1e-6, float(pi)))
        total += -(yi * math.log(pi) + (1 - yi) * math.log(1 - pi))
    return total / len(y)


def metrics(rows: list[dict], probs: list[float]) -> dict:
    if not rows or len(rows) != len(probs):
        return {"n": 0, "selected_n": 0, "accuracy": None, "brier": None, "log_loss": None}
    y = [int(r["target"]) for r in rows]
    selected = [(yy, pp) for yy, pp in zip(y, probs) if pp >= SELECT_THRESHOLD]
    return {
        "n": len(rows),
        "selected_n": len(selected),
        "accuracy": round(100 * sum(y for y, _ in selected) / len(selected), 1) if selected else None,
        "brier": round(_brier(y, probs), 5),
        "log_loss": round(_logloss(y, probs), 5),
        "avg_probability": round(100 * mean(probs), 1) if probs else None,
    }


def _field_probs(rows: list[dict], field: str) -> tuple[list[dict], list[float]]:
    usable, probs = [], []
    for row in rows:
        p = _prob(row.get(field))
        if p is None:
            continue
        usable.append(row)
        probs.append(p)
    return usable, probs


def _baseline_metrics(rows: list[dict]) -> dict:
    out = {}
    for label, field in (
        ("catboost", "catboost_score"),
        ("ensemble", "ensemble_score"),
        ("ensemble_player_formula", "ensemble_player_shadow"),
        ("player_formula", "player_probability"),
    ):
        usable, probs = _field_probs(rows, field)
        out[label] = metrics(usable, probs)
    return out


def _candidate_gate(candidate: dict, baselines: dict, holdout_matches: int) -> dict:
    base_choices = [
        (name, row)
        for name, row in baselines.items()
        if row.get("n", 0) >= max(10, int(candidate.get("n", 0) * 0.7))
        and row.get("brier") is not None
    ]
    if candidate.get("n", 0) < 30 or holdout_matches < 8 or not base_choices:
        return {
            "status": "collecting",
            "production_influence": False,
            "auto_promotion": False,
            "reason": "need_more_holdout_data",
        }

    base_name, base = min(base_choices, key=lambda x: x[1]["brier"])
    cb, bb = candidate.get("brier"), base.get("brier")
    cl, bl = candidate.get("log_loss"), base.get("log_loss")
    ca, ba = candidate.get("accuracy"), base.get("accuracy")
    brier_gain = None if cb is None or bb is None else bb - cb
    loss_gain = None if cl is None or bl is None else bl - cl
    accuracy_delta = None if ca is None or ba is None else ca - ba

    promising = (
        brier_gain is not None and brier_gain >= 0.002
        and loss_gain is not None and loss_gain >= 0
        and (accuracy_delta is None or accuracy_delta >= -1.0)
    )
    strong = promising and brier_gain >= 0.005 and (accuracy_delta is None or accuracy_delta >= 0)
    return {
        "status": "strong_candidate" if strong else ("promising" if promising else "watch"),
        "production_influence": False,
        "auto_promotion": False,
        "comparison_baseline": base_name,
        "brier_gain": round(brier_gain, 5) if brier_gain is not None else None,
        "log_loss_gain": round(loss_gain, 5) if loss_gain is not None else None,
        "accuracy_delta_pp": round(accuracy_delta, 1) if accuracy_delta is not None else None,
        "reason": "shadow_only_manual_gate",
    }


def _segments(rows: list[dict], probs: list[float], field: str) -> dict:
    grouped = defaultdict(lambda: ([], []))
    for row, prob in zip(rows, probs):
        key = str(row.get(field) or "N/D")
        grouped[key][0].append(row)
        grouped[key][1].append(prob)
    return {
        key: metrics(rr, pp)
        for key, (rr, pp) in grouped.items()
        if len(rr) >= 10
    }


def _current_row(match: dict, signal: dict) -> dict | None:
    pi_signal = signal.get("player_intelligence_v85") or {}
    if _num(pi_signal.get("probability")) is None:
        return None
    pseudo = {
        "match_id": match.get("match_id"),
        "id": match.get("id"),
        "p1": match.get("p1"),
        "p2": match.get("p2"),
        "scheduled_time": match.get("scheduled_time"),
        "tournament": match.get("tournament"),
        "tour": match.get("tour"),
        "surface": match.get("surface"),
    }
    p = {
        "key": signal.get("key"),
        "market": signal.get("market"),
        "pick": signal.get("pick"),
        "line": signal.get("line"),
        "checkpoint": signal.get("checkpoint"),
        "player_probability": pi_signal.get("probability"),
        "ensemble_base": pi_signal.get("ensemble_base"),
        "shadow_score": pi_signal.get("shadow_score"),
        "support_score": pi_signal.get("support_score"),
        "quality": pi_signal.get("quality"),
        "ml_features_v89": feature_snapshot(match, signal),
    }
    return _row(pseudo, p, signal, target=None)


def decorate_current(results: list[dict], model, model_status: str) -> tuple[list[dict], int]:
    if model is None:
        return results, 0
    out = []
    scored = 0
    for m0 in results or []:
        m = dict(m0)
        auto = dict(m.get("autolearn_v84") or {})
        signals = [dict(s) for s in (auto.get("signals") or [])]
        rows, positions = [], []
        for idx, signal in enumerate(signals):
            row = _current_row(m, signal)
            if row:
                rows.append(row)
                positions.append(idx)
        probs = _predict(model, rows)
        for idx, row, prob in zip(positions, rows, probs):
            signal = signals[idx]
            ensemble = _prob(row.get("ensemble_score"))
            cat = _prob(row.get("catboost_score"))
            signal["player_model_shadow_v89"] = {
                "version": VERSION,
                "mode": MODE,
                "score": round(prob * 100, 1),
                "ensemble_delta_pp": round((prob - ensemble) * 100, 1) if ensemble is not None else None,
                "catboost_delta_pp": round((prob - cat) * 100, 1) if cat is not None else None,
                "feature_coverage": row.get("feature_coverage"),
                "quality": row.get("pi_quality"),
                "model_status": model_status,
                "production_influence": False,
            }
            signal["player_model_features_v89"] = feature_snapshot(m, signal)
            scored += 1
        auto["signals"] = signals
        auto["by_key"] = {str(s.get("key")): s for s in signals if s.get("key")}
        m["autolearn_v84"] = auto
        if positions:
            m["player_model_shadow_v89"] = {
                "version": VERSION,
                "mode": MODE,
                "scored_signals": len(positions),
                "production_influence": False,
            }
        out.append(m)
    return out, scored


def run(now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    results = _read(RESULTS_PATH, [])
    history = _read(HISTORY_PATH, [])
    telemetry = _read(TELEMETRY_PATH, {})
    meta = _read(META_PATH, {})
    if not isinstance(results, list):
        results = []
    if not isinstance(history, list):
        history = []
    if not isinstance(telemetry, dict):
        telemetry = {}
    if not isinstance(meta, dict):
        meta = {}

    history, frozen_features = freeze_feature_snapshots(history, results)
    history, historical_features, historical_backfill_skipped = backfill_historical_feature_snapshots(history)
    rows = build_training_rows(history)
    train, holdout = split_by_match(rows)
    train_matches = len({r["match_key"] for r in train})
    holdout_matches = len({r["match_key"] for r in holdout})

    enough = (
        len(train) >= MIN_TRAIN_ROWS
        and train_matches >= MIN_TRAIN_MATCHES
        and len(holdout) >= MIN_HOLDOUT_ROWS
        and holdout_matches >= MIN_HOLDOUT_MATCHES
        and len({r["target"] for r in train}) >= 2
    )

    candidate_metrics = {"n": 0, "selected_n": 0, "accuracy": None, "brier": None, "log_loss": None}
    baselines = _baseline_metrics(holdout)
    segments = {"surface": {}, "market": {}}
    gate = {
        "status": "collecting",
        "production_influence": False,
        "auto_promotion": False,
        "reason": "minimum_training_sample_not_reached",
    }
    current_scored = 0
    model_status = "collecting"

    if enough:
        eval_model = _fit(train)
        holdout_probs = _predict(eval_model, holdout)
        if holdout_probs:
            candidate_metrics = metrics(holdout, holdout_probs)
            segments = {
                "surface": _segments(holdout, holdout_probs, "surface"),
                "market": _segments(holdout, holdout_probs, "market"),
            }
            gate = _candidate_gate(candidate_metrics, baselines, holdout_matches)
            model_status = gate.get("status") or "shadow"
            full_model = _fit(rows)
            results, current_scored = decorate_current(results, full_model, model_status)

    feature_rows = sum(1 for r in rows if _num(r.get("feature_coverage"), 0) > 0)
    report = {
        "version": VERSION,
        "generated_at": now.isoformat(),
        "mode": MODE,
        "status": "ACTIVE_SHADOW" if enough else "COLLECTING",
        "production_influence": False,
        "auto_promotion": False,
        "training": {
            "rows_total": len(rows),
            "matches_total": len({r["match_key"] for r in rows}),
            "train_rows": len(train),
            "train_matches": train_matches,
            "holdout_rows": len(holdout),
            "holdout_matches": holdout_matches,
            "rows_with_granular_pi_features": feature_rows,
            "granular_feature_share": round(feature_rows / len(rows), 4) if rows else 0.0,
            "chronological_match_split": "80/20",
        },
        "features": {
            "numeric_n": len(NUMERIC_FEATURES),
            "categorical_n": len(CATEGORICAL_FEATURES),
            "player_indexes": list(PROFILE_INDEXES),
            "player_metrics": list(PROFILE_METRICS),
            "uses_current_catboost_tabpfn_ensemble": True,
            "uses_player_probability": True,
            "uses_granular_player_profiles": True,
            "leakage_policy": "pre_match_frozen_features_only",
        },
        "holdout": {
            "player_catboost_shadow": candidate_metrics,
            "baselines": baselines,
            "segments": segments,
        },
        "gate": gate,
        "current_scored_signals": current_scored,
        "frozen_feature_snapshots_added": frozen_features,
        "historical_feature_snapshots_added": historical_features,
        "historical_backfill_matches_skipped": historical_backfill_skipped,
        "note": (
            "CatBoost + Player Intelligence działa wyłącznie w SHADOW. "
            "Nie zmienia Ensemble, Generatora, Adaptive PROD ani final_score. "
            "Wpływ produkcyjny wymaga osobnego gate po wiarygodnym holdoucie."
        ),
    }

    telemetry["player_model_shadow_v89"] = report
    meta.update({
        "player_model_shadow_v89_version": VERSION,
        "player_model_shadow_v89_mode": MODE,
        "player_model_shadow_v89_status": report["status"],
        "player_model_shadow_v89_training_rows": len(rows),
        "player_model_shadow_v89_holdout_rows": len(holdout),
        "player_model_shadow_v89_current_scored": current_scored,
        "player_model_shadow_v89_production_influence": False,
        "player_model_shadow_v89_updated_at": now.isoformat(),
    })

    _write(HISTORY_PATH, history)
    _write(RESULTS_PATH, results)
    _write(REPORT_PATH, report)
    _write(TELEMETRY_PATH, telemetry)
    _write(META_PATH, meta)
    return {
        "status": report["status"],
        "training_rows": len(rows),
        "holdout_rows": len(holdout),
        "current_scored": current_scored,
        "frozen_features": frozen_features,
        "historical_features": historical_features,
        "historical_backfill_skipped": historical_backfill_skipped,
        "gate": gate.get("status"),
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
