from __future__ import annotations

"""TASK 015: fail-closed integration safety gate for TennisMyLife 2024 archives.

Audit only. This module reuses the four public 2024 TennisMyLife archives from
TASK 014 and checks whether they are structurally safe candidates for a later
production-history integration PR. It never writes production cache, never
changes the resolver, never changes model math or the minimum-history gate, and
never authorizes runtime use by itself.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import pandas as pd

try:
    from . import model, update
    from . import tml_2024_history_preview as task014
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
except ImportError:  # pragma: no cover
    import model, update
    import tml_2024_history_preview as task014
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "tml_2024_integration_safety_gate.json"
VERSION = "task-015-tml-2024-integration-safety-gate-v1"
MIN_MATCHES = task014.MIN_MATCHES

MODEL_HISTORY_COLUMNS = (
    "tourney_date", "tourney_name", "surface", "winner_name", "loser_name", "score",
    "winner_rank", "loser_rank",
    "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon", "w_SvGms", "w_bpSaved", "w_bpFaced",
    "l_svpt", "l_1stIn", "l_1stWon", "l_2ndWon", "l_SvGms", "l_bpSaved", "l_bpFaced",
)
MODEL_DEDUPE_COLUMNS = ("tourney_date", "tourney_name", "winner_name", "loser_name", "score")
MATCH_IDENTITY_COLUMNS = ("tourney_date", "tourney_name", "winner_name", "loser_name")


def _key(value: Any) -> str:
    return model._core._key(value)


def _id_token(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else format(value, ".15g")
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _results_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("matches", [])
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _annotate(frame: pd.DataFrame, source: dict[str, str]) -> pd.DataFrame:
    out = frame.copy()
    out["source_tour"] = source["tour"]
    out["source_key"] = source["key"]
    return out


def source_schema_status(frame: pd.DataFrame) -> dict[str, Any]:
    columns = set(frame.columns) if frame is not None else set()
    missing = sorted(set(MODEL_HISTORY_COLUMNS) - columns)
    return {
        "rows": int(len(frame)) if frame is not None else 0,
        "missing_model_history_columns": missing,
        "model_schema_compatible": not missing,
    }


def source_date_status(frame: pd.DataFrame) -> dict[str, Any]:
    if frame is None or frame.empty or "tourney_date" not in frame.columns:
        return {"valid_dates": 0, "invalid_dates": int(len(frame)) if frame is not None else 0, "out_of_2024_rows": 0, "only_2024": False}
    dates = pd.to_datetime(frame["tourney_date"].astype(str).str[:8], format="%Y%m%d", errors="coerce")
    valid = dates.notna()
    out = valid & (dates.dt.year != 2024)
    return {
        "valid_dates": int(valid.sum()),
        "invalid_dates": int((~valid).sum()),
        "out_of_2024_rows": int(out.sum()),
        "only_2024": bool(valid.all() and not out.any()),
    }


def _signature(row: pd.Series, columns: tuple[str, ...]) -> tuple[str, ...]:
    values = []
    for column in columns:
        value = row.get(column)
        values.append("" if pd.isna(value) else str(value).strip())
    return tuple(values)


def _signature_set(frame: pd.DataFrame, columns: tuple[str, ...]) -> set[tuple[str, ...]]:
    if frame is None or frame.empty or not set(columns).issubset(frame.columns):
        return set()
    return {_signature(row, columns) for _, row in frame.iterrows()}


def _duplicate_report(baseline_clean: pd.DataFrame, archive_clean: pd.DataFrame) -> dict[str, int]:
    archive_sigs = [_signature(row, MODEL_DEDUPE_COLUMNS) for _, row in archive_clean.iterrows()]
    baseline_sigs = _signature_set(baseline_clean, MODEL_DEDUPE_COLUMNS)
    unique_archive = set(archive_sigs)
    overlap = unique_archive & baseline_sigs
    return {
        "archive_clean_rows": int(len(archive_clean)),
        "archive_unique_model_signatures": len(unique_archive),
        "archive_internal_duplicate_rows": max(0, len(archive_sigs) - len(unique_archive)),
        "archive_signatures_already_in_baseline": len(overlap),
        "archive_net_new_model_signatures": len(unique_archive - baseline_sigs),
    }


def _match_identity_conflicts(combined_clean: pd.DataFrame) -> list[dict[str, Any]]:
    if combined_clean is None or combined_clean.empty:
        return []
    required = set(MATCH_IDENTITY_COLUMNS) | {"score", "source_tour"}
    if not required.issubset(combined_clean.columns):
        return []
    scores: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for _, row in combined_clean.iterrows():
        identity = (str(row.get("source_tour") or "").upper(),) + _signature(row, MATCH_IDENTITY_COLUMNS)
        score = str(row.get("score") or "").strip()
        if score:
            scores[identity].add(score)
    conflicts = []
    for identity, values in scores.items():
        if len(values) > 1:
            conflicts.append({"identity": list(identity), "scores": sorted(values)})
    return conflicts


def _visible_players(results: list[dict[str, Any]]) -> list[str]:
    names = []
    seen = set()
    for match in results:
        for side in ("p1", "p2"):
            name = str(match.get(side) or "").strip()
            key = _key(name)
            if name and key and key not in seen:
                seen.add(key)
                names.append(name)
    return names


def _resolution_map(long_df: pd.DataFrame, players: list[str]) -> dict[str, dict[str, Any]]:
    out = {}
    for player in players:
        key, mode = model._resolve_history_player_key(long_df, player)
        out[_key(player)] = {"player": player, "resolved_key": key, "mode": mode}
    return out


def compare_resolution_maps(
    baseline: dict[str, dict[str, Any]],
    augmented: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    changes = []
    for requested_key in sorted(set(baseline) | set(augmented)):
        before = baseline.get(requested_key) or {}
        after = augmented.get(requested_key) or {}
        if before.get("resolved_key") != after.get("resolved_key"):
            changes.append({
                "requested_key": requested_key,
                "player": before.get("player") or after.get("player"),
                "baseline_resolved_key": before.get("resolved_key"),
                "augmented_resolved_key": after.get("resolved_key"),
                "baseline_mode": before.get("mode"),
                "augmented_mode": after.get("mode"),
            })
    return changes


def _current_key_id_conflicts(combined_clean: pd.DataFrame, current_keys: set[str]) -> list[dict[str, Any]]:
    if combined_clean is None or combined_clean.empty:
        return []
    ids: dict[tuple[str, str], set[str]] = defaultdict(set)
    for _, row in combined_clean.iterrows():
        namespace = str(row.get("source_tour") or "").strip().upper()
        if not namespace:
            continue
        for side in ("winner", "loser"):
            name_key = _key(row.get(f"{side}_name"))
            if name_key not in current_keys:
                continue
            player_id = _id_token(row.get(f"{side}_id"))
            if player_id is not None:
                ids[(namespace, name_key)].add(player_id)
    conflicts = []
    for (namespace, name_key), values in sorted(ids.items()):
        if len(values) > 1:
            conflicts.append({"namespace": namespace, "player_key": name_key, "ids": sorted(values)})
    return conflicts


def _pre_count(long_df: pd.DataFrame, key: str | None, scheduled_time: Any) -> int:
    if not key or long_df is None or long_df.empty or "player_key" not in long_df.columns:
        return 0
    dated = model._dated_history(long_df)
    if dated is None or dated.empty or "date" not in dated.columns:
        return 0
    cutoff = model._naive_cutoff(scheduled_time)
    if cutoff is not None:
        dated = dated[dated["date"] <= cutoff]
    return int((dated["player_key"] == key).sum())


def _match_gate_delta(
    results: list[dict[str, Any]],
    baseline_long: pd.DataFrame,
    augmented_long: pd.DataFrame,
) -> dict[str, Any]:
    rows = []
    for match in results:
        side_rows = []
        stable = True
        for side in ("p1", "p2"):
            player = str(match.get(side) or "").strip()
            before_key, before_mode = model._resolve_history_player_key(baseline_long, player)
            after_key, after_mode = model._resolve_history_player_key(augmented_long, player)
            same = before_key == after_key
            stable = stable and same
            before = _pre_count(baseline_long, before_key, match.get("scheduled_time"))
            after = _pre_count(augmented_long, after_key if same else None, match.get("scheduled_time"))
            side_rows.append({
                "side": side,
                "player": player,
                "baseline_key": before_key,
                "augmented_key": after_key,
                "baseline_mode": before_mode,
                "augmented_mode": after_mode,
                "identity_stable": same,
                "baseline_pre_match_rows": before,
                "augmented_pre_match_rows": after,
            })
        baseline_ready = all(row["baseline_pre_match_rows"] >= MIN_MATCHES for row in side_rows)
        augmented_ready = stable and all(row["augmented_pre_match_rows"] >= MIN_MATCHES for row in side_rows)
        rows.append({
            "match_id": match.get("id"),
            "scheduled_time": match.get("scheduled_time"),
            "identity_stable": stable,
            "baseline_model_ready_by_history": baseline_ready,
            "augmented_model_ready_by_history": augmented_ready,
            "newly_model_ready_by_history": bool(not baseline_ready and augmented_ready),
            "players": side_rows,
        })
    return {
        "baseline_model_ready_matches": sum(1 for row in rows if row["baseline_model_ready_by_history"]),
        "augmented_model_ready_matches": sum(1 for row in rows if row["augmented_model_ready_by_history"]),
        "newly_model_ready_matches": sum(1 for row in rows if row["newly_model_ready_by_history"]),
        "identity_unstable_matches": sum(1 for row in rows if not row["identity_stable"]),
        "newly_model_ready_examples": [row for row in rows if row["newly_model_ready_by_history"]][:12],
    }


def build_report(
    *,
    baseline_raw: pd.DataFrame,
    results: list[dict[str, Any]],
    archive_frames: dict[str, pd.DataFrame],
    source_status: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source_status = source_status or []
    source_rows = []
    annotated_archives = []
    for source in task014.TML_2024_SOURCES:
        frame = archive_frames.get(source["key"])
        schema = source_schema_status(frame)
        dates = source_date_status(frame)
        fetched = bool(frame is not None and not frame.empty)
        external = next((row for row in source_status if row.get("key") == source["key"]), {})
        source_rows.append({
            "key": source["key"],
            "tour": source["tour"],
            "url": source["url"],
            "fetch_success": bool(external.get("fetch_success", fetched)),
            "fetch_error": external.get("error"),
            **schema,
            **dates,
        })
        if fetched:
            annotated_archives.append(_annotate(frame, source))

    archive_raw = pd.concat(annotated_archives, ignore_index=True, sort=False) if annotated_archives else pd.DataFrame()
    baseline_clean, baseline_hygiene = clean_history(baseline_raw)
    archive_clean, archive_hygiene = clean_history(archive_raw)
    combined_raw = pd.concat([baseline_raw, archive_raw], ignore_index=True, sort=False)
    combined_clean, combined_hygiene = clean_history(combined_raw)
    baseline_long = model.normalize_matches(baseline_clean)
    augmented_long = model.normalize_matches(combined_clean)

    players = _visible_players(results)
    baseline_resolution = _resolution_map(baseline_long, players)
    augmented_resolution = _resolution_map(augmented_long, players)
    resolution_changes = compare_resolution_maps(baseline_resolution, augmented_resolution)
    current_keys = {_key(player) for player in players}
    id_conflicts = _current_key_id_conflicts(combined_clean, current_keys)
    match_conflicts = _match_identity_conflicts(combined_clean)
    duplicates = _duplicate_report(baseline_clean, archive_clean)
    gate_delta = _match_gate_delta(results, baseline_long, augmented_long)

    preview = task014.build_report(
        baseline_raw=baseline_raw,
        results=results,
        archive_frames=archive_frames,
        source_status=source_status,
    )

    all_fetched = all(row["fetch_success"] for row in source_rows) and len(source_rows) == len(task014.TML_2024_SOURCES)
    schema_ok = all(row["model_schema_compatible"] for row in source_rows)
    dates_ok = all(row["only_2024"] for row in source_rows)
    no_resolution_change = not resolution_changes
    no_id_conflicts = not id_conflicts
    no_match_conflicts = not match_conflicts
    no_model_ready_regression = gate_delta["augmented_model_ready_matches"] >= gate_delta["baseline_model_ready_matches"]

    gate_passed = all((
        all_fetched,
        schema_ok,
        dates_ok,
        no_resolution_change,
        no_id_conflicts,
        no_match_conflicts,
        no_model_ready_regression,
    ))

    return {
        "version": VERSION,
        "policy": {
            "live_tennis_api_calls": 0,
            "tennismylife_requests": len(task014.TML_2024_SOURCES),
            "tennismylife_2024_only": True,
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
            "all_sources_model_schema_compatible": schema_ok,
            "all_source_rows_within_2024": dates_ok,
            "baseline_resolution_changes": len(resolution_changes),
            "current_player_same_namespace_id_conflicts": len(id_conflicts),
            "match_identity_score_conflicts": len(match_conflicts),
            **duplicates,
            "players_with_positive_2024_gain": preview["summary"]["players_with_positive_2024_gain"],
            "players_reaching_minimum_5": preview["summary"]["players_reaching_minimum_5"],
            "total_net_2024_clean_pre_match_rows": preview["summary"]["total_net_2024_clean_pre_match_rows"],
            **gate_delta,
            "integration_safety_gate_passed": gate_passed,
        },
        "baseline_hygiene": baseline_hygiene,
        "archive_hygiene": archive_hygiene,
        "combined_hygiene": combined_hygiene,
        "sources": source_rows,
        "resolution_changes": resolution_changes,
        "current_player_id_conflicts": id_conflicts,
        "match_identity_conflicts": match_conflicts[:50],
        "task014_preview": {
            "summary": preview["summary"],
            "category_counts": preview["category_counts"],
            "priority": preview["priority"],
        },
        "decision": {
            "runtime_change": False,
            "authorize_2024_archive": False,
            "integration_candidate_ready_for_separate_runtime_pr": gate_passed,
            "reason": (
                "TASK 015 is a fail-closed integration safety audit only. A passing gate means a separate PR may be considered "
                "to add immutable 2024 TML sources; this report itself never changes production history inputs."
            ),
        },
    }


def run(
    *,
    results_path: Path = DEFAULT_RESULTS,
    output_path: Path = DEFAULT_OUTPUT,
    downloader: Callable[[str], pd.DataFrame] = update.download_csv,
) -> dict[str, Any]:
    baseline_raw = load_cached_history()
    results = _results_list(_read_json(results_path, []))
    archive_frames: dict[str, pd.DataFrame] = {}
    status = []
    for source in task014.TML_2024_SOURCES:
        try:
            frame = downloader(source["url"])
            if frame is None or frame.empty:
                raise RuntimeError("empty_csv")
            archive_frames[source["key"]] = frame
            status.append({"key": source["key"], "fetch_success": True, "rows": int(len(frame)), "error": None})
        except Exception as exc:
            status.append({"key": source["key"], "fetch_success": False, "rows": 0, "error": type(exc).__name__})

    report = build_report(
        baseline_raw=baseline_raw,
        results=results,
        archive_frames=archive_frames,
        source_status=status,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed TML 2024 integration safety gate")
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
