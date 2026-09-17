from __future__ import annotations

"""TASK 016: audit-only blocker decomposition for TML 2024 integration.

This module explains TASK 015 fail-closed blockers, separates pre-existing
baseline conflicts from archive-introduced conflicts, and computes a conservative
2024-only candidate subset that preserves current resolver behavior. It never
changes runtime history sources or production/model behavior.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

import pandas as pd

try:
    from . import model, update
    from . import tml_2024_history_preview as task014
    from . import tml_2024_integration_safety_gate as task015
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
except ImportError:  # pragma: no cover
    import model, update
    import tml_2024_history_preview as task014
    import tml_2024_integration_safety_gate as task015
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "tml_2024_blocker_audit.json"
VERSION = "task-016-tml-2024-blocker-audit-v1"
MIN_MATCHES = task014.MIN_MATCHES


def _key(value: Any) -> str:
    return model._core._key(value)


def _id_token(value: Any) -> str | None:
    return task015._id_token(value)


def _read_json(path: Path, default: Any) -> Any:
    return task015._read_json(path, default)


def _results_list(value: Any) -> list[dict[str, Any]]:
    return task015._results_list(value)


def _annotated_archive(archive_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for source in task014.TML_2024_SOURCES:
        frame = archive_frames.get(source["key"])
        if frame is None or frame.empty:
            continue
        out = frame.copy().reset_index(drop=True)
        out["source_tour"] = source["tour"]
        out["source_key"] = source["key"]
        out["source_row_number"] = range(2, len(out) + 2)
        frames.append(out)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _parsed_dates(frame: pd.DataFrame) -> pd.Series:
    if frame is None or frame.empty or "tourney_date" not in frame.columns:
        return pd.Series(index=getattr(frame, "index", None), dtype="datetime64[ns]")
    return pd.to_datetime(frame["tourney_date"].astype(str).str[:8], format="%Y%m%d", errors="coerce")


def _row_record(row: pd.Series) -> dict[str, Any]:
    source_key = str(row.get("source_key") or "")
    source = next((s for s in task014.TML_2024_SOURCES if s["key"] == source_key), {})
    return {
        "source_key": source_key,
        "source_tour": str(row.get("source_tour") or ""),
        "source_url": source.get("url"),
        "source_row_number": int(row.get("source_row_number")) if pd.notna(row.get("source_row_number")) else None,
        "tourney_date": str(row.get("tourney_date") or ""),
        "tourney_name": str(row.get("tourney_name") or ""),
        "surface": str(row.get("surface") or ""),
        "winner_name": str(row.get("winner_name") or ""),
        "loser_name": str(row.get("loser_name") or ""),
        "winner_id": _id_token(row.get("winner_id")),
        "loser_id": _id_token(row.get("loser_id")),
        "score": str(row.get("score") or ""),
    }


def _date_blocker_details(archive_raw: pd.DataFrame) -> dict[str, Any]:
    if archive_raw is None or archive_raw.empty:
        return {"total_out_of_2024_rows": 0, "sources": [], "rows": []}
    dates = _parsed_dates(archive_raw)
    valid = dates.notna()
    out = (~valid) | (dates.dt.year != 2024)
    blocked = archive_raw.loc[out].copy()
    blocked_dates = dates.loc[out]
    source_rows = []
    for source in task014.TML_2024_SOURCES:
        mask = blocked["source_key"].eq(source["key"]) if not blocked.empty else pd.Series(dtype=bool)
        source_blocked = blocked.loc[mask].copy() if not blocked.empty else pd.DataFrame()
        source_dates = blocked_dates.loc[source_blocked.index] if not source_blocked.empty else pd.Series(dtype="datetime64[ns]")
        years = Counter("invalid" if pd.isna(value) else str(int(value.year)) for value in source_dates)
        valid_source_dates = source_dates.dropna()
        source_rows.append({
            "source_key": source["key"],
            "source_tour": source["tour"],
            "source_url": source["url"],
            "out_of_2024_rows": int(len(source_blocked)),
            "years": dict(sorted(years.items())),
            "min_date": valid_source_dates.min().strftime("%Y%m%d") if not valid_source_dates.empty else None,
            "max_date": valid_source_dates.max().strftime("%Y%m%d") if not valid_source_dates.empty else None,
        })
    records = []
    for index, row in blocked.iterrows():
        record = _row_record(row)
        parsed = blocked_dates.loc[index]
        record["parsed_year"] = None if pd.isna(parsed) else int(parsed.year)
        records.append(record)
    return {"total_out_of_2024_rows": int(len(blocked)), "sources": source_rows, "rows": records}


def _valid_2024_rows(archive_raw: pd.DataFrame) -> pd.DataFrame:
    if archive_raw is None or archive_raw.empty:
        return archive_raw.copy() if archive_raw is not None else pd.DataFrame()
    dates = _parsed_dates(archive_raw)
    return archive_raw.loc[dates.notna() & dates.dt.year.eq(2024)].copy()


def _id_sets(frame: pd.DataFrame, current_keys: set[str]) -> dict[tuple[str, str], set[str]]:
    values: dict[tuple[str, str], set[str]] = defaultdict(set)
    if frame is None or frame.empty:
        return values
    for _, row in frame.iterrows():
        namespace = str(row.get("source_tour") or "").strip().upper()
        if not namespace:
            continue
        for side in ("winner", "loser"):
            player_key = _key(row.get(f"{side}_name"))
            if player_key not in current_keys:
                continue
            token = _id_token(row.get(f"{side}_id"))
            if token is not None:
                values[(namespace, player_key)].add(token)
    return values


def _classify_id_conflicts(baseline_clean: pd.DataFrame, archive_clean: pd.DataFrame, current_keys: set[str]) -> list[dict[str, Any]]:
    baseline = _id_sets(baseline_clean, current_keys)
    archive = _id_sets(archive_clean, current_keys)
    rows = []
    for namespace, player_key in sorted(set(baseline) | set(archive)):
        before = baseline.get((namespace, player_key), set())
        added = archive.get((namespace, player_key), set())
        union = before | added
        if len(union) <= 1:
            continue
        baseline_conflict = len(before) > 1
        new_ids = added - before
        if baseline_conflict and not new_ids:
            classification = "baseline_only"
        elif baseline_conflict:
            classification = "archive_worsened"
        else:
            classification = "archive_introduced"
        rows.append({
            "namespace": namespace,
            "player_key": player_key,
            "baseline_ids": sorted(before),
            "archive_2024_ids": sorted(added),
            "combined_ids": sorted(union),
            "archive_new_ids": sorted(new_ids),
            "classification": classification,
            "archive_involved": classification != "baseline_only",
        })
    return rows


def _score_sets(frame: pd.DataFrame) -> dict[tuple[str, ...], set[str]]:
    values: dict[tuple[str, ...], set[str]] = defaultdict(set)
    if frame is None or frame.empty:
        return values
    required = set(task015.MATCH_IDENTITY_COLUMNS) | {"score", "source_tour"}
    if not required.issubset(frame.columns):
        return values
    for _, row in frame.iterrows():
        identity = (str(row.get("source_tour") or "").strip().upper(),) + task015._signature(row, task015.MATCH_IDENTITY_COLUMNS)
        score = str(row.get("score") or "").strip()
        if score:
            values[identity].add(score)
    return values


def _classify_score_conflicts(baseline_clean: pd.DataFrame, archive_clean: pd.DataFrame) -> list[dict[str, Any]]:
    baseline = _score_sets(baseline_clean)
    archive = _score_sets(archive_clean)
    rows = []
    for identity in sorted(set(baseline) | set(archive)):
        before = baseline.get(identity, set())
        added = archive.get(identity, set())
        union = before | added
        if len(union) <= 1:
            continue
        baseline_conflict = len(before) > 1
        new_scores = added - before
        if baseline_conflict and not new_scores:
            classification = "baseline_only"
        elif baseline_conflict:
            classification = "archive_worsened"
        else:
            classification = "archive_introduced"
        rows.append({
            "identity": list(identity),
            "baseline_scores": sorted(before),
            "archive_2024_scores": sorted(added),
            "combined_scores": sorted(union),
            "archive_new_scores": sorted(new_scores),
            "classification": classification,
            "archive_involved": classification != "baseline_only",
        })
    return rows


def _resolution_changes_for(baseline_clean: pd.DataFrame, augmented_clean: pd.DataFrame, players: list[str]) -> list[dict[str, Any]]:
    baseline_long = model.normalize_matches(baseline_clean)
    augmented_long = model.normalize_matches(augmented_clean)
    return task015.compare_resolution_maps(
        task015._resolution_map(baseline_long, players),
        task015._resolution_map(augmented_long, players),
    )


def _row_identity(row: pd.Series) -> tuple[str, ...]:
    return (str(row.get("source_tour") or "").strip().upper(),) + task015._signature(row, task015.MATCH_IDENTITY_COLUMNS)


def _touches_player_keys(row: pd.Series, player_keys: set[str]) -> bool:
    return any(_key(row.get(f"{side}_name")) in player_keys for side in ("winner", "loser"))


def _touches_id_blocker(row: pd.Series, blocked: set[tuple[str, str]]) -> bool:
    namespace = str(row.get("source_tour") or "").strip().upper()
    return any((namespace, _key(row.get(f"{side}_name"))) in blocked for side in ("winner", "loser"))


def _dedupe_archive(archive_clean: pd.DataFrame, baseline_clean: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    if archive_clean is None or archive_clean.empty:
        return pd.DataFrame(columns=getattr(archive_clean, "columns", [])), {
            "rows_before_dedupe": 0,
            "removed_internal_duplicates": 0,
            "removed_baseline_overlaps": 0,
            "rows_after_dedupe": 0,
        }
    baseline_signatures = task015._signature_set(baseline_clean, task015.MODEL_DEDUPE_COLUMNS)
    seen: set[tuple[str, ...]] = set()
    keep = []
    internal = 0
    overlap = 0
    for index, row in archive_clean.iterrows():
        signature = task015._signature(row, task015.MODEL_DEDUPE_COLUMNS)
        if signature in baseline_signatures:
            overlap += 1
            continue
        if signature in seen:
            internal += 1
            continue
        seen.add(signature)
        keep.append(index)
    out = archive_clean.loc[keep].copy()
    return out, {
        "rows_before_dedupe": int(len(archive_clean)),
        "removed_internal_duplicates": internal,
        "removed_baseline_overlaps": overlap,
        "rows_after_dedupe": int(len(out)),
    }


def _safe_subset(*, baseline_raw: pd.DataFrame, baseline_clean: pd.DataFrame, archive_raw: pd.DataFrame, results: list[dict[str, Any]]) -> dict[str, Any]:
    players = task015._visible_players(results)
    current_keys = {_key(player) for player in players}
    date_valid_raw = _valid_2024_rows(archive_raw)
    date_valid_clean, date_valid_hygiene = clean_history(date_valid_raw)
    date_valid_combined, _ = clean_history(pd.concat([baseline_raw, date_valid_raw], ignore_index=True, sort=False))

    resolution_changes = _resolution_changes_for(baseline_clean, date_valid_combined, players)
    resolution_keys = {row["requested_key"] for row in resolution_changes}
    id_conflicts = _classify_id_conflicts(baseline_clean, date_valid_clean, current_keys)
    id_blockers = {(row["namespace"], row["player_key"]) for row in id_conflicts if row["archive_involved"]}
    score_conflicts = _classify_score_conflicts(baseline_clean, date_valid_clean)
    score_blockers = {tuple(row["identity"]) for row in score_conflicts if row["archive_involved"]}

    excluded = Counter()
    keep_indices = []
    for index, row in date_valid_clean.iterrows():
        reasons = []
        if _touches_player_keys(row, resolution_keys):
            reasons.append("resolution_change")
        if _touches_id_blocker(row, id_blockers):
            reasons.append("archive_id_conflict")
        if _row_identity(row) in score_blockers:
            reasons.append("archive_score_conflict")
        if reasons:
            for reason in set(reasons):
                excluded[reason] += 1
            continue
        keep_indices.append(index)
    candidate = date_valid_clean.loc[keep_indices].copy()
    candidate, dedupe = _dedupe_archive(candidate, baseline_clean)

    iterative_resolution_exclusions: list[dict[str, Any]] = []
    for _ in range(8):
        combined, _ = clean_history(pd.concat([baseline_raw, candidate], ignore_index=True, sort=False))
        remaining = _resolution_changes_for(baseline_clean, combined, players)
        if not remaining:
            break
        keys = {row["requested_key"] for row in remaining}
        before = len(candidate)
        candidate = candidate.loc[~candidate.apply(lambda row: _touches_player_keys(row, keys), axis=1)].copy()
        removed = before - len(candidate)
        iterative_resolution_exclusions.append({"changes": remaining, "removed_rows": removed})
        if removed <= 0:
            break

    safe_combined, _ = clean_history(pd.concat([baseline_raw, candidate], ignore_index=True, sort=False))
    final_resolution = _resolution_changes_for(baseline_clean, safe_combined, players)
    final_id_conflicts = _classify_id_conflicts(baseline_clean, candidate, current_keys)
    final_score_conflicts = _classify_score_conflicts(baseline_clean, candidate)
    archive_id_remaining = [row for row in final_id_conflicts if row["archive_involved"]]
    archive_score_remaining = [row for row in final_score_conflicts if row["archive_involved"]]
    parsed = _parsed_dates(candidate)
    all_2024 = bool(candidate.empty or (parsed.notna().all() and parsed.dt.year.eq(2024).all()))
    verified = bool(all_2024 and not final_resolution and not archive_id_remaining and not archive_score_remaining)

    source_counts = []
    for source in task014.TML_2024_SOURCES:
        source_counts.append({
            "source_key": source["key"],
            "source_tour": source["tour"],
            "source_url": source["url"],
            "safe_rows": int(candidate["source_key"].eq(source["key"]).sum()) if "source_key" in candidate.columns else 0,
        })

    return {
        "safe_archive_clean": candidate,
        "date_valid_hygiene": date_valid_hygiene,
        "resolution_changes_after_year_filter": resolution_changes,
        "id_conflicts_after_year_filter": id_conflicts,
        "score_conflicts_after_year_filter": score_conflicts,
        "excluded_row_reason_counts": dict(sorted(excluded.items())),
        "dedupe": dedupe,
        "iterative_resolution_exclusions": iterative_resolution_exclusions,
        "safe_validation": {
            "all_rows_within_2024": all_2024,
            "resolution_changes": final_resolution,
            "archive_involved_id_conflicts": archive_id_remaining,
            "archive_involved_score_conflicts": archive_score_remaining,
            "verified": verified,
        },
        "source_counts": source_counts,
    }


def _frames_by_source(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    if frame is None or frame.empty or "source_key" not in frame.columns:
        return out
    for source in task014.TML_2024_SOURCES:
        part = frame.loc[frame["source_key"].eq(source["key"])].copy()
        if not part.empty:
            out[source["key"]] = part
    return out


def _positive_cases(preview: dict[str, Any]) -> list[dict[str, Any]]:
    priority = preview.get("priority") or {}
    rows = list(priority.get("reaches_minimum_5") or []) + list(priority.get("gains_history_but_below_5") or [])
    seen: set[tuple[Any, ...]] = set()
    out = []
    for row in rows:
        marker = (row.get("match_id"), row.get("side"), row.get("baseline_key"))
        if marker not in seen:
            seen.add(marker)
            out.append(row)
    return out


def _score_conflict_player_keys(conflicts: list[dict[str, Any]], *, archive_only: bool | None = None) -> set[str]:
    keys = set()
    for row in conflicts:
        if archive_only is True and not row.get("archive_involved"):
            continue
        identity = row.get("identity") or []
        if len(identity) >= 5:
            keys.add(_key(identity[3]))
            keys.add(_key(identity[4]))
    return {key for key in keys if key}


def _out_of_year_player_keys(details: dict[str, Any]) -> set[str]:
    keys = set()
    for row in details.get("rows") or []:
        keys.add(_key(row.get("winner_name")))
        keys.add(_key(row.get("loser_name")))
    return {key for key in keys if key}


def _gain_overlap(*, full_preview: dict[str, Any], safe_preview: dict[str, Any], resolution_changes: list[dict[str, Any]], id_conflicts: list[dict[str, Any]], score_conflicts: list[dict[str, Any]], date_details: dict[str, Any]) -> list[dict[str, Any]]:
    resolution_keys = {row["requested_key"] for row in resolution_changes}
    any_id = {row["player_key"] for row in id_conflicts}
    archive_id = {row["player_key"] for row in id_conflicts if row["archive_involved"]}
    any_score = _score_conflict_player_keys(score_conflicts)
    archive_score = _score_conflict_player_keys(score_conflicts, archive_only=True)
    out_year = _out_of_year_player_keys(date_details)
    safe_by_marker = {(row.get("match_id"), row.get("side"), row.get("baseline_key")): row for row in _positive_cases(safe_preview)}
    rows = []
    for row in _positive_cases(full_preview):
        key = row.get("baseline_key")
        marker = (row.get("match_id"), row.get("side"), key)
        safe = safe_by_marker.get(marker)
        rows.append({
            "match_id": row.get("match_id"),
            "side": row.get("side"),
            "player": row.get("player"),
            "player_key": key,
            "full_net_2024_rows": int(row.get("net_2024_clean_pre_match_rows") or 0),
            "full_reaches_minimum_5": bool(row.get("reaches_minimum_5")),
            "touches_resolution_change": key in resolution_keys,
            "touches_any_same_namespace_id_conflict": key in any_id,
            "touches_archive_involved_id_conflict": key in archive_id,
            "touches_any_score_conflict": key in any_score,
            "touches_archive_involved_score_conflict": key in archive_score,
            "appears_in_out_of_2024_rows": key in out_year,
            "safe_net_2024_rows": int((safe or {}).get("net_2024_clean_pre_match_rows") or 0),
            "safe_reaches_minimum_5": bool((safe or {}).get("reaches_minimum_5")),
            "retained_positive_gain": bool(safe and int(safe.get("net_2024_clean_pre_match_rows") or 0) > 0),
        })
    return rows


def _safe_gain_records(safe_archive_clean: pd.DataFrame, safe_preview: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for case in _positive_cases(safe_preview):
        player_key = str(case.get("baseline_key") or "")
        if not player_key:
            continue
        matching = safe_archive_clean.loc[safe_archive_clean.apply(
            lambda row: _key(row.get("winner_name")) == player_key or _key(row.get("loser_name")) == player_key,
            axis=1,
        )]
        for _, row in matching.iterrows():
            record = _row_record(row)
            record.update({
                "player": case.get("player"),
                "player_key": player_key,
                "match_id": case.get("match_id"),
                "side": case.get("side"),
                "player_result_side": "winner" if _key(row.get("winner_name")) == player_key else "loser",
                "model_signature": list(task015._signature(row, task015.MODEL_DEDUPE_COLUMNS)),
            })
            rows.append(record)
    rows.sort(key=lambda row: (str(row.get("player_key")), str(row.get("tourney_date")), str(row.get("tourney_name")), int(row.get("source_row_number") or 0)))
    return rows


def build_report(*, baseline_raw: pd.DataFrame, results: list[dict[str, Any]], archive_frames: dict[str, pd.DataFrame], source_status: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    source_status = source_status or []
    archive_raw = _annotated_archive(archive_frames)
    baseline_clean, baseline_hygiene = clean_history(baseline_raw)
    archive_clean, archive_hygiene = clean_history(archive_raw)

    task015_report = task015.build_report(
        baseline_raw=baseline_raw,
        results=results,
        archive_frames=archive_frames,
        source_status=source_status,
    )
    date_details = _date_blocker_details(archive_raw)
    subset = _safe_subset(baseline_raw=baseline_raw, baseline_clean=baseline_clean, archive_raw=archive_raw, results=results)
    safe_archive_clean = subset.pop("safe_archive_clean")
    safe_frames = _frames_by_source(safe_archive_clean)
    safe_preview = task014.build_report(
        baseline_raw=baseline_raw,
        results=results,
        archive_frames=safe_frames,
        source_status=source_status,
    )
    safe_combined, safe_combined_hygiene = clean_history(pd.concat([baseline_raw, safe_archive_clean], ignore_index=True, sort=False))
    baseline_long = model.normalize_matches(baseline_clean)
    safe_long = model.normalize_matches(safe_combined)
    safe_gate_delta = task015._match_gate_delta(results, baseline_long, safe_long)

    players = task015._visible_players(results)
    current_keys = {_key(player) for player in players}
    full_id_classification = _classify_id_conflicts(baseline_clean, archive_clean, current_keys)
    full_score_classification = _classify_score_conflicts(baseline_clean, archive_clean)
    overlap = _gain_overlap(
        full_preview=task015_report["task014_preview"],
        safe_preview=safe_preview,
        resolution_changes=subset["resolution_changes_after_year_filter"],
        id_conflicts=subset["id_conflicts_after_year_filter"],
        score_conflicts=subset["score_conflicts_after_year_filter"],
        date_details=date_details,
    )
    gain_records = _safe_gain_records(safe_archive_clean, safe_preview)

    retained_gain_players = {row["player_key"] for row in overlap if row["retained_positive_gain"]}
    retained_reaching = {row["player_key"] for row in overlap if row["safe_reaches_minimum_5"]}
    all_fetched = all(row.get("fetch_success") for row in source_status) and len(source_status) == len(task014.TML_2024_SOURCES)

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
        },
        "summary": {
            "visible_matches": len(results),
            "visible_players": len(players),
            "all_2024_sources_fetched": all_fetched,
            "task015_gate_passed": bool(task015_report["summary"]["integration_safety_gate_passed"]),
            "out_of_2024_rows": int(date_details["total_out_of_2024_rows"]),
            "resolution_changes_after_year_filter": len(subset["resolution_changes_after_year_filter"]),
            "same_namespace_id_conflicts_full_combined": len(full_id_classification),
            "same_namespace_id_conflicts_after_year_filter": len(subset["id_conflicts_after_year_filter"]),
            "archive_involved_id_conflicts_after_year_filter": sum(1 for row in subset["id_conflicts_after_year_filter"] if row["archive_involved"]),
            "score_conflicts_full_combined": len(full_score_classification),
            "score_conflicts_after_year_filter": len(subset["score_conflicts_after_year_filter"]),
            "archive_involved_score_conflicts_after_year_filter": sum(1 for row in subset["score_conflicts_after_year_filter"] if row["archive_involved"]),
            "safe_candidate_subset_verified": bool(subset["safe_validation"]["verified"]),
            "safe_archive_rows": int(len(safe_archive_clean)),
            "safe_players_with_positive_2024_gain": len(retained_gain_players),
            "safe_players_reaching_minimum_5": len(retained_reaching),
            "safe_total_net_2024_clean_pre_match_rows": int(safe_preview["summary"]["total_net_2024_clean_pre_match_rows"]),
            "safe_baseline_model_ready_matches": int(safe_gate_delta["baseline_model_ready_matches"]),
            "safe_augmented_model_ready_matches": int(safe_gate_delta["augmented_model_ready_matches"]),
            "safe_newly_model_ready_matches": int(safe_gate_delta["newly_model_ready_matches"]),
        },
        "baseline_hygiene": baseline_hygiene,
        "archive_hygiene": archive_hygiene,
        "safe_combined_hygiene": safe_combined_hygiene,
        "task015_snapshot": {
            "summary": task015_report["summary"],
            "resolution_changes": task015_report["resolution_changes"],
            "current_player_id_conflicts": task015_report["current_player_id_conflicts"],
            "match_identity_conflicts": task015_report["match_identity_conflicts"],
        },
        "date_blocker": date_details,
        "id_conflict_classification_full": full_id_classification,
        "score_conflict_classification_full": full_score_classification,
        "safe_subset": subset,
        "gain_player_blocker_overlap": overlap,
        "safe_gain_preview": {
            "summary": safe_preview["summary"],
            "category_counts": safe_preview["category_counts"],
            "priority": safe_preview["priority"],
            "match_gate_delta": safe_gate_delta,
        },
        "safe_gain_records": gain_records,
        "decision": {
            "runtime_change": False,
            "authorize_2024_archive": False,
            "safe_subset_candidate_exists": bool(subset["safe_validation"]["verified"] and len(safe_archive_clean) > 0),
            "separate_integration_pr_required": True,
            "reason": "TASK 016 is audit-only. It may identify a conservative 2024-only candidate subset, but it does not add that subset to TML_SOURCES or authorize runtime use.",
        },
    }


def run(*, results_path: Path = DEFAULT_RESULTS, output_path: Path = DEFAULT_OUTPUT, downloader: Callable[[str], pd.DataFrame] = update.download_csv) -> dict[str, Any]:
    baseline_raw = load_cached_history()
    results = _results_list(_read_json(results_path, []))
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

    report = build_report(baseline_raw=baseline_raw, results=results, archive_frames=archive_frames, source_status=status)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit TASK 015 blockers and compute a conservative TML 2024 subset")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(results_path=args.results, output_path=args.output)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    if report["decision"]["runtime_change"]:
        return 2
    if not report["summary"]["all_2024_sources_fetched"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
