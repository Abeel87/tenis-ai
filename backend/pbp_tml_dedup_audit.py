from __future__ import annotations

"""TASK 007: audit PBP/TennisMyLife overlap for short-history players.

Diagnostic only. Uses existing cached TennisMyLife CSVs and local Live Tennis
PBP payloads. It never makes network requests and never authorizes PBP as model
history. Cross-provider numeric IDs are never compared.
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from . import pbp_enrich as pbp
    from . import pbp_short_history_supply_audit as task006
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
    from .player_identity import player_identity_map
except ImportError:  # pragma: no cover
    import pbp_enrich as pbp
    import pbp_short_history_supply_audit as task006
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history
    from player_identity import player_identity_map


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = ROOT / "data" / "cache"
DEFAULT_PBP_ROOT = DEFAULT_CACHE_ROOT / "pbp_v7"
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "pbp_tml_dedup_audit.json"

VERSION = "task-007-pbp-tml-dedup-audit-v1"
MAX_TOURNAMENT_DAY_GAP = 8
MAX_EXAMPLES = 24
SET_TOKEN_RE = re.compile(r"^(\d+)\s*[-:]\s*(\d+)")


def _key(value: Any) -> str:
    return pbp._key(value)


def _parse_dt(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    return parsed


def _parse_tml_day(value: Any):
    text = str(value or "").strip()
    if not text:
        return None
    parsed = pd.to_datetime(text[:8], format="%Y%m%d", errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def _parse_tml_score(score: Any) -> tuple[tuple[int, int], ...]:
    if not isinstance(score, str):
        return ()
    out: list[tuple[int, int]] = []
    for token in score.replace(",", " ").split():
        match = SET_TOKEN_RE.match(token.strip())
        if match:
            out.append((int(match.group(1)), int(match.group(2))))
    return tuple(out)


def _pbp_score(payload: dict[str, Any]) -> tuple[tuple[int, int], ...]:
    match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    games = score.get("games")
    if not (
        isinstance(games, list)
        and len(games) == 2
        and all(isinstance(row, list) for row in games)
    ):
        return ()
    out: list[tuple[int, int]] = []
    for left, right in zip(games[0], games[1]):
        try:
            pair = (int(left), int(right))
        except (TypeError, ValueError):
            return ()
        if pair == (0, 0):
            continue
        out.append(pair)
    return tuple(out)


def _canonical_pair_score(
    p1: Any,
    p2: Any,
    sets: tuple[tuple[int, int], ...],
) -> tuple[tuple[str, str], tuple[tuple[int, int], ...]] | None:
    k1, k2 = _key(p1), _key(p2)
    if not k1 or not k2 or k1 == k2:
        return None
    if k1 < k2:
        return (k1, k2), sets
    return (k2, k1), tuple((b, a) for a, b in sets)


def _surface(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _tml_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    required = {"winner_name", "loser_name", "tourney_date", "score"}
    if not required.issubset(frame.columns):
        return []
    out: list[dict[str, Any]] = []
    for idx, row in frame.iterrows():
        score = _parse_tml_score(row.get("score"))
        canonical = _canonical_pair_score(row.get("winner_name"), row.get("loser_name"), score)
        day = _parse_tml_day(row.get("tourney_date"))
        if canonical is None or day is None:
            continue
        pair, canonical_score = canonical
        out.append(
            {
                "row_index": int(idx) if isinstance(idx, int) else str(idx),
                "pair": pair,
                "score": canonical_score,
                "day": day,
                "surface": _surface(row.get("surface")),
                "tourney_id": row.get("tourney_id"),
                "match_num": row.get("match_num"),
                "winner_name": row.get("winner_name"),
                "loser_name": row.get("loser_name"),
                "score_text": row.get("score"),
            }
        )
    return out


def _index_tml(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        out[row["pair"]].append(row)
    return out


def _day_gap(pbp_dt: datetime | None, tml_day) -> int | None:
    if pbp_dt is None or tml_day is None:
        return None
    return abs((pbp_dt.date() - tml_day).days)


def _surface_compatible(pbp_surface: str, tml_surface: str) -> bool:
    return not pbp_surface or not tml_surface or pbp_surface == tml_surface


def _window_rows(
    rows: list[dict[str, Any]],
    *,
    pbp_dt: datetime | None,
    pbp_surface: str,
) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        gap = _day_gap(pbp_dt, row.get("day"))
        if gap is None or gap > MAX_TOURNAMENT_DAY_GAP:
            continue
        if not _surface_compatible(pbp_surface, str(row.get("surface") or "")):
            continue
        out.append(row)
    return out


def classify_overlap(
    *,
    pair: tuple[str, str],
    score: tuple[tuple[int, int], ...],
    scheduled_dt: datetime | None,
    surface: str,
    clean_index: dict[tuple[str, str], list[dict[str, Any]]],
    raw_index: dict[tuple[str, str], list[dict[str, Any]]],
) -> tuple[str, list[dict[str, Any]]]:
    """Classify one terminal PBP event without authorizing any runtime use."""
    if not score:
        return "ambiguous_missing_pbp_score", []

    clean_window = _window_rows(
        clean_index.get(pair, []),
        pbp_dt=scheduled_dt,
        pbp_surface=surface,
    )
    clean_exact = [row for row in clean_window if row["score"] == score]
    if len(clean_exact) == 1:
        return "deterministic_duplicate_clean_tml", clean_exact
    if len(clean_exact) > 1:
        return "ambiguous_multiple_clean_exact", clean_exact

    raw_window = _window_rows(
        raw_index.get(pair, []),
        pbp_dt=scheduled_dt,
        pbp_surface=surface,
    )
    raw_exact = [row for row in raw_window if row["score"] == score]
    if len(raw_exact) == 1:
        return "raw_only_duplicate_tml", raw_exact
    if len(raw_exact) > 1:
        return "ambiguous_multiple_raw_exact", raw_exact

    if clean_window or raw_window:
        return "ambiguous_pair_window_score_conflict", (clean_window or raw_window)

    return "unmatched_in_tml_cache", []


def _target_players(task006_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for row in task006_report.get("players") or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("player_key") or "").strip()
        stable_id = row.get("stable_provider_id")
        cutoff = _parse_dt(row.get("cutoff"))
        if (
            not key
            or isinstance(stable_id, bool)
            or not isinstance(stable_id, int)
            or row.get("provider_identity_conflict")
            or cutoff is None
        ):
            continue
        out[key] = {
            "player": row.get("player"),
            "player_key": key,
            "stable_provider_id": stable_id,
            "cutoff": cutoff,
            "current_clean_history_matches": int(row.get("current_clean_history_matches") or 0),
        }
    return out


def _collect_terminal_observations(
    *,
    targets: dict[str, dict[str, Any]],
    pbp_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    observations: list[dict[str, Any]] = []
    scanned = readable = stable_identity = 0
    file_id_mismatch = 0

    paths = sorted((pbp_root / "matches").glob("*.json.gz"))
    for path in paths:
        scanned += 1
        payload = pbp._read_gzip_json(path)
        if not isinstance(payload, dict):
            continue
        readable += 1
        mapping = player_identity_map(payload)
        if mapping is None:
            continue
        stable_identity += 1

        payload_mid, payload_time = pbp._cached_match_identity_and_time(payload)
        file_mid = path.name.removesuffix(".json.gz")
        file_id_ok = payload_mid is not None and str(payload_mid) == file_mid
        if not file_id_ok:
            file_id_mismatch += 1
            continue

        match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
        if match.get("is_doubles") is True:
            continue
        scheduled_dt = _parse_dt(payload_time)
        if scheduled_dt is None or not pbp._cache_has_terminal_stats(payload):
            continue

        p1, p2 = mapping[1], mapping[2]
        canonical = _canonical_pair_score(p1.get("name"), p2.get("name"), _pbp_score(payload))
        if canonical is None:
            continue
        pair, canonical_score = canonical
        surface = _surface(match.get("surface"))

        for side, record in ((1, p1), (2, p2)):
            key = _key(record.get("name"))
            target = targets.get(key)
            if target is None:
                continue
            if int(record["id"]) != int(target["stable_provider_id"]):
                continue
            if scheduled_dt >= target["cutoff"]:
                continue
            observations.append(
                {
                    "player": target["player"],
                    "player_key": key,
                    "current_clean_history_matches": target["current_clean_history_matches"],
                    "stable_provider_id": target["stable_provider_id"],
                    "match_id": payload_mid,
                    "scheduled_time": payload_time,
                    "scheduled_dt": scheduled_dt,
                    "pair": pair,
                    "score": canonical_score,
                    "surface": surface,
                    "side": side,
                    "p1": p1.get("name"),
                    "p2": p2.get("name"),
                }
            )

    return observations, {
        "cache_payload_files_scanned": scanned,
        "cache_payloads_readable": readable,
        "cache_payloads_with_stable_identity": stable_identity,
        "cache_payload_file_id_mismatches": file_id_mismatch,
    }


def build_report(
    *,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    pbp_root: Path = DEFAULT_PBP_ROOT,
    results_path: Path = DEFAULT_RESULTS,
) -> dict[str, Any]:
    task006_report = task006.build_report(
        cache_root=cache_root,
        pbp_root=pbp_root,
        results_path=results_path,
    )
    targets = _target_players(task006_report)

    raw_history = load_cached_history()
    clean_history_df, hygiene = clean_history(raw_history)
    raw_rows = _tml_rows(raw_history)
    clean_rows = _tml_rows(clean_history_df)
    raw_index = _index_tml(raw_rows)
    clean_index = _index_tml(clean_rows)

    observations, scan = _collect_terminal_observations(
        targets=targets,
        pbp_root=pbp_root,
    )

    classified: list[dict[str, Any]] = []
    counts = Counter()
    supply_by_player: dict[str, Counter[str]] = defaultdict(Counter)

    for obs in observations:
        category, matches = classify_overlap(
            pair=obs["pair"],
            score=obs["score"],
            scheduled_dt=obs["scheduled_dt"],
            surface=obs["surface"],
            clean_index=clean_index,
            raw_index=raw_index,
        )
        counts[category] += 1
        supply_by_player[obs["player_key"]][category] += 1
        classified.append(
            {
                **{k: v for k, v in obs.items() if k != "scheduled_dt"},
                "score": [list(pair) for pair in obs["score"]],
                "category": category,
                "tml_matches": [
                    {
                        "day": row["day"].isoformat(),
                        "surface": row["surface"],
                        "tourney_id": row["tourney_id"],
                        "match_num": row["match_num"],
                        "winner_name": row["winner_name"],
                        "loser_name": row["loser_name"],
                        "score_text": row["score_text"],
                    }
                    for row in matches[:4]
                ],
            }
        )

    player_rows = []
    for key, target in sorted(targets.items()):
        c = supply_by_player.get(key, Counter())
        clean_dup = int(c["deterministic_duplicate_clean_tml"])
        raw_only = int(c["raw_only_duplicate_tml"])
        unmatched = int(c["unmatched_in_tml_cache"])
        ambiguous = int(sum(v for k, v in c.items() if k.startswith("ambiguous_")))
        potentially_additive = raw_only + unmatched
        player_rows.append(
            {
                "player": target["player"],
                "player_key": key,
                "current_clean_history_matches": target["current_clean_history_matches"],
                "terminal_pbp_observations": int(sum(c.values())),
                "clean_tml_duplicates": clean_dup,
                "raw_only_duplicates": raw_only,
                "unmatched_in_tml_cache": unmatched,
                "ambiguous": ambiguous,
                "potentially_additive_if_schema_proven": potentially_additive,
                "upper_bound_reaches_five_after_clean_dedup": (
                    target["current_clean_history_matches"] + potentially_additive >= 5
                ),
            }
        )

    unique_match_ids = {str(row["match_id"]) for row in classified}
    categories_by_match: dict[str, set[str]] = defaultdict(set)
    for row in classified:
        categories_by_match[str(row["match_id"])].add(row["category"])

    return {
        "version": VERSION,
        "policy": {
            "network_calls": 0,
            "fuzzy_matching": False,
            "similarity_thresholds": False,
            "manual_aliases": False,
            "cross_provider_numeric_id_comparison": False,
            "pbp_provider_id_used_only_within_pbp_namespace": True,
            "minimum_match_gate_changed": False,
            "history_hygiene_changed": False,
            "identity_resolver_changed": False,
            "runtime_change_authorized": False,
            "pbp_authorized_for_main_history": False,
            "unmatched_pbp_authorized_as_new_history": False,
            "schema_compatibility_proven": False,
            "tournament_date_gap_days": MAX_TOURNAMENT_DAY_GAP,
            "deterministic_duplicate_requires": (
                "exact normalized participant pair + exact orientation-normalized set score + "
                "surface compatibility when both present + unique TML row within tournament-date window"
            ),
        },
        "summary": {
            "task006_audited_unique_players": int(
                task006_report.get("summary", {}).get("audited_unique_players") or 0
            ),
            "target_players_with_stable_pbp_identity": len(targets),
            **scan,
            "tml_raw_rows_indexed": len(raw_rows),
            "tml_clean_rows_indexed": len(clean_rows),
            "terminal_pbp_player_observations": len(classified),
            "terminal_pbp_unique_matches": len(unique_match_ids),
            "deterministic_duplicate_clean_tml": int(counts["deterministic_duplicate_clean_tml"]),
            "raw_only_duplicate_tml": int(counts["raw_only_duplicate_tml"]),
            "unmatched_in_tml_cache": int(counts["unmatched_in_tml_cache"]),
            "ambiguous_observations": int(
                sum(v for k, v in counts.items() if k.startswith("ambiguous_"))
            ),
            "players_with_potentially_additive_supply": sum(
                1 for row in player_rows if row["potentially_additive_if_schema_proven"] > 0
            ),
            "upper_bound_players_reaching_five_after_clean_dedup": sum(
                1 for row in player_rows if row["upper_bound_reaches_five_after_clean_dedup"]
            ),
            "unique_matches_with_mixed_player_classification": sum(
                1 for categories in categories_by_match.values() if len(categories) > 1
            ),
        },
        "history_hygiene": hygiene,
        "category_counts": dict(sorted(counts.items())),
        "players": player_rows,
        "observations": classified,
        "examples": classified[:MAX_EXAMPLES],
        "decision": {
            "runtime_change": False,
            "history_gate_change": False,
            "reason": (
                "TASK 007 only identifies overlap against existing TennisMyLife cache. "
                "Raw-only and unmatched PBP events remain unauthorized until a separate "
                "schema-compatibility audit proves they can reproduce the model's required "
                "historical fields without changing model mathematics."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit terminal PBP overlap against cached TennisMyLife history"
    )
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--pbp-root", type=Path, default=DEFAULT_PBP_ROOT)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_report(
        cache_root=args.cache_root,
        pbp_root=args.pbp_root,
        results_path=args.results,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    if report["policy"]["network_calls"] != 0 or report["decision"]["runtime_change"]:
        return 2
    if report["summary"]["terminal_pbp_player_observations"] <= 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
