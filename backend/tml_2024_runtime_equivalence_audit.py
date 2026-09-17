from __future__ import annotations

"""TASK 018: audit-only runtime-equivalence / blast-radius check for locked TML 2024.

The locked TASK 017 candidate is materialized only in memory. The audit compares
current production pre-calibration model output on the existing cached history
against the same output on cached history + the locked candidate.

No runtime source is changed, no production cache is written, and no model,
resolver, threshold, weight, training, Player DNA, Surface Elo, Symphony,
Neuron, PLAYABLE, settlement, SHADOW/PROD or iNeed$ code is modified.
"""

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

import pandas as pd

try:
    from . import model, update
    from . import tml_2024_candidate_lock as task017
    from . import tml_2024_history_preview as task014
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
    from .prediction_integrity_v78a import apply_pre_output_guards
    from .joint_builder_v78b import add_joint_builder
except ImportError:  # pragma: no cover
    import model, update
    import tml_2024_candidate_lock as task017
    import tml_2024_history_preview as task014
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history
    from prediction_integrity_v78a import apply_pre_output_guards
    from joint_builder_v78b import add_joint_builder


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_MANIFEST = ROOT / "audits" / "tml_2024_candidate_lock_manifest.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "tml_2024_runtime_equivalence_audit.json"
VERSION = "task-018-tml-2024-runtime-equivalence-audit-v1"
MIN_MATCHES = task014.MIN_MATCHES

FIXTURE_KEYS = (
    "id", "tour", "tournament", "surface", "p1", "p2", "p1_id", "p2_id",
    "p1_rank", "p2_rank", "scheduled_time", "best_of", "feed_status", "event_status",
)


def _read_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
        return value
    except Exception:
        return default


def _results_list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _fixture_from_result(row: dict[str, Any]) -> dict[str, Any]:
    fixture = {key: row.get(key) for key in FIXTURE_KEYS}
    fixture["p1"] = str(fixture.get("p1") or "")
    fixture["p2"] = str(fixture.get("p2") or "")
    return fixture


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _canonical(value: Any) -> str:
    return json.dumps(_normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _diff_paths(left: Any, right: Any, prefix: str = "") -> list[str]:
    left = _normalize(left)
    right = _normalize(right)
    if isinstance(left, dict) and isinstance(right, dict):
        out: list[str] = []
        for key in sorted(set(left) | set(right)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                out.append(path)
            else:
                out.extend(_diff_paths(left[key], right[key], path))
        return out
    if isinstance(left, list) and isinstance(right, list):
        out = []
        for index in range(max(len(left), len(right))):
            path = f"{prefix}[{index}]"
            if index >= len(left) or index >= len(right):
                out.append(path)
            else:
                out.extend(_diff_paths(left[index], right[index], path))
        return out
    return [] if left == right else [prefix or "$" ]


def _generated_projection(result: dict[str, Any]) -> dict[str, Any]:
    """Compare every production pre-calibration field except immutable fixture input."""
    return {key: value for key, value in result.items() if key not in FIXTURE_KEYS}


def _production_precalibration(long_df: pd.DataFrame, fixture: dict[str, Any]) -> dict[str, Any]:
    analysed = model.analyse_match(long_df, fixture)
    guarded = apply_pre_output_guards(analysed)
    return add_joint_builder(guarded)


def _candidate_pre_match_rows(
    candidate_long: pd.DataFrame,
    *,
    resolved_key: str | None,
    scheduled_time: Any,
) -> int:
    if not resolved_key or candidate_long is None or candidate_long.empty:
        return 0
    if "player_key" not in candidate_long.columns:
        return 0
    rows = candidate_long[candidate_long["player_key"].eq(resolved_key)]
    if rows.empty:
        return 0
    cut = model._naive_cutoff(scheduled_time)
    if cut is not None and "date" in rows.columns:
        rows = rows[rows["date"].notna() & rows["date"].le(cut)]
    return int(len(rows))


def _player_evidence(
    *,
    player: str,
    scheduled_time: Any,
    baseline_long: pd.DataFrame,
    augmented_long: pd.DataFrame,
    candidate_long: pd.DataFrame,
    baseline_stats: dict[str, Any],
    augmented_stats: dict[str, Any],
) -> dict[str, Any]:
    baseline_key, baseline_mode = model._resolve_history_player_key(baseline_long, player)
    augmented_key, augmented_mode = model._resolve_history_player_key(augmented_long, player)
    candidate_rows = _candidate_pre_match_rows(
        candidate_long,
        resolved_key=augmented_key,
        scheduled_time=scheduled_time,
    )
    return {
        "player": player,
        "baseline_resolved_key": baseline_key,
        "augmented_resolved_key": augmented_key,
        "baseline_identity_mode": baseline_mode,
        "augmented_identity_mode": augmented_mode,
        "identity_stable": baseline_key == augmented_key and baseline_mode == augmented_mode,
        "candidate_pre_match_rows_for_resolved_key": candidate_rows,
        "direct_candidate_history_touched": candidate_rows > 0,
        "baseline_profile_matches": int((baseline_stats or {}).get("matches") or 0),
        "augmented_profile_matches": int((augmented_stats or {}).get("matches") or 0),
        "profile_match_delta": int((augmented_stats or {}).get("matches") or 0) - int((baseline_stats or {}).get("matches") or 0),
        "baseline_quality": (baseline_stats or {}).get("quality"),
        "augmented_quality": (augmented_stats or {}).get("quality"),
    }


def _prior_snapshot(long_df: pd.DataFrame, fixture: dict[str, Any]) -> dict[str, Any]:
    history_df = model._dated_history(long_df)
    surface = str(fixture.get("surface") or "").lower()
    cut = model._naive_cutoff(fixture.get("scheduled_time"))
    return model._core._surface_priors(history_df, surface, cut)


def _classify_output_change(
    *,
    baseline_projection: dict[str, Any],
    augmented_projection: dict[str, Any],
    direct_history_touched: bool,
    prior_changed: bool,
) -> dict[str, Any]:
    changed_paths = _diff_paths(baseline_projection, augmented_projection)
    output_changed = bool(changed_paths)
    unrelated = bool(output_changed and not direct_history_touched)
    return {
        "output_changed": output_changed,
        "direct_history_touched": bool(direct_history_touched),
        "prior_changed": bool(prior_changed),
        "unrelated_output_change": unrelated,
        "changed_paths_count": len(changed_paths),
        "changed_paths": changed_paths[:80],
    }


def _download_locked_sources(
    downloader: Callable[[str], pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    frames: dict[str, pd.DataFrame] = {}
    status: list[dict[str, Any]] = []
    for source in task014.TML_2024_SOURCES:
        try:
            frame = downloader(source["url"])
            if frame is None or frame.empty:
                raise RuntimeError("empty_csv")
            frames[source["key"]] = frame
            status.append({
                "key": source["key"],
                "tour": source["tour"],
                "url": source["url"],
                "fetch_success": True,
                "rows": int(len(frame)),
                "error": None,
            })
        except Exception as exc:
            status.append({
                "key": source["key"],
                "tour": source["tour"],
                "url": source["url"],
                "fetch_success": False,
                "rows": 0,
                "error": type(exc).__name__,
            })
    return frames, status


def _materialize_locked_candidate(
    *,
    baseline_clean: pd.DataFrame,
    archive_frames: dict[str, pd.DataFrame],
    manifest: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    archive_raw = task017._annotated_archive(archive_frames)
    task016_candidate, materialization = task017._materialize_task016_manifest_candidate(
        baseline_clean=baseline_clean,
        archive_raw=archive_raw,
        manifest=manifest,
    )
    candidate, hardening = task017._apply_global_hardening(task016_candidate, manifest)
    source_fp = task017._source_fingerprints(archive_frames)
    expectation = task017._expectation_check(
        manifest=manifest,
        candidate=candidate,
        source_fingerprints=source_fp,
    )
    return candidate, {
        "task016_materialization": materialization,
        "hardening": hardening,
        "source_fingerprints": source_fp,
        "expectation_check": expectation,
    }


def build_report(
    *,
    baseline_raw: pd.DataFrame,
    results: list[dict[str, Any]],
    archive_frames: dict[str, pd.DataFrame],
    source_status: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    baseline_clean, baseline_hygiene = clean_history(baseline_raw)
    candidate, candidate_lock = _materialize_locked_candidate(
        baseline_clean=baseline_clean,
        archive_frames=archive_frames,
        manifest=manifest,
    )
    expectation = candidate_lock["expectation_check"]
    all_sources_fetched = bool(
        len(source_status) == len(task014.TML_2024_SOURCES)
        and all(row.get("fetch_success") for row in source_status)
    )
    locked_candidate_verified = bool(expectation.get("locked") and expectation.get("matches"))

    augmented_raw = pd.concat([baseline_raw, candidate], ignore_index=True, sort=False)
    augmented_clean, augmented_hygiene = clean_history(augmented_raw)
    baseline_long = model.normalize_matches(baseline_clean)
    augmented_long = model.normalize_matches(augmented_clean)
    candidate_long = model.normalize_matches(candidate)

    runtime_source_keys = {str(source.get("key")) for source in update.TML_SOURCES}
    locked_source_keys = {str(source.get("key")) for source in task014.TML_2024_SOURCES}
    runtime_contains_locked_2024 = bool(runtime_source_keys & locked_source_keys)

    fixture_rows: list[dict[str, Any]] = []
    unrelated_changes: list[dict[str, Any]] = []
    direct_changes: list[dict[str, Any]] = []
    identity_changes: list[dict[str, Any]] = []
    newly_ready: list[dict[str, Any]] = []
    lost_ready: list[dict[str, Any]] = []
    unchanged_untouched = 0
    prior_changed_matches = 0
    direct_touched_matches = 0
    surfaces_with_prior_change: Counter[str] = Counter()
    touched_players: set[str] = set()

    for row in results:
        fixture = _fixture_from_result(row)
        if not fixture["p1"] or not fixture["p2"]:
            continue

        baseline_result = _production_precalibration(baseline_long, fixture)
        augmented_result = _production_precalibration(augmented_long, fixture)
        baseline_projection = _generated_projection(baseline_result)
        augmented_projection = _generated_projection(augmented_result)

        p1 = _player_evidence(
            player=fixture["p1"],
            scheduled_time=fixture.get("scheduled_time"),
            baseline_long=baseline_long,
            augmented_long=augmented_long,
            candidate_long=candidate_long,
            baseline_stats=baseline_result.get("p1_stats") or {},
            augmented_stats=augmented_result.get("p1_stats") or {},
        )
        p2 = _player_evidence(
            player=fixture["p2"],
            scheduled_time=fixture.get("scheduled_time"),
            baseline_long=baseline_long,
            augmented_long=augmented_long,
            candidate_long=candidate_long,
            baseline_stats=baseline_result.get("p2_stats") or {},
            augmented_stats=augmented_result.get("p2_stats") or {},
        )
        for player in (p1, p2):
            if player["direct_candidate_history_touched"]:
                touched_players.add(str(player["player"]))

        direct_touched = bool(p1["direct_candidate_history_touched"] or p2["direct_candidate_history_touched"])
        identity_stable = bool(p1["identity_stable"] and p2["identity_stable"])
        if direct_touched:
            direct_touched_matches += 1

        baseline_priors = _prior_snapshot(baseline_long, fixture)
        augmented_priors = _prior_snapshot(augmented_long, fixture)
        prior_paths = _diff_paths(baseline_priors, augmented_priors)
        prior_changed = bool(prior_paths)
        if prior_changed:
            prior_changed_matches += 1
            surfaces_with_prior_change[str(fixture.get("surface") or "").lower()] += 1

        change = _classify_output_change(
            baseline_projection=baseline_projection,
            augmented_projection=augmented_projection,
            direct_history_touched=direct_touched,
            prior_changed=prior_changed,
        )
        base_ready = bool(baseline_result.get("model_ready"))
        aug_ready = bool(augmented_result.get("model_ready"))
        summary = {
            "match_id": fixture.get("id"),
            "scheduled_time": fixture.get("scheduled_time"),
            "surface": fixture.get("surface"),
            "p1": fixture["p1"],
            "p2": fixture["p2"],
            "baseline_model_ready": base_ready,
            "augmented_model_ready": aug_ready,
            "p1_evidence": p1,
            "p2_evidence": p2,
            "identity_stable": identity_stable,
            "surface_prior_changed": prior_changed,
            "surface_prior_changed_paths": prior_paths[:40],
            **change,
        }
        fixture_rows.append(summary)

        if not identity_stable:
            identity_changes.append(summary)
        if not base_ready and aug_ready:
            newly_ready.append(summary)
        elif base_ready and not aug_ready:
            lost_ready.append(summary)
        if change["unrelated_output_change"]:
            unrelated_changes.append(summary)
        elif direct_touched and change["output_changed"]:
            direct_changes.append(summary)
        elif not direct_touched and not change["output_changed"]:
            unchanged_untouched += 1

    gate_passed = bool(
        all_sources_fetched
        and locked_candidate_verified
        and not runtime_contains_locked_2024
        and not identity_changes
        and not lost_ready
        and not unrelated_changes
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
            "fail_closed_on_unrelated_output_change": True,
        },
        "summary": {
            "visible_fixtures_audited": len(fixture_rows),
            "all_2024_sources_fetched": all_sources_fetched,
            "locked_candidate_verified": locked_candidate_verified,
            "locked_candidate_rows": int(len(candidate)),
            "runtime_contains_locked_2024_sources": runtime_contains_locked_2024,
            "direct_touched_matches": direct_touched_matches,
            "direct_touched_players": len(touched_players),
            "surface_prior_changed_matches": prior_changed_matches,
            "unrelated_output_change_matches": len(unrelated_changes),
            "direct_output_change_matches": len(direct_changes),
            "unchanged_untouched_matches": unchanged_untouched,
            "identity_changes": len(identity_changes),
            "newly_model_ready_matches": len(newly_ready),
            "lost_model_ready_matches": len(lost_ready),
            "runtime_equivalence_gate_passed": gate_passed,
        },
        "baseline_hygiene": baseline_hygiene,
        "augmented_hygiene": augmented_hygiene,
        "candidate_lock": candidate_lock,
        "surface_prior_change_counts": dict(sorted(surfaces_with_prior_change.items())),
        "unrelated_output_changes": unrelated_changes,
        "direct_output_changes": direct_changes,
        "identity_changes": identity_changes,
        "newly_model_ready_matches": newly_ready,
        "lost_model_ready_matches": lost_ready,
        "fixtures": fixture_rows,
        "decision": {
            "runtime_change": False,
            "authorize_2024_archive": False,
            "integration_authorized": False,
            "runtime_equivalence_gate_passed": gate_passed,
            "separate_mitigation_or_integration_pr_required": True,
            "reason": (
                "TASK 018 is audit-only. A false equivalence gate means locked 2024 history has model-output blast radius outside players with direct candidate rows; no runtime integration is authorized."
                if not gate_passed else
                "TASK 018 found no unrelated pre-calibration output changes for the currently visible fixtures, but runtime integration still requires a separate PR."
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
    results = _results_list(_read_json(results_path, []))
    manifest = _read_json(manifest_path, {})
    archive_frames, source_status = _download_locked_sources(downloader)
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
    parser = argparse.ArgumentParser(description="Audit locked TML 2024 runtime equivalence without runtime integration")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(results_path=args.results, manifest_path=args.manifest, output_path=args.output)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True))

    summary = report["summary"]
    if report["decision"]["runtime_change"]:
        return 2
    if not summary["all_2024_sources_fetched"]:
        return 3
    if not summary["locked_candidate_verified"]:
        return 4
    if summary["runtime_contains_locked_2024_sources"]:
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
