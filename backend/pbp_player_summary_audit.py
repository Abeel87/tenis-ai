from __future__ import annotations

"""TASK 012: zero-network audit of cached Live Tennis player-index summaries.

This module is diagnostic only. It inspects the already-cached
``data/cache/pbp_v7/players.json`` index and current short-history players.
It never performs provider requests, never compares IDs across providers, and
never authorizes summary metadata as model history.
"""

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / "data" / "cache"
DEFAULT_INDEX = DEFAULT_CACHE / "pbp_v7" / "players.json"
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "pbp_player_summary_audit.json"
VERSION = "task-012-pbp-player-summary-audit-v1"
MIN_MATCHES = 5
MAX_EXAMPLES = 20


def _key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _parse_dt(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _strict_positive_int(value: Any) -> int | None:
    # bool is an int subclass but is not a valid provider identity.
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value.strip()):
        return int(value.strip())
    return None


def _short_players(results: Any) -> list[dict[str, Any]]:
    rows = results if isinstance(results, list) else []
    by_key: dict[str, dict[str, Any]] = {}
    for match in rows:
        if not isinstance(match, dict):
            continue
        cutoff = _parse_dt(match.get("scheduled_time"))
        for side in ("p1", "p2"):
            stats = match.get(f"{side}_stats")
            if not isinstance(stats, dict):
                continue
            try:
                matches = int(stats.get("matches") or 0)
            except (TypeError, ValueError):
                continue
            if not 0 < matches < MIN_MATCHES:
                continue
            player = str(match.get(side) or "").strip()
            requested_key = _key(player)
            if not player or not requested_key:
                continue
            row = by_key.setdefault(
                requested_key,
                {
                    "player": player,
                    "requested_key": requested_key,
                    "current_matches": matches,
                    "identity_modes": set(),
                    "history_player_keys": set(),
                    "cutoff": cutoff,
                    "fixture_ids": [],
                },
            )
            row["current_matches"] = min(int(row["current_matches"]), matches)
            mode = str(stats.get("history_identity_mode") or "none")
            row["identity_modes"].add(mode)
            history_key = stats.get("history_player_key")
            if isinstance(history_key, str) and history_key.strip():
                row["history_player_keys"].add(history_key.strip())
            if cutoff is not None and (row["cutoff"] is None or cutoff < row["cutoff"]):
                row["cutoff"] = cutoff
            if match.get("id") is not None:
                row["fixture_ids"].append(match.get("id"))

    out = []
    for row in by_key.values():
        out.append(
            {
                **row,
                "identity_modes": sorted(row["identity_modes"]),
                "history_player_keys": sorted(row["history_player_keys"]),
                "cutoff": row["cutoff"].isoformat() if row["cutoff"] else None,
                "fixture_ids": list(dict.fromkeys(row["fixture_ids"])),
            }
        )
    return sorted(out, key=lambda row: row["requested_key"])


def _entry_identity(entry_key: str, entry: Any) -> tuple[bool, str, int | None]:
    if not isinstance(entry, dict):
        return False, "entry_not_object", None
    player = str(entry.get("player") or "").strip()
    if not player or _key(player) != entry_key:
        return False, "entry_player_name_mismatch", None
    player_id = _strict_positive_int(entry.get("player_id"))
    if player_id is None:
        return False, "invalid_provider_player_id", None
    return True, "exact_index_identity", player_id


def _provider_id_collisions(players: dict[str, Any]) -> dict[str, set[int]]:
    ids_by_key: dict[str, set[int]] = defaultdict(set)
    for entry_key, entry in players.items():
        if not isinstance(entry_key, str) or not isinstance(entry, dict):
            continue
        normalized = _key(entry.get("player"))
        player_id = _strict_positive_int(entry.get("player_id"))
        if normalized and player_id is not None:
            ids_by_key[normalized].add(player_id)
    return {key: values for key, values in ids_by_key.items() if len(values) > 1}


def _candidate_summary(summary: Any, cutoff: datetime | None) -> tuple[bool, str]:
    if not isinstance(summary, dict):
        return False, "not_object"
    if summary.get("is_doubles"):
        return False, "doubles"
    if summary.get("id") is None:
        return False, "missing_match_id"
    tape = summary.get("tape")
    if not isinstance(tape, dict):
        return False, "missing_tape_metadata"
    if tape.get("coverage") != "from_start":
        return False, "not_from_start"
    if tape.get("starts_at_love") is False:
        return False, "not_from_love"
    completeness = tape.get("completeness")
    if completeness is not None:
        try:
            if float(completeness) < 0.95:
                return False, "low_completeness"
        except (TypeError, ValueError):
            return False, "invalid_completeness"
    try:
        if int(tape.get("rows") or 0) < 20:
            return False, "too_few_tape_rows"
    except (TypeError, ValueError):
        return False, "invalid_tape_rows"
    scheduled = _parse_dt(summary.get("scheduled_time"))
    if scheduled is None:
        return False, "missing_scheduled_time"
    if cutoff is not None and scheduled >= cutoff:
        return False, "not_pre_cutoff"
    return True, "candidate_ok"


def _walk_keys(value: Any, *, max_nodes: int = 400) -> set[str]:
    found: set[str] = set()
    stack = [value]
    seen = 0
    while stack and seen < max_nodes:
        item = stack.pop()
        seen += 1
        if isinstance(item, dict):
            for key, child in item.items():
                found.add(str(key))
                if isinstance(child, (dict, list)):
                    stack.append(child)
        elif isinstance(item, list):
            stack.extend(child for child in item[:80] if isinstance(child, (dict, list)))
    return found


def _summary_schema(summary: dict[str, Any]) -> dict[str, Any]:
    recursive = _walk_keys(summary)
    top_keys = sorted(str(key) for key in summary)
    tape = summary.get("tape") if isinstance(summary.get("tape"), dict) else {}
    feature_names = {
        "hold_rate",
        "break_rate",
        "serve_points_won",
        "return_points_won",
        "first_serve_in",
        "first_serve_won",
        "second_serve_won",
    }
    direct_features = sorted(feature_names & recursive)
    has_stats_payload = "stats" in recursive or "profiles" in recursive
    has_score_payload = bool({"score", "sets", "games"} & recursive)
    has_player_payload = bool({"players", "p1", "p2", "player1", "player2"} & recursive)
    return {
        "top_keys": top_keys,
        "tape_keys": sorted(str(key) for key in tape),
        "direct_model_style_features": direct_features,
        "has_stats_or_profiles": has_stats_payload,
        "has_score_payload": has_score_payload,
        "has_player_payload": has_player_payload,
        "metadata_only_for_model_history": not (has_stats_payload and has_score_payload),
    }


def _audit_player(
    player: dict[str, Any],
    *,
    index_players: dict[str, Any],
    cache_root: Path,
    provider_collisions: dict[str, set[int]],
) -> dict[str, Any]:
    key = player["requested_key"]
    entry = index_players.get(key)
    identity_ok, identity_reason, player_id = _entry_identity(key, entry)
    if key in provider_collisions:
        identity_ok = False
        identity_reason = "multiple_provider_ids_for_exact_key"

    base = {
        **player,
        "index_entry_present": entry is not None,
        "index_identity_ok": identity_ok,
        "index_identity_reason": identity_reason,
        "provider_player_id": player_id if identity_ok else None,
    }
    if not identity_ok or not isinstance(entry, dict):
        return {
            **base,
            "summary_count": 0,
            "valid_pre_cutoff_summaries": 0,
            "with_local_tape": 0,
            "summary_only": 0,
            "summary_only_with_stats_or_profiles": 0,
            "summary_only_metadata_only": 0,
            "upper_bound_reaches_five": False,
            "rejection_counts": {},
            "summary_only_examples": [],
        }

    cutoff = _parse_dt(player.get("cutoff"))
    summaries = entry.get("matches") if isinstance(entry.get("matches"), list) else []
    seen_ids: set[str] = set()
    rejection_counts: Counter[str] = Counter()
    valid_rows: list[dict[str, Any]] = []
    for summary in summaries:
        ok, reason = _candidate_summary(summary, cutoff)
        if not ok:
            rejection_counts[reason] += 1
            continue
        mid = str(summary.get("id"))
        if mid in seen_ids:
            rejection_counts["duplicate_match_id"] += 1
            continue
        seen_ids.add(mid)
        path = cache_root / "pbp_v7" / "matches" / f"{mid}.json.gz"
        schema = _summary_schema(summary)
        valid_rows.append(
            {
                "match_id": summary.get("id"),
                "scheduled_time": summary.get("scheduled_time"),
                "local_tape_exists": path.exists(),
                "schema": schema,
            }
        )

    summary_only = [row for row in valid_rows if not row["local_tape_exists"]]
    with_stats = [row for row in summary_only if row["schema"]["has_stats_or_profiles"]]
    metadata_only = [row for row in summary_only if row["schema"]["metadata_only_for_model_history"]]
    current_matches = int(player.get("current_matches") or 0)
    return {
        **base,
        "summary_count": len(summaries),
        "valid_pre_cutoff_summaries": len(valid_rows),
        "with_local_tape": sum(1 for row in valid_rows if row["local_tape_exists"]),
        "summary_only": len(summary_only),
        "summary_only_with_stats_or_profiles": len(with_stats),
        "summary_only_metadata_only": len(metadata_only),
        # Deliberately only an upper bound: distinctness vs TML is not proven here.
        "upper_bound_reaches_five": current_matches + len(summary_only) >= MIN_MATCHES,
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "summary_only_examples": summary_only[:MAX_EXAMPLES],
    }


def build_report(
    *,
    cache_root: Path = DEFAULT_CACHE,
    index_path: Path = DEFAULT_INDEX,
    results_path: Path = DEFAULT_RESULTS,
) -> dict[str, Any]:
    results = _read_json(results_path, [])
    if isinstance(results, dict):
        results = results.get("matches", [])
    if not isinstance(results, list):
        results = []

    index = _read_json(index_path, {})
    players = index.get("players") if isinstance(index, dict) else {}
    players = players if isinstance(players, dict) else {}
    short_players = _short_players(results)
    collisions = _provider_id_collisions(players)
    rows = [
        _audit_player(
            player,
            index_players=players,
            cache_root=cache_root,
            provider_collisions=collisions,
        )
        for player in short_players
    ]

    schema_top_keys: Counter[str] = Counter()
    schema_tape_keys: Counter[str] = Counter()
    global_summary_only_ids: set[str] = set()
    for row in rows:
        for example in row["summary_only_examples"]:
            global_summary_only_ids.add(str(example.get("match_id")))
            for key in example["schema"]["top_keys"]:
                schema_top_keys[key] += 1
            for key in example["schema"]["tape_keys"]:
                schema_tape_keys[key] += 1

    exact_index_rows = [row for row in rows if row["index_identity_ok"]]
    summary_supply_rows = [row for row in rows if row["summary_only"] > 0]
    upper_bound_five = [row for row in rows if row["upper_bound_reaches_five"]]
    stats_summary_rows = [row for row in rows if row["summary_only_with_stats_or_profiles"] > 0]

    total_index_summaries = 0
    for entry in players.values():
        if isinstance(entry, dict) and isinstance(entry.get("matches"), list):
            total_index_summaries += len(entry["matches"])

    return {
        "version": VERSION,
        "policy": {
            "network_calls": 0,
            "provider_requests": 0,
            "production_cache_writes": 0,
            "fuzzy_matching": False,
            "manual_aliases": False,
            "cross_provider_id_comparison": False,
            "minimum_match_gate": MIN_MATCHES,
            "minimum_match_gate_changed": False,
            "identity_resolver_changed": False,
            "model_math_changed": False,
            "runtime_change_authorized": False,
            "summary_metadata_authorized_as_history": False,
            "upper_bound_is_not_runtime_coverage": True,
        },
        "summary": {
            "visible_matches": len(results),
            "short_history_players": len(short_players),
            "index_players": len(players),
            "index_total_summaries": total_index_summaries,
            "provider_identity_collision_keys": len(collisions),
            "short_players_with_exact_index_identity": len(exact_index_rows),
            "short_players_with_summary_only_supply": len(summary_supply_rows),
            "short_players_with_summary_only_stats_or_profiles": len(stats_summary_rows),
            "summary_only_observations": sum(row["summary_only"] for row in rows),
            "summary_only_unique_match_ids_in_examples": len(global_summary_only_ids),
            "upper_bound_players_reaching_five": len(upper_bound_five),
        },
        "summary_only_schema": {
            "top_key_counts_in_examples": dict(sorted(schema_top_keys.items())),
            "tape_key_counts_in_examples": dict(sorted(schema_tape_keys.items())),
        },
        "provider_identity_collisions": {
            key: sorted(values) for key, values in sorted(collisions.items())
        },
        "players": rows,
        "priority": {
            "summary_only_supply": summary_supply_rows[:MAX_EXAMPLES],
            "upper_bound_reaches_five": upper_bound_five[:MAX_EXAMPLES],
            "summary_only_with_stats_or_profiles": stats_summary_rows[:MAX_EXAMPLES],
        },
        "decision": {
            "runtime_change": False,
            "authorize_summary_as_history": False,
            "reason": (
                "Audit only. Player-index match summaries are provider metadata; any summary-only supply "
                "must still prove TML distinctness and full model-history feature compatibility before use."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit cached PBP player-index summaries for short-history players")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_report(cache_root=args.cache_root, index_path=args.index, results_path=args.results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    print(json.dumps(report["summary_only_schema"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
