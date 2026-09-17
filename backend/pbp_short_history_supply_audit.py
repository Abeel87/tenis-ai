from __future__ import annotations

"""TASK 006: audit local PBP supply for safely-resolved short-history players.

Diagnostic only. Reads existing TennisMyLife/history evidence and the restored
Live Tennis PBP cache. It performs no network requests and changes no runtime
state. PBP and TennisMyLife records may overlap and use different schemas, so
this audit never authorizes PBP as main model history.
"""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from . import insufficient_history_evidence as short_history
    from . import pbp_enrich as pbp
    from .player_identity import player_identity_map
except ImportError:  # pragma: no cover
    import insufficient_history_evidence as short_history
    import pbp_enrich as pbp
    from player_identity import player_identity_map

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = ROOT / "data" / "cache"
DEFAULT_PBP_ROOT = DEFAULT_CACHE_ROOT / "pbp_v7"
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "pbp_short_history_supply_audit.json"
VERSION = "task-006-pbp-short-history-supply-audit-v2"
MAX_EXAMPLES = 20


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _parse_dt(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _earliest_cutoff(cases: list[dict[str, Any]]) -> datetime | None:
    values = [_parse_dt(row.get("scheduled_time")) for row in cases]
    values = [value for value in values if value is not None]
    return min(values) if values else None


def _group_genuine_short_cases(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for case in report.get("cases") or []:
        if not isinstance(case, dict) or case.get("category") != "genuine_short_clean_history":
            continue
        player = str(case.get("player") or "").strip()
        key = pbp._key(player)
        if player and key:
            grouped.setdefault(key, []).append(case)
    return grouped


def _index_identity(players_index: dict[str, Any], key: str) -> tuple[bool, int | None]:
    entry = players_index.get(key)
    if not isinstance(entry, dict):
        return False, None
    value = entry.get("player_id")
    if isinstance(value, bool) or not isinstance(value, int):
        return True, None
    return True, value


def _scan_payload_supply(
    *,
    grouped: dict[str, list[dict[str, Any]]],
    players_index: dict[str, Any],
    pbp_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    target_keys = set(grouped)
    observed_ids: dict[str, set[int]] = defaultdict(set)
    raw_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scanned = 0
    readable = 0
    stable_identity_payloads = 0
    exact_key_observations = 0
    invalid_file_payload_ids = 0

    match_dir = pbp_root / "matches"
    paths = sorted(match_dir.glob("*.json.gz")) if match_dir.exists() else []
    for path in paths:
        scanned += 1
        payload = pbp._read_gzip_json(path)
        if not isinstance(payload, dict):
            continue
        readable += 1

        mapping = player_identity_map(payload)
        if mapping is None:
            continue
        stable_identity_payloads += 1

        file_mid = path.name.removesuffix(".json.gz")
        payload_mid, payload_time = pbp._cached_match_identity_and_time(payload)
        payload_dt = _parse_dt(payload_time)
        file_payload_id_ok = payload_mid is not None and str(payload_mid) == file_mid
        if not file_payload_id_ok:
            invalid_file_payload_ids += 1

        match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
        if match.get("is_doubles") is True:
            continue

        for side in (1, 2):
            record = mapping[side]
            raw_name = record.get("name")
            key = pbp._key(raw_name)
            if key not in target_keys:
                continue
            exact_key_observations += 1
            observed_ids[key].add(int(record["id"]))
            raw_candidates[key].append(
                {
                    "match_id": payload_mid,
                    "file_match_id": file_mid,
                    "scheduled_time": payload_time,
                    "scheduled_dt": payload_dt,
                    "file_payload_id_ok": file_payload_id_ok,
                    "provider_id": int(record["id"]),
                    "exact_name": raw_name,
                    "payload": payload,
                }
            )

    players: list[dict[str, Any]] = []
    for key, cases in sorted(grouped.items()):
        player = str(cases[0].get("player") or "")
        cutoff = _earliest_cutoff(cases)
        current_history = min(int(row.get("clean_pre_match_rows") or 0) for row in cases)
        index_present, index_id = _index_identity(players_index, key)

        ids = set(observed_ids.get(key, set()))
        provider_identity_conflict = len(ids) > 1 or (
            index_id is not None and bool(ids) and index_id not in ids
        )
        stable_provider_id = next(iter(ids)) if len(ids) == 1 and not provider_identity_conflict else None
        if stable_provider_id is None and not ids and index_id is not None:
            stable_provider_id = index_id

        exact_matches = 0
        pre_cutoff = 0
        identity_valid = 0
        terminal = 0
        extractable = 0
        invalid_identity = 0
        nonterminal = 0
        seen_ids: set[str] = set()
        examples: list[dict[str, Any]] = []

        if not provider_identity_conflict and len(ids) == 1:
            required_id = next(iter(ids))
            for candidate in raw_candidates.get(key, []):
                if candidate["provider_id"] != required_id:
                    continue
                exact_matches += 1
                payload_dt = candidate["scheduled_dt"]
                if cutoff is None or payload_dt is None or payload_dt >= cutoff:
                    continue
                pre_cutoff += 1

                match_id = candidate["match_id"]
                token = str(match_id)
                if token in seen_ids:
                    continue
                seen_ids.add(token)

                if not candidate["file_payload_id_ok"]:
                    invalid_identity += 1
                    continue
                identity_valid += 1

                payload = candidate["payload"]
                is_terminal = bool(pbp._cache_has_terminal_stats(payload))
                if is_terminal:
                    terminal += 1
                else:
                    nonterminal += 1

                can_extract = bool(is_terminal and pbp.extract_first_set_games(payload) is not None)
                if can_extract:
                    extractable += 1

                if len(examples) < 4:
                    examples.append(
                        {
                            "match_id": match_id,
                            "scheduled_time": candidate["scheduled_time"],
                            "provider_id": required_id,
                            "exact_name": candidate["exact_name"],
                            "terminal": is_terminal,
                            "first_set_extractable": can_extract,
                        }
                    )

        players.append(
            {
                "player": player,
                "player_key": key,
                "current_clean_history_matches": current_history,
                "cutoff": cutoff.isoformat() if cutoff else None,
                "pbp_index_present": index_present,
                "pbp_index_player_id": index_id,
                "payload_provider_ids": sorted(ids),
                "stable_provider_id": stable_provider_id,
                "provider_identity_conflict": provider_identity_conflict,
                "exact_payload_matches": exact_matches,
                "pre_cutoff_candidates": pre_cutoff,
                "payload_identity_valid": identity_valid,
                "terminal_tapes": terminal,
                "first_set_extractable": extractable,
                "invalid_payload_identity": invalid_identity,
                "nonterminal_tapes": nonterminal,
                "upper_bound_reaches_five_if_all_terminal_are_distinct": (
                    current_history + terminal >= short_history.MIN_MATCHES
                ),
                "examples": examples,
            }
        )

    scan = {
        "cache_payload_files_scanned": scanned,
        "cache_payloads_readable": readable,
        "cache_payloads_with_stable_identity": stable_identity_payloads,
        "exact_target_key_observations": exact_key_observations,
        "cache_payload_file_id_mismatches": invalid_file_payload_ids,
    }
    return players, scan


def build_report(
    *,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    pbp_root: Path = DEFAULT_PBP_ROOT,
    results_path: Path = DEFAULT_RESULTS,
) -> dict[str, Any]:
    task005 = short_history.build_report(cache_root=cache_root, results_path=results_path)
    grouped = _group_genuine_short_cases(task005)

    index_doc = _read_json(pbp_root / "players.json", {"players": {}})
    players_index = index_doc.get("players") if isinstance(index_doc, dict) else {}
    if not isinstance(players_index, dict):
        players_index = {}

    players, scan = _scan_payload_supply(
        grouped=grouped,
        players_index=players_index,
        pbp_root=pbp_root,
    )

    counts = Counter()
    for row in players:
        counts["pbp_index_present"] += int(bool(row["pbp_index_present"]))
        counts["players_with_payload_provider_identity"] += int(len(row["payload_provider_ids"]) == 1)
        counts["players_with_provider_identity_conflict"] += int(bool(row["provider_identity_conflict"]))
        counts["players_with_exact_payload_match"] += int(row["exact_payload_matches"] > 0)
        counts["players_with_pre_cutoff_candidates"] += int(row["pre_cutoff_candidates"] > 0)
        counts["players_with_identity_valid_tape"] += int(row["payload_identity_valid"] > 0)
        counts["players_with_terminal_tape"] += int(row["terminal_tapes"] > 0)
        counts["players_with_extractable_first_set"] += int(row["first_set_extractable"] > 0)
        counts["upper_bound_players_reaching_five"] += int(
            bool(row["upper_bound_reaches_five_if_all_terminal_are_distinct"])
        )

    sums = {
        field: int(sum(int(row[field]) for row in players))
        for field in (
            "exact_payload_matches",
            "pre_cutoff_candidates",
            "payload_identity_valid",
            "terminal_tapes",
            "first_set_extractable",
            "invalid_payload_identity",
            "nonterminal_tapes",
        )
    }

    priority = sorted(
        players,
        key=lambda row: (
            bool(row["upper_bound_reaches_five_if_all_terminal_are_distinct"]),
            int(row["terminal_tapes"]),
            int(row["first_set_extractable"]),
        ),
        reverse=True,
    )

    return {
        "version": VERSION,
        "policy": {
            "network_calls": 0,
            "fuzzy_matching": False,
            "similarity_thresholds": False,
            "manual_aliases": False,
            "exact_normalized_current_player_key_only": True,
            "stable_provider_integer_identity_required": True,
            "provider_id_conflicts_fail_closed": True,
            "cross_provider_numeric_id_comparison": False,
            "minimum_match_gate_changed": False,
            "history_hygiene_changed": False,
            "identity_resolver_changed": False,
            "runtime_change_authorized": False,
            "pbp_authorized_for_main_history": False,
            "cross_source_deduplication_proven": False,
            "schema_compatibility_proven": False,
        },
        "summary": {
            "task005_insufficient_cases": int(
                task005.get("summary", {}).get("insufficient_player_cases") or 0
            ),
            "task005_unique_insufficient_players": int(
                task005.get("summary", {}).get("unique_insufficient_players") or 0
            ),
            "audited_unique_players": len(players),
            **scan,
            **dict(counts),
            **sums,
        },
        "players": players,
        "priority_examples": priority[:MAX_EXAMPLES],
        "decision": {
            "runtime_change": False,
            "history_gate_change": False,
            "reason": (
                "PBP supply is audit-only. Even terminal local tapes cannot be counted as net-new "
                "TennisMyLife history until cross-source match deduplication and schema compatibility "
                "are separately proven."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit cached PBP supply for current short-history players"
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
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    if report["policy"]["network_calls"] != 0 or report["decision"]["runtime_change"]:
        return 2
    if report["summary"]["audited_unique_players"] <= 0:
        return 3
    if report["summary"]["cache_payload_files_scanned"] <= 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
