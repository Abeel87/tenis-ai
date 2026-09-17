from __future__ import annotations

"""TASK 014: preview TennisMyLife 2024 archives without mutating runtime/cache.

The audit downloads four public 2024 TennisMyLife CSVs into memory only. It
never calls Live Tennis API, never writes ``data/cache``, never changes the
identity resolver, and never changes the model's minimum-history gate.

For current 1-4-match history cases, the audit reuses the already-resolved
baseline history key and only counts exact normalized ``player_key`` matches in
an augmented baseline+2024 snapshot. It deliberately does not use provider IDs,
alias inference, fuzzy matching, or cross-provider joins.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import pandas as pd

try:
    from . import insufficient_history_evidence as task005
    from . import model, update
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
except ImportError:  # pragma: no cover
    import insufficient_history_evidence as task005
    import model, update
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "tml_2024_history_preview.json"
VERSION = "task-014-tml-2024-history-preview-v1"
MIN_MATCHES = task005.MIN_MATCHES

TML_2024_SOURCES = (
    {"key": "atp_2024", "tour": "ATP", "url": "https://stats.tennismylife.org/data/2024.csv"},
    {"key": "atp_quali_2024", "tour": "ATP", "url": "https://stats.tennismylife.org/data/atp_quali/2024_atp_quali.csv"},
    {"key": "ch_2024", "tour": "CH", "url": "https://stats.tennismylife.org/data/2024_challenger.csv"},
    {"key": "wta_2024", "tour": "WTA", "url": "https://stats.tennismylife.org/data/2024_wta.csv"},
)


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


def _dated_pre_count(long_df: pd.DataFrame, key: str | None, scheduled_time: Any) -> int:
    if not key or long_df is None or long_df.empty or "player_key" not in long_df.columns:
        return 0
    dated = model._dated_history(long_df)
    if dated is None or dated.empty or "date" not in dated.columns:
        return 0
    cutoff = model._naive_cutoff(scheduled_time)
    if cutoff is not None:
        dated = dated[dated["date"] <= cutoff]
    return int((dated["player_key"] == key).sum())


def _baseline_cases(results: list[dict[str, Any]], baseline_long: pd.DataFrame) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for case in task005._fixture_cases(results):
        key, mode = task005._resolved_key(baseline_long, case)
        if not key:
            continue
        count = _dated_pre_count(baseline_long, key, case.get("scheduled_time"))
        if not 0 < count < MIN_MATCHES:
            continue
        cases.append({
            **case,
            "baseline_key": key,
            "baseline_mode": mode,
            "baseline_clean_pre_match_rows": count,
        })
    return cases


def _profile_case(case: dict[str, Any], augmented_long: pd.DataFrame) -> dict[str, Any]:
    baseline_count = int(case["baseline_clean_pre_match_rows"])
    augmented_count = _dated_pre_count(
        augmented_long,
        case["baseline_key"],
        case.get("scheduled_time"),
    )
    gain = max(0, augmented_count - baseline_count)
    return {
        "match_id": case.get("match_id"),
        "scheduled_time": case.get("scheduled_time"),
        "side": case.get("side"),
        "player": case.get("player"),
        "requested_key": case.get("requested_key"),
        "baseline_key": case["baseline_key"],
        "baseline_mode": case["baseline_mode"],
        "baseline_clean_pre_match_rows": baseline_count,
        "augmented_clean_pre_match_rows": augmented_count,
        "net_2024_clean_pre_match_rows": gain,
        "reaches_minimum_5": bool(baseline_count < MIN_MATCHES <= augmented_count),
    }


def build_report(
    *,
    baseline_raw: pd.DataFrame,
    results: list[dict[str, Any]],
    archive_frames: dict[str, pd.DataFrame],
    source_status: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    baseline_clean, baseline_hygiene = clean_history(baseline_raw)
    baseline_long = model.normalize_matches(baseline_clean)
    cases = _baseline_cases(results, baseline_long)

    frames = [baseline_raw.copy()]
    for source in TML_2024_SOURCES:
        frame = archive_frames.get(source["key"])
        if frame is not None and not frame.empty:
            frames.append(_annotate(frame, source))
    augmented_raw = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    augmented_clean, augmented_hygiene = clean_history(augmented_raw)
    augmented_long = model.normalize_matches(augmented_clean)

    rows = [_profile_case(case, augmented_long) for case in cases]
    positive = [row for row in rows if row["net_2024_clean_pre_match_rows"] > 0]
    reached = [row for row in rows if row["reaches_minimum_5"]]
    unique_players = {row["baseline_key"] for row in rows}
    positive_players = {row["baseline_key"] for row in positive}
    reached_players = {row["baseline_key"] for row in reached}

    categories = Counter()
    for row in rows:
        if row["reaches_minimum_5"]:
            categories["reaches_minimum_5"] += 1
        elif row["net_2024_clean_pre_match_rows"] > 0:
            categories["gains_history_but_below_5"] += 1
        else:
            categories["no_exact_key_gain"] += 1

    source_status = source_status or [
        {
            "key": source["key"],
            "tour": source["tour"],
            "url": source["url"],
            "fetch_success": source["key"] in archive_frames,
            "rows": int(len(archive_frames[source["key"]])) if source["key"] in archive_frames else 0,
            "error": None,
        }
        for source in TML_2024_SOURCES
    ]

    return {
        "version": VERSION,
        "policy": {
            "live_tennis_api_calls": 0,
            "tennismylife_requests": len(TML_2024_SOURCES),
            "tennismylife_2024_only": True,
            "production_cache_writes": 0,
            "temporary_or_memory_only": True,
            "fuzzy_matching": False,
            "manual_aliases": False,
            "provider_id_matching": False,
            "cross_provider_id_comparison": False,
            "uses_existing_baseline_history_key_only": True,
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
            "baseline_raw_rows": int(len(baseline_raw)),
            "baseline_clean_rows": int(len(baseline_clean)),
            "augmented_raw_rows": int(len(augmented_raw)),
            "augmented_clean_rows": int(len(augmented_clean)),
            "short_history_slots": len(rows),
            "short_history_players": len(unique_players),
            "slots_with_positive_2024_gain": len(positive),
            "players_with_positive_2024_gain": len(positive_players),
            "slots_reaching_minimum_5": len(reached),
            "players_reaching_minimum_5": len(reached_players),
            "total_net_2024_clean_pre_match_rows": int(sum(row["net_2024_clean_pre_match_rows"] for row in rows)),
            "all_2024_sources_fetched": all(row.get("fetch_success") for row in source_status),
        },
        "category_counts": dict(sorted(categories.items())),
        "baseline_hygiene": baseline_hygiene,
        "augmented_hygiene": augmented_hygiene,
        "sources": source_status,
        "priority": {
            "reaches_minimum_5": reached,
            "gains_history_but_below_5": [row for row in positive if not row["reaches_minimum_5"]],
        },
        "cases": rows,
        "decision": {
            "runtime_change": False,
            "authorize_2024_archive": False,
            "reason": (
                "TASK 014 is preview-only. A positive coverage result is evidence for a separate provenance/integration review, "
                "not authorization to change production history inputs."
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
    status: list[dict[str, Any]] = []

    for source in TML_2024_SOURCES:
        try:
            frame = downloader(source["url"])
            if frame is None or frame.empty:
                raise RuntimeError("empty_csv")
            archive_frames[source["key"]] = frame
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
    parser = argparse.ArgumentParser(description="Preview TML 2024 archives against current short-history cases")
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
