from __future__ import annotations

"""TASK 017: deterministic, audit-only lock for the conservative TML 2024 candidate.

TASK 016 is a frozen audit basis. TASK 017 reproduces that frozen candidate from
explicit manifest rules, applies only evidence-backed hardening exclusions, then
revalidates the result against the *current* baseline/results state. Current
Match Browser drift is therefore a fresh safety gate, not a rewrite of TASK 016.
No production history inputs or runtime/model behavior are changed here.
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

import pandas as pd

try:
    from . import model, update
    from . import tml_2024_history_preview as task014
    from . import tml_2024_integration_safety_gate as task015
    from . import tml_2024_blocker_audit as task016
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
except ImportError:  # pragma: no cover
    import model, update
    import tml_2024_history_preview as task014
    import tml_2024_integration_safety_gate as task015
    import tml_2024_blocker_audit as task016
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_MANIFEST = ROOT / "audits" / "tml_2024_candidate_lock_manifest.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "tml_2024_candidate_lock.json"
VERSION = "task-017-tml-2024-candidate-lock-v3"
MIN_MATCHES = task014.MIN_MATCHES


def _key(value: Any) -> str:
    return model._core._key(value)


def _id_token(value: Any) -> str | None:
    return task015._id_token(value)


def _read_json(path: Path, default: Any) -> Any:
    return task015._read_json(path, default)


def _results_list(value: Any) -> list[dict[str, Any]]:
    return task015._results_list(value)


def _scalar(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else format(value, ".15g")
    return str(value)


def _frame_hash(frame: pd.DataFrame, *, columns: list[str] | None = None, sort_rows: bool = False) -> str:
    if frame is None:
        frame = pd.DataFrame()
    cols = list(columns) if columns is not None else sorted(str(c) for c in frame.columns)
    rows = [[_scalar(row.get(col)) for col in cols] for _, row in frame.iterrows()]
    if sort_rows:
        rows.sort()
    payload = json.dumps({"columns": cols, "rows": rows}, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _annotated_archive(archive_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return task016._annotated_archive(archive_frames)


def _manifest_sources_match(manifest: dict[str, Any]) -> bool:
    expected = [{"key": s["key"], "tour": s["tour"], "url": s["url"]} for s in task014.TML_2024_SOURCES]
    return (manifest.get("sources") or []) == expected


def _score_identity(row: pd.Series) -> tuple[str, ...]:
    return task016._row_identity(row)


def _touches_player(row: pd.Series, blocked: set[str]) -> bool:
    return any(_key(row.get(f"{side}_name")) in blocked for side in ("winner", "loser"))


def _materialize_task016_manifest_candidate(
    *, baseline_clean: pd.DataFrame, archive_raw: pd.DataFrame, manifest: dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Reproduce the frozen TASK 016 candidate from explicit evidence rules."""
    rules = manifest.get("task016_rules") or {}
    year = int(rules.get("year") or 2024)
    dates = task016._parsed_dates(archive_raw)
    year_rows = archive_raw.loc[dates.notna() & dates.dt.year.eq(year)].copy()
    year_clean, hygiene = clean_history(year_rows)

    blocked_players = {str(v) for v in (rules.get("exclude_player_keys") or []) if str(v)}
    blocked_scores = {
        tuple(str(part) for part in identity)
        for identity in (rules.get("exclude_score_identities") or [])
        if isinstance(identity, list)
    }
    keep = []
    counts = Counter()
    for index, row in year_clean.iterrows():
        player_block = _touches_player(row, blocked_players)
        score_block = _score_identity(row) in blocked_scores
        if player_block:
            counts["resolution_change"] += 1
        if score_block:
            counts["score_conflict"] += 1
        if not player_block and not score_block:
            keep.append(index)

    candidate = year_clean.loc[keep].copy()
    candidate, dedupe = task016._dedupe_archive(candidate, baseline_clean)
    return candidate, {
        "year_rows": int(len(year_rows)),
        "year_clean_rows": int(len(year_clean)),
        "hygiene": hygiene,
        "excluded_row_reason_counts": dict(sorted(counts.items())),
        "dedupe": dedupe,
    }


def _id_evidence(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    hardening = manifest.get("global_hardening") or {}
    rows = []
    for item in hardening.get("exclude_archive_id_evidence") or []:
        if not isinstance(item, dict):
            continue
        namespace = str(item.get("namespace") or "").upper().strip()
        player_key = str(item.get("player_key") or "").strip()
        ids = sorted({_id_token(v) for v in (item.get("archive_new_ids") or []) if _id_token(v) is not None})
        if namespace and player_key and ids:
            rows.append({"namespace": namespace, "player_key": player_key, "archive_new_ids": ids})
    return rows


def _row_hits_id_evidence(row: pd.Series, evidence: dict[str, Any]) -> bool:
    if str(row.get("source_tour") or "").upper().strip() != evidence["namespace"]:
        return False
    ids = set(evidence["archive_new_ids"])
    for side in ("winner", "loser"):
        if _key(row.get(f"{side}_name")) != evidence["player_key"]:
            continue
        if _id_token(row.get(f"{side}_id")) in ids:
            return True
    return False


def _apply_global_hardening(candidate: pd.DataFrame, manifest: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    hardening = manifest.get("global_hardening") or {}
    shadow_keys = {str(v).strip() for v in (hardening.get("exclude_exact_shadow_player_keys") or []) if str(v).strip()}
    resolution_keys = {
        str(v).strip() for v in (hardening.get("exclude_visible_resolution_player_keys") or []) if str(v).strip()
    }
    id_evidence = _id_evidence(manifest)
    id_hits = [0 for _ in id_evidence]
    shadow_hits = {key: 0 for key in sorted(shadow_keys)}
    resolution_hits = {key: 0 for key in sorted(resolution_keys)}
    reason_counts = Counter()
    keep = []

    for index, row in candidate.iterrows():
        blocked = False
        row_keys = {_key(row.get(f"{side}_name")) for side in ("winner", "loser")}

        touched_shadow = row_keys & shadow_keys
        if touched_shadow:
            blocked = True
            reason_counts["exact_shadow"] += 1
            for key in touched_shadow:
                shadow_hits[key] += 1

        touched_resolution = row_keys & resolution_keys
        if touched_resolution:
            blocked = True
            reason_counts["visible_resolution_change"] += 1
            for key in touched_resolution:
                resolution_hits[key] += 1

        for pos, evidence in enumerate(id_evidence):
            if _row_hits_id_evidence(row, evidence):
                blocked = True
                reason_counts["archive_id_conflict"] += 1
                id_hits[pos] += 1

        if not blocked:
            keep.append(index)

    final = candidate.loc[keep].copy()
    id_match_rows = [{**evidence, "matched_rows": id_hits[pos]} for pos, evidence in enumerate(id_evidence)]
    unmatched_id = [row for row in id_match_rows if row["matched_rows"] <= 0]
    unmatched_shadow = [key for key, count in shadow_hits.items() if count <= 0]
    unmatched_resolution = [key for key, count in resolution_hits.items() if count <= 0]
    return final, {
        "input_rows": int(len(candidate)),
        "output_rows": int(len(final)),
        "removed_rows": int(len(candidate) - len(final)),
        "reason_counts": dict(sorted(reason_counts.items())),
        "id_evidence_matches": id_match_rows,
        "shadow_evidence_matches": shadow_hits,
        "visible_resolution_evidence_matches": resolution_hits,
        "unmatched_id_evidence": unmatched_id,
        "unmatched_shadow_evidence": unmatched_shadow,
        "unmatched_visible_resolution_evidence": unmatched_resolution,
        "all_evidence_matched": not unmatched_id and not unmatched_shadow and not unmatched_resolution,
    }


def _all_player_keys(frame: pd.DataFrame) -> set[str]:
    long_df = model.normalize_matches(frame)
    if long_df is None or long_df.empty or "player_key" not in long_df.columns:
        return set()
    return {str(v).strip() for v in long_df["player_key"].dropna().unique().tolist() if str(v).strip()}


def _global_id_conflicts(baseline_clean: pd.DataFrame, candidate: pd.DataFrame) -> list[dict[str, Any]]:
    keys = _all_player_keys(baseline_clean) | _all_player_keys(candidate)
    return task016._classify_id_conflicts(baseline_clean, candidate, keys)


def _token_index(keys: set[str]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for key in keys:
        for token in set(key.split()):
            index[token].add(key)
    return index


def _exact_shadow_collisions(baseline_clean: pd.DataFrame, candidate: pd.DataFrame) -> list[dict[str, Any]]:
    baseline_keys = _all_player_keys(baseline_clean)
    candidate_keys = _all_player_keys(candidate)
    token_index = _token_index(baseline_keys)
    rows = []
    for archive_key in sorted(candidate_keys - baseline_keys):
        pool: set[str] = set()
        for token in archive_key.split():
            pool.update(token_index.get(token, set()))
        matches = sorted(key for key in pool if model._history_name_variant_matches(archive_key, key))
        if matches:
            rows.append({
                "archive_exact_key": archive_key,
                "baseline_variant_candidates": matches,
                "baseline_resolution_before": "expanded-name" if len(matches) == 1 else "ambiguous",
                "resolution_after_candidate": "exact",
            })
    return rows


def _candidate_model_columns() -> list[str]:
    return ["source_key", "source_tour", *task015.MODEL_HISTORY_COLUMNS, "winner_id", "loser_id"]


def _source_fingerprints(archive_frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows = []
    for source in task014.TML_2024_SOURCES:
        frame = archive_frames.get(source["key"])
        rows.append({
            "source_key": source["key"],
            "source_tour": source["tour"],
            "source_url": source["url"],
            "rows": int(len(frame)) if frame is not None else 0,
            "logical_sha256": _frame_hash(frame if frame is not None else pd.DataFrame(), sort_rows=False),
        })
    return rows


def _source_counts(candidate: pd.DataFrame) -> dict[str, int]:
    return {
        source["key"]: int(candidate["source_key"].eq(source["key"]).sum())
        if candidate is not None and not candidate.empty and "source_key" in candidate.columns else 0
        for source in task014.TML_2024_SOURCES
    }


def _expectation_check(
    *, manifest: dict[str, Any], candidate: pd.DataFrame, source_fingerprints: list[dict[str, Any]]
) -> dict[str, Any]:
    expected = manifest.get("expected") if isinstance(manifest.get("expected"), dict) else {}
    current = {
        "candidate_rows": int(len(candidate)),
        "source_counts": _source_counts(candidate),
        "candidate_logical_sha256": _frame_hash(candidate, columns=_candidate_model_columns(), sort_rows=True),
        "source_logical_sha256": {row["source_key"]: row["logical_sha256"] for row in source_fingerprints},
    }
    required = {"candidate_rows", "source_counts", "candidate_logical_sha256", "source_logical_sha256"}
    locked = required.issubset(expected)
    mismatches = {}
    if locked:
        for key in sorted(required):
            if expected.get(key) != current.get(key):
                mismatches[key] = {"expected": expected.get(key), "current": current.get(key)}
    return {
        "locked": locked,
        "matches": bool(locked and not mismatches),
        "mismatches": mismatches,
        "current": current,
        "expected": expected,
    }


def _task016_frozen_shape_matches(manifest: dict[str, Any], candidate: pd.DataFrame) -> bool:
    shape = manifest.get("task016_expected_shape") or {}
    return bool(
        int(shape.get("candidate_rows") or -1) == int(len(candidate))
        and (shape.get("source_counts") or {}) == _source_counts(candidate)
    )


def build_report(
    *,
    baseline_raw: pd.DataFrame,
    results: list[dict[str, Any]],
    archive_frames: dict[str, pd.DataFrame],
    manifest: dict[str, Any],
    source_status: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source_status = source_status or []
    baseline_clean, baseline_hygiene = clean_history(baseline_raw)
    archive_raw = _annotated_archive(archive_frames)

    task016_manifest_candidate, materialization = _materialize_task016_manifest_candidate(
        baseline_clean=baseline_clean, archive_raw=archive_raw, manifest=manifest
    )
    frozen_shape_matches = _task016_frozen_shape_matches(manifest, task016_manifest_candidate)

    # Diagnostic only: the current visible match universe may legitimately differ
    # from the one used when TASK 016 was merged. Drift here must never rewrite the
    # frozen TASK 016 evidence; current safety is checked again below on `candidate`.
    current_task016 = task016._safe_subset(
        baseline_raw=baseline_raw,
        baseline_clean=baseline_clean,
        archive_raw=archive_raw,
        results=results,
    )
    current_task016_candidate = current_task016.pop("safe_archive_clean")
    current_dynamic_matches_frozen = bool(
        len(task016_manifest_candidate) == len(current_task016_candidate)
        and _frame_hash(task016_manifest_candidate, columns=_candidate_model_columns(), sort_rows=True)
        == _frame_hash(current_task016_candidate, columns=_candidate_model_columns(), sort_rows=True)
    )

    candidate, hardening = _apply_global_hardening(task016_manifest_candidate, manifest)
    global_id = _global_id_conflicts(baseline_clean, candidate)
    archive_global_id = [row for row in global_id if row.get("archive_involved")]
    exact_shadow = _exact_shadow_collisions(baseline_clean, candidate)
    score_conflicts = task016._classify_score_conflicts(baseline_clean, candidate)
    archive_score = [row for row in score_conflicts if row.get("archive_involved")]

    combined, combined_hygiene = clean_history(pd.concat([baseline_raw, candidate], ignore_index=True, sort=False))
    visible_players = task015._visible_players(results)
    visible_resolution_changes = task016._resolution_changes_for(baseline_clean, combined, visible_players)
    parsed = task016._parsed_dates(candidate)
    all_2024 = bool(candidate.empty or (parsed.notna().all() and parsed.dt.year.eq(2024).all()))

    candidate_frames = task016._frames_by_source(candidate)
    preview = task014.build_report(
        baseline_raw=baseline_raw,
        results=results,
        archive_frames=candidate_frames,
        source_status=source_status,
    )
    baseline_long = model.normalize_matches(baseline_clean)
    combined_long = model.normalize_matches(combined)
    gate_delta = task015._match_gate_delta(results, baseline_long, combined_long)

    source_fp = _source_fingerprints(archive_frames)
    expectation = _expectation_check(manifest=manifest, candidate=candidate, source_fingerprints=source_fp)
    fetched = all(row.get("fetch_success") for row in source_status) and len(source_status) == len(task014.TML_2024_SOURCES)
    safety_verified = bool(
        fetched
        and _manifest_sources_match(manifest)
        and frozen_shape_matches
        and hardening["all_evidence_matched"]
        and all_2024
        and not archive_global_id
        and not exact_shadow
        and not archive_score
        and not visible_resolution_changes
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
            "visible_matches": len(results),
            "all_2024_sources_fetched": fetched,
            "manifest_sources_match_task014": _manifest_sources_match(manifest),
            "task016_candidate_rows": int(len(task016_manifest_candidate)),
            "task016_candidate_source_counts": _source_counts(task016_manifest_candidate),
            "task016_frozen_shape_matches": frozen_shape_matches,
            "current_task016_dynamic_matches_frozen": current_dynamic_matches_frozen,
            "current_task016_candidate_rows": int(len(current_task016_candidate)),
            "current_task016_candidate_source_counts": _source_counts(current_task016_candidate),
            "global_hardening_removed_rows": int(hardening["removed_rows"]),
            "global_hardening_all_evidence_matched": bool(hardening["all_evidence_matched"]),
            "candidate_rows": int(len(candidate)),
            "candidate_source_counts": _source_counts(candidate),
            "archive_involved_global_id_conflicts": len(archive_global_id),
            "exact_shadow_variant_collisions": len(exact_shadow),
            "archive_involved_score_conflicts": len(archive_score),
            "visible_resolution_changes": len(visible_resolution_changes),
            "all_candidate_rows_within_2024": all_2024,
            "players_with_positive_2024_gain": int(preview["summary"]["players_with_positive_2024_gain"]),
            "players_reaching_minimum_5": int(preview["summary"]["players_reaching_minimum_5"]),
            "total_net_2024_clean_pre_match_rows": int(preview["summary"]["total_net_2024_clean_pre_match_rows"]),
            "baseline_model_ready_matches": int(gate_delta["baseline_model_ready_matches"]),
            "augmented_model_ready_matches": int(gate_delta["augmented_model_ready_matches"]),
            "newly_model_ready_matches": int(gate_delta["newly_model_ready_matches"]),
            "candidate_lock_safety_verified": safety_verified,
            "fingerprint_lock_present": bool(expectation["locked"]),
            "fingerprint_lock_matches": bool(expectation["matches"]),
            "candidate_ready_for_separate_integration_review": bool(safety_verified and expectation["matches"]),
        },
        "baseline_hygiene": baseline_hygiene,
        "combined_hygiene": combined_hygiene,
        "task016_materialization": materialization,
        "current_task016_dynamic_validation": {
            "matches_frozen": current_dynamic_matches_frozen,
            "candidate_rows": int(len(current_task016_candidate)),
            "candidate_source_counts": _source_counts(current_task016_candidate),
            "note": "Diagnostic only. Current results drift never rewrites the frozen TASK 016 basis.",
        },
        "global_hardening": hardening,
        "source_fingerprints": source_fp,
        "candidate_fingerprint": expectation["current"]["candidate_logical_sha256"],
        "expectation_check": expectation,
        "global_same_namespace_id_conflicts": global_id,
        "archive_involved_global_id_conflicts": archive_global_id,
        "exact_shadow_variant_collisions": exact_shadow,
        "score_conflicts": score_conflicts,
        "archive_involved_score_conflicts": archive_score,
        "visible_resolution_changes": visible_resolution_changes,
        "gain_preview": {
            "summary": preview["summary"],
            "priority": preview["priority"],
            "match_gate_delta": gate_delta,
        },
        "decision": {
            "runtime_change": False,
            "authorize_2024_archive": False,
            "candidate_lock_ready": bool(safety_verified and expectation["matches"]),
            "separate_integration_pr_required": True,
            "reason": "TASK 017 locks provenance and an evidence-hardened candidate only; it never changes runtime history inputs.",
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
    archive_frames: dict[str, pd.DataFrame] = {}
    status: list[dict[str, Any]] = []
    for source in task014.TML_2024_SOURCES:
        try:
            frame = downloader(source["url"])
            if frame is None or frame.empty:
                raise RuntimeError("empty_csv")
            archive_frames[source["key"]] = frame
            status.append({
                "key": source["key"], "tour": source["tour"], "url": source["url"],
                "fetch_success": True, "rows": int(len(frame)), "error": None,
            })
        except Exception as exc:
            status.append({
                "key": source["key"], "tour": source["tour"], "url": source["url"],
                "fetch_success": False, "rows": 0, "error": type(exc).__name__,
            })

    report = build_report(
        baseline_raw=baseline_raw,
        results=results,
        archive_frames=archive_frames,
        manifest=manifest,
        source_status=status,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Lock deterministic TML 2024 integration candidate")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(results_path=args.results, manifest_path=args.manifest, output_path=args.output)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    if report["decision"]["runtime_change"]:
        return 2
    if not report["summary"]["all_2024_sources_fetched"]:
        return 3
    if not report["summary"]["candidate_lock_safety_verified"]:
        return 4
    if report["summary"]["fingerprint_lock_present"] and not report["summary"]["fingerprint_lock_matches"]:
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
