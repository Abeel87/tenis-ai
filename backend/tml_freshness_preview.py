from __future__ import annotations

"""TASK 010: preview fresh TennisMyLife sources without mutating production cache.

The audit downloads only the same public TennisMyLife sources already declared by
``backend.update.TML_SOURCES``. It never calls Live Tennis API, never writes the
production cache, and never changes model/runtime state. Fresh refreshable
sources are held in memory and substituted into a preview history snapshot;
immutable sources remain the exact restored cache.
"""

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

try:
    from . import insufficient_history_evidence as task005
    from . import model
    from . import update
    from .history_hygiene_v78a import clean_history
except ImportError:  # pragma: no cover
    import insufficient_history_evidence as task005
    import model
    import update
    from history_hygiene_v78a import clean_history

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = ROOT / "data" / "cache"
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "tml_freshness_preview.json"
VERSION = "task-010-tml-freshness-preview-v1"
MIN_MATCHES = task005.MIN_MATCHES

IDENTITY_COLUMNS = (
    "tourney_id",
    "match_num",
    "tourney_date",
    "winner_name",
    "loser_name",
    "score",
)


def _read_cached(cache_root: Path, source: dict[str, Any]) -> pd.DataFrame | None:
    path = cache_root / f"{source['key']}.csv.gz"
    try:
        frame = pd.read_csv(path, compression="gzip", low_memory=False)
    except Exception:
        return None
    return frame if not frame.empty else None


def _read_manifest(cache_root: Path) -> dict[str, Any]:
    path = cache_root / update.CACHE_MANIFEST
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _row_signature(row: pd.Series) -> tuple[str, ...]:
    return tuple(str(row.get(column) if pd.notna(row.get(column)) else "") for column in IDENTITY_COLUMNS)


def _signatures(frame: pd.DataFrame | None) -> set[tuple[str, ...]]:
    if frame is None or frame.empty:
        return set()
    return {_row_signature(row) for _, row in frame.iterrows()}


def _latest_tourney_date(frame: pd.DataFrame | None) -> str | None:
    if frame is None or frame.empty or "tourney_date" not in frame.columns:
        return None
    parsed = pd.to_datetime(frame["tourney_date"].astype(str).str[:8], format="%Y%m%d", errors="coerce")
    parsed = parsed.dropna()
    return parsed.max().date().isoformat() if not parsed.empty else None


def _combine(source_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    source_map = {source["key"]: source for source in update.TML_SOURCES}
    for source in update.TML_SOURCES:
        frame = source_frames.get(source["key"])
        if frame is None or frame.empty:
            continue
        copy = frame.copy()
        copy["source_tour"] = source_map[source["key"]]["tour"]
        frames.append(copy)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _pre_count(long_df: pd.DataFrame, key: str | None, scheduled_time: Any) -> int:
    if not key or long_df is None or long_df.empty or "player_key" not in long_df.columns:
        return 0
    dated = model._dated_history(long_df)
    if dated is None or dated.empty:
        return 0
    cut = model._naive_cutoff(scheduled_time)
    if cut is not None and "date" in dated.columns:
        dated = dated[dated["date"] <= cut]
    return int((dated["player_key"] == key).sum())


def _resolved_key(long_df: pd.DataFrame, player: str) -> tuple[str | None, str]:
    return model._resolve_history_player_key(long_df, player)


def _short_cases(results_path: Path, baseline_clean_long: pd.DataFrame) -> list[dict[str, Any]]:
    results = task005._read_json(results_path, [])
    if isinstance(results, dict):
        results = results.get("matches", [])
    if not isinstance(results, list):
        return []
    cases = []
    for case in task005._fixture_cases(results):
        key, mode = task005._resolved_key(baseline_clean_long, case)
        if not key:
            continue
        baseline_count = _pre_count(baseline_clean_long, key, case.get("scheduled_time"))
        if 0 < baseline_count < MIN_MATCHES:
            cases.append({**case, "baseline_key": key, "baseline_mode": mode, "baseline_clean_pre_match_rows": baseline_count})
    return cases


def _profile_case(case: dict[str, Any], preview_clean_long: pd.DataFrame) -> dict[str, Any]:
    preview_key, preview_mode = _resolved_key(preview_clean_long, case["player"])
    same_identity = bool(preview_key and preview_key == case["baseline_key"])
    preview_count = _pre_count(preview_clean_long, preview_key if same_identity else None, case.get("scheduled_time"))
    baseline_count = int(case["baseline_clean_pre_match_rows"])
    return {
        "match_id": case.get("match_id"),
        "scheduled_time": case.get("scheduled_time"),
        "player": case.get("player"),
        "requested_key": case.get("requested_key"),
        "baseline_key": case["baseline_key"],
        "baseline_mode": case["baseline_mode"],
        "preview_key": preview_key,
        "preview_mode": preview_mode,
        "identity_stable": same_identity,
        "baseline_clean_pre_match_rows": baseline_count,
        "preview_clean_pre_match_rows": preview_count,
        "net_clean_pre_match_rows": preview_count - baseline_count if same_identity else 0,
        "reaches_minimum_5": bool(same_identity and baseline_count < MIN_MATCHES <= preview_count),
    }


def build_report(
    *,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    results_path: Path = DEFAULT_RESULTS,
    downloader: Callable[[str], pd.DataFrame] = update.download_csv,
    now: datetime | None = None,
) -> dict[str, Any]:
    cache_root = Path(cache_root)
    now = now or datetime.now(timezone.utc)
    manifest = _read_manifest(cache_root)

    baseline_frames: dict[str, pd.DataFrame] = {}
    preview_frames: dict[str, pd.DataFrame] = {}
    source_rows = []
    refresh_attempts = refresh_success = refresh_failures = 0

    for source in update.TML_SOURCES:
        cached = _read_cached(cache_root, source)
        if cached is not None:
            baseline_frames[source["key"]] = cached
            preview_frames[source["key"]] = cached

        refreshable = source.get("refresh_hours") is not None
        fresh = None
        error = None
        if refreshable:
            refresh_attempts += 1
            try:
                candidate = downloader(source["url"])
                if candidate is None or candidate.empty:
                    raise RuntimeError("empty_csv")
                fresh = candidate
                preview_frames[source["key"]] = fresh
                refresh_success += 1
            except Exception as exc:  # audit records outage and leaves cached source in preview
                error = type(exc).__name__
                refresh_failures += 1

        old_sigs = _signatures(cached)
        new_sigs = _signatures(fresh) if fresh is not None else old_sigs
        manifest_row = ((manifest.get("sources") or {}).get(source["key"]) or {})
        source_rows.append({
            "key": source["key"],
            "tour": source["tour"],
            "refresh_hours": source.get("refresh_hours"),
            "refreshable": refreshable,
            "fetch_success": fresh is not None,
            "fetch_error": error,
            "manifest_fetched_at": manifest_row.get("fetched_at"),
            "cached_rows": int(len(cached)) if cached is not None else 0,
            "fresh_rows": int(len(fresh)) if fresh is not None else None,
            "cached_latest_tourney_date": _latest_tourney_date(cached),
            "fresh_latest_tourney_date": _latest_tourney_date(fresh),
            "new_row_signatures": len(new_sigs - old_sigs) if fresh is not None else 0,
            "missing_from_fresh_signatures": len(old_sigs - new_sigs) if fresh is not None else 0,
        })

    baseline_raw = _combine(baseline_frames)
    preview_raw = _combine(preview_frames)
    baseline_clean, baseline_hygiene = clean_history(baseline_raw)
    preview_clean, preview_hygiene = clean_history(preview_raw)
    baseline_long = model.normalize_matches(baseline_clean)
    preview_long = model.normalize_matches(preview_clean)

    cases = _short_cases(results_path, baseline_long)
    case_rows = [_profile_case(case, preview_long) for case in cases]
    reached = [row for row in case_rows if row["reaches_minimum_5"]]
    unstable = [row for row in case_rows if not row["identity_stable"]]
    positive = [row for row in case_rows if row["net_clean_pre_match_rows"] > 0]

    unique_players = {row["requested_key"] for row in case_rows if row.get("requested_key")}
    reached_players = {row["requested_key"] for row in reached if row.get("requested_key")}
    positive_players = {row["requested_key"] for row in positive if row.get("requested_key")}
    category_counts = Counter()
    for row in case_rows:
        if not row["identity_stable"]:
            category_counts["identity_changed_fail_closed"] += 1
        elif row["reaches_minimum_5"]:
            category_counts["reaches_minimum_5"] += 1
        elif row["net_clean_pre_match_rows"] > 0:
            category_counts["gains_history_but_below_5"] += 1
        elif row["net_clean_pre_match_rows"] < 0:
            category_counts["fresh_snapshot_has_fewer_pre_match_rows"] += 1
        else:
            category_counts["no_change"] += 1

    return {
        "version": VERSION,
        "generated_at": now.isoformat(),
        "policy": {
            "live_tennis_api_calls": 0,
            "tennismylife_requests_only": True,
            "uses_existing_declared_tml_urls_only": True,
            "production_cache_writes": 0,
            "runtime_change_authorized": False,
            "minimum_match_gate_changed": False,
            "history_hygiene_changed": False,
            "identity_resolver_changed": False,
            "model_math_changed": False,
            "fresh_data_authorized_for_runtime": False,
        },
        "summary": {
            "declared_sources": len(update.TML_SOURCES),
            "refreshable_sources": sum(1 for source in update.TML_SOURCES if source.get("refresh_hours") is not None),
            "immutable_sources": sum(1 for source in update.TML_SOURCES if source.get("refresh_hours") is None),
            "refresh_attempts": refresh_attempts,
            "refresh_success": refresh_success,
            "refresh_failures": refresh_failures,
            "baseline_raw_rows": int(len(baseline_raw)),
            "preview_raw_rows": int(len(preview_raw)),
            "baseline_clean_rows": int(len(baseline_clean)),
            "preview_clean_rows": int(len(preview_clean)),
            "short_history_cases": len(case_rows),
            "unique_short_history_players": len(unique_players),
            "cases_with_positive_history_gain": len(positive),
            "players_with_positive_history_gain": len(positive_players),
            "cases_reaching_minimum_5": len(reached),
            "players_reaching_minimum_5": len(reached_players),
            "identity_changed_fail_closed": len(unstable),
            "total_new_clean_pre_match_rows_across_cases": int(sum(max(0, row["net_clean_pre_match_rows"]) for row in case_rows)),
        },
        "category_counts": dict(sorted(category_counts.items())),
        "baseline_hygiene": baseline_hygiene,
        "preview_hygiene": preview_hygiene,
        "sources": source_rows,
        "cases": case_rows,
        "priority": {
            "reaches_minimum_5": reached,
            "gains_history_but_below_5": [row for row in positive if not row["reaches_minimum_5"]],
            "identity_changed_fail_closed": unstable,
        },
        "decision": {
            "runtime_change": False,
            "history_gate_change": False,
            "authorize_fresh_tml": False,
            "reason": (
                "TASK 010 is a non-mutating freshness preview. If current declared TML sources add safe clean pre-match rows, "
                "the existing production refresh pipeline can be evaluated separately; this audit never writes cache or model state."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview current declared TennisMyLife sources against restored cache")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report(cache_root=args.cache_root, results_path=args.results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    if report["policy"]["live_tennis_api_calls"] != 0 or report["decision"]["runtime_change"]:
        return 2
    if report["summary"]["refresh_success"] <= 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
