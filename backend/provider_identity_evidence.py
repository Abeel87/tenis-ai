from __future__ import annotations

"""Zero-network provider identity evidence audit for TASK 003.

This module never calls Live Tennis API. It inspects only already-restored cache
material, current published results, and the existing historical CSV cache.

Important safety rule: a numeric Live Tennis API player ID is accepted as an
explicit identity inside one cached payload/index record, but this audit does NOT
assume that the numeric ID is globally unique across provider namespaces. Cross-
match same-number joins are therefore reported only as an *unscoped upper bound*
until a namespace can be proven from cached provider material.

No fuzzy matching, similarity scoring, manual aliases, or guessed namespace is
used. Ambiguous/colliding evidence fails closed.
"""

import argparse
import gzip
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

try:
    from . import model
    from .history_coverage_audit import classify_player_history, load_cached_history
    from .history_hygiene_v78a import clean_history
    from .player_identity import player_identity_map
except ImportError:  # pragma: no cover - direct script execution from backend/
    import model
    from history_coverage_audit import classify_player_history, load_cached_history
    from history_hygiene_v78a import clean_history
    from player_identity import player_identity_map


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PBP_ROOT = ROOT / "data" / "cache" / "pbp_v7"
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "provider_identity_evidence.json"
VERSION = "task-003-provider-identity-evidence-v2"
MAX_SOURCE_EXAMPLES = 5


def _provider_id(value: Any) -> int | None:
    """Accept only provider integers; never coerce strings/floats/bools."""
    return value if type(value) is int else None


def _key(value: Any) -> str:
    return model._core._key(value)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _read_gzip_json(path: Path) -> dict[str, Any] | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def iter_cached_payloads(matches_dir: Path) -> Iterable[tuple[str, dict[str, Any]]]:
    if not matches_dir.exists():
        return
    for path in sorted(matches_dir.glob("*.json.gz")):
        payload = _read_gzip_json(path)
        if payload is not None:
            yield path.name.removesuffix(".json.gz"), payload


def _sorted_counter(counter: Counter[Any]) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": int(count)}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))
    ]


def build_provider_evidence(
    *,
    players_index: dict[str, Any],
    match_payloads: Iterable[tuple[str, dict[str, Any]]],
    current_players: Iterable[str] = (),
    history_keys: Iterable[str] = (),
    existing_resolutions: dict[str, tuple[str | None, str]] | None = None,
) -> dict[str, Any]:
    """Inventory strict IDs and compute only a namespace-unscoped upper bound.

    Same numeric IDs observed in different cached matches are deliberately NOT
    authorized as runtime aliases. They are useful only to prove an upper bound:
    if even the broad same-number relation yields zero current->history candidate,
    any stricter namespace-scoped relation must also yield zero.
    """
    existing_resolutions = existing_resolutions or {}

    id_names: dict[int, Counter[str]] = defaultdict(Counter)
    id_keys: dict[int, Counter[str]] = defaultdict(Counter)
    id_sources: dict[int, Counter[str]] = defaultdict(Counter)
    id_source_examples: dict[int, list[str]] = defaultdict(list)
    key_ids: dict[str, Counter[int]] = defaultdict(Counter)
    key_names: dict[str, Counter[str]] = defaultdict(Counter)
    index_exact: dict[str, int] = {}
    invalid_index_ids = 0
    payload_files = 0
    payloads_with_identity = 0

    def observe_key(player_id: int, key: str, source: str, *, raw_name: str | None = None) -> None:
        if not key:
            return
        id_keys[player_id][key] += 1
        key_ids[key][player_id] += 1
        id_sources[player_id][source] += 1
        if raw_name:
            id_names[player_id][raw_name] += 1
            key_names[key][raw_name] += 1

    raw_players = players_index.get("players") if isinstance(players_index, dict) else {}
    if not isinstance(raw_players, dict):
        raw_players = {}

    for stored_key, entry in raw_players.items():
        if not isinstance(entry, dict):
            continue
        player_id = _provider_id(entry.get("player_id"))
        if player_id is None:
            if entry.get("player_id") is not None:
                invalid_index_ids += 1
            continue
        normalized_stored_key = _key(stored_key)
        if not normalized_stored_key:
            continue
        index_exact[normalized_stored_key] = player_id
        raw_name = entry.get("player")
        raw_name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else None
        observe_key(player_id, normalized_stored_key, "players_index", raw_name=raw_name)
        example = f"players.json:{normalized_stored_key}"
        if example not in id_source_examples[player_id] and len(id_source_examples[player_id]) < MAX_SOURCE_EXAMPLES:
            id_source_examples[player_id].append(example)

    for match_id, payload in match_payloads:
        payload_files += 1
        mapping = player_identity_map(payload)
        if mapping is None:
            continue
        payloads_with_identity += 1
        for side in (1, 2):
            record = mapping[side]
            player_id = record["id"]
            raw_name = record.get("name")
            if not isinstance(raw_name, str) or not raw_name.strip():
                continue
            raw_name = raw_name.strip()
            normalized = _key(raw_name)
            if not normalized:
                continue
            observe_key(player_id, normalized, "match_payload", raw_name=raw_name)
            example = f"match:{match_id}:p{side}"
            if example not in id_source_examples[player_id] and len(id_source_examples[player_id]) < MAX_SOURCE_EXAMPLES:
                id_source_examples[player_id].append(example)

    collision_keys = {
        key: sorted(counter)
        for key, counter in key_ids.items()
        if len(counter) > 1
    }

    provider_rows: dict[str, Any] = {}
    unscoped_numeric_pairs = 0
    ids_with_multiple_names = 0
    ids_with_multiple_keys = 0
    ids_with_multiple_collision_free_keys = 0

    for player_id in sorted(set(id_keys) | set(id_names) | set(id_sources)):
        collision_free_keys = sorted(
            key for key in id_keys[player_id]
            if set(key_ids[key]) == {player_id}
        )
        if len(id_names[player_id]) > 1:
            ids_with_multiple_names += 1
        if len(id_keys[player_id]) > 1:
            ids_with_multiple_keys += 1
        if len(collision_free_keys) > 1:
            ids_with_multiple_collision_free_keys += 1
            unscoped_numeric_pairs += sum(1 for _ in combinations(collision_free_keys, 2))
        provider_rows[str(player_id)] = {
            "exact_names": _sorted_counter(id_names[player_id]),
            "normalized_keys": _sorted_counter(id_keys[player_id]),
            "collision_free_numeric_id_keys": collision_free_keys,
            "sources": dict(sorted(id_sources[player_id].items())),
            "source_examples": id_source_examples[player_id],
            "cross_match_scope": "UNVERIFIED_PROVIDER_NAMESPACE",
        }

    key_rows = {
        key: {
            "numeric_provider_ids": [
                {"id": player_id, "count": int(count)}
                for player_id, count in sorted(counter.items())
            ],
            "numeric_id_collision": len(counter) > 1,
            "exact_names": _sorted_counter(key_names[key]),
        }
        for key, counter in sorted(key_ids.items())
    }

    history_set = {_key(value) for value in history_keys if _key(value)}
    current_by_key: dict[str, set[str]] = defaultdict(set)
    for name in current_players:
        normalized = _key(name)
        if normalized:
            current_by_key[normalized].add(str(name))

    current_rows: list[dict[str, Any]] = []
    unscoped_current_candidates: list[dict[str, Any]] = []
    ambiguous_unscoped_candidates: list[dict[str, Any]] = []
    conflicting_current_keys: list[dict[str, Any]] = []

    for current_key in sorted(current_by_key):
        names = sorted(current_by_key[current_key])
        player_id = index_exact.get(current_key)
        existing_key, existing_mode = existing_resolutions.get(current_key, (None, "none"))
        row: dict[str, Any] = {
            "current_key": current_key,
            "current_names": names,
            "numeric_provider_id": player_id,
            "existing_resolution": {"resolved_key": existing_key, "mode": existing_mode},
            "status": "no_exact_current_numeric_provider_id",
            "history_candidates_unscoped": [],
        }
        if player_id is None:
            current_rows.append(row)
            continue

        observed_ids = set(key_ids.get(current_key, {}))
        if observed_ids and observed_ids != {player_id}:
            row["status"] = "conflicting_current_numeric_id"
            row["observed_numeric_provider_ids"] = sorted(observed_ids)
            conflicting_current_keys.append(dict(row))
            current_rows.append(row)
            continue

        collision_free_keys = {
            key for key in id_keys.get(player_id, {})
            if set(key_ids.get(key, {})) == {player_id}
        }
        history_candidates = sorted(
            key for key in (collision_free_keys & history_set)
            if key != current_key
        )
        row["history_candidates_unscoped"] = history_candidates

        if current_key in history_set:
            row["status"] = "history_exact_already_available"
        elif existing_key is not None:
            row["status"] = "history_already_resolved"
        elif len(history_candidates) == 1:
            row["status"] = "unscoped_numeric_id_history_candidate"
            unscoped_current_candidates.append({
                "current_key": current_key,
                "current_names": names,
                "numeric_provider_id": player_id,
                "history_key": history_candidates[0],
                "scope": "UPPER_BOUND_ONLY_NAMESPACE_NOT_PROVEN",
            })
        elif len(history_candidates) > 1:
            row["status"] = "ambiguous_unscoped_numeric_id_history_keys"
            ambiguous_unscoped_candidates.append(dict(row))
        else:
            row["status"] = "no_numeric_id_backed_history_key_even_unscoped"
        current_rows.append(row)

    return {
        "version": VERSION,
        "policy": {
            "network_calls": 0,
            "fuzzy_matching": False,
            "similarity_thresholds": False,
            "manual_aliases": False,
            "numeric_id_cross_match_scope": "UPPER_BOUND_ONLY_NAMESPACE_NOT_PROVEN",
            "runtime_alias_authorized": False,
            "safe_provider_alias_pairs": 0,
            "fail_closed_on_collision": True,
        },
        "summary": {
            "cached_match_payloads_scanned": payload_files,
            "cached_match_payloads_with_strict_integer_identity": payloads_with_identity,
            "distinct_numeric_provider_ids": len(provider_rows),
            "numeric_provider_ids_with_multiple_exact_names": ids_with_multiple_names,
            "numeric_provider_ids_with_multiple_normalized_keys": ids_with_multiple_keys,
            "numeric_provider_ids_with_multiple_collision_free_keys": ids_with_multiple_collision_free_keys,
            "normalized_key_numeric_id_collisions": len(collision_keys),
            "same_numeric_id_multi_key_pairs_unscoped": unscoped_numeric_pairs,
            "safe_provider_alias_pairs": 0,
            "current_player_keys": len(current_by_key),
            "current_players_with_exact_index_numeric_provider_id": sum(
                1 for row in current_rows if row["numeric_provider_id"] is not None
            ),
            "current_players_with_unscoped_numeric_id_history_candidate": len(unscoped_current_candidates),
            "current_players_with_safe_provider_alias": 0,
            "current_players_with_ambiguous_unscoped_history_keys": len(ambiguous_unscoped_candidates),
            "current_player_numeric_id_conflicts": len(conflicting_current_keys),
            "history_keys": len(history_set),
            "invalid_non_integer_index_ids": invalid_index_ids,
        },
        "numeric_provider_ids": provider_rows,
        "normalized_keys": key_rows,
        "collision_keys": collision_keys,
        "current_players": current_rows,
        "unscoped_current_candidates": unscoped_current_candidates,
        "safe_current_aliases": [],
        "ambiguous_unscoped_candidates": ambiguous_unscoped_candidates,
        "conflicting_current_keys": conflicting_current_keys,
    }


def _history_keys(long_df) -> set[str]:
    if long_df is None or getattr(long_df, "empty", True):
        return set()
    if "player_key" in long_df.columns:
        return {
            str(value).strip()
            for value in long_df["player_key"].dropna().tolist()
            if str(value).strip()
        }
    if "player" in long_df.columns:
        return {_key(value) for value in long_df["player"].dropna().tolist() if _key(value)}
    return set()


def _current_names(results: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for match in results:
        if not isinstance(match, dict):
            continue
        for side in ("p1", "p2"):
            value = match.get(side)
            if isinstance(value, str) and value.strip():
                names.append(value.strip())
    return names


def _existing_resolutions(long_df, names: Iterable[str]) -> dict[str, tuple[str | None, str]]:
    out: dict[str, tuple[str | None, str]] = {}
    for name in names:
        key = _key(name)
        if key and key not in out:
            out[key] = model._resolve_history_player_key(long_df, name)
    return out


def _candidate_case_impact(
    results: list[dict[str, Any]],
    *,
    raw_long,
    clean_long,
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Measure only an upper bound for current no-safe-identity cases."""
    candidate_by_current = {
        row["current_key"]: row["history_key"]
        for row in candidate_rows
        if row.get("current_key") and row.get("history_key")
    }
    cases = 0
    cases_with_pre_match_rows = 0
    cases_with_at_least_five_pre_match_rows = 0
    examples: list[dict[str, Any]] = []

    dated = model._dated_history(clean_long)
    for match in results:
        if not isinstance(match, dict):
            continue
        for side in ("p1", "p2"):
            player = str(match.get(side) or "")
            current_key = _key(player)
            target_key = candidate_by_current.get(current_key)
            if not target_key:
                continue
            item = classify_player_history(
                player=player,
                stats=match.get(f"{side}_stats") or {},
                scheduled_time=match.get("scheduled_time"),
                raw_long=raw_long,
                clean_long=clean_long,
            )
            if item.get("reason") != "no_safe_identity_candidate":
                continue
            cases += 1

            pre_rows = 0
            if dated is not None and not getattr(dated, "empty", True):
                subset = dated
                if "player_key" in subset.columns:
                    subset = subset[subset["player_key"] == target_key]
                elif "player" in subset.columns:
                    subset = subset[subset["player"].map(_key).eq(target_key)]
                else:
                    subset = subset.iloc[0:0]
                cut = model._naive_cutoff(match.get("scheduled_time"))
                if "date" in subset.columns and cut is not None:
                    subset = subset[subset["date"] <= cut]
                pre_rows = int(len(subset))

            if pre_rows > 0:
                cases_with_pre_match_rows += 1
            if pre_rows >= 5:
                cases_with_at_least_five_pre_match_rows += 1
            if len(examples) < 20:
                examples.append({
                    "match_id": match.get("id"),
                    "player": player,
                    "current_key": current_key,
                    "history_key": target_key,
                    "pre_match_rows": pre_rows,
                })

    return {
        "scope": "UPPER_BOUND_ONLY_NAMESPACE_NOT_PROVEN",
        "no_safe_identity_candidate_cases_with_unscoped_numeric_candidate": cases,
        "cases_with_any_pre_match_history_rows": cases_with_pre_match_rows,
        "cases_with_at_least_five_pre_match_history_rows": cases_with_at_least_five_pre_match_rows,
        "examples": examples,
    }


def build_real_cache_audit(
    *,
    pbp_root: Path = DEFAULT_PBP_ROOT,
    results_path: Path = DEFAULT_RESULTS,
) -> dict[str, Any]:
    players_index = _read_json(pbp_root / "players.json", {"players": {}})
    results = _read_json(results_path, [])
    if not isinstance(results, list):
        results = []

    raw_history = load_cached_history()
    cleaned_history, hygiene = clean_history(raw_history)
    raw_long = model.normalize_matches(raw_history)
    clean_long = model.normalize_matches(cleaned_history)

    names = _current_names(results)
    evidence = build_provider_evidence(
        players_index=players_index,
        match_payloads=iter_cached_payloads(pbp_root / "matches"),
        current_players=names,
        history_keys=_history_keys(clean_long),
        existing_resolutions=_existing_resolutions(clean_long, names),
    )
    evidence["source_snapshot"] = {
        "pbp_root": str(pbp_root.relative_to(ROOT)) if pbp_root.is_relative_to(ROOT) else str(pbp_root),
        "players_index_entries": len((players_index.get("players") or {})) if isinstance(players_index, dict) else 0,
        "results_matches": len(results),
        "raw_history_rows": int(len(raw_history)),
        "clean_history_rows": int(len(cleaned_history)),
        "hygiene_removed_rows": int((hygiene or {}).get("removed_rows", 0)),
    }
    evidence["unscoped_upper_bound_case_impact"] = _candidate_case_impact(
        results,
        raw_long=raw_long,
        clean_long=clean_long,
        candidate_rows=evidence["unscoped_current_candidates"],
    )
    evidence["safe_case_impact"] = {
        "authorized_provider_aliases": 0,
        "no_safe_identity_candidate_cases_resolved": 0,
        "reason": "provider namespace not proven; unscoped numeric-ID joins are never runtime-authorized",
    }
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit cached provider identity without network or alias guessing")
    parser.add_argument("--pbp-root", type=Path, default=DEFAULT_PBP_ROOT)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_real_cache_audit(pbp_root=args.pbp_root, results_path=args.results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        **report["summary"],
        "unscoped_upper_bound_case_impact": report["unscoped_upper_bound_case_impact"],
        "safe_case_impact": report["safe_case_impact"],
        "output": str(args.output),
    }, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
