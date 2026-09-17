from __future__ import annotations

"""TASK 004: zero-network repeated match-level identity bridge audit.

The audit inspects only existing local/cache material:
- TennisMyLife historical ``*.csv.gz`` rows already present under ``data/cache``;
- cached Live Tennis API match payloads under ``data/cache/pbp_v7/matches``;
- current published ``frontend/data/results.json``.

It never calls the Live Tennis API and never authorizes runtime aliases.  It does
not compare IDs across provider namespaces.  Candidate player-name bridges are
reported only when the same exact cross-source relationship is independently
repeated in at least two distinct matches with two distinct exact-name anchors.

No fuzzy matching, similarity thresholds, guessed/manual aliases, model changes,
threshold changes, or training changes are performed here.
"""

import argparse
import csv
import gzip
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

try:
    from . import model
    from .history_coverage_audit import classify_player_history, load_cached_history
    from .history_hygiene_v78a import clean_history
    from .player_identity import player_identity_map
except ImportError:  # pragma: no cover
    import model
    from history_coverage_audit import classify_player_history, load_cached_history
    from history_hygiene_v78a import clean_history
    from player_identity import player_identity_map


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = ROOT / "data" / "cache"
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "repeat_match_identity_bridge.json"
VERSION = "task-004-repeat-match-identity-bridge-v1"

MIN_DISTINCT_MEETINGS = 2
MIN_DISTINCT_ANCHORS = 2
MAX_TOURNAMENT_DAY_GAP = 8
MAX_EXAMPLES = 8

_COMPLETED = {"finished", "completed", "ended"}
_BAD_SCORE_MARKERS = ("RET", "W/O", "WO", "DEF", "ABN")


def _player_key(value: Any) -> str:
    return model._core._key(value)


def _label_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold().replace("ł", "l"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"[^\W_]+", text, re.UNICODE))


def _surface(value: Any) -> str:
    key = _label_key(value)
    aliases = {
        "hard": "hard",
        "clay": "clay",
        "grass": "grass",
        "carpet": "carpet",
    }
    return aliases.get(key, "")


def _parse_day(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    token = raw[:10]
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(token.replace("-", "") if fmt == "%Y%m%d" else token, fmt).date()
        except ValueError:
            pass
    return None


def _tml_tournament_day(value: Any) -> date | None:
    raw = str(value or "").strip()
    if len(raw) < 8:
        return None
    try:
        return datetime.strptime(raw[:8], "%Y%m%d").date()
    except ValueError:
        return None


def _score_from_text(value: Any) -> tuple[tuple[int, int], ...]:
    text = str(value or "").upper()
    if not text or any(marker in text for marker in _BAD_SCORE_MARKERS):
        return ()
    sets = tuple((int(a), int(b)) for a, b in re.findall(r"(?<!\d)(\d+)\s*[-:]\s*(\d+)", text))
    return sets if len(sets) >= 2 else ()


def _score_from_live(match: dict[str, Any], winner_side: int) -> tuple[tuple[int, int], ...]:
    games = (match.get("score") or {}).get("games")
    if (
        not isinstance(games, list)
        or len(games) != 2
        or not all(isinstance(side, list) for side in games)
        or len(games[0]) != len(games[1])
        or len(games[0]) < 2
    ):
        return ()
    try:
        pairs = tuple((int(a), int(b)) for a, b in zip(games[0], games[1]))
    except (TypeError, ValueError):
        return ()
    if winner_side == 1:
        return pairs
    if winner_side == 2:
        return tuple((b, a) for a, b in pairs)
    return ()


def _tournament_name(payload: dict[str, Any], match: dict[str, Any]) -> str:
    candidates: list[Any] = [
        match.get("tournament_name"),
        match.get("competition_name"),
        match.get("league_name"),
    ]
    tournament = match.get("tournament")
    if isinstance(tournament, dict):
        candidates.extend((tournament.get("name"), tournament.get("title")))
    else:
        candidates.append(tournament)
    outer = payload.get("tournament")
    if isinstance(outer, dict):
        candidates.extend((outer.get("name"), outer.get("title")))
    else:
        candidates.append(outer)
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _iter_cached_payloads(matches_dir: Path) -> Iterable[tuple[str, dict[str, Any]]]:
    if not matches_dir.exists():
        return
    for path in sorted(matches_dir.glob("*.json.gz")):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            yield path.name.removesuffix(".json.gz"), payload


def _iter_tml_rows(cache_root: Path) -> Iterable[dict[str, Any]]:
    for path in sorted(cache_root.glob("*.csv.gz")):
        try:
            with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
                for row_number, row in enumerate(csv.DictReader(stream), start=2):
                    winner = str(row.get("winner_name") or "").strip()
                    loser = str(row.get("loser_name") or "").strip()
                    tournament = str(row.get("tourney_name") or "").strip()
                    day = _tml_tournament_day(row.get("tourney_date"))
                    surface = _surface(row.get("surface"))
                    score = _score_from_text(row.get("score"))
                    winner_key = _player_key(winner)
                    loser_key = _player_key(loser)
                    tournament_key = _label_key(tournament)
                    if not all((winner_key, loser_key, tournament_key, day, surface, score)):
                        continue
                    identity = "|".join(
                        (
                            path.name,
                            str(row.get("tourney_id") or ""),
                            str(row.get("match_num") or ""),
                            str(row_number),
                        )
                    )
                    yield {
                        "id": identity,
                        "winner": winner,
                        "loser": loser,
                        "winner_key": winner_key,
                        "loser_key": loser_key,
                        "tournament": tournament,
                        "tournament_key": tournament_key,
                        "tournament_day": day,
                        "surface": surface,
                        "score": score,
                        "source_file": path.name,
                    }
        except OSError:
            continue


def _live_record(source_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    identities = player_identity_map(payload)
    if not identities:
        return None
    match = payload.get("match")
    if not isinstance(match, dict):
        return None
    status = str(match.get("event_status") or "").casefold()
    winner_side = match.get("winner")
    if status not in _COMPLETED or type(winner_side) is not int or winner_side not in (1, 2):
        return None
    loser_side = 2 if winner_side == 1 else 1
    winner = str(identities[winner_side].get("name") or "").strip()
    loser = str(identities[loser_side].get("name") or "").strip()
    winner_key = _player_key(winner)
    loser_key = _player_key(loser)
    tournament = _tournament_name(payload, match)
    tournament_key = _label_key(tournament)
    match_day = _parse_day(match.get("scheduled_time"))
    surface = _surface(match.get("surface"))
    score = _score_from_live(match, winner_side)
    if not all((winner_key, loser_key, tournament_key, match_day, surface, score)):
        return None
    return {
        "id": str(match.get("id") or source_id),
        "source_id": source_id,
        "winner": winner,
        "loser": loser,
        "winner_key": winner_key,
        "loser_key": loser_key,
        "tournament": tournament,
        "tournament_key": tournament_key,
        "match_day": match_day,
        "surface": surface,
        "score": score,
    }


def _match_proposal(live: dict[str, Any], tml: dict[str, Any]) -> dict[str, Any] | None:
    if live["tournament_key"] != tml["tournament_key"]:
        return None
    if live["surface"] != tml["surface"] or live["score"] != tml["score"]:
        return None
    gap = (live["match_day"] - tml["tournament_day"]).days
    if gap < 0 or gap > MAX_TOURNAMENT_DAY_GAP:
        return None

    winner_anchor = live["winner_key"] == tml["winner_key"]
    loser_anchor = live["loser_key"] == tml["loser_key"]
    if winner_anchor == loser_anchor:
        return None

    if winner_anchor:
        current_key, history_key = live["loser_key"], tml["loser_key"]
        current_name, history_name = live["loser"], tml["loser"]
        anchor_key, anchor_name = live["winner_key"], live["winner"]
    else:
        current_key, history_key = live["winner_key"], tml["winner_key"]
        current_name, history_name = live["winner"], tml["winner"]
        anchor_key, anchor_name = live["loser_key"], live["loser"]

    if not current_key or not history_key or current_key == history_key:
        return None

    return {
        "live_match_id": live["id"],
        "tml_row_id": tml["id"],
        "current_key": current_key,
        "history_key": history_key,
        "current_name": current_name,
        "history_name": history_name,
        "anchor_key": anchor_key,
        "anchor_name": anchor_name,
        "tournament_key": live["tournament_key"],
        "surface": live["surface"],
        "score": [list(pair) for pair in live["score"]],
        "day_gap": gap,
    }


def build_repeat_match_bridge(
    *,
    live_records: Iterable[dict[str, Any]],
    tml_rows: Iterable[dict[str, Any]],
    current_players: Iterable[str] = (),
    history_keys: Iterable[str] = (),
    existing_resolutions: dict[str, tuple[str | None, str]] | None = None,
) -> dict[str, Any]:
    existing_resolutions = existing_resolutions or {}
    current_keys = {_player_key(name) for name in current_players if _player_key(name)}
    history_set = {_player_key(key) for key in history_keys if _player_key(key)}

    tml_index: dict[tuple[str, str, tuple[tuple[int, int], ...]], list[dict[str, Any]]] = defaultdict(list)
    tml_rows_list = list(tml_rows)
    for row in tml_rows_list:
        tml_index[(row["tournament_key"], row["surface"], row["score"])].append(row)

    live_records_list = list(live_records)
    raw_proposals: list[dict[str, Any]] = []
    for live in live_records_list:
        base = (live["tournament_key"], live["surface"], live["score"])
        for tml in tml_index.get(base, []):
            proposal = _match_proposal(live, tml)
            if proposal is not None:
                raw_proposals.append(proposal)

    by_live: Counter[str] = Counter(p["live_match_id"] for p in raw_proposals)
    by_tml: Counter[str] = Counter(p["tml_row_id"] for p in raw_proposals)
    unique_proposals = [
        p for p in raw_proposals
        if by_live[p["live_match_id"]] == 1 and by_tml[p["tml_row_id"]] == 1
    ]

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for proposal in unique_proposals:
        grouped[(proposal["current_key"], proposal["history_key"])].append(proposal)

    repeated: list[dict[str, Any]] = []
    for (current_key, history_key), rows in sorted(grouped.items()):
        meetings = sorted({r["live_match_id"] for r in rows})
        anchors = sorted({r["anchor_key"] for r in rows})
        if len(meetings) < MIN_DISTINCT_MEETINGS or len(anchors) < MIN_DISTINCT_ANCHORS:
            continue
        repeated.append({
            "current_key": current_key,
            "history_key": history_key,
            "meetings": len(meetings),
            "distinct_anchors": len(anchors),
            "anchor_keys": anchors,
            "examples": rows[:MAX_EXAMPLES],
        })

    current_targets: dict[str, set[str]] = defaultdict(set)
    history_sources: dict[str, set[str]] = defaultdict(set)
    for row in repeated:
        current_targets[row["current_key"]].add(row["history_key"])
        history_sources[row["history_key"]].add(row["current_key"])

    collision_current_keys = sorted(k for k, values in current_targets.items() if len(values) > 1)
    collision_history_keys = sorted(k for k, values in history_sources.items() if len(values) > 1)

    collision_free = [
        row for row in repeated
        if row["current_key"] not in collision_current_keys
        and row["history_key"] not in collision_history_keys
    ]

    relevant: list[dict[str, Any]] = []
    for row in collision_free:
        current_key = row["current_key"]
        history_key = row["history_key"]
        existing_key, existing_mode = existing_resolutions.get(current_key, (None, "none"))
        if current_key not in current_keys or history_key not in history_set:
            continue
        if current_key in history_set or existing_key is not None:
            continue
        relevant.append({
            **row,
            "existing_resolution": {
                "resolved_key": existing_key,
                "mode": existing_mode,
            },
            "status": "repeat_match_bridge_candidate_audit_only",
        })

    return {
        "version": VERSION,
        "policy": {
            "network_calls": 0,
            "fuzzy_matching": False,
            "similarity_thresholds": False,
            "manual_aliases": False,
            "cross_provider_numeric_id_comparison": False,
            "runtime_alias_authorized": False,
            "minimum_distinct_meetings": MIN_DISTINCT_MEETINGS,
            "minimum_distinct_exact_anchors": MIN_DISTINCT_ANCHORS,
            "exact_tournament_required": True,
            "exact_surface_required": True,
            "exact_winner_oriented_score_required": True,
            "fail_closed_on_match_ambiguity": True,
            "fail_closed_on_alias_collision": True,
        },
        "summary": {
            "live_records": len(live_records_list),
            "tml_rows": len(tml_rows_list),
            "raw_one_anchor_proposals": len(raw_proposals),
            "ambiguous_live_matches": sum(1 for count in by_live.values() if count > 1),
            "ambiguous_tml_rows": sum(1 for count in by_tml.values() if count > 1),
            "unique_match_bridges": len(unique_proposals),
            "repeated_bridge_pairs": len(repeated),
            "collision_current_keys": len(collision_current_keys),
            "collision_history_keys": len(collision_history_keys),
            "collision_free_repeated_pairs": len(collision_free),
            "current_history_candidates_audit_only": len(relevant),
        },
        "collision_current_keys": collision_current_keys,
        "collision_history_keys": collision_history_keys,
        "repeated_pairs": repeated,
        "current_history_candidates": relevant,
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
        return {_player_key(value) for value in long_df["player"].dropna().tolist() if _player_key(value)}
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
        key = _player_key(name)
        if key and key not in out:
            out[key] = model._resolve_history_player_key(long_df, name)
    return out


def _candidate_case_impact(
    results: list[dict[str, Any]],
    *,
    raw_long,
    clean_long,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    target_by_current = {
        row["current_key"]: row["history_key"]
        for row in candidates
        if row.get("current_key") and row.get("history_key")
    }
    dated = model._dated_history(clean_long)
    cases = 0
    with_rows = 0
    with_five = 0
    examples: list[dict[str, Any]] = []

    for match in results:
        if not isinstance(match, dict):
            continue
        for side in ("p1", "p2"):
            player = str(match.get(side) or "")
            current_key = _player_key(player)
            history_key = target_by_current.get(current_key)
            if not history_key:
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
            subset = dated
            if subset is None or getattr(subset, "empty", True) or "player_key" not in subset.columns:
                count = 0
            else:
                subset = subset[subset["player_key"] == history_key]
                cutoff = pd.to_datetime(match.get("scheduled_time"), utc=True, errors="coerce")
                if not pd.isna(cutoff) and "date" in subset.columns:
                    dates = pd.to_datetime(subset["date"], utc=True, errors="coerce")
                    subset = subset[dates < cutoff]
                count = int(len(subset))
            if count > 0:
                with_rows += 1
            if count >= 5:
                with_five += 1
            if len(examples) < MAX_EXAMPLES:
                examples.append({
                    "match_id": match.get("id"),
                    "player": player,
                    "current_key": current_key,
                    "history_key": history_key,
                    "pre_match_rows": count,
                })

    return {
        "no_safe_identity_candidate_cases": cases,
        "with_pre_match_rows": with_rows,
        "with_at_least_five_pre_match_rows": with_five,
        "examples": examples,
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

    names = _current_names(results)
    resolutions = _existing_resolutions(clean_long, names)

    live_records: list[dict[str, Any]] = []
    payloads_scanned = 0
    for source_id, payload in _iter_cached_payloads(cache_root / "pbp_v7" / "matches"):
        payloads_scanned += 1
        record = _live_record(source_id, payload)
        if record is not None:
            live_records.append(record)

    tml_rows = list(_iter_tml_rows(cache_root))
    bridge = build_repeat_match_bridge(
        live_records=live_records,
        tml_rows=tml_rows,
        current_players=names,
        history_keys=_history_keys(clean_long),
        existing_resolutions=resolutions,
    )
    bridge["summary"]["cached_payloads_scanned"] = payloads_scanned
    bridge["summary"]["current_player_keys"] = len({_player_key(name) for name in names if _player_key(name)})
    bridge["summary"]["history_keys"] = len(_history_keys(clean_long))
    bridge["history_hygiene"] = hygiene
    bridge["case_impact"] = _candidate_case_impact(
        results,
        raw_long=raw_long,
        clean_long=clean_long,
        candidates=bridge["current_history_candidates"],
    )
    bridge["decision"] = {
        "runtime_change": False,
        "reason": "audit-only; review repeated match-level evidence before any resolver change",
    }
    return bridge


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit repeated exact match-level cross-source identity evidence")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_report(cache_root=args.cache_root, results_path=args.results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    print(json.dumps(report["case_impact"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
