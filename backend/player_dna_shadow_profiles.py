from __future__ import annotations

"""Leakage-safe SHADOW profile snapshots for Player DNA.

Profiles are built only from strict context-ready Player DNA point rows. For each
player-match target, the snapshot sees matches with scheduled_time strictly
earlier than the target. Same-time matches are snapshotted before either match is
added to history. No threshold is activated and no production model consumes
these profiles.
"""

import gzip
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "data" / "derived" / "player_dna" / "point_events.jsonl.gz"
OUT_DIR = ROOT / "data" / "derived" / "player_dna"
OUT_JSONL = OUT_DIR / "profile_snapshots.jsonl.gz"
OUT_SUMMARY = ROOT / "frontend" / "data" / "player_dna_shadow_profile_summary.json"

VERSION = "player-dna-shadow-profiles-v1"
THRESHOLDS = (1, 3, 5, 10)


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def iter_point_rows(path: Path = POINTS) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def _empty_stats() -> dict[str, int]:
    return {
        "matches": 0,
        "serve_points": 0,
        "serve_wins": 0,
        "return_points": 0,
        "return_wins": 0,
        "tiebreak_points": 0,
        "tiebreak_wins": 0,
    }


def _rate(wins: int, points: int) -> float | None:
    return round(wins / points, 6) if points > 0 else None


def _project(stats: dict[str, int] | None) -> dict[str, Any]:
    stats = stats or _empty_stats()
    serve_points = int(stats.get("serve_points") or 0)
    serve_wins = int(stats.get("serve_wins") or 0)
    return_points = int(stats.get("return_points") or 0)
    return_wins = int(stats.get("return_wins") or 0)
    tb_points = int(stats.get("tiebreak_points") or 0)
    tb_wins = int(stats.get("tiebreak_wins") or 0)
    return {
        "matches": int(stats.get("matches") or 0),
        "serve_points": serve_points,
        "serve_wins": serve_wins,
        "serve_win_rate": _rate(serve_wins, serve_points),
        "return_points": return_points,
        "return_wins": return_wins,
        "return_win_rate": _rate(return_wins, return_points),
        "tiebreak_points": tb_points,
        "tiebreak_wins": tb_wins,
        "tiebreak_win_rate": _rate(tb_wins, tb_points),
    }


def _accumulate(target: dict[str, int], contribution: dict[str, int]) -> None:
    target["matches"] += 1
    for key in (
        "serve_points", "serve_wins", "return_points", "return_wins",
        "tiebreak_points", "tiebreak_wins",
    ):
        target[key] += int(contribution.get(key) or 0)


def _prepare_matches(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    matches: dict[str, dict[str, Any]] = {}
    counters = Counter()

    for row in rows:
        if not isinstance(row, dict):
            continue
        counters["point_rows_seen"] += 1
        if row.get("context_ready_player_point") is not True:
            counters["non_strict_rows_skipped"] += 1
            continue

        match_id = str(row.get("match_id") or "").strip()
        scheduled = _parse_utc(row.get("match_scheduled_time"))
        p1 = row.get("p1_player_id")
        p2 = row.get("p2_player_id")
        server = row.get("server_player_id")
        receiver = row.get("receiver_player_id")
        if (
            not match_id or scheduled is None
            or isinstance(p1, bool) or not isinstance(p1, int)
            or isinstance(p2, bool) or not isinstance(p2, int)
            or isinstance(server, bool) or not isinstance(server, int)
            or isinstance(receiver, bool) or not isinstance(receiver, int)
        ):
            counters["strict_rows_with_invalid_identity_or_time"] += 1
            continue

        surface = str(row.get("surface") or "unknown")
        entry = matches.setdefault(match_id, {
            "match_id": match_id,
            "scheduled": scheduled,
            "surface": surface,
            "tour": row.get("tour"),
            "format": row.get("match_format"),
            "round_code": row.get("round_code"),
            "p1": p1,
            "p2": p2,
            "p1_ranking": row.get("p1_ranking"),
            "p2_ranking": row.get("p2_ranking"),
            "contrib": {p1: _empty_stats(), p2: _empty_stats()},
            "conflict": False,
        })

        if (
            entry["scheduled"] != scheduled or entry["surface"] != surface
            or entry["p1"] != p1 or entry["p2"] != p2
        ):
            entry["conflict"] = True
            counters["conflicting_rows"] += 1
            continue

        for pid in (p1, p2):
            entry["contrib"].setdefault(pid, _empty_stats())

        if server not in entry["contrib"] or receiver not in entry["contrib"] or server == receiver:
            entry["conflict"] = True
            counters["side_identity_conflicts"] += 1
            continue

        entry["contrib"][server]["serve_points"] += 1
        entry["contrib"][server]["serve_wins"] += int(row.get("server_won") is True)
        entry["contrib"][receiver]["return_points"] += 1
        entry["contrib"][receiver]["return_wins"] += int(row.get("receiver_won") is True)

        if row.get("is_tiebreak_before") is True:
            winner = row.get("point_winner")
            winner_id = p1 if winner == 1 else p2 if winner == 2 else None
            for pid in (p1, p2):
                entry["contrib"][pid]["tiebreak_points"] += 1
                entry["contrib"][pid]["tiebreak_wins"] += int(winner_id == pid)

        counters["strict_rows_used"] += 1

    valid = []
    for entry in matches.values():
        if entry.get("conflict"):
            counters["conflicting_matches_rejected"] += 1
            continue
        if not any(
            int(stats.get("serve_points") or 0) + int(stats.get("return_points") or 0) > 0
            for stats in entry["contrib"].values()
        ):
            counters["empty_strict_matches_rejected"] += 1
            continue
        valid.append(entry)

    valid.sort(key=lambda m: (m["scheduled"], m["match_id"]))
    counters["strict_matches"] = len(valid)
    return valid, dict(counters)


def build_snapshots_from_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    matches, source_counts = _prepare_matches(rows)

    overall: dict[int, dict[str, int]] = defaultdict(_empty_stats)
    by_surface: dict[int, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(_empty_stats))
    snapshots: list[dict[str, Any]] = []
    readiness_any = Counter()
    readiness_surface = Counter()
    same_time_groups = 0

    for scheduled, group_iter in groupby(matches, key=lambda m: m["scheduled"]):
        group = list(group_iter)
        if len(group) > 1:
            same_time_groups += 1

        # Snapshot the entire time group before adding any of its matches.
        for match in group:
            for side, pid, opponent, ranking, opponent_ranking in (
                ("p1", match["p1"], match["p2"], match.get("p1_ranking"), match.get("p2_ranking")),
                ("p2", match["p2"], match["p1"], match.get("p2_ranking"), match.get("p1_ranking")),
            ):
                overall_snapshot = _project(overall.get(pid))
                surface_snapshot = _project(by_surface.get(pid, {}).get(match["surface"]))

                for threshold in THRESHOLDS:
                    readiness_any[threshold] += int(overall_snapshot["matches"] >= threshold)
                    readiness_surface[threshold] += int(surface_snapshot["matches"] >= threshold)

                snapshots.append({
                    "version": VERSION,
                    "mode": "SHADOW_AS_OF_PROFILE",
                    "production_influence": False,
                    "training_join_enabled": False,
                    "profile_threshold_activation_enabled": False,
                    "strict_as_of": True,
                    "same_time_matches_count_as_prior": False,
                    "target_match_id": match["match_id"],
                    "target_scheduled_time": scheduled.isoformat(),
                    "target_surface": match["surface"],
                    "target_tour": match.get("tour"),
                    "target_format": match.get("format"),
                    "target_round_code": match.get("round_code"),
                    "player_side": side,
                    "player_id": pid,
                    "opponent_id": opponent,
                    "player_ranking": ranking,
                    "opponent_ranking": opponent_ranking,
                    "overall_prior": overall_snapshot,
                    "same_surface_prior": surface_snapshot,
                })

        # Only after all snapshots at this timestamp exist does history advance.
        for match in group:
            for pid in (match["p1"], match["p2"]):
                contribution = match["contrib"][pid]
                _accumulate(overall[pid], contribution)
                _accumulate(by_surface[pid][match["surface"]], contribution)

    targets = len(snapshots)
    players = {int(row["player_id"]) for row in snapshots}
    summary = {
        "version": VERSION,
        "mode": "SHADOW_AS_OF_PROFILE",
        "source": "player-dna-point-dataset-v3 strict context-ready rows",
        "network_calls": 0,
        "production_influence": False,
        "training_join_enabled": False,
        "profile_threshold_activation_enabled": False,
        "strict_as_of_policy": "prior_match_scheduled_time < target_match_scheduled_time",
        "same_time_matches_count_as_prior": False,
        "strict_matches": int(source_counts.get("strict_matches") or 0),
        "player_match_snapshots": targets,
        "players": len(players),
        "same_time_groups": same_time_groups,
        "source_counts": source_counts,
        "readiness_any_surface": {
            str(threshold): {
                "targets": int(readiness_any[threshold]),
                "rate": round(readiness_any[threshold] / targets, 6) if targets else 0.0,
            }
            for threshold in THRESHOLDS
        },
        "readiness_same_surface": {
            str(threshold): {
                "targets": int(readiness_surface[threshold]),
                "rate": round(readiness_surface[threshold] / targets, 6) if targets else 0.0,
            }
            for threshold in THRESHOLDS
        },
        "features": {
            "overall_prior": [
                "matches", "serve_points", "serve_wins", "serve_win_rate",
                "return_points", "return_wins", "return_win_rate",
                "tiebreak_points", "tiebreak_wins", "tiebreak_win_rate",
            ],
            "same_surface_prior": [
                "matches", "serve_points", "serve_wins", "serve_win_rate",
                "return_points", "return_wins", "return_win_rate",
                "tiebreak_points", "tiebreak_wins", "tiebreak_win_rate",
            ],
        },
        "note": (
            "SHADOW evidence only. Raw support counts accompany every rate. "
            "No minimum-history threshold, training join or production influence is activated."
        ),
    }
    return snapshots, summary


def build() -> dict[str, Any]:
    snapshots, summary = build_snapshots_from_rows(iter_point_rows() or ())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(OUT_JSONL, "wt", encoding="utf-8") as handle:
        for row in snapshots:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    summary["dataset_path"] = str(OUT_JSONL.relative_to(ROOT))
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    build()
