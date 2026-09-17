from __future__ import annotations

"""LOGIC-03 audit-only population/surface prior counterfactual.

Measures the current mixed-population ``_surface_priors`` against ATP / CH / WTA
priors on the exact restored TennisMyLife cache. No runtime or model behavior is
modified; the monkeypatch used for counterfactual analysis exists only inside
this audit process and is always restored.
"""

import argparse
import copy
import json
import math
from contextlib import contextmanager
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
ARTIFACT_PATH = ROOT / "artifacts" / "population_priors_audit.json"
VERSION = "logic-03-population-priors"
POPULATIONS = ("ATP", "CH", "WTA")
PRIOR_METRICS = (
    "won", "hold_rate", "break_rate", "serve_points_won", "return_points_won",
    "first_set_won", "second_set_won", "second_after_first_win",
    "second_after_first_loss", "third_set_won", "first_set_over85",
    "first_set_over95", "first_set_over105", "first_set_over115",
    "first_set_over125",
)
PROFILE_METRICS = (
    "hold_rate", "break_rate", "serve_points_won", "return_points_won",
    "first_set_won", "second_set_won", "second_after_first_win",
    "second_after_first_loss", "third_set_won",
)
CURRENT_OUTPUT_KEYS = (
    "best_of", "model_ready", "quality", "model_confidence", "service_model",
    "game_states", "first_set_win", "second_set_win", "second_set_context",
    "third_set_win", "over_under", "exact_first_set", "match_over_under",
    "expected_match_games", "match_win", "total_sets", "exact_match_score",
    "pick_first_set", "score_first_set", "score_over85", "score_lead_after6",
    "score_joint_builder",
)
EXACT_TOUR_MAP = {
    "ATP": "ATP",
    "WTA": "WTA",
    "CH": "CH",
    "CHALLENGER": "CH",
    "ATP CHALLENGER": "CH",
}


def _read_json(path: Path, fallback):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict) and isinstance(value.get("matches"), list):
        return [row for row in value["matches"] if isinstance(row, dict)]
    return []


def _cutoff(value: Any) -> pd.Timestamp | None:
    cut = model._naive_cutoff(value)
    return pd.Timestamp(cut).normalize() if cut is not None else None


def _fixture_population(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return EXACT_TOUR_MAP.get(text)


def _surface(value: Any) -> str:
    return str(value or "").strip().lower()


def _precut(df: pd.DataFrame, cut: pd.Timestamp | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=getattr(df, "columns", None))
    x = df
    if cut is not None and "date" in x.columns:
        x = x[x["date"].notna() & (x["date"] <= cut)]
    return x


def _prior_support(df: pd.DataFrame, surface: str, cut: pd.Timestamp | None) -> dict[str, Any]:
    pre = _precut(df, cut)
    total_rows = int(len(pre))
    surface_known = bool(surface)
    surface_rows = (
        int((pre["surface"] == surface).sum())
        if surface_known and "surface" in pre.columns else 0
    )
    surface_specific = bool(surface_known and surface_rows >= 100)
    if surface_specific:
        fallback = None
        fallback_reason = None
        used_rows = surface_rows
    else:
        fallback = "all_surfaces_within_input_population"
        fallback_reason = "surface_missing" if not surface_known else "surface_support_below_threshold"
        used_rows = total_rows
    return {
        "pre_cut_rows": total_rows,
        "surface_known": surface_known,
        "surface_rows": surface_rows,
        "production_surface_threshold": 100,
        "surface_specific_used": surface_specific,
        "fallback": fallback,
        "fallback_reason": fallback_reason,
        "rows_used_by_prior_mean": used_rows,
    }


def _priors(df: pd.DataFrame, surface: str, cut: pd.Timestamp | None) -> dict[str, float]:
    return dict(model._core._surface_priors(df, surface, cut))


def _prior_record(df: pd.DataFrame, surface: str, cut: pd.Timestamp | None) -> dict[str, Any]:
    values = _priors(df, surface, cut)
    return {
        "support": _prior_support(df, surface, cut),
        "values": {key: values.get(key) for key in PRIOR_METRICS},
    }


def _metric_deltas(left: dict[str, Any], right: dict[str, Any], keys) -> dict[str, float]:
    out = {}
    for key in keys:
        a, b = left.get(key), right.get(key)
        if isinstance(a, (int, float)) and not isinstance(a, bool) and isinstance(b, (int, float)) and not isinstance(b, bool):
            if math.isfinite(float(a)) and math.isfinite(float(b)):
                out[key] = round(float(b) - float(a), 12)
    return out


def _numeric_leaves(value: Any, prefix: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.update(_numeric_leaves(item, path))
    elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        out[prefix] = float(value)
    return out


def _output_view(result: dict[str, Any]) -> dict[str, Any]:
    return {key: result.get(key) for key in CURRENT_OUTPUT_KEYS}


def _output_delta(baseline: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    left = _numeric_leaves(_output_view(baseline))
    right = _numeric_leaves(_output_view(probe))
    common = sorted(set(left) & set(right))
    changed = [(key, abs(right[key] - left[key])) for key in common if abs(right[key] - left[key]) > 1e-12]
    changed.sort(key=lambda item: item[1], reverse=True)
    return {
        "numeric_common_fields": len(common),
        "changed_numeric_fields": len(changed),
        "max_absolute_delta": round(changed[0][1], 12) if changed else 0.0,
        "largest_deltas": [{"field": key, "absolute_delta": round(delta, 12)} for key, delta in changed[:10]],
    }


def _profile_delta(baseline: dict[str, Any], probe: dict[str, Any], side: str) -> dict[str, Any]:
    left = baseline.get(f"{side}_stats") or {}
    right = probe.get(f"{side}_stats") or {}
    deltas = _metric_deltas(left, right, PROFILE_METRICS)
    changed = {key: value for key, value in deltas.items() if abs(value) > 1e-12}
    return {
        "changed": bool(changed),
        "deltas": changed,
        "max_absolute_delta": round(max((abs(v) for v in changed.values()), default=0.0), 12),
    }


@contextmanager
def _frozen_surface_priors(priors: dict[str, float]):
    original = model._core._surface_priors

    def frozen(*_args, **_kwargs):
        return dict(priors)

    model._core._surface_priors = frozen
    try:
        yield
    finally:
        model._core._surface_priors = original


def _analyse_with_priors(long_df: pd.DataFrame, match: dict[str, Any], priors: dict[str, float]) -> dict[str, Any]:
    with _frozen_surface_priors(priors):
        return model.analyse_match(long_df, copy.deepcopy(match))


def _snapshot_cut(results: list[dict[str, Any]]) -> pd.Timestamp | None:
    cuts = [_cutoff(row.get("scheduled_time")) for row in results]
    cuts = [cut for cut in cuts if cut is not None]
    return max(cuts) if cuts else None


def _prior_table(long_df: pd.DataFrame, results: list[dict[str, Any]]) -> dict[str, Any]:
    cut = _snapshot_cut(results)
    surfaces = sorted({
        _surface(row.get("surface")) for row in results if _surface(row.get("surface"))
    } | {
        str(value).strip().lower()
        for value in long_df.get("surface", pd.Series(dtype="object")).dropna().tolist()
        if str(value).strip()
    })
    table = {}
    for surface in surfaces:
        mixed = _prior_record(long_df, surface, cut)
        row = {"mixed": mixed, "populations": {}}
        for population in POPULATIONS:
            segment = long_df[long_df["source_tour"].astype(str).str.upper() == population].copy()
            record = _prior_record(segment, surface, cut)
            record["delta_vs_mixed"] = _metric_deltas(
                mixed["values"], record["values"],
                ("hold_rate", "break_rate", "serve_points_won", "return_points_won"),
            )
            row["populations"][population] = record
        table[surface] = row
    return {
        "as_of": cut.date().isoformat() if cut is not None else None,
        "surfaces": table,
    }


def _empty_population_effect() -> dict[str, Any]:
    return {
        "eligible_model_ready_fixtures": 0,
        "fixtures_with_output_change": 0,
        "player_profiles_changed": 0,
        "max_current_output_absolute_delta": 0.0,
        "max_profile_metric_absolute_delta": 0.0,
    }


def build_report(
    long_df: pd.DataFrame,
    results: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    stamp = now or datetime.now(timezone.utc)
    prior_table = _prior_table(long_df, results)
    tour_values: dict[str, int] = {}
    mapped_counts = {population: 0 for population in POPULATIONS}
    mapped_ready_counts = {population: 0 for population in POPULATIONS}
    unknown_tours: dict[str, int] = {}
    unknown_ready_tours: dict[str, int] = {}
    fixture_rows = []
    errors = []
    eligible = 0
    output_changed = 0
    profile_changed = 0
    max_output_delta = 0.0
    max_profile_delta = 0.0
    fallback_counts: dict[str, int] = {}
    missing_surface_ready: dict[str, int] = {}
    population_effect = {population: _empty_population_effect() for population in POPULATIONS}

    for match in results:
        ready = bool(match.get("model_ready"))
        raw_tour = str(match.get("tour") or "").strip()
        tour_values[raw_tour] = tour_values.get(raw_tour, 0) + 1
        population = _fixture_population(raw_tour)
        if population is None:
            unknown_tours[raw_tour] = unknown_tours.get(raw_tour, 0) + 1
            if ready:
                unknown_ready_tours[raw_tour] = unknown_ready_tours.get(raw_tour, 0) + 1
            continue
        mapped_counts[population] += 1
        if not ready:
            continue
        mapped_ready_counts[population] += 1

        surface = _surface(match.get("surface"))
        if not surface:
            missing_surface_ready[population] = missing_surface_ready.get(population, 0) + 1
        cut = _cutoff(match.get("scheduled_time"))
        segment = long_df[long_df["source_tour"].astype(str).str.upper() == population].copy()
        support = _prior_support(segment, surface, cut)
        if support["pre_cut_rows"] <= 0:
            errors.append({"match_id": match.get("id"), "reason": "population_segment_has_no_pre_cut_rows", "population": population})
            continue

        try:
            baseline = model.analyse_match(long_df, copy.deepcopy(match))
            segment_priors = _priors(segment, surface, cut)
            probe = _analyse_with_priors(long_df, match, segment_priors)
        except Exception as exc:
            errors.append({"match_id": match.get("id"), "reason": type(exc).__name__, "population": population})
            continue

        eligible += 1
        output = _output_delta(baseline, probe)
        p1 = _profile_delta(baseline, probe, "p1")
        p2 = _profile_delta(baseline, probe, "p2")
        changed_profiles = int(p1["changed"]) + int(p2["changed"])
        fixture_output_changed = int(output["changed_numeric_fields"] > 0)
        output_changed += fixture_output_changed
        profile_changed += changed_profiles
        max_output_delta = max(max_output_delta, output["max_absolute_delta"])
        max_profile_delta = max(max_profile_delta, p1["max_absolute_delta"], p2["max_absolute_delta"])
        fallback_reason = support["fallback_reason"] or "surface_specific"
        fallback_counts[fallback_reason] = fallback_counts.get(fallback_reason, 0) + 1

        effect = population_effect[population]
        effect["eligible_model_ready_fixtures"] += 1
        effect["fixtures_with_output_change"] += fixture_output_changed
        effect["player_profiles_changed"] += changed_profiles
        effect["max_current_output_absolute_delta"] = round(
            max(effect["max_current_output_absolute_delta"], output["max_absolute_delta"]), 12
        )
        effect["max_profile_metric_absolute_delta"] = round(
            max(effect["max_profile_metric_absolute_delta"], p1["max_absolute_delta"], p2["max_absolute_delta"]), 12
        )

        mixed_priors = _priors(long_df, surface, cut)
        fixture_rows.append({
            "match_id": match.get("id"),
            "scheduled_time": match.get("scheduled_time"),
            "tour_raw": raw_tour,
            "population": population,
            "surface": surface,
            "stored_model_ready": ready,
            "baseline_recomputed_model_ready": bool(baseline.get("model_ready")),
            "population_probe_model_ready": bool(probe.get("model_ready")),
            "population_prior_support": support,
            "mixed_priors": mixed_priors,
            "population_priors": segment_priors,
            "prior_deltas_population_minus_mixed": _metric_deltas(
                mixed_priors, segment_priors,
                ("hold_rate", "break_rate", "serve_points_won", "return_points_won"),
            ),
            "profiles_changed": changed_profiles,
            "p1_profile_delta": p1,
            "p2_profile_delta": p2,
            "output_delta": output,
        })

    return {
        "version": VERSION,
        "generated_at": stamp.isoformat(),
        "policy": {
            "audit_only": True,
            "shadow_only": True,
            "runtime_change": False,
            "model_math_changed": False,
            "probability_changed": False,
            "thresholds_changed": False,
            "weights_changed": False,
            "training_changed": False,
            "player_dna_changed": False,
            "surface_elo_changed": False,
            "symphony_changed": False,
            "neuron_changed": False,
            "playable_changed": False,
            "settlement_changed": False,
            "ineed_calculations_changed": False,
            "live_tennis_api_calls": 0,
            "production_cache_writes": 0,
            "production_surface_support_threshold_changed": False,
        },
        "production_contract": {
            "surface_prior_owner": "model_core._surface_priors",
            "surface_support_threshold": 100,
            "current_population_behavior": "mixed ATP/CH/WTA source rows; no source_tour segmentation",
            "surface_behavior": "known surface subset only when >=100 pre-cut rows; missing surface or insufficient support falls back to all rows in the input dataframe",
        },
        "sources": {
            "history": "exact restored TennisMyLife cache used by update.py",
            "population_field": "source_tour from update.TML_SOURCES",
            "population_values": list(POPULATIONS),
            "fixture_tour_mapping": EXACT_TOUR_MAP,
            "unmapped_fixture_tours_are_not_guessed": True,
        },
        "current_snapshot_priors": prior_table,
        "summary": {
            "visible_matches": len(results),
            "model_ready_matches": sum(bool(row.get("model_ready")) for row in results),
            "fixture_tour_raw_counts": dict(sorted(tour_values.items())),
            "fixture_tour_unknown_counts": dict(sorted(unknown_tours.items())),
            "model_ready_fixture_tour_unknown_counts": dict(sorted(unknown_ready_tours.items())),
            "fixture_population_mapped_counts": mapped_counts,
            "model_ready_fixture_population_mapped_counts": mapped_ready_counts,
            "model_ready_missing_surface_by_population": dict(sorted(missing_surface_ready.items())),
            "eligible_model_ready_counterfactuals": eligible,
            "counterfactual_errors": errors,
            "fixtures_with_output_change": output_changed,
            "player_profiles_changed": profile_changed,
            "max_current_output_absolute_delta": round(max_output_delta, 12),
            "max_profile_metric_absolute_delta": round(max_profile_delta, 12),
            "population_prior_fallback_reason_counts": dict(sorted(fallback_counts.items())),
            "population_counterfactual_effect": population_effect,
        },
        "fixtures": fixture_rows,
        "candidate_hierarchy": {
            "status": "EVIDENCE_ONLY_NOT_PROD",
            "steps": [
                "population+surface when exact fixture population and surface are known and segment has >=100 pre-cut surface rows",
                "population all-surfaces when exact population is known but the surface is missing",
                "population all-surfaces when exact population and surface are known but surface support is <100",
                "mixed production prior only as a last-resort candidate requiring separate validation",
            ],
            "production_change_authorized": False,
            "threshold_100_change_authorized": False,
        },
        "decision": {
            "production_change_authorized": False,
            "population_split_promotion_authorized": False,
            "fallback_policy_promotion_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LOGIC-03 population / priors audit")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--output", type=Path, default=ARTIFACT_PATH)
    args = parser.parse_args()

    raw = load_cached_history()
    if raw is None or raw.empty:
        raise SystemExit("production history cache unavailable")
    cleaned, _ = clean_history(raw)
    long_df = model.normalize_matches(cleaned)
    if "source_tour" not in long_df.columns:
        raise SystemExit("source_tour missing from normalized production history")
    results = _rows(_read_json(args.results, []))
    if not results:
        raise SystemExit("current results snapshot unavailable or empty")

    report = build_report(long_df, results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
