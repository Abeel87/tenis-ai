from __future__ import annotations

"""TASK 005: zero-network audit of insufficient pre-match history samples.

This module is diagnostic only. It does not relax the 5-match gate, change
history hygiene, alter identity resolution, call external APIs, or write model
state. It explains why currently-resolved players still have 1-4 usable
pre-match history rows and inventories any undeclared cached CSV files without
trusting or consuming them.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from . import model
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history, score_is_complete
except ImportError:  # pragma: no cover
    import model
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history, score_is_complete


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = ROOT / "data" / "cache"
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "insufficient_history_evidence.json"
VERSION = "task-005-insufficient-history-evidence-v1"
MIN_MATCHES = 5
MAX_EXAMPLES = 12


def _key(value: Any) -> str:
    return model._core._key(value)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _rows_for_key(df: pd.DataFrame, key: str | None) -> int:
    if not key or df is None or df.empty or "player_key" not in df.columns:
        return 0
    return int((df["player_key"] == key).sum())


def _pre_match(df: pd.DataFrame, scheduled_time: Any) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    dated = model._dated_history(df)
    if dated is None or dated.empty or "date" not in dated.columns:
        return dated
    cut = model._naive_cutoff(scheduled_time)
    if cut is None:
        return dated
    return dated[dated["date"] <= cut].copy()


def classify_short_sample(
    *,
    current_matches: int,
    raw_pre_rows: int,
    clean_total_rows: int,
    clean_dated_rows: int,
    clean_pre_rows: int,
) -> str:
    """Explain a 1-4 match profile without changing any model rule."""
    if not 0 < int(current_matches) < MIN_MATCHES:
        return "not_insufficient_sample"
    if clean_pre_rows >= MIN_MATCHES:
        return "runtime_profile_count_mismatch"
    if raw_pre_rows >= MIN_MATCHES and clean_pre_rows < MIN_MATCHES:
        return "hygiene_blocks_threshold"
    if clean_total_rows >= MIN_MATCHES and clean_dated_rows < MIN_MATCHES:
        return "undated_rows_block_threshold"
    if clean_dated_rows >= MIN_MATCHES and clean_pre_rows < MIN_MATCHES:
        return "post_cutoff_rows_block_threshold"
    return "genuine_short_clean_history"


def _declared_cache_files() -> set[str]:
    try:
        from .update import TML_SOURCES
    except ImportError:  # pragma: no cover
        from update import TML_SOURCES
    return {f"{source['key']}.csv.gz" for source in TML_SOURCES}


def _fixture_cases(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for match in results:
        if not isinstance(match, dict):
            continue
        for side in ("p1", "p2"):
            stats = match.get(f"{side}_stats") or {}
            try:
                matches = int(stats.get("matches") or 0)
            except (TypeError, ValueError):
                matches = 0
            if not 0 < matches < MIN_MATCHES:
                continue
            player = str(match.get(side) or "").strip()
            if not player:
                continue
            cases.append({
                "match_id": match.get("id"),
                "scheduled_time": match.get("scheduled_time"),
                "side": side,
                "player": player,
                "requested_key": _key(player),
                "current_matches": matches,
                "current_quality": str(stats.get("quality") or "LOW"),
                "identity_mode": str(stats.get("history_identity_mode") or "none"),
                "history_player_key": stats.get("history_player_key"),
            })
    return cases


def _resolved_key(clean_long: pd.DataFrame, case: dict[str, Any]) -> tuple[str | None, str]:
    stored = case.get("history_player_key")
    if isinstance(stored, str) and stored.strip():
        return stored.strip(), str(case.get("identity_mode") or "stored")
    key, mode = model._resolve_history_player_key(clean_long, case["player"])
    return key, mode


def _profile_case(
    case: dict[str, Any],
    *,
    raw_long: pd.DataFrame,
    clean_long: pd.DataFrame,
) -> dict[str, Any]:
    resolved_key, resolver_mode = _resolved_key(clean_long, case)
    raw_dated = model._dated_history(raw_long)
    clean_dated = model._dated_history(clean_long)
    raw_pre = _pre_match(raw_long, case.get("scheduled_time"))
    clean_pre = _pre_match(clean_long, case.get("scheduled_time"))

    raw_total_rows = _rows_for_key(raw_long, resolved_key)
    raw_dated_rows = _rows_for_key(raw_dated, resolved_key)
    raw_pre_rows = _rows_for_key(raw_pre, resolved_key)
    clean_total_rows = _rows_for_key(clean_long, resolved_key)
    clean_dated_rows = _rows_for_key(clean_dated, resolved_key)
    clean_pre_rows = _rows_for_key(clean_pre, resolved_key)

    category = classify_short_sample(
        current_matches=case["current_matches"],
        raw_pre_rows=raw_pre_rows,
        clean_total_rows=clean_total_rows,
        clean_dated_rows=clean_dated_rows,
        clean_pre_rows=clean_pre_rows,
    )
    return {
        **case,
        "resolved_key": resolved_key,
        "resolver_mode": resolver_mode,
        "raw_total_rows": raw_total_rows,
        "raw_dated_rows": raw_dated_rows,
        "raw_pre_match_rows": raw_pre_rows,
        "clean_total_rows": clean_total_rows,
        "clean_dated_rows": clean_dated_rows,
        "clean_pre_match_rows": clean_pre_rows,
        "rows_removed_or_invalid_before_cutoff": max(0, raw_pre_rows - clean_pre_rows),
        "category": category,
    }


def _earliest_cutoffs(cases: list[dict[str, Any]]) -> dict[str, pd.Timestamp]:
    out: dict[str, pd.Timestamp] = {}
    for case in cases:
        key = case.get("resolved_key")
        if not key:
            continue
        cut = pd.to_datetime(case.get("scheduled_time"), utc=True, errors="coerce")
        if pd.isna(cut):
            continue
        normalized = pd.Timestamp(cut.date(), tz="UTC")
        previous = out.get(key)
        if previous is None or normalized < previous:
            out[key] = normalized
    return out


def _scan_undeclared_cache(
    cache_root: Path,
    *,
    declared_files: set[str],
    resolved_keys: set[str],
    earliest_cutoffs: dict[str, pd.Timestamp],
) -> dict[str, Any]:
    """Inventory exact-name complete rows in undeclared cache files.

    These rows are never consumed by the model and never authorized here. The
    inventory only answers whether already-present cache material deserves a
    separate provenance review.
    """
    extra_files = sorted(
        path for path in cache_root.glob("*.csv.gz")
        if path.name not in declared_files
    )
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    readable_files = 0
    scanned_rows = 0

    for path in extra_files:
        try:
            frame = pd.read_csv(path, compression="gzip", low_memory=False)
        except Exception:
            continue
        readable_files += 1
        if frame.empty:
            continue
        scanned_rows += int(len(frame))
        if not {"winner_name", "loser_name", "score"}.issubset(frame.columns):
            continue

        for _, row in frame.iterrows():
            score = row.get("score")
            best_of = row.get("best_of") if "best_of" in frame.columns else None
            if not score_is_complete(score, best_of):
                continue
            date_value = pd.to_datetime(str(row.get("tourney_date") or ""), format="%Y%m%d", errors="coerce", utc=True)
            if pd.isna(date_value):
                continue
            for name_col in ("winner_name", "loser_name"):
                key = _key(row.get(name_col))
                if key not in resolved_keys:
                    continue
                cutoff = earliest_cutoffs.get(key)
                if cutoff is None or date_value > cutoff:
                    continue
                counts[key][path.name] += 1

    rows = [
        {
            "history_key": key,
            "files": dict(sorted(counter.items())),
            "complete_pre_match_rows": int(sum(counter.values())),
        }
        for key, counter in sorted(counts.items())
        if counter
    ]
    return {
        "extra_csv_files": [path.name for path in extra_files],
        "readable_extra_csv_files": readable_files,
        "scanned_extra_rows": scanned_rows,
        "exact_complete_pre_match_rows_by_key": rows,
        "authorized_for_runtime": False,
    }


def build_report(
    *,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    results_path: Path = DEFAULT_RESULTS,
) -> dict[str, Any]:
    results = _read_json(results_path, [])
    if isinstance(results, dict):
        results = results.get("matches", [])
    if not isinstance(results, list):
        results = []

    raw_history = load_cached_history()
    cleaned_history, hygiene = clean_history(raw_history)
    raw_long = model.normalize_matches(raw_history)
    clean_long = model.normalize_matches(cleaned_history)

    fixture_cases = _fixture_cases(results)
    case_rows = [
        _profile_case(case, raw_long=raw_long, clean_long=clean_long)
        for case in fixture_cases
    ]
    categories = Counter(row["category"] for row in case_rows)

    declared_files = _declared_cache_files()
    present_files = {path.name for path in cache_root.glob("*.csv.gz")}
    missing_declared = sorted(declared_files - present_files)

    resolved_keys = {row["resolved_key"] for row in case_rows if row.get("resolved_key")}
    undeclared = _scan_undeclared_cache(
        cache_root,
        declared_files=declared_files,
        resolved_keys=resolved_keys,
        earliest_cutoffs=_earliest_cutoffs(case_rows),
    )

    unique_players = sorted({row["requested_key"] for row in case_rows if row.get("requested_key")})
    runtime_mismatch = [row for row in case_rows if row["category"] == "runtime_profile_count_mismatch"]
    hygiene_blocked = [row for row in case_rows if row["category"] == "hygiene_blocks_threshold"]
    post_cutoff = [row for row in case_rows if row["category"] == "post_cutoff_rows_block_threshold"]
    undated = [row for row in case_rows if row["category"] == "undated_rows_block_threshold"]
    genuine_short = [row for row in case_rows if row["category"] == "genuine_short_clean_history"]

    return {
        "version": VERSION,
        "policy": {
            "network_calls": 0,
            "fuzzy_matching": False,
            "similarity_thresholds": False,
            "manual_aliases": False,
            "minimum_match_gate_changed": False,
            "minimum_match_gate": MIN_MATCHES,
            "history_hygiene_changed": False,
            "identity_resolver_changed": False,
            "runtime_change_authorized": False,
            "undeclared_cache_rows_authorized": False,
        },
        "summary": {
            "visible_matches": len(results),
            "insufficient_player_cases": len(case_rows),
            "unique_insufficient_players": len(unique_players),
            "category_counts": dict(sorted(categories.items())),
            "runtime_profile_count_mismatch": len(runtime_mismatch),
            "hygiene_blocks_threshold": len(hygiene_blocked),
            "undated_rows_block_threshold": len(undated),
            "post_cutoff_rows_block_threshold": len(post_cutoff),
            "genuine_short_clean_history": len(genuine_short),
            "declared_cache_files": len(declared_files),
            "present_root_csv_files": len(present_files),
            "missing_declared_cache_files": len(missing_declared),
            "undeclared_cache_files": len(undeclared["extra_csv_files"]),
            "undeclared_exact_complete_keys": len(undeclared["exact_complete_pre_match_rows_by_key"]),
        },
        "history_hygiene": hygiene,
        "missing_declared_cache_files": missing_declared,
        "undeclared_cache_inventory": undeclared,
        "cases": case_rows,
        "priority": {
            "runtime_profile_count_mismatch": runtime_mismatch[:MAX_EXAMPLES],
            "hygiene_blocks_threshold": hygiene_blocked[:MAX_EXAMPLES],
            "undated_rows_block_threshold": undated[:MAX_EXAMPLES],
            "post_cutoff_rows_block_threshold": post_cutoff[:MAX_EXAMPLES],
            "genuine_short_clean_history": genuine_short[:MAX_EXAMPLES],
        },
        "decision": {
            "runtime_change": False,
            "reason": "diagnostic-only; only a proven runtime count mismatch or separately validated cache provenance can justify follow-up code changes",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit why safely-resolved players have fewer than five pre-match rows")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_report(cache_root=args.cache_root, results_path=args.results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
