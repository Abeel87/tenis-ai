from __future__ import annotations

"""Leakage-safe current-card SHADOW scoring for Player DNA.

This stage does NOT predict match winner and does NOT influence PROD, Symfonia
or Superbet PLAYABLE. It fits the validated profile-only point model strictly on
history before the earliest current-card scheduled time, then estimates each
player's serve-point win probability using stable provider IDs and as-of profiles.
"""

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

try:
    from backend.player_dna_point_scorer import (
        CATEGORICAL,
        EVAL_MIN_PRIOR_MATCHES,
        PROFILE_NUMERIC,
        VERSION as SCORER_VERSION,
        _cohort,
        _fit_logistic_newton,
        _frame,
        _iter_jsonl_gz,
        _model_meta,
        _predict_logistic,
        build_feature_rows,
        evaluate,
    )
    from backend.player_dna_shadow_profiles import (
        build_current_target_profiles,
        iter_point_rows,
    )
except ModuleNotFoundError:  # direct execution
    from player_dna_point_scorer import (
        CATEGORICAL,
        EVAL_MIN_PRIOR_MATCHES,
        PROFILE_NUMERIC,
        VERSION as SCORER_VERSION,
        _cohort,
        _fit_logistic_newton,
        _frame,
        _iter_jsonl_gz,
        _model_meta,
        _predict_logistic,
        build_feature_rows,
        evaluate,
    )
    from player_dna_shadow_profiles import (
        build_current_target_profiles,
        iter_point_rows,
    )

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "frontend" / "data" / "results.json"
POINTS = ROOT / "data" / "derived" / "player_dna" / "point_events.jsonl.gz"
PROFILES = ROOT / "data" / "derived" / "player_dna" / "profile_snapshots.jsonl.gz"
MODEL_ARTIFACT = ROOT / "data" / "derived" / "player_dna" / "current_point_model_shadow.json"
OUT = ROOT / "frontend" / "data" / "player_dna_current_shadow.json"

VERSION = "player-dna-current-shadow-v1"
MODE = "SHADOW_CURRENT_ONLY"


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _provider_ranking(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _legacy_runtime_validation(validation: dict[str, Any]) -> tuple[str, bool, str | None]:
    """Keep current-card profile-only runtime gated by the legacy profile signal.

    Stateful context is evaluated separately and must not silently redefine the
    validation contract for the still-profile-only current scorer.
    """
    signal = validation.get("signal") if isinstance(validation, dict) else {}
    signal = signal if isinstance(signal, dict) else {}
    legacy_positive = signal.get("legacy_profile_signal_positive")
    if legacy_positive is None:
        legacy_positive = signal.get("status") == "POSITIVE_HOLDOUT_SIGNAL"
    status = "POSITIVE_HOLDOUT_SIGNAL" if legacy_positive is True else "MIXED_OR_NO_INCREMENTAL_SIGNAL"
    stateful_reference_status = signal.get("status")
    return status, bool(legacy_positive is True), stateful_reference_status


def _serialize_model(model: dict[str, Any], *, cutoff: datetime, training: pd.DataFrame) -> dict[str, Any]:
    meta = _model_meta(model)
    beta = np.asarray(model["beta"], dtype=float)
    return {
        "version": VERSION,
        "mode": "SHADOW_MODEL_ARTIFACT",
        "source_scorer_version": SCORER_VERSION,
        "feature_group": "profile_only",
        "production_influence": False,
        "prod_runtime_model": False,
        "shadow_current_scoring_only": True,
        "evaluation_support_gate": EVAL_MIN_PRIOR_MATCHES,
        "evaluation_support_gate_is_prod_gate": False,
        "training_cutoff_exclusive": cutoff.isoformat(),
        "training_points": int(len(training)),
        "training_matches": int(training["match_id"].astype(str).nunique()) if len(training) else 0,
        "feature_names": [str(v) for v in model["feature_names"]],
        "schema": model["schema"],
        "beta": [round(float(v), 12) for v in beta],
        "fit": meta,
    }


def _profile_map(current_profiles: Iterable[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    out = {}
    for row in current_profiles:
        if not isinstance(row, dict):
            continue
        match_id = str(row.get("target_match_id") or "").strip()
        player_id = row.get("player_id")
        if not match_id or isinstance(player_id, bool) or not isinstance(player_id, int):
            continue
        if row.get("strict_as_of") is not True or row.get("current_card_excluded_from_history") is not True:
            continue
        out[(match_id, player_id)] = row
    return out


def _serve_feature_row(
    target: dict[str, Any],
    server_profile: dict[str, Any],
    receiver_profile: dict[str, Any],
) -> dict[str, Any]:
    so = server_profile.get("overall_prior") if isinstance(server_profile.get("overall_prior"), dict) else {}
    ro = receiver_profile.get("overall_prior") if isinstance(receiver_profile.get("overall_prior"), dict) else {}
    ss = server_profile.get("same_surface_prior") if isinstance(server_profile.get("same_surface_prior"), dict) else {}
    rs = receiver_profile.get("same_surface_prior") if isinstance(receiver_profile.get("same_surface_prior"), dict) else {}
    best_of = target.get("best_of")
    return {
        "match_id": str(target.get("id")),
        "surface": str(target.get("surface") or "unknown").strip().lower(),
        "tour": str(target.get("tour") or "unknown").strip().upper(),
        "match_format": f"BO{int(best_of)}" if isinstance(best_of, int) and not isinstance(best_of, bool) else "unknown",
        "server_overall_serve_rate": so.get("serve_win_rate"),
        "receiver_overall_return_rate": ro.get("return_win_rate"),
        "server_surface_serve_rate": ss.get("serve_win_rate"),
        "receiver_surface_return_rate": rs.get("return_win_rate"),
        "server_overall_matches": int(so.get("matches") or 0),
        "receiver_overall_matches": int(ro.get("matches") or 0),
        "server_surface_matches": int(ss.get("matches") or 0),
        "receiver_surface_matches": int(rs.get("matches") or 0),
    }


def build_current_scores(
    point_rows: list[dict[str, Any]],
    historical_profile_rows: list[dict[str, Any]],
    current_results: list[dict[str, Any]],
    *,
    generated_at: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    generated_at = generated_at or datetime.now(timezone.utc)

    valid_targets = []
    stable_id_targets = 0
    for row in current_results:
        if not isinstance(row, dict):
            continue
        p1 = row.get("p1_id")
        p2 = row.get("p2_id")
        when = _parse_utc(row.get("scheduled_time"))
        if isinstance(p1, int) and not isinstance(p1, bool) and isinstance(p2, int) and not isinstance(p2, bool):
            stable_id_targets += 1
        if (
            row.get("id") is not None
            and isinstance(p1, int) and not isinstance(p1, bool)
            and isinstance(p2, int) and not isinstance(p2, bool)
            and p1 != p2 and when is not None
        ):
            valid_targets.append(row)

    rank_context_matches = sum(
        1
        for row in valid_targets
        if _provider_ranking(row.get("p1_rank")) is not None
        and _provider_ranking(row.get("p2_rank")) is not None
    )

    report: dict[str, Any] = {
        "version": VERSION,
        "mode": MODE,
        "generated_at": generated_at.isoformat(),
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "match_winner_probability_enabled": False,
        "point_serve_probability_only": True,
        "rank_features_used": False,
        "provider_rank_context_passthrough": True,
        "rank_context_source": "fixture.players.p1/p2.ranking",
        "rank_context_matches": rank_context_matches,
        "rank_context_coverage": (
            round(rank_context_matches / len(valid_targets), 6)
            if valid_targets else 0.0
        ),
        "stable_provider_identity_required": True,
        "evaluation_support_gate": EVAL_MIN_PRIOR_MATCHES,
        "evaluation_support_gate_is_prod_gate": False,
        "current_matches": len(current_results),
        "stable_id_matches": stable_id_targets,
        "valid_target_matches": len(valid_targets),
        "status": "BLOCKED_NO_VALID_TARGETS" if not valid_targets else "BUILDING",
        "matches": [],
    }
    if not valid_targets:
        return report, None

    target_times = [_parse_utc(row.get("scheduled_time")) for row in valid_targets]
    cutoff = min(t for t in target_times if t is not None)
    target_ids = {str(row.get("id")) for row in valid_targets}

    historical_features, join_counts = build_feature_rows(point_rows, historical_profile_rows)
    leakage_safe_history = [
        row for row in historical_features
        if row.get("scheduled_time") < cutoff and str(row.get("match_id")) not in target_ids
    ]

    validation = evaluate(
        leakage_safe_history,
        readiness={},
        include_stateful_diagnostics=False,
    )
    legacy_status, legacy_positive, stateful_reference_status = _legacy_runtime_validation(validation)
    validation_signal = validation.get("signal") or {}
    report["historical_validation"] = {
        "status": legacy_status,
        "runtime_feature_group": "profile_only",
        "stateful_reference_status": stateful_reference_status,
        "stateful_reference_is_runtime_gate": False,
        "train_points": validation.get("train_points_after_support_gate"),
        "holdout_points": validation.get("holdout_points_after_support_gate"),
        "profile_only_brier_gain_vs_rank": validation_signal.get("profile_only_brier_gain_vs_rank"),
        "combined_brier_gain_vs_rank": validation_signal.get("combined_brier_gain_vs_rank"),
        "split": validation.get("split"),
    }
    if validation.get("real_shadow_training") is not True or not legacy_positive:
        report["status"] = "BLOCKED_VALIDATION_NOT_POSITIVE"
        report["historical_join_counts"] = join_counts
        return report, None

    training_rows = _cohort(leakage_safe_history, EVAL_MIN_PRIOR_MATCHES)
    training = _frame(training_rows)
    if (
        training.empty
        or training["match_id"].astype(str).nunique() < 30
        or training["server_won"].nunique() != 2
    ):
        report["status"] = "BLOCKED_INSUFFICIENT_PRE_CUTOFF_TRAINING"
        return report, None

    model = _fit_logistic_newton(training, list(PROFILE_NUMERIC))
    model_artifact = _serialize_model(model, cutoff=cutoff, training=training)
    if model_artifact["fit"].get("converged") is not True:
        report["status"] = "BLOCKED_MODEL_DID_NOT_CONVERGE"
        return report, None

    current_profiles, profile_summary = build_current_target_profiles(point_rows, valid_targets)
    profiles = _profile_map(current_profiles)

    scored = []
    eligible = 0
    for target in valid_targets:
        match_id = str(target.get("id"))
        p1_id = int(target["p1_id"])
        p2_id = int(target["p2_id"])
        p1_profile = profiles.get((match_id, p1_id))
        p2_profile = profiles.get((match_id, p2_id))
        base = {
            "match_id": target.get("id"),
            "scheduled_time": target.get("scheduled_time"),
            "tour": target.get("tour"),
            "surface": target.get("surface"),
            "best_of": target.get("best_of"),
            "p1": target.get("p1"),
            "p2": target.get("p2"),
            "p1_id": p1_id,
            "p2_id": p2_id,
            "p1_rank": _provider_ranking(target.get("p1_rank")),
            "p2_rank": _provider_ranking(target.get("p2_rank")),
            "production_influence": False,
            "not_match_win_probability": True,
        }
        if p1_profile is None or p2_profile is None:
            base["status"] = "NO_PROFILE"
            scored.append(base)
            continue

        p1_support = int((p1_profile.get("overall_prior") or {}).get("matches") or 0)
        p2_support = int((p2_profile.get("overall_prior") or {}).get("matches") or 0)
        p1_surface_support = int((p1_profile.get("same_surface_prior") or {}).get("matches") or 0)
        p2_surface_support = int((p2_profile.get("same_surface_prior") or {}).get("matches") or 0)
        base["support"] = {
            "p1_prior_matches": p1_support,
            "p2_prior_matches": p2_support,
            "p1_same_surface_matches": p1_surface_support,
            "p2_same_surface_matches": p2_surface_support,
        }
        if p1_support < EVAL_MIN_PRIOR_MATCHES or p2_support < EVAL_MIN_PRIOR_MATCHES:
            base["status"] = "COLLECTING_HISTORY"
            scored.append(base)
            continue

        eligible += 1
        p1_serve = _serve_feature_row(target, p1_profile, p2_profile)
        p2_serve = _serve_feature_row(target, p2_profile, p1_profile)
        frame = pd.DataFrame([p1_serve, p2_serve])
        probabilities = _predict_logistic(model, frame)
        base.update({
            "status": "SHADOW_SCORED",
            "p1_serve_point_win_probability": round(float(probabilities[0]), 6),
            "p2_serve_point_win_probability": round(float(probabilities[1]), 6),
            "model_fingerprint_sha256": model_artifact["fit"]["model_fingerprint_sha256"],
            "feature_group": "profile_only",
        })
        scored.append(base)

    report.update({
        "status": "ACTIVE_SHADOW" if eligible > 0 else "COLLECTING_HISTORY",
        "training_cutoff_exclusive": cutoff.isoformat(),
        "historical_join_counts": join_counts,
        "pre_cutoff_training_points": int(len(training)),
        "pre_cutoff_training_matches": int(training["match_id"].astype(str).nunique()),
        "model_fingerprint_sha256": model_artifact["fit"]["model_fingerprint_sha256"],
        "current_profile_summary": profile_summary,
        "eligible_matches": eligible,
        "scored_matches": sum(1 for row in scored if row.get("status") == "SHADOW_SCORED"),
        "collecting_history_matches": sum(1 for row in scored if row.get("status") == "COLLECTING_HISTORY"),
        "no_profile_matches": sum(1 for row in scored if row.get("status") == "NO_PROFILE"),
        "matches": scored,
    })
    return report, model_artifact


def build() -> dict[str, Any]:
    current_results = _read_json(RESULTS, [])
    point_rows = list(iter_point_rows() or ())
    historical_profiles = list(_iter_jsonl_gz(PROFILES) or ())

    report, artifact = build_current_scores(
        point_rows,
        historical_profiles,
        current_results if isinstance(current_results, list) else [],
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if artifact is not None:
        MODEL_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        MODEL_ARTIFACT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "version": report.get("version"),
        "status": report.get("status"),
        "current_matches": report.get("current_matches"),
        "stable_id_matches": report.get("stable_id_matches"),
        "eligible_matches": report.get("eligible_matches"),
        "scored_matches": report.get("scored_matches"),
        "collecting_history_matches": report.get("collecting_history_matches"),
        "training_cutoff_exclusive": report.get("training_cutoff_exclusive"),
        "model_fingerprint_sha256": report.get("model_fingerprint_sha256"),
        "production_influence": report.get("production_influence"),
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
