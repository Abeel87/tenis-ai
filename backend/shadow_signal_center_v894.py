from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from .player_intelligence_v85 import _load_long_df
    from .player_model_shadow_v89 import build_training_rows, _current_row, _match_key, _num, _prob
    from .ensemble_player_learning_v891 import learn_policy
    from .surface_elo_integration_v893 import (
        EloIndex,
        _elo_features,
        _enrich,
        _fit_elo_cat,
        _predict,
        _ensemble_prob,
        _fuse,
    )
except ImportError:
    from player_intelligence_v85 import _load_long_df
    from player_model_shadow_v89 import build_training_rows, _current_row, _match_key, _num, _prob
    from ensemble_player_learning_v891 import learn_policy
    from surface_elo_integration_v893 import (
        EloIndex,
        _elo_features,
        _enrich,
        _fit_elo_cat,
        _predict,
        _ensemble_prob,
        _fuse,
    )

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
RESULTS = OUT / "results.json"
HISTORY = OUT / "history.json"
PLAYER_REPORT = OUT / "player_model_shadow_v89.json"
LEARNING_REPORT = OUT / "ensemble_player_learning_v891.json"
ELO_REPORT = OUT / "surface_elo_integration_v893.json"
REPORT = OUT / "shadow_signals_v894.json"
META = OUT / "meta.json"

VERSION = "v8.9.4"
MODE = "SHADOW"

MODEL_META = {
    "player_intelligence": {"label": "Player Intelligence", "icon": "🧬", "version": "v8.5"},
    "catboost_player": {"label": "CatBoost + Player", "icon": "🐱🧬", "version": "v8.9"},
    "ensemble_player": {"label": "Ensemble + Player Learning", "icon": "🧠🧬", "version": "v8.9.1"},
    "catboost_player_elo": {"label": "CatBoost + Player + Surface Elo", "icon": "🐱🏟️", "version": "v8.9.3"},
    "ensemble_player_elo": {"label": "Ensemble + Player + Surface Elo", "icon": "🧠🏟️", "version": "v8.9.3"},
    "tabpfn_elo": {"label": "TabPFN + Surface Elo", "icon": "🧩🏟️", "version": "v8.9.3"},
}


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


def _score(value):
    x = _num(value)
    if x is None:
        return None
    if 0 <= x <= 1:
        x *= 100.0
    return round(max(0.0, min(100.0, x)), 1)


def _line(signal: dict):
    direct = _num(signal.get("line"), _num(signal.get("selected_line"), _num(signal.get("suggested_line"))))
    if direct is not None:
        return direct
    parts = str(signal.get("key") or "").split("|")
    return _num(parts[1]) if len(parts) > 1 else None


def _market(value: str) -> str:
    x = str(value or "").lower()
    return {
        "match_win": "match_winner",
        "set1_win": "set1_winner",
        "set2_win": "set2_winner",
        "set3_win": "set3_winner",
    }.get(x, x or "other")


def _signal_label(match: dict, signal: dict) -> str:
    market = _market(signal.get("market"))
    pick = str(signal.get("pick") or "").strip()
    line = _line(signal)
    checkpoint = _num(signal.get("checkpoint"))

    if market == "match_winner":
        return f"Wygra mecz · {pick}" if pick else "Wygra mecz"
    if market == "set1_winner":
        return f"Wygra 1. set · {pick}" if pick else "Wygra 1. set"
    if market == "set2_winner":
        return f"Wygra 2. set · {pick}" if pick else "Wygra 2. set"
    if market == "set3_winner":
        return f"Wygra 3. set · {pick}" if pick else "Wygra 3. set"
    if market == "set1_total" and line is not None:
        return f"1. set · {pick.upper()} {line:g} gema"
    if market == "match_total" and line is not None:
        return f"Mecz · {pick.upper()} {line:g} gema"
    if market == "game_state":
        suffix = f" po {int(checkpoint)} gemach" if checkpoint is not None else ""
        return f"Stan{suffix} · {pick}" if pick else f"Stan{suffix}"
    raw = str(signal.get("label") or signal.get("key") or market or "Sygnał").strip()
    return raw or "Sygnał"


def _gate_status(report: dict, key: str | None = None, default="shadow") -> str:
    if key:
        return str(((report.get("gates") or {}).get(key) or {}).get("status") or default)
    return str((report.get("gate") or {}).get("status") or default)


def _model_list(player_report: dict, learning_report: dict, elo_report: dict) -> list[dict]:
    statuses = {
        "player_intelligence": "shadow",
        "catboost_player": _gate_status(player_report),
        "ensemble_player": _gate_status(learning_report),
        "catboost_player_elo": _gate_status(elo_report, "catboost_player_elo", "collecting"),
        "ensemble_player_elo": _gate_status(elo_report, "ensemble_player_elo", "collecting"),
        "tabpfn_elo": _gate_status(elo_report, "tabpfn_elo", "collecting"),
    }
    return [
        {
            "id": model_id,
            **meta,
            "status": statuses[model_id],
            "production_influence": False,
        }
        for model_id, meta in MODEL_META.items()
    ]


def _current_scores(match: dict, signal: dict, index: EloIndex, elo_model, policy: dict, ensemble_alpha: float, tab_alpha: float):
    pi = signal.get("player_intelligence_v85") or {}
    player_score = _score(pi.get("probability"))
    cat_player = _score((signal.get("player_model_shadow_v89") or {}).get("score"))
    ensemble_player = _score((signal.get("ensemble_player_learning_v891") or {}).get("score"))

    row = _current_row(match, signal)
    elo = None
    cat_elo = ens_elo = tab_elo = None
    if row is not None:
        snap = index.match(match.get("p1"), match.get("p2"), match.get("surface"), match.get("scheduled_time"))
        elo = _elo_features(snap, row.get("pick_side"))
        row = {**row, **elo}

        if elo_model is not None:
            probs = _predict(elo_model, [row])
            if probs:
                cat_elo = _score(probs[0])

        base_ens = _prob(ensemble_player)
        if base_ens is None:
            base_ens = _ensemble_prob(row, policy)
        ens_elo = _score(_fuse(row, base_ens, ensemble_alpha)) if base_ens is not None else None

        base_tab = _prob(row.get("tabpfn_score"))
        tab_elo = _score(_fuse(row, base_tab, tab_alpha)) if base_tab is not None else None

    scores = {
        "player_intelligence": player_score,
        "catboost_player": cat_player,
        "ensemble_player": ensemble_player,
        "catboost_player_elo": cat_elo,
        "ensemble_player_elo": ens_elo,
        "tabpfn_elo": tab_elo,
    }
    scores = {k: v for k, v in scores.items() if v is not None}
    return scores, elo


def build_feed(now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    results = _read(RESULTS, [])
    history = _read(HISTORY, [])
    player_report = _read(PLAYER_REPORT, {})
    learning_report = _read(LEARNING_REPORT, {})
    elo_report = _read(ELO_REPORT, {})

    if not isinstance(results, list):
        results = []
    if not isinstance(history, list):
        history = []

    index = EloIndex(_load_long_df())
    history_map = {_match_key(e): e for e in history if isinstance(e, dict)}
    training_rows = _enrich(build_training_rows(history), history_map, index)
    enough = len(training_rows) >= 100 and index.stats().get("events", 0) > 0
    elo_model = _fit_elo_cat(training_rows) if enough else None
    policy = learn_policy(training_rows) if training_rows else learn_policy([])

    learned = elo_report.get("learned") or {}
    ensemble_alpha = max(0.0, min(0.35, _num(learned.get("ensemble_elo_alpha"), 0.0)))
    tab_alpha = max(0.0, min(0.35, _num(learned.get("tabpfn_elo_alpha"), 0.0)))

    model_counts = Counter()
    matches = []
    for match in results:
        if not isinstance(match, dict):
            continue
        signals = ((match.get("autolearn_v84") or {}).get("signals") or [])
        packed = []
        elo_summary = None
        for signal in signals:
            if not isinstance(signal, dict):
                continue
            scores, elo = _current_scores(match, signal, index, elo_model, policy, ensemble_alpha, tab_alpha)
            if not scores:
                continue
            for model_id in scores:
                model_counts[model_id] += 1
            if elo and elo_summary is None:
                elo_summary = {
                    "quality": elo.get("elo_quality"),
                    "confidence": round(float(elo.get("elo_confidence") or 0.0), 4),
                    "p1_general": round(float(elo.get("elo_p1_general") or 1500.0), 1),
                    "p2_general": round(float(elo.get("elo_p2_general") or 1500.0), 1),
                    "p1_surface": round(float(elo.get("elo_p1_surface") or 1500.0), 1),
                    "p2_surface": round(float(elo.get("elo_p2_surface") or 1500.0), 1),
                    "p1_surface_n": int(elo.get("elo_p1_surface_n") or 0),
                    "p2_surface_n": int(elo.get("elo_p2_surface_n") or 0),
                }
            packed.append({
                "key": str(signal.get("key") or ""),
                "label": _signal_label(match, signal),
                "market": _market(signal.get("market")),
                "pick": signal.get("pick"),
                "line": _line(signal),
                "checkpoint": _num(signal.get("checkpoint")),
                "scores": scores,
            })

        if not packed:
            continue
        matches.append({
            "id": match.get("id") if match.get("id") is not None else match.get("match_id"),
            "match_id": match.get("match_id"),
            "match_key": _match_key(match),
            "p1": match.get("p1"),
            "p2": match.get("p2"),
            "scheduled_time": match.get("scheduled_time"),
            "tour": match.get("tour"),
            "tournament": match.get("tournament"),
            "surface": match.get("surface"),
            "event_status": match.get("event_status") or match.get("feed_status") or match.get("status"),
            "quality": match.get("quality"),
            "elo": elo_summary,
            "signals": packed,
        })

    matches.sort(key=lambda m: str(m.get("scheduled_time") or ""))
    models = _model_list(player_report, learning_report, elo_report)
    report = {
        "version": VERSION,
        "generated_at": now.isoformat(),
        "mode": MODE,
        "status": "ACTIVE_SHADOW" if matches else "COLLECTING",
        "production_influence": False,
        "auto_promotion": False,
        "training_rows": len(training_rows),
        "elo_events": index.stats().get("events", 0),
        "models": models,
        "model_signal_counts": dict(model_counts),
        "matches_count": len(matches),
        "matches": matches,
        "note": "Centrum SHADOW służy wyłącznie do ręcznych testów modeli. Żaden wynik z tego pliku nie zmienia Adaptive PROD, Generatora ani final_score.",
    }
    return report


def run(now=None) -> dict:
    report = build_feed(now)
    _write(REPORT, report)
    meta = _read(META, {})
    if not isinstance(meta, dict):
        meta = {}
    meta.update({
        "shadow_signal_center_v894_version": VERSION,
        "shadow_signal_center_v894_status": report.get("status"),
        "shadow_signal_center_v894_matches": report.get("matches_count", 0),
        "shadow_signal_center_v894_production_influence": False,
        "shadow_signal_center_v894_updated_at": report.get("generated_at"),
    })
    _write(META, meta)
    return {
        "status": report.get("status"),
        "matches": report.get("matches_count", 0),
        "training_rows": report.get("training_rows", 0),
        "model_signal_counts": report.get("model_signal_counts", {}),
        "production_influence": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
