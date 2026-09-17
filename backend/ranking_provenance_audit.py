from __future__ import annotations

"""LOGIC-02 audit-only ranking provenance report.

Traces current fixture ranking from the committed Live Tennis API snapshot and
historical player/opponent ranking from the restored TennisMyLife cache. It does
not change runtime/model behavior, probability, weights, thresholds or training.
"""

import argparse
import copy
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from . import model
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
except ImportError:  # pragma: no cover
    import model
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "frontend" / "data" / "results.json"
META_PATH = ROOT / "frontend" / "data" / "meta.json"
PLAYER_DNA_CURRENT_PATH = ROOT / "frontend" / "data" / "player_dna_current_shadow.json"
ARTIFACT_PATH = ROOT / "artifacts" / "ranking_provenance_audit.json"
VERSION = "logic-02-ranking-provenance-v1"
AGE_THRESHOLDS = (30, 90, 180, 365)
CURRENT_OUTPUT_KEYS = (
    "best_of", "model_ready", "quality", "model_confidence", "service_model",
    "game_states", "first_set_win", "second_set_win", "second_set_context",
    "third_set_win", "over_under", "exact_first_set", "match_over_under",
    "expected_match_games", "match_win", "total_sets", "exact_match_score",
    "pick_first_set", "score_first_set", "score_over85", "score_lead_after6",
    "score_joint_builder",
)


def _read_json(path: Path, fallback):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _result_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict) and isinstance(value.get("matches"), list):
        return [row for row in value["matches"] if isinstance(row, dict)]
    return []


def _positive_rank(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return int(round(number))


def _cutoff(value: Any) -> pd.Timestamp | None:
    cut = model._naive_cutoff(value)
    return pd.Timestamp(cut).normalize() if cut is not None else None


def _age_days(cut: pd.Timestamp | None, value: Any) -> int | None:
    if cut is None:
        return None
    date = pd.to_datetime(value, errors="coerce")
    if pd.isna(date):
        return None
    return max(0, int((cut - pd.Timestamp(date).normalize()).days))


def _quantiles(values: list[float | int]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "median": None, "p90": None, "max": None}
    series = pd.Series(values, dtype="float64")
    return {
        "n": len(values),
        "median": round(float(series.quantile(0.50)), 2),
        "p90": round(float(series.quantile(0.90)), 2),
        "max": round(float(series.max()), 2),
    }


def _legal_player_rows(long_df: pd.DataFrame, player: str, scheduled_time: Any):
    dated = model._dated_history(long_df)
    cut = _cutoff(scheduled_time)
    if dated is None or dated.empty or cut is None:
        return pd.DataFrame(), None, "none"
    # Mirror production identity semantics: resolve on the dated history frame,
    # then apply the fixture-date cutoff. Returned evidence remains pre-match only.
    resolved_key, mode = model._resolve_history_player_key(dated, player)
    if resolved_key is None:
        return pd.DataFrame(), None, mode
    pre = dated[dated["date"].notna() & (dated["date"] <= cut)].copy()
    if "player_key" in pre.columns:
        rows = pre[pre["player_key"] == resolved_key].copy()
    else:
        rows = pre[pre["player"] == player].copy()
    return rows.sort_values("date", ascending=False), resolved_key, mode


def _profile_rank_observation(used_rows: pd.DataFrame) -> dict[str, Any]:
    """Mirror Current player_profile rank semantics on exact head(20)."""
    if used_rows is None or used_rows.empty or "rank" not in used_rows.columns:
        return {"rank": None, "observation_date": None, "source_row_position": None}
    frame = used_rows.reset_index(drop=True)
    ranks = pd.to_numeric(frame["rank"], errors="coerce")
    for pos, value in enumerate(ranks.tolist(), start=1):
        if pd.notna(value):
            date = frame.iloc[pos - 1].get("date")
            return {
                "rank": int(round(float(value))) if float(value) > 0 else None,
                "observation_date": pd.Timestamp(date).date().isoformat() if not pd.isna(date) else None,
                "source_row_position": pos,
            }
    return {"rank": None, "observation_date": None, "source_row_position": None}


def _latest_available_rank_observation(all_rows: pd.DataFrame) -> dict[str, Any]:
    if all_rows is None or all_rows.empty or "rank" not in all_rows.columns:
        return {"rank": None, "observation_date": None}
    frame = all_rows.reset_index(drop=True)
    ranks = pd.to_numeric(frame["rank"], errors="coerce")
    for pos, value in enumerate(ranks.tolist()):
        if pd.notna(value) and float(value) > 0:
            date = frame.iloc[pos].get("date")
            return {
                "rank": int(round(float(value))),
                "observation_date": pd.Timestamp(date).date().isoformat() if not pd.isna(date) else None,
            }
    return {"rank": None, "observation_date": None}


def _opponent_rank_evidence(used_rows: pd.DataFrame, cut: pd.Timestamp | None) -> dict[str, Any]:
    if used_rows is None or used_rows.empty or "opponent_rank" not in used_rows.columns:
        return {"used_rows": int(len(used_rows)) if used_rows is not None else 0,
                "rows_with_opponent_rank": 0, "coverage": 0.0,
                "newest_observation_date": None, "newest_age_days": None}
    numeric = pd.to_numeric(used_rows["opponent_rank"], errors="coerce")
    valid = used_rows[numeric.notna() & (numeric > 0)]
    newest = valid.iloc[0] if not valid.empty else None
    date = newest.get("date") if newest is not None else None
    return {
        "used_rows": int(len(used_rows)),
        "rows_with_opponent_rank": int(len(valid)),
        "coverage": round(len(valid) / len(used_rows), 6) if len(used_rows) else 0.0,
        "newest_observation_date": pd.Timestamp(date).date().isoformat() if date is not None and not pd.isna(date) else None,
        "newest_age_days": _age_days(cut, date),
    }


def _current_output_view(result: dict[str, Any]) -> dict[str, Any]:
    # Exclude passthrough fixture metadata and p1_stats/p2_stats input metadata.
    return {key: result.get(key) for key in CURRENT_OUTPUT_KEYS}


def _views_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return json.dumps(left, sort_keys=True, default=str) == json.dumps(right, sort_keys=True, default=str)


def _fixture_rank_counterfactual(long_df: pd.DataFrame, match: dict[str, Any]) -> dict[str, Any]:
    try:
        baseline = model.analyse_match(long_df, match)
        changed = copy.deepcopy(match)
        changed["p1_rank"], changed["p2_rank"] = 1, 9999
        probe = model.analyse_match(long_df, changed)
        return {"ran": True, "current_output_changed": not _views_equal(_current_output_view(baseline), _current_output_view(probe)), "error": None}
    except Exception as exc:
        return {"ran": False, "current_output_changed": None, "error": type(exc).__name__}


def _history_rank_counterfactual(long_df: pd.DataFrame, rank_probe_df: pd.DataFrame, match: dict[str, Any]) -> dict[str, Any]:
    try:
        baseline = model.analyse_match(long_df, match)
        probe = model.analyse_match(rank_probe_df, match)
        return {"ran": True, "current_output_changed": not _views_equal(_current_output_view(baseline), _current_output_view(probe)), "error": None}
    except Exception as exc:
        return {"ran": False, "current_output_changed": None, "error": type(exc).__name__}


def _player_dna_rank_contract(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict) or not report:
        return {"available": False}
    keys = (
        "mode", "production_influence", "rank_features_used",
        "provider_rank_context_passthrough", "rank_context_source",
        "fixture_rank_context_matches", "rank_context_matches", "rank_context_coverage",
        "strict_prior_provider_rank_fallback_enabled", "name_or_fuzzy_rank_fallback_forbidden",
    )
    return {"available": True, **{key: report.get(key) for key in keys}}


def build_report(long_df: pd.DataFrame, results: list[dict[str, Any]], meta: dict[str, Any], player_dna_current: dict[str, Any] | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    stamp = now or datetime.now(timezone.utc)
    profiles: list[dict[str, Any]] = []
    history_rank_ages: list[int] = []
    history_rank_ages_ready: list[int] = []
    abs_rank_deltas: list[int] = []
    abs_rank_deltas_ready: list[int] = []
    opponent_coverages: list[float] = []
    fixture_cf: dict[str, Any] = {"ran": 0, "changed": 0, "errors": []}
    history_cf: dict[str, Any] = {"ran": 0, "changed": 0, "errors": []}
    fixture_rank_matches = fixture_both_rank_matches = 0
    model_ready_matches = model_ready_both_fixture_rank = 0

    rank_probe_df = long_df.copy()
    if "rank" in rank_probe_df.columns:
        rank_probe_df["rank"] = 9999
    if "opponent_rank" in rank_probe_df.columns:
        rank_probe_df["opponent_rank"] = 9999

    for match in results:
        ready = bool(match.get("model_ready"))
        model_ready_matches += int(ready)
        p1_rank = _positive_rank(match.get("p1_rank"))
        p2_rank = _positive_rank(match.get("p2_rank"))
        fixture_rank_matches += int(p1_rank is not None or p2_rank is not None)
        fixture_both_rank_matches += int(p1_rank is not None and p2_rank is not None)
        model_ready_both_fixture_rank += int(ready and p1_rank is not None and p2_rank is not None)

        if ready:
            for target, result in ((fixture_cf, _fixture_rank_counterfactual(long_df, match)),
                                   (history_cf, _history_rank_counterfactual(long_df, rank_probe_df, match))):
                if result["ran"]:
                    target["ran"] += 1
                    target["changed"] += int(bool(result["current_output_changed"]))
                else:
                    target["errors"].append({"match_id": match.get("id"), "error": result["error"]})

        for side in ("p1", "p2"):
            player = str(match.get(side) or "").strip()
            if not player:
                continue
            fixture_rank = _positive_rank(match.get(f"{side}_rank"))
            all_rows, resolved_key, mode = _legal_player_rows(long_df, player, match.get("scheduled_time"))
            used_rows = all_rows.head(20).copy()
            profile_rank = _profile_rank_observation(used_rows)
            latest_available = _latest_available_rank_observation(all_rows)
            cut = _cutoff(match.get("scheduled_time"))
            rank_age = _age_days(cut, profile_rank.get("observation_date"))
            opponent = _opponent_rank_evidence(used_rows, cut)
            opponent_coverages.append(float(opponent["coverage"]))
            stored_profile_rank = _positive_rank((match.get(f"{side}_stats") or {}).get("rank"))
            delta = fixture_rank - profile_rank["rank"] if fixture_rank is not None and profile_rank["rank"] is not None else None
            abs_delta = abs(delta) if delta is not None else None
            if rank_age is not None:
                history_rank_ages.append(rank_age)
                if ready:
                    history_rank_ages_ready.append(rank_age)
            if abs_delta is not None:
                abs_rank_deltas.append(abs_delta)
                if ready:
                    abs_rank_deltas_ready.append(abs_delta)

            profiles.append({
                "match_id": match.get("id"), "scheduled_time": match.get("scheduled_time"),
                "model_ready_match": ready, "side": side, "player": player,
                "resolved_history_key": resolved_key, "identity_mode": mode,
                "fixture_provider_rank": fixture_rank,
                "fixture_rank_source": "Live Tennis API fixture players.*.ranking",
                "fixture_rank_snapshot_observed_at": meta.get("updated_at"),
                "fixture_rank_effective_date_available": False,
                "historical_profile_rank": profile_rank["rank"],
                "historical_profile_rank_observation_date": profile_rank["observation_date"],
                "historical_profile_rank_age_days": rank_age,
                "historical_profile_rank_source_row_position": profile_rank["source_row_position"],
                "historical_rank_source": "TennisMyLife winner_rank/loser_rank on historical match row",
                "latest_available_pre_match_rank": latest_available["rank"],
                "latest_available_pre_match_rank_observation_date": latest_available["observation_date"],
                "stored_p_stats_rank": stored_profile_rank,
                "stored_profile_rank_matches_recomputed": stored_profile_rank == profile_rank["rank"],
                "fixture_minus_historical_rank": delta,
                "absolute_fixture_historical_rank_delta": abs_delta,
                "used_history_rows": int(len(used_rows)),
                "historical_opponent_rank": opponent,
            })

    model_ready_profiles = [row for row in profiles if row["model_ready_match"]]
    fixture_rank_profiles = sum(row["fixture_provider_rank"] is not None for row in profiles)
    historical_rank_profiles = sum(row["historical_profile_rank"] is not None for row in profiles)
    both_rank_profiles = sum(row["fixture_provider_rank"] is not None and row["historical_profile_rank"] is not None for row in profiles)
    opponent_rank_profiles = sum(row["historical_opponent_rank"]["rows_with_opponent_rank"] > 0 for row in profiles)
    thresholds = {str(days): sum(age > days for age in history_rank_ages) for days in AGE_THRESHOLDS}
    ready_thresholds = {str(days): sum(age > days for age in history_rank_ages_ready) for days in AGE_THRESHOLDS}

    consumer_map = {
        "current_engine_fixture_provider_rank": {
            "source": "results p1_rank/p2_rank from update.fetch_fixtures() Live Tennis API players.*.ranking",
            "preserved_in_match_output": True,
            "used_in_current_probability_math": fixture_cf["changed"] > 0,
            "counterfactual": fixture_cf,
            "note_contract_warning": "model.py note says 'forma/ranking'; this counterfactual is authoritative for actual Current output influence",
            "production_change": False,
        },
        "current_engine_historical_latest_rank": {
            "source": "TML winner_rank/loser_rank -> normalize_matches rank -> player_profile head(20) first non-null rank",
            "exposed_as_profile_metadata": True,
            "used_in_current_probability_math": history_cf["changed"] > 0,
            "counterfactual": history_cf,
            "production_change": False,
        },
        "current_engine_historical_opponent_rank": {
            "source": "TML opponent winner_rank/loser_rank -> normalize_matches opponent_rank",
            "used_in_current_probability_math": history_cf["changed"] > 0,
            "production_change": False,
        },
        "player_dna_current_shadow": _player_dna_rank_contract(player_dna_current or {}),
        "player_dna_historical_point_scorer": {
            "mode": "SHADOW_EVAL_ONLY", "ranking_features": ["server_rank", "receiver_rank"],
            "compares_rank_only_profile_only_and_combined": True, "production_influence": False,
        },
    }

    return {
        "version": VERSION,
        "generated_at": stamp.isoformat(),
        "policy": {
            "audit_only": True, "runtime_change": False, "model_math_changed": False,
            "probability_changed": False, "thresholds_changed": False, "weights_changed": False,
            "training_changed": False, "history_sources_changed": False,
            "live_tennis_api_calls": 0, "production_cache_writes": 0,
            "identity_rules_changed": False,
        },
        "sources": {
            "fixture_ranking": {
                "provider": "Live Tennis API", "field_path": "players.p1/p2.ranking -> results p1_rank/p2_rank",
                "snapshot_observed_at": meta.get("updated_at"), "ranking_effective_date_available": False,
            },
            "historical_ranking": {
                "provider": "TennisMyLife", "field_path": "winner_rank/loser_rank -> normalized rank/opponent_rank",
                "observation_date_field": "tourney_date -> normalized date",
                "separate_ranking_effective_date_available": False,
            },
        },
        "summary": {
            "visible_matches": len(results), "model_ready_matches": model_ready_matches,
            "audited_player_fixture_profiles": len(profiles),
            "model_ready_player_fixture_profiles": len(model_ready_profiles),
            "matches_with_any_fixture_provider_rank": fixture_rank_matches,
            "matches_with_both_fixture_provider_ranks": fixture_both_rank_matches,
            "model_ready_matches_with_both_fixture_provider_ranks": model_ready_both_fixture_rank,
            "profiles_with_fixture_provider_rank": fixture_rank_profiles,
            "profiles_with_historical_profile_rank": historical_rank_profiles,
            "profiles_with_both_fixture_and_historical_rank": both_rank_profiles,
            "historical_rank_age_days": _quantiles(history_rank_ages),
            "model_ready_historical_rank_age_days": _quantiles(history_rank_ages_ready),
            "historical_rank_older_than_days": thresholds,
            "model_ready_historical_rank_older_than_days": ready_thresholds,
            "absolute_fixture_vs_historical_rank_delta": _quantiles(abs_rank_deltas),
            "model_ready_absolute_fixture_vs_historical_rank_delta": _quantiles(abs_rank_deltas_ready),
            "profiles_with_any_historical_opponent_rank": int(opponent_rank_profiles),
            "historical_opponent_rank_coverage_per_profile": _quantiles(opponent_coverages),
            "current_engine_fixture_rank_counterfactual": fixture_cf,
            "current_engine_history_rank_counterfactual": history_cf,
        },
        "consumer_map": consumer_map,
        "profiles": profiles,
        "decision": {
            "production_change_authorized": False,
            "ranking_feature_activation_authorized": False,
            "opponent_adjustment_authorized": False,
            "reason": "LOGIC-02 is provenance audit only; feature activation requires later SHADOW validation and explicit promotion.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LOGIC-02 ranking provenance audit")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--meta", type=Path, default=META_PATH)
    parser.add_argument("--player-dna-current", type=Path, default=PLAYER_DNA_CURRENT_PATH)
    parser.add_argument("--output", type=Path, default=ARTIFACT_PATH)
    args = parser.parse_args()
    raw = load_cached_history()
    if raw is None or raw.empty:
        raise SystemExit("production history cache unavailable")
    cleaned, _ = clean_history(raw)
    long_df = model.normalize_matches(cleaned)
    results = _result_rows(_read_json(args.results, []))
    if not results:
        raise SystemExit("current results snapshot unavailable or empty")
    report = build_report(long_df, results, _read_json(args.meta, {}), _read_json(args.player_dna_current, {}))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
