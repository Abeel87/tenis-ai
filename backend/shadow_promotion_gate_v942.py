from __future__ import annotations

"""Evidence gate for promoting SHADOW models.

This module is intentionally diagnostic.  It never changes model weights,
PLAYABLE thresholds, Symphony, or production outputs.  It evaluates every
settled SHADOW model on frozen operator-verified history, then performs a deeper
same-universe selection audit for the strongest eligible candidate.
"""

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
HISTORY = OUT / "history.json"
PLAYABLE_STATS = OUT / "superbet_playable_stats_v912.json"
SURFACE_ELO = OUT / "surface_elo_integration_v893.json"
REPORT = OUT / "shadow_promotion_gate_v942.json"

VERSION = "v9.4.2-shadow-promotion-gate"
THRESHOLD = 68.0
CANDIDATE = "ensemble_player_elo"
BASELINES = ("ensemble", "adaptive_prod")


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
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


def _event_id(row: dict) -> str:
    return str(row.get("id") or row.get("key") or "")


def _metrics(rows: list[dict], score_key: str = "score", threshold: float | None = None) -> dict:
    usable = []
    for row in rows:
        if row.get("result") not in {"hit", "miss"}:
            continue
        score = _num(row.get(score_key))
        if score is None or (threshold is not None and score < threshold):
            continue
        usable.append((score, 1.0 if row["result"] == "hit" else 0.0))
    if not usable:
        return {"n": 0, "hits": 0, "accuracy": None, "brier": None, "log_loss": None}
    hits = int(sum(y for _, y in usable))
    brier = 0.0
    log_loss = 0.0
    for score, y in usable:
        p = min(1.0 - 1e-6, max(1e-6, score / 100.0))
        brier += (p - y) ** 2
        log_loss += -(y * math.log(p) + (1.0 - y) * math.log(1.0 - p))
    n = len(usable)
    return {
        "n": n,
        "hits": hits,
        "misses": n - hits,
        "accuracy": round(100.0 * hits / n, 2),
        "brier": round(brier / n, 5),
        "log_loss": round(log_loss / n, 5),
    }


def _shadow_leaderboard(history: list[dict]) -> dict[str, dict]:
    rows_by_model: dict[str, list[dict]] = defaultdict(list)
    for entry in history:
        if not isinstance(entry, dict):
            continue
        for row in entry.get("playable_shadow_models_v912") or []:
            if not isinstance(row, dict) or row.get("result") not in {"hit", "miss"}:
                continue
            model = str(row.get("source_model") or "").strip()
            if model:
                rows_by_model[model].append(row)
    out = {}
    for model, rows in sorted(rows_by_model.items()):
        selected = _metrics(rows, threshold=THRESHOLD)
        all_captured = _metrics(rows)
        out[model] = {
            "captured_settled": all_captured["n"],
            "selected_threshold": THRESHOLD,
            "selected": selected,
        }
    return out


def _baseline_score(row: dict, model: str):
    if model == "adaptive_prod":
        adaptive = row.get("adaptive_prod_v79") or {}
        return _num(adaptive.get("final_score")) if isinstance(adaptive, dict) else None
    return _num((row.get("model_scores") or {}).get(model))


def _candidate_common_events(history: list[dict], candidate: str = CANDIDATE) -> list[dict]:
    common = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        auto = {}
        for row in entry.get("playable_autolearn_signals_v912") or []:
            if isinstance(row, dict) and row.get("result") in {"hit", "miss"}:
                rid = _event_id(row)
                if rid:
                    auto[rid] = row
        shadow = {}
        for row in entry.get("playable_shadow_models_v912") or []:
            if not isinstance(row, dict) or str(row.get("source_model") or "") != candidate:
                continue
            if row.get("result") not in {"hit", "miss"}:
                continue
            rid = _event_id(row)
            if rid:
                shadow[rid] = row
        for rid in sorted(set(auto) & set(shadow)):
            a, s = auto[rid], shadow[rid]
            if a.get("result") != s.get("result"):
                continue
            candidate_score = _num(s.get("score"))
            if candidate_score is None:
                continue
            row = {
                "id": rid,
                "result": s.get("result"),
                "candidate": candidate_score,
                "market": s.get("market") or a.get("market"),
            }
            for baseline in BASELINES:
                row[baseline] = _baseline_score(a, baseline)
            common.append(row)
    return common


def _selection_delta(common: list[dict], baseline: str) -> dict:
    usable = [r for r in common if _num(r.get(baseline)) is not None]
    candidate_rows = [{"result": r["result"], "score": r["candidate"]} for r in usable]
    baseline_rows = [{"result": r["result"], "score": r[baseline]} for r in usable]
    candidate_selected = _metrics(candidate_rows, threshold=THRESHOLD)
    baseline_selected = _metrics(baseline_rows, threshold=THRESHOLD)
    candidate_cal = _metrics(candidate_rows)
    baseline_cal = _metrics(baseline_rows)

    both, candidate_only, baseline_only, neither = [], [], [], []
    for r in usable:
        c = float(r["candidate"]) >= THRESHOLD
        b = float(r[baseline]) >= THRESHOLD
        target = both if c and b else candidate_only if c else baseline_only if b else neither
        target.append({"result": r["result"], "score": r["candidate"] if c else r[baseline]})

    return {
        "common_settled": len(usable),
        "candidate_selected": candidate_selected,
        "baseline_selected": baseline_selected,
        "candidate_calibration_common": candidate_cal,
        "baseline_calibration_common": baseline_cal,
        "accuracy_delta_pp": (
            round(candidate_selected["accuracy"] - baseline_selected["accuracy"], 2)
            if candidate_selected["accuracy"] is not None and baseline_selected["accuracy"] is not None else None
        ),
        "brier_gain_common": (
            round(baseline_cal["brier"] - candidate_cal["brier"], 5)
            if baseline_cal["brier"] is not None and candidate_cal["brier"] is not None else None
        ),
        "log_loss_gain_common": (
            round(baseline_cal["log_loss"] - candidate_cal["log_loss"], 5)
            if baseline_cal["log_loss"] is not None and candidate_cal["log_loss"] is not None else None
        ),
        "selection_sets": {
            "both": _metrics(both),
            "candidate_only": _metrics(candidate_only),
            "baseline_only": _metrics(baseline_only),
            "neither": {"n": len(neither)},
        },
    }


def build_report(history: list[dict], playable_stats: dict, surface_elo: dict) -> dict:
    leaderboard = _shadow_leaderboard(history)
    common = _candidate_common_events(history)
    comparisons = {baseline: _selection_delta(common, baseline) for baseline in BASELINES}

    operator_model = ((playable_stats.get("models") or {}).get(f"shadow_{CANDIDATE}") or {})
    holdout = ((surface_elo.get("holdout") or {}).get(CANDIDATE) or {})
    holdout_gate = ((surface_elo.get("gates") or {}).get(CANDIDATE) or {})
    ensemble_cmp = comparisons.get("ensemble") or {}
    candidate_only = ((ensemble_cmp.get("selection_sets") or {}).get("candidate_only") or {})

    checks = {
        "operator_settled_ge_300": int(operator_model.get("settled") or 0) >= 300,
        "operator_accuracy_ge_80": (_num(operator_model.get("accuracy"), 0.0) or 0.0) >= 80.0,
        "chronological_holdout_ge_150": int(holdout.get("n") or 0) >= 150,
        "holdout_gate_promising": str(holdout_gate.get("status") or "").lower() == "promising",
        "holdout_accuracy_gain_ge_1pp": (_num(holdout_gate.get("accuracy_delta_pp"), -999.0) or -999.0) >= 1.0,
        "holdout_brier_gain_positive": (_num(holdout_gate.get("brier_gain"), -999.0) or -999.0) > 0.0,
        "holdout_log_loss_gain_positive": (_num(holdout_gate.get("log_loss_gain"), -999.0) or -999.0) > 0.0,
        "same_universe_common_ge_250": int(ensemble_cmp.get("common_settled") or 0) >= 250,
        "same_universe_brier_not_worse": (_num(ensemble_cmp.get("brier_gain_common"), -999.0) or -999.0) >= 0.0,
        "same_universe_log_loss_not_worse": (_num(ensemble_cmp.get("log_loss_gain_common"), -999.0) or -999.0) >= 0.0,
        "candidate_only_sample_ge_40": int(candidate_only.get("n") or 0) >= 40,
        "candidate_only_accuracy_ge_75": (_num(candidate_only.get("accuracy"), 0.0) or 0.0) >= 75.0,
    }
    ready = all(checks.values())
    return {
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "SHADOW_PROMOTION_AUDIT",
        "candidate": CANDIDATE,
        "threshold": THRESHOLD,
        "status": "CANARY_READY" if ready else "WATCH",
        "production_influence": False,
        "playable_influence": False,
        "symphony_prod_influence": False,
        "auto_promote": False,
        "leaderboard": leaderboard,
        "operator_verified_candidate": operator_model,
        "chronological_holdout": holdout,
        "existing_holdout_gate": holdout_gate,
        "same_universe_comparisons": comparisons,
        "promotion_checks": checks,
        "next_step": "BOUNDED_CANARY_REVIEW" if ready else "KEEP_SHADOW_AND_COLLECT",
        "note": "CANARY_READY is evidence only; this report never changes production weights or thresholds.",
    }


def main() -> None:
    history = _read(HISTORY, [])
    playable_stats = _read(PLAYABLE_STATS, {})
    surface_elo = _read(SURFACE_ELO, {})
    if not isinstance(history, list):
        raise SystemExit("STOP: history.json is not a list")
    report = build_report(history, playable_stats if isinstance(playable_stats, dict) else {}, surface_elo if isinstance(surface_elo, dict) else {})
    _write(REPORT, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
