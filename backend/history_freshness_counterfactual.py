from __future__ import annotations

"""LOGIC-01: audit-only freshness counterfactual for Current history and PBP/Early Hold.

This module intentionally does not change production policy. It reuses the
production Current model on the restored production history snapshot, freezes
surface priors from the no-age-cutoff baseline, and varies only the maximum age
of player-history observations. PBP/Early Hold freshness is measured from the
already-produced current PBP evidence; it is not promoted into Current history.
"""

import argparse
import json
import math
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

try:
    from . import model
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
    from .model_core import _key
except ImportError:  # pragma: no cover - direct script execution
    import model
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history
    from model_core import _key

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "frontend" / "data" / "results.json"
PBP_INDEX_PATH = ROOT / "data" / "cache" / "pbp_v7" / "players.json"
ARTIFACT_PATH = ROOT / "artifacts" / "history_freshness_counterfactual.json"
SCENARIOS_DAYS = (30, 60, 90, 120, 180, 365)
MIN_MATCHES = 5
VERSION = "logic-01-freshness-counterfactual-v1"

# Frozen evidence from TASK 019 artifact produced by PR #383 / run 35255159461.
# It is historical evidence, not a substitute for the live LOGIC-01 run below.
TASK019_BASELINE_EVIDENCE = {
    "source_pr": 383,
    "source_head": "3d6fb71ea1886a35102e180fbc494b9d9015c9cc",
    "source_workflow_run": 35255159461,
    "visible_matches": 160,
    "audited_player_fixture_profiles": 319,
    "profiles_with_any_used_row_older_than_days": {"90": 174, "180": 97, "365": 54},
    "model_ready_profiles_with_any_used_row_older_than_days": {"90": 92, "180": 40, "365": 18},
    "model_has_explicit_max_history_age_days": False,
}


def _load_json(path: Path, fallback):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _result_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        rows = value.get("matches")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _cutoff(value: Any) -> pd.Timestamp | None:
    cut = model._naive_cutoff(value)
    return pd.Timestamp(cut).normalize() if cut is not None else None


def _fresh_history(long_df: pd.DataFrame, scheduled_time: Any, max_age_days: int) -> pd.DataFrame:
    """Keep only legal pre-match rows within max_age_days."""
    dated = model._dated_history(long_df)
    cut = _cutoff(scheduled_time)
    if dated is None or dated.empty or cut is None:
        columns = dated.columns if isinstance(dated, pd.DataFrame) else None
        return pd.DataFrame(columns=columns)
    lower = cut - pd.Timedelta(days=int(max_age_days))
    return dated[
        dated["date"].notna()
        & (dated["date"] <= cut)
        & (dated["date"] >= lower)
    ].copy()


def _baseline_priors(long_df: pd.DataFrame, match: dict[str, Any]) -> dict[str, float]:
    dated = model._dated_history(long_df)
    surface = str(match.get("surface") or "").lower()
    cut = model._naive_cutoff(match.get("scheduled_time"))
    return dict(model._core._surface_priors(dated, surface, cut))


@contextmanager
def _frozen_surface_priors(priors: dict[str, float]) -> Iterator[None]:
    """Freeze only the prior producer while executing unmodified model math."""
    original = model._core._surface_priors

    def frozen(*_args, **_kwargs):
        return dict(priors)

    model._core._surface_priors = frozen
    try:
        yield
    finally:
        model._core._surface_priors = original


def _run_with_frozen_priors(
    scenario_df: pd.DataFrame,
    match: dict[str, Any],
    priors: dict[str, float],
) -> dict[str, Any]:
    with _frozen_surface_priors(priors):
        return model.analyse_match(scenario_df, match)


def _profile_matches(result: dict[str, Any], side: str) -> int:
    stats = result.get(f"{side}_stats") or {}
    try:
        return int(stats.get("matches") or 0)
    except (TypeError, ValueError):
        return 0


def _numeric_leaves(value: Any, prefix: str = "") -> dict[str, float]:
    """Flatten numeric model outputs while excluding player-profile inputs."""
    out: dict[str, float] = {}
    if isinstance(value, bool) or value is None:
        return out
    if isinstance(value, (int, float)):
        number = float(value)
        if math.isfinite(number):
            out[prefix or "value"] = number
        return out
    if isinstance(value, dict):
        for key, child in value.items():
            key = str(key)
            if not prefix and key in {"p1_stats", "p2_stats", "id"}:
                continue
            child_prefix = f"{prefix}.{key}" if prefix else key
            out.update(_numeric_leaves(child, child_prefix))
        return out
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            out.update(_numeric_leaves(child, f"{prefix}[{index}]"))
    return out


def _output_delta(baseline: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    left = _numeric_leaves(baseline)
    right = _numeric_leaves(scenario)
    keys = sorted(set(left).intersection(right))
    deltas = [(key, abs(right[key] - left[key])) for key in keys]
    deltas.sort(key=lambda item: item[1], reverse=True)
    changed = [(key, delta) for key, delta in deltas if delta > 1e-12]
    return {
        "common_numeric_outputs": len(keys),
        "changed_numeric_outputs": len(changed),
        "max_abs_delta": round(changed[0][1], 6) if changed else 0.0,
        "mean_abs_delta": round(sum(delta for _, delta in deltas) / len(deltas), 6) if deltas else None,
        "top_changed_outputs": [
            {"path": key, "abs_delta": round(delta, 6)} for key, delta in changed[:12]
        ],
    }


def _safe_model_run(long_df: pd.DataFrame, match: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return model.analyse_match(long_df, match), None
    except Exception as exc:
        return None, type(exc).__name__


def _safe_scenario_run(
    long_df: pd.DataFrame,
    match: dict[str, Any],
    days: int,
    priors: dict[str, float],
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        fresh = _fresh_history(long_df, match.get("scheduled_time"), days)
        return _run_with_frozen_priors(fresh, match, priors), None
    except Exception as exc:
        return None, type(exc).__name__


def build_current_history_counterfactual(
    long_df: pd.DataFrame,
    results: list[dict[str, Any]],
    scenarios: tuple[int, ...] = SCENARIOS_DAYS,
) -> dict[str, Any]:
    baseline_rows: dict[str, dict[str, Any]] = {}
    baseline_errors: list[dict[str, Any]] = []

    for index, match in enumerate(results):
        fixture_key = str(match.get("id") or f"row-{index}")
        baseline, error = _safe_model_run(long_df, match)
        if baseline is None:
            baseline_errors.append({"fixture": fixture_key, "error": error})
            continue
        try:
            priors = _baseline_priors(long_df, match)
        except Exception as exc:
            baseline_errors.append({"fixture": fixture_key, "error": f"priors:{type(exc).__name__}"})
            continue
        baseline_rows[fixture_key] = {"match": match, "result": baseline, "priors": priors}

    stored_ready = sum(1 for match in results if bool(match.get("model_ready")))
    baseline_ready = sum(1 for row in baseline_rows.values() if bool(row["result"].get("model_ready")))
    baseline_profiles = sum(
        1 for row in baseline_rows.values() for side in ("p1", "p2")
        if _profile_matches(row["result"], side) > 0
    )
    baseline_profiles_ge5 = sum(
        1 for row in baseline_rows.values() for side in ("p1", "p2")
        if _profile_matches(row["result"], side) >= MIN_MATCHES
    )

    scenario_reports: dict[str, Any] = {}
    for days in scenarios:
        profiles_retained = profiles_ge5 = 0
        model_ready = common_ready = ready_lost = 0
        errors: list[dict[str, Any]] = []
        affected: list[dict[str, Any]] = []
        common_deltas: list[float] = []
        common_changed_outputs = 0

        for fixture_key, item in baseline_rows.items():
            match = item["match"]
            baseline = item["result"]
            scenario, error = _safe_scenario_run(long_df, match, days, item["priors"])
            if scenario is None:
                errors.append({"fixture": fixture_key, "error": error})
                continue

            p1_before = _profile_matches(baseline, "p1")
            p2_before = _profile_matches(baseline, "p2")
            p1_after = _profile_matches(scenario, "p1")
            p2_after = _profile_matches(scenario, "p2")
            profiles_retained += int(p1_after > 0) + int(p2_after > 0)
            profiles_ge5 += int(p1_after >= MIN_MATCHES) + int(p2_after >= MIN_MATCHES)

            baseline_is_ready = bool(baseline.get("model_ready"))
            scenario_is_ready = bool(scenario.get("model_ready"))
            model_ready += int(scenario_is_ready)
            common_ready += int(baseline_is_ready and scenario_is_ready)
            ready_lost += int(baseline_is_ready and not scenario_is_ready)

            delta = None
            if baseline_is_ready and scenario_is_ready:
                delta = _output_delta(baseline, scenario)
                common_deltas.append(float(delta["max_abs_delta"] or 0.0))
                common_changed_outputs += int(delta["changed_numeric_outputs"])

            changed = (
                p1_before != p1_after
                or p2_before != p2_after
                or baseline_is_ready != scenario_is_ready
                or bool(delta and delta["changed_numeric_outputs"])
            )
            if changed:
                affected.append({
                    "fixture": fixture_key,
                    "scheduled_time": match.get("scheduled_time"),
                    "surface": match.get("surface"),
                    "p1": match.get("p1"),
                    "p2": match.get("p2"),
                    "p1_matches_baseline": p1_before,
                    "p1_matches_scenario": p1_after,
                    "p2_matches_baseline": p2_before,
                    "p2_matches_scenario": p2_after,
                    "model_ready_baseline": baseline_is_ready,
                    "model_ready_scenario": scenario_is_ready,
                    "output_delta": delta,
                })

        affected.sort(key=lambda row: (
            not (row["model_ready_baseline"] and not row["model_ready_scenario"]),
            -float((row.get("output_delta") or {}).get("max_abs_delta") or 0.0),
            str(row.get("fixture")),
        ))
        scenario_reports[str(days)] = {
            "max_age_days": int(days),
            "profiles_with_any_history_retained": profiles_retained,
            "profiles_with_minimum_5_retained": profiles_ge5,
            "baseline_profiles_with_any_history": baseline_profiles,
            "baseline_profiles_with_minimum_5": baseline_profiles_ge5,
            "model_ready_matches": model_ready,
            "baseline_model_ready_matches": baseline_ready,
            "common_model_ready_matches": common_ready,
            "baseline_model_ready_lost": ready_lost,
            "fixture_errors": errors,
            "common_set_output_delta": {
                "fixtures": len(common_deltas),
                "max_abs_delta": round(max(common_deltas), 6) if common_deltas else None,
                "mean_of_fixture_max_abs_delta": round(sum(common_deltas) / len(common_deltas), 6) if common_deltas else None,
                "changed_numeric_outputs": common_changed_outputs,
            },
            "affected_fixture_count": len(affected),
            "affected_fixtures": affected,
        }

    return {
        "baseline": {
            "visible_fixtures_input": len(results),
            "fixtures_recomputed": len(baseline_rows),
            "stored_snapshot_model_ready_matches": stored_ready,
            "recomputed_no_age_cutoff_model_ready_matches": baseline_ready,
            "profiles_with_any_history": baseline_profiles,
            "profiles_with_minimum_5": baseline_profiles_ge5,
            "errors": baseline_errors,
            "surface_priors_policy": "full legal pre-match production history per fixture, frozen unchanged for every age scenario",
        },
        "scenarios": scenario_reports,
        "settled_common_set_metrics": {
            "available": False,
            "brier": None,
            "calibration": None,
            "accuracy": None,
            "reason": "Current visible fixtures have no dedicated unbiased settled prediction ledger in this audit input; do not infer labels from selection/output state. Prediction-ledger integrity is LOGIC-09.",
        },
    }


def _age_days(cut: pd.Timestamp | None, value: Any) -> int | None:
    if cut is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    naive = pd.Timestamp(parsed).tz_convert(None).normalize()
    return max(0, int((cut - naive).days))


def _pbp_id_dates(index: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    players = index.get("players") if isinstance(index, dict) else None
    if not isinstance(players, dict):
        return out
    for entry in players.values():
        if not isinstance(entry, dict):
            continue
        for match in entry.get("matches") or []:
            if isinstance(match, dict) and match.get("id") is not None and match.get("scheduled_time"):
                out.setdefault(str(match["id"]), match.get("scheduled_time"))
    return out


def build_pbp_freshness(
    results: list[dict[str, Any]],
    pbp_index: dict[str, Any],
    scenarios: tuple[int, ...] = SCENARIOS_DAYS,
) -> dict[str, Any]:
    players = pbp_index.get("players") if isinstance(pbp_index, dict) else {}
    players = players if isinstance(players, dict) else {}
    global_id_dates = _pbp_id_dates(pbp_index)
    profiles: list[dict[str, Any]] = []

    for match in results:
        cut = _cutoff(match.get("scheduled_time"))
        early = match.get("early_hold_v7") or {}
        for side in ("p1", "p2"):
            player = str(match.get(side) or "").strip()
            if not player:
                continue
            entry = players.get(_key(player))
            entry = entry if isinstance(entry, dict) else {}
            candidate_ages = []
            entry_id_dates: dict[str, Any] = {}
            for candidate in entry.get("matches") or []:
                if not isinstance(candidate, dict) or candidate.get("id") is None:
                    continue
                candidate_time = candidate.get("scheduled_time")
                entry_id_dates[str(candidate["id"])] = candidate_time
                age = _age_days(cut, candidate_time)
                if age is not None:
                    candidate_ages.append(age)

            profile = early.get(side) if isinstance(early, dict) else None
            profile = profile if isinstance(profile, dict) else {}
            sample_ids = [str(value) for value in (profile.get("sample_ids") or []) if value is not None]
            sample_ages = []
            missing_sample_dates = []
            for sample_id in sample_ids:
                when = entry_id_dates.get(sample_id) or global_id_dates.get(sample_id)
                age = _age_days(cut, when)
                if age is None:
                    missing_sample_dates.append(sample_id)
                else:
                    sample_ages.append(age)

            profiles.append({
                "match_id": match.get("id"),
                "scheduled_time": match.get("scheduled_time"),
                "side": side,
                "player": player,
                "pbp_index_found": bool(entry),
                "pbp_candidate_matches": len(candidate_ages),
                "pbp_candidate_ages_days": candidate_ages,
                "pbp_candidate_newest_age_days": min(candidate_ages) if candidate_ages else None,
                "pbp_candidate_oldest_age_days": max(candidate_ages) if candidate_ages else None,
                "early_hold_ready": bool(profile.get("ready")),
                "early_hold_sample_count": len(sample_ids),
                "early_hold_sample_ids": sample_ids,
                "early_hold_sample_ages_days": sample_ages,
                "early_hold_missing_sample_dates": missing_sample_dates,
            })

    scenario_summary: dict[str, Any] = {}
    for days in scenarios:
        pbp_ge5 = early_ge5 = early_ready_ge5 = 0
        for row in profiles:
            candidate_count = sum(1 for age in row["pbp_candidate_ages_days"] if age <= days)
            sample_count = sum(1 for age in row["early_hold_sample_ages_days"] if age <= days)
            pbp_ge5 += int(candidate_count >= MIN_MATCHES)
            early_ge5 += int(sample_count >= MIN_MATCHES)
            early_ready_ge5 += int(row["early_hold_ready"] and sample_count >= MIN_MATCHES)
        scenario_summary[str(days)] = {
            "max_age_days": int(days),
            "pbp_profiles_with_at_least_5_cached_candidates": pbp_ge5,
            "early_hold_profiles_with_at_least_5_selected_samples": early_ge5,
            "currently_ready_early_hold_profiles_retaining_at_least_5_samples": early_ready_ge5,
        }

    all_candidate_ages = [age for row in profiles for age in row["pbp_candidate_ages_days"]]
    all_sample_ages = [age for row in profiles for age in row["early_hold_sample_ages_days"]]
    return {
        "available": bool(pbp_index),
        "profiles": len(profiles),
        "profiles_with_pbp_index": sum(1 for row in profiles if row["pbp_index_found"]),
        "profiles_with_early_hold_samples": sum(1 for row in profiles if row["early_hold_sample_count"] > 0),
        "currently_ready_early_hold_profiles": sum(1 for row in profiles if row["early_hold_ready"]),
        "early_hold_sample_dates_resolved": len(all_sample_ages),
        "early_hold_sample_dates_missing": sum(len(row["early_hold_missing_sample_dates"]) for row in profiles),
        "early_hold_oldest_sample_age_days": max(all_sample_ages) if all_sample_ages else None,
        "pbp_oldest_candidate_age_days": max(all_candidate_ages) if all_candidate_ages else None,
        "scenarios": scenario_summary,
        "details": profiles,
        "policy": {
            "source": "existing data/cache/pbp_v7 player index + current results early_hold_v7.sample_ids",
            "live_tennis_api_calls": 0,
            "production_cache_writes": 0,
            "pbp_authorized_as_main_history": False,
            "early_hold_algorithm_changed": False,
            "early_hold_score_recomputed": False,
        },
    }


def build_report(
    long_df: pd.DataFrame,
    results: list[dict[str, Any]],
    pbp_index: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    stamp = now or datetime.now(timezone.utc)
    return {
        "version": VERSION,
        "generated_at": stamp.isoformat(),
        "policy": {
            "audit_only": True,
            "shadow_counterfactual_only": True,
            "runtime_change": False,
            "model_math_changed": False,
            "probability_policy_changed": False,
            "thresholds_changed": False,
            "weights_changed": False,
            "training_changed": False,
            "player_dna_changed": False,
            "surface_elo_changed": False,
            "symphony_changed": False,
            "neuron_changed": False,
            "playable_changed": False,
            "settlement_changed": False,
            "shadow_prod_promotion": False,
            "ineed_calculations_changed": False,
            "history_sources_changed": False,
            "live_tennis_api_calls": 0,
            "production_cache_writes": 0,
            "global_surface_priors_recomputed_per_scenario": False,
        },
        "task019_frozen_baseline_evidence": TASK019_BASELINE_EVIDENCE,
        "current_player_history": build_current_history_counterfactual(long_df, results),
        "pbp_early_hold_freshness": build_pbp_freshness(results, pbp_index or {}),
        "decision": {
            "production_cutoff_selected": False,
            "production_change_authorized": False,
            "reason": "LOGIC-01 measures counterfactual evidence only. Any cutoff/policy choice requires separate review and later promotion authorization.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LOGIC-01 history freshness counterfactual")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--pbp-index", type=Path, default=PBP_INDEX_PATH)
    parser.add_argument("--output", type=Path, default=ARTIFACT_PATH)
    args = parser.parse_args()

    raw = load_cached_history()
    if raw is None or raw.empty:
        raise SystemExit("production history cache unavailable")
    cleaned, _ = clean_history(raw)
    long_df = model.normalize_matches(cleaned)
    results = _result_rows(_load_json(args.results, []))
    if not results:
        raise SystemExit("current results snapshot unavailable or empty")
    pbp_index = _load_json(args.pbp_index, {})
    if not pbp_index:
        raise SystemExit("PBP player index unavailable")

    report = build_report(long_df, results, pbp_index)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "baseline": report["current_player_history"]["baseline"],
        "scenarios": {
            key: {
                "profiles_ge5": value["profiles_with_minimum_5_retained"],
                "model_ready": value["model_ready_matches"],
                "model_ready_lost": value["baseline_model_ready_lost"],
                "common_output_delta": value["common_set_output_delta"],
            }
            for key, value in report["current_player_history"]["scenarios"].items()
        },
        "pbp": {
            "profiles_with_pbp_index": report["pbp_early_hold_freshness"]["profiles_with_pbp_index"],
            "profiles_with_early_hold_samples": report["pbp_early_hold_freshness"]["profiles_with_early_hold_samples"],
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
