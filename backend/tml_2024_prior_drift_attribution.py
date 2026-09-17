from __future__ import annotations

"""TASK 019: attribute TASK 018 unrelated profile drift to surface priors.

This is audit-only. It reuses the locked TASK 017 candidate and TASK 018
baseline/augmented comparison, then performs a counterfactual check: for each
untouched player whose profile changed, keep the baseline player history fixed
and inject only the augmented surface priors. If that reproduces the augmented
profile exactly, the drift is attributable to prior shrinkage rather than hidden
candidate rows or a model/resolver change.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import pandas as pd

try:
    from . import model, update
    from . import tml_2024_runtime_equivalence_audit as task018
    from . import tml_2024_candidate_lock as task017
    from . import tml_2024_history_preview as task014
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
except ImportError:  # pragma: no cover
    import model, update
    import tml_2024_runtime_equivalence_audit as task018
    import tml_2024_candidate_lock as task017
    import tml_2024_history_preview as task014
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_MANIFEST = ROOT / "audits" / "tml_2024_candidate_lock_manifest.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "tml_2024_prior_drift_attribution.json"
VERSION = "task-019-tml-2024-prior-drift-attribution-v1"
MIN_MATCHES = task014.MIN_MATCHES

PROFILE_ROOTS = {"p1_stats", "p2_stats"}
MARKET_OR_ACTIONABLE_ROOTS = {
    "pick_first_set", "score_first_set", "score_over85", "score_lead_after6",
    "score_joint_builder", "model_confidence", "model_ready", "service_model",
    "game_states", "first_set_win", "second_set_win", "second_set_context",
    "third_set_win", "over_under", "exact_first_set", "match_over_under",
    "expected_match_games", "match_win", "total_sets", "exact_match_score",
    "joint_builder_v78b",
}


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def _root(path: str) -> str:
    return str(path).split(".", 1)[0].split("[", 1)[0]


def _get_path(value: Any, path: str) -> Any:
    current = value
    for part in str(path).split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if pd.notna(out) else None


def _fixture_marker(fixture: dict[str, Any]) -> tuple[Any, ...]:
    if fixture.get("id") is not None:
        return ("id", fixture.get("id"))
    return (
        "fallback",
        fixture.get("scheduled_time"),
        fixture.get("p1"),
        fixture.get("p2"),
        fixture.get("tournament"),
    )


def _counterfactual_profile(
    *,
    baseline_long: pd.DataFrame,
    fixture: dict[str, Any],
    player: str,
    augmented_priors: dict[str, Any],
) -> dict[str, Any]:
    surface = str(fixture.get("surface") or "").lower()
    cut = model._naive_cutoff(fixture.get("scheduled_time"))
    return model.player_profile(baseline_long, player, surface, cut, augmented_priors)


def _changed_value_rows(
    baseline_projection: dict[str, Any],
    augmented_projection: dict[str, Any],
    changed_paths: list[str],
) -> list[dict[str, Any]]:
    rows = []
    for path in changed_paths:
        before = _get_path(baseline_projection, path)
        after = _get_path(augmented_projection, path)
        before_num = _number(before)
        after_num = _number(after)
        delta = None if before_num is None or after_num is None else after_num - before_num
        rows.append({
            "path": path,
            "root": _root(path),
            "baseline": task018._normalize(before),
            "augmented": task018._normalize(after),
            "delta": delta,
            "abs_delta": abs(delta) if delta is not None else None,
        })
    return rows


def build_report(
    *,
    baseline_raw: pd.DataFrame,
    results: list[dict[str, Any]],
    archive_frames: dict[str, pd.DataFrame],
    source_status: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    task018_report = task018.build_report(
        baseline_raw=baseline_raw,
        results=results,
        archive_frames=archive_frames,
        source_status=source_status,
        manifest=manifest,
    )

    baseline_clean, _ = clean_history(baseline_raw)
    candidate, candidate_lock = task018._materialize_locked_candidate(
        baseline_clean=baseline_clean,
        archive_frames=archive_frames,
        manifest=manifest,
    )
    augmented_clean, _ = clean_history(pd.concat([baseline_raw, candidate], ignore_index=True, sort=False))
    baseline_long = model.normalize_matches(baseline_clean)
    augmented_long = model.normalize_matches(augmented_clean)

    fixture_map = {}
    for row in results:
        fixture = task018._fixture_from_result(row)
        fixture_map[_fixture_marker(fixture)] = fixture

    cases: list[dict[str, Any]] = []
    profile_only_cases = 0
    non_profile_cases = 0
    actionable_cases = 0
    prior_only_cases = 0
    prior_attribution_failures: list[dict[str, Any]] = []
    baseline_ready_cases = 0
    augmented_ready_cases = 0
    max_abs_delta: dict[str, float] = defaultdict(float)

    for item in task018_report.get("unrelated_output_changes") or []:
        marker = ("id", item.get("match_id")) if item.get("match_id") is not None else (
            "fallback", item.get("scheduled_time"), item.get("p1"), item.get("p2"), None
        )
        fixture = fixture_map.get(marker)
        if fixture is None:
            # Fallback scan only for rare id-less fixtures.
            fixture = next((
                value for value in fixture_map.values()
                if value.get("scheduled_time") == item.get("scheduled_time")
                and value.get("p1") == item.get("p1")
                and value.get("p2") == item.get("p2")
            ), None)
        if fixture is None:
            prior_attribution_failures.append({"match_id": item.get("match_id"), "reason": "fixture_not_found"})
            continue

        baseline_result = task018._production_precalibration(baseline_long, fixture)
        augmented_result = task018._production_precalibration(augmented_long, fixture)
        baseline_projection = task018._generated_projection(baseline_result)
        augmented_projection = task018._generated_projection(augmented_result)
        changed_paths = task018._diff_paths(baseline_projection, augmented_projection)
        profile_paths = [path for path in changed_paths if _root(path) in PROFILE_ROOTS]
        non_profile_paths = [path for path in changed_paths if _root(path) not in PROFILE_ROOTS]
        actionable_paths = [path for path in changed_paths if _root(path) in MARKET_OR_ACTIONABLE_ROOTS]
        profile_only = bool(changed_paths and len(profile_paths) == len(changed_paths))

        baseline_priors = task018._prior_snapshot(baseline_long, fixture)
        augmented_priors = task018._prior_snapshot(augmented_long, fixture)
        prior_changed_paths = task018._diff_paths(baseline_priors, augmented_priors)

        side_attribution = {}
        all_changed_sides_attributed = True
        for side in ("p1", "p2"):
            stats_key = f"{side}_stats"
            side_changed = any(path.startswith(stats_key + ".") or path == stats_key for path in changed_paths)
            if not side_changed:
                side_attribution[side] = {"changed": False, "prior_only_reproduced": True}
                continue
            player = str(fixture.get(side) or "")
            counterfactual = _counterfactual_profile(
                baseline_long=baseline_long,
                fixture=fixture,
                player=player,
                augmented_priors=augmented_priors,
            )
            augmented_stats = augmented_result.get(stats_key) or {}
            reproduced = task018._canonical(counterfactual) == task018._canonical(augmented_stats)
            side_attribution[side] = {
                "changed": True,
                "player": player,
                "prior_only_reproduced": reproduced,
                "counterfactual_diff_paths": task018._diff_paths(counterfactual, augmented_stats)[:40],
            }
            if not reproduced:
                all_changed_sides_attributed = False

        prior_only_attributed = bool(profile_only and prior_changed_paths and all_changed_sides_attributed)
        values = _changed_value_rows(baseline_projection, augmented_projection, changed_paths)
        for row in values:
            if row["abs_delta"] is not None:
                max_abs_delta[row["path"]] = max(max_abs_delta[row["path"]], float(row["abs_delta"]))

        case = {
            "match_id": fixture.get("id"),
            "scheduled_time": fixture.get("scheduled_time"),
            "surface": fixture.get("surface"),
            "p1": fixture.get("p1"),
            "p2": fixture.get("p2"),
            "baseline_model_ready": bool(baseline_result.get("model_ready")),
            "augmented_model_ready": bool(augmented_result.get("model_ready")),
            "profile_only_change": profile_only,
            "changed_paths_count": len(changed_paths),
            "profile_changed_paths": profile_paths,
            "non_profile_changed_paths": non_profile_paths,
            "actionable_changed_paths": actionable_paths,
            "surface_prior_changed_paths": prior_changed_paths,
            "prior_only_attributed": prior_only_attributed,
            "side_attribution": side_attribution,
            "changed_values": values,
        }
        cases.append(case)

        if case["baseline_model_ready"]:
            baseline_ready_cases += 1
        if case["augmented_model_ready"]:
            augmented_ready_cases += 1
        if profile_only:
            profile_only_cases += 1
        else:
            non_profile_cases += 1
        if actionable_paths:
            actionable_cases += 1
        if prior_only_attributed:
            prior_only_cases += 1
        else:
            prior_attribution_failures.append(case)

    strict_unrelated = int(task018_report["summary"]["unrelated_output_change_matches"])
    attribution_complete = bool(
        len(cases) == strict_unrelated
        and not prior_attribution_failures
        and prior_only_cases == strict_unrelated
    )
    actionable_isolation_gate = bool(
        attribution_complete
        and non_profile_cases == 0
        and actionable_cases == 0
        and baseline_ready_cases == 0
        and augmented_ready_cases == 0
        and int(task018_report["summary"]["identity_changes"]) == 0
        and int(task018_report["summary"]["lost_model_ready_matches"]) == 0
    )

    return {
        "version": VERSION,
        "policy": {
            "live_tennis_api_calls": 0,
            "tennismylife_requests": len(task014.TML_2024_SOURCES),
            "production_cache_writes": 0,
            "temporary_or_memory_only": True,
            "fuzzy_matching": False,
            "manual_aliases": False,
            "cross_provider_id_comparison": False,
            "minimum_match_gate": MIN_MATCHES,
            "minimum_match_gate_changed": False,
            "identity_resolver_changed": False,
            "history_hygiene_changed": False,
            "model_math_changed": False,
            "runtime_change_authorized": False,
            "archive_data_authorized_for_runtime": False,
            "tml_sources_changed": False,
        },
        "summary": {
            "task018_strict_runtime_equivalence_gate_passed": bool(task018_report["summary"]["runtime_equivalence_gate_passed"]),
            "strict_unrelated_output_change_matches": strict_unrelated,
            "profile_only_unrelated_change_matches": profile_only_cases,
            "non_profile_unrelated_change_matches": non_profile_cases,
            "actionable_market_probability_change_matches": actionable_cases,
            "prior_only_attributed_matches": prior_only_cases,
            "prior_attribution_failures": len(prior_attribution_failures),
            "unrelated_baseline_model_ready_matches": baseline_ready_cases,
            "unrelated_augmented_model_ready_matches": augmented_ready_cases,
            "identity_changes": int(task018_report["summary"]["identity_changes"]),
            "lost_model_ready_matches": int(task018_report["summary"]["lost_model_ready_matches"]),
            "newly_model_ready_matches": int(task018_report["summary"]["newly_model_ready_matches"]),
            "locked_candidate_verified": bool(task018_report["summary"]["locked_candidate_verified"]),
            "locked_candidate_rows": int(task018_report["summary"]["locked_candidate_rows"]),
            "attribution_complete": attribution_complete,
            "actionable_isolation_gate_passed": actionable_isolation_gate,
        },
        "task018_summary": task018_report["summary"],
        "candidate_lock": candidate_lock,
        "max_abs_delta_by_path": dict(sorted(max_abs_delta.items())),
        "cases": cases,
        "prior_attribution_failures": prior_attribution_failures,
        "decision": {
            "runtime_change": False,
            "authorize_2024_archive": False,
            "integration_authorized": False,
            "strict_equivalence_passed": bool(task018_report["summary"]["runtime_equivalence_gate_passed"]),
            "actionable_isolation_gate_passed": actionable_isolation_gate,
            "separate_integration_review_required": True,
            "reason": (
                "TASK 019 attributed all strict unrelated drift to surface-prior shrinkage of non-model-ready player profiles, with zero unrelated market/probability paths; strict full-output equivalence remains false and no runtime integration is authorized."
                if actionable_isolation_gate else
                "TASK 019 could not fully isolate TASK 018 drift to non-actionable prior-only profile changes; integration remains fail-closed."
            ),
        },
    }


def run(
    *,
    results_path: Path = DEFAULT_RESULTS,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_path: Path = DEFAULT_OUTPUT,
    downloader: Callable[[str], pd.DataFrame] = update.download_csv,
) -> dict[str, Any]:
    baseline_raw = load_cached_history()
    results = task018._results_list(_read_json(results_path, []))
    manifest = _read_json(manifest_path, {})
    archive_frames, source_status = task018._download_locked_sources(downloader)
    report = build_report(
        baseline_raw=baseline_raw,
        results=results,
        archive_frames=archive_frames,
        source_status=source_status,
        manifest=manifest,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Attribute TML 2024 untouched-profile drift to surface priors")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(results_path=args.results, manifest_path=args.manifest, output_path=args.output)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True))

    summary = report["summary"]
    if report["decision"]["runtime_change"]:
        return 2
    if not summary["locked_candidate_verified"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
