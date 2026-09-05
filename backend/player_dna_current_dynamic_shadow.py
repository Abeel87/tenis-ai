from __future__ import annotations

"""Current-card dynamic lean Player DNA candidate in strict SHADOW.

This stage reuses the exact historical dynamic-state simulator candidate that is
already exercised by the market backtest. It fits the lean point model only on
strict historical rows scheduled before the current-card cutoff, uses provider
rank context carried by the current fixture payload, and applies the segment
consensus diagnostic market-by-market.

Nothing here switches runtime probabilities or influences PROD, Symfonia 2.0 or
Superbet PLAYABLE. Conflicts and insufficient segment evidence remain blocked.
"""

import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

try:
    from backend.player_dna_market_backtest import (
        BINARY_MARKETS,
        MIN_PRIOR_MATCHES,
        _binary_probability,
        _dynamic_candidate_simulation,
        _snapshot_pairs,
    )
    from backend.player_dna_point_scorer import (
        LEAN_STATE_NUMERIC,
        PROFILE_NUMERIC,
        RANK_NUMERIC,
        _cohort,
        _fit_logistic_newton,
        _model_meta,
        build_feature_rows,
    )
    from backend.player_dna_shadow_profiles import build_current_target_profiles
    from backend.player_dna_tennis_simulator import simulate_match
except ModuleNotFoundError:  # direct execution
    from player_dna_market_backtest import (
        BINARY_MARKETS,
        MIN_PRIOR_MATCHES,
        _binary_probability,
        _dynamic_candidate_simulation,
        _snapshot_pairs,
    )
    from player_dna_point_scorer import (
        LEAN_STATE_NUMERIC,
        PROFILE_NUMERIC,
        RANK_NUMERIC,
        _cohort,
        _fit_logistic_newton,
        _model_meta,
        build_feature_rows,
    )
    from player_dna_shadow_profiles import build_current_target_profiles
    from player_dna_tennis_simulator import simulate_match


ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "data" / "derived" / "player_dna" / "point_events.jsonl.gz"
PROFILES = ROOT / "data" / "derived" / "player_dna" / "profile_snapshots.jsonl.gz"
CURRENT = ROOT / "frontend" / "data" / "player_dna_current_shadow.json"
WALK_FORWARD = ROOT / "frontend" / "data" / "player_dna_dynamic_market_walk_forward.json"
OUT = ROOT / "frontend" / "data" / "player_dna_current_dynamic_shadow.json"

VERSION = "player-dna-current-dynamic-shadow-v1"
MODE = "SHADOW_CURRENT_DYNAMIC_LEAN_ONLY"
FEATURE_GROUPS = ("profile", "rank", "point_pressure", "set_match_state")


def _iter_jsonl_gz(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def _read_json(path: Path, fallback):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback
    return value


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _finite_positive_rank(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        rank = float(value)
    except (TypeError, ValueError):
        return None
    if rank <= 0.0:
        return None
    return rank


def _compact_market_probabilities(simulation: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for market in BINARY_MARKETS:
        probability = _binary_probability(simulation, market)
        if probability is not None:
            out[market] = float(probability)
    return out


def segment_market_policy(
    walk_forward: dict[str, Any],
    *,
    tour: Any,
    surface: Any,
) -> dict[str, str]:
    consensus = (
        walk_forward.get("segment_consensus_shadow_policy")
        if isinstance(walk_forward, dict)
        else None
    )
    if not isinstance(consensus, dict):
        return {market: "INSUFFICIENT_OR_MIXED" for market in BINARY_MARKETS}
    if (
        consensus.get("mode") != "SHADOW_SEGMENT_CONSENSUS_DIAGNOSTIC_ONLY"
        or consensus.get("production_influence") is not False
        or consensus.get("runtime_switch_enabled") is not False
        or consensus.get("auto_promote") is not False
    ):
        return {market: "INSUFFICIENT_OR_MIXED" for market in BINARY_MARKETS}

    key = f"{str(tour or '').strip().lower()}|{str(surface or '').strip().lower()}"
    segment = (consensus.get("segments") or {}).get(key) or {}
    markets = segment.get("markets") if isinstance(segment, dict) else {}
    markets = markets if isinstance(markets, dict) else {}
    allowed = {
        "CONSENSUS_DYNAMIC_CANDIDATE",
        "CONSENSUS_PROFILE_REFERENCE",
        "CONFLICT",
        "INSUFFICIENT_OR_MIXED",
    }
    return {
        market: (
            str((markets.get(market) or {}).get("decision"))
            if str((markets.get(market) or {}).get("decision")) in allowed
            else "INSUFFICIENT_OR_MIXED"
        )
        for market in BINARY_MARKETS
    }


def _training_before_current_cutoff(
    feature_rows: list[dict[str, Any]],
    cutoff: datetime,
    current_match_ids: set[str],
) -> list[dict[str, Any]]:
    historical = [
        row
        for row in feature_rows
        if row.get("scheduled_time") is not None
        and row["scheduled_time"] < cutoff
        and str(row.get("match_id") or "") not in current_match_ids
    ]
    return _cohort(historical, MIN_PRIOR_MATCHES)


def build_current_dynamic_shadow(
    point_rows: list[dict[str, Any]],
    historical_profile_rows: list[dict[str, Any]],
    current: dict[str, Any],
    walk_forward: dict[str, Any],
) -> dict[str, Any]:
    base = {
        "version": VERSION,
        "mode": MODE,
        "status": "BLOCKED_INPUT_CONTRACT",
        "production_influence": False,
        "runtime_switch_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "candidate_only": True,
        "prospective_validation_required": True,
        "feature_groups": list(FEATURE_GROUPS),
        "dropped_state_groups": ["tiebreak_context", "prior_momentum"],
        "tiebreak_policy": "PROFILE_ONLY_NEUTRAL_FIXED_PER_MATCH",
        "market_policy_source": "segment_consensus_shadow_policy",
        "matches": [],
    }

    if not isinstance(current, dict) or current.get("mode") != "SHADOW_CURRENT_ONLY":
        return base
    current_rows = current.get("matches")
    current_rows = current_rows if isinstance(current_rows, list) else []
    cutoff = _parse_utc(current.get("training_cutoff_exclusive"))
    if cutoff is None or not current_rows:
        return base

    consensus = (
        walk_forward.get("segment_consensus_shadow_policy")
        if isinstance(walk_forward, dict)
        else None
    )
    if (
        not isinstance(consensus, dict)
        or consensus.get("mode") != "SHADOW_SEGMENT_CONSENSUS_DIAGNOSTIC_ONLY"
        or consensus.get("production_influence") is not False
        or consensus.get("runtime_switch_enabled") is not False
        or consensus.get("auto_promote") is not False
        or consensus.get("prospective_validation_required") is not True
    ):
        base["status"] = "BLOCKED_SEGMENT_CONSENSUS_CONTRACT"
        return base

    feature_rows, join_counts = build_feature_rows(point_rows, historical_profile_rows)
    current_ids = {
        str(row.get("match_id") or row.get("id") or "").strip()
        for row in current_rows
        if isinstance(row, dict)
    }
    current_ids.discard("")
    training_rows = _training_before_current_cutoff(feature_rows, cutoff, current_ids)
    if not training_rows:
        base["status"] = "BLOCKED_NO_PRE_CUTOFF_TRAINING"
        base["historical_join_counts"] = join_counts
        return base

    training = pd.DataFrame(training_rows)
    lean_model = _fit_logistic_newton(
        training,
        list(PROFILE_NUMERIC) + list(RANK_NUMERIC) + list(LEAN_STATE_NUMERIC),
    )
    fit = _model_meta(lean_model)
    if fit.get("converged") is not True:
        base["status"] = "BLOCKED_LEAN_MODEL_DID_NOT_CONVERGE"
        base["lean_model_fit"] = fit
        return base

    current_profiles, profile_summary = build_current_target_profiles(
        point_rows,
        current_rows,
    )
    pairs = _snapshot_pairs(current_profiles)
    counts = Counter()
    out_rows = []

    for row in current_rows:
        if not isinstance(row, dict):
            continue
        match_id = str(row.get("match_id") or row.get("id") or "").strip()
        common = {
            "match_id": row.get("match_id") or row.get("id"),
            "scheduled_time": row.get("scheduled_time"),
            "tour": row.get("tour"),
            "surface": row.get("surface"),
            "best_of": row.get("best_of"),
            "p1": row.get("p1"),
            "p2": row.get("p2"),
            "p1_id": row.get("p1_id"),
            "p2_id": row.get("p2_id"),
            "p1_rank": row.get("p1_rank"),
            "p2_rank": row.get("p2_rank"),
            "production_influence": False,
            "runtime_switch_enabled": False,
        }
        if row.get("status") != "SHADOW_SCORED":
            common["status"] = "BLOCKED_CURRENT_PROFILE_NOT_SCORED"
            counts["blocked_current_profile_not_scored"] += 1
            out_rows.append(common)
            continue

        pair = pairs.get(match_id) or {}
        p1_profile = pair.get("p1")
        p2_profile = pair.get("p2")
        if not isinstance(p1_profile, dict) or not isinstance(p2_profile, dict):
            common["status"] = "BLOCKED_MISSING_CURRENT_PROFILE_PAIR"
            counts["blocked_missing_current_profile_pair"] += 1
            out_rows.append(common)
            continue

        p1_rank = _finite_positive_rank(row.get("p1_rank"))
        p2_rank = _finite_positive_rank(row.get("p2_rank"))
        p1_rank_source = row.get("p1_rank_source")
        p2_rank_source = row.get("p2_rank_source")
        if p1_rank is None:
            p1_rank = _finite_positive_rank(p1_profile.get("player_ranking"))
            p1_rank_source = p1_profile.get("player_ranking_source") if p1_rank is not None else None
        if p2_rank is None:
            p2_rank = _finite_positive_rank(p2_profile.get("player_ranking"))
            p2_rank_source = p2_profile.get("player_ranking_source") if p2_rank is not None else None
        common["p1_rank"] = p1_rank
        common["p2_rank"] = p2_rank
        common["p1_rank_source"] = p1_rank_source
        common["p2_rank_source"] = p2_rank_source
        if p1_rank is None or p2_rank is None:
            common["status"] = "BLOCKED_MISSING_PROVIDER_RANK"
            counts["blocked_missing_provider_rank"] += 1
            out_rows.append(common)
            continue
        if (
            p1_rank_source == "latest_strict_prior_provider_match_context"
            or p2_rank_source == "latest_strict_prior_provider_match_context"
        ):
            counts["dynamic_scored_with_strict_prior_provider_rank_fallback"] += 1

        p1_serve = row.get("p1_serve_point_win_probability")
        p2_serve = row.get("p2_serve_point_win_probability")
        try:
            p1_serve = float(p1_serve)
            p2_serve = float(p2_serve)
        except (TypeError, ValueError):
            common["status"] = "BLOCKED_MISSING_PROFILE_POINT_PROBABILITY"
            counts["blocked_missing_profile_point_probability"] += 1
            out_rows.append(common)
            continue

        best_of = row.get("best_of")
        best_of = int(best_of) if isinstance(best_of, int) and not isinstance(best_of, bool) else 3
        if best_of not in (3, 5):
            best_of = 3

        reference = simulate_match(p1_serve, p2_serve, best_of=best_of)
        dynamic = _dynamic_candidate_simulation(
            p1_profile,
            p2_profile,
            p1_rank=p1_rank,
            p2_rank=p2_rank,
            lean_model=lean_model,
            profile_p1_serve=p1_serve,
            profile_p2_serve=p2_serve,
            best_of=best_of,
        )
        reference_probabilities = _compact_market_probabilities(reference)
        dynamic_probabilities = _compact_market_probabilities(dynamic)
        policy = segment_market_policy(
            walk_forward,
            tour=row.get("tour"),
            surface=row.get("surface"),
        )

        markets = {}
        for market in BINARY_MARKETS:
            decision = policy[market]
            selected_probability = None
            if decision == "CONSENSUS_DYNAMIC_CANDIDATE":
                selected_probability = dynamic_probabilities.get(market)
            elif decision == "CONSENSUS_PROFILE_REFERENCE":
                selected_probability = reference_probabilities.get(market)
            markets[market] = {
                "decision": decision,
                "profile_reference_probability": reference_probabilities.get(market),
                "dynamic_candidate_probability": dynamic_probabilities.get(market),
                "shadow_policy_probability": selected_probability,
                "production_influence": False,
            }

        common.update({
            "status": "DYNAMIC_SHADOW_SCORED",
            "market_segment_key": (
                f"{str(row.get('tour') or '').strip().lower()}|"
                f"{str(row.get('surface') or '').strip().lower()}"
            ),
            "model_fingerprint_sha256": fit.get("model_fingerprint_sha256"),
            "dynamic_callback_unique_states": dynamic.get("dynamic_callback_unique_states"),
            "dynamic_hold_cache_states": dynamic.get("dynamic_hold_cache_states"),
            "dynamic_set_cache_states": dynamic.get("dynamic_set_cache_states"),
            "markets": markets,
        })
        counts["dynamic_shadow_scored"] += 1
        counts["dynamic_candidate_market_slots"] += sum(
            1 for item in markets.values()
            if item.get("decision") == "CONSENSUS_DYNAMIC_CANDIDATE"
        )
        counts["profile_reference_market_slots"] += sum(
            1 for item in markets.values()
            if item.get("decision") == "CONSENSUS_PROFILE_REFERENCE"
        )
        counts["conflict_market_slots"] += sum(
            1 for item in markets.values()
            if item.get("decision") == "CONFLICT"
        )
        counts["insufficient_market_slots"] += sum(
            1 for item in markets.values()
            if item.get("decision") == "INSUFFICIENT_OR_MIXED"
        )
        out_rows.append(common)

    base.update({
        "status": "ACTIVE_SHADOW" if counts["dynamic_shadow_scored"] > 0 else "COLLECTING_CONTEXT",
        "training_cutoff_exclusive": cutoff.isoformat(),
        "training_points": int(len(training)),
        "training_matches": int(training["match_id"].astype(str).nunique()),
        "historical_join_counts": join_counts,
        "lean_model_fit": fit,
        "current_profile_summary": profile_summary,
        "counts": dict(counts),
        "current_matches": len(current_rows),
        "matches": out_rows,
    })
    return base


def build() -> dict[str, Any]:
    point_rows = list(_iter_jsonl_gz(POINTS) or ())
    profile_rows = list(_iter_jsonl_gz(PROFILES) or ())
    current = _read_json(CURRENT, {})
    walk_forward = _read_json(WALK_FORWARD, {})
    report = build_current_dynamic_shadow(
        point_rows,
        profile_rows,
        current if isinstance(current, dict) else {},
        walk_forward if isinstance(walk_forward, dict) else {},
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": report.get("version"),
        "mode": report.get("mode"),
        "status": report.get("status"),
        "current_matches": report.get("current_matches"),
        "counts": report.get("counts"),
        "training_cutoff_exclusive": report.get("training_cutoff_exclusive"),
        "production_influence": report.get("production_influence"),
        "runtime_switch_enabled": report.get("runtime_switch_enabled"),
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
