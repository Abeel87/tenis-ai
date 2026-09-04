from __future__ import annotations

"""Leakage-safe SHADOW Player DNA rolling profiles.

Profiles are computed only from matches with strictly earlier scheduled_time.
Matches sharing the same scheduled_time are processed as one group, so they can
never leak into one another. This module has no PROD, Symfonia 2.0 or PLAYABLE
influence and does not enable any training join.
"""

import gzip
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.player_dna_match_context import resolve_match_context
    from backend.player_dna_point_dataset import CACHE, _read, observations_from_payload
except ModuleNotFoundError:  # direct execution
    from player_dna_match_context import resolve_match_context
    from player_dna_point_dataset import CACHE, _read, observations_from_payload

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "derived" / "player_dna"
OUT_JSONL = OUT_DIR / "chronological_profiles.jsonl.gz"
OUT_SUMMARY = ROOT / "frontend" / "data" / "player_dna_profiles_summary.json"
PROFILE_VERSION = "player-dna-chronological-profiles"
WINDOWS = (5, 10, 20)
PRIOR_STRENGTH_POINTS = 50.0


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def match_record_from_observations(
    context: dict[str, Any], observations: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    players = {
        int(context["p1"]["id"]): {"serve_points": 0, "serve_won": 0, "return_points": 0, "return_won": 0},
        int(context["p2"]["id"]): {"serve_points": 0, "serve_won": 0, "return_points": 0, "return_won": 0},
    }
    for obs in observations:
        if not obs.get("trainable_player_point"):
            continue
        server_id = obs.get("server_player_id")
        receiver_id = obs.get("receiver_player_id")
        if server_id not in players or receiver_id not in players:
            continue
        players[server_id]["serve_points"] += 1
        players[server_id]["serve_won"] += int(obs.get("server_won") is True)
        players[receiver_id]["return_points"] += 1
        players[receiver_id]["return_won"] += int(obs.get("receiver_won") is True)
    return {
        "match_id": context.get("match_id"),
        "scheduled_time": context["scheduled_time"],
        "surface": context.get("surface"),
        "players": players,
    }


def record_from_payload(payload: dict[str, Any], match_id: Any) -> dict[str, Any] | None:
    context = resolve_match_context(payload)
    if context is None:
        return None
    observations = observations_from_payload(payload, match_id)
    return match_record_from_observations(context, observations)


def iter_cached_records() -> Iterable[dict[str, Any]]:
    if not CACHE.exists():
        return
    for path in sorted(CACHE.glob("*.json.gz")):
        payload = _read(path)
        if payload is None:
            continue
        match_id = path.name.removesuffix(".json.gz")
        record = record_from_payload(payload, match_id)
        if record is not None:
            yield record


def _aggregate(matches: list[dict[str, Any]], player_id: int) -> dict[str, int]:
    out = {"matches": 0, "serve_points": 0, "serve_won": 0, "return_points": 0, "return_won": 0}
    for match in matches:
        stats = (match.get("players") or {}).get(player_id)
        if not isinstance(stats, dict):
            continue
        out["matches"] += 1
        for key in ("serve_points", "serve_won", "return_points", "return_won"):
            out[key] += int(stats.get(key) or 0)
    return out


def _rate(wins: int, points: int) -> float | None:
    return round(wins / points, 6) if points > 0 else None


def _shrunk_rate(wins: int, points: int, prior_rate: float, prior_strength: float) -> float:
    return round((wins + prior_rate * prior_strength) / (points + prior_strength), 6)


def _metric_block(wins: int, points: int, prior_rate: float) -> dict[str, Any]:
    return {
        "wins": wins,
        "points": points,
        "raw_rate": _rate(wins, points),
        "shrunk_rate": _shrunk_rate(wins, points, prior_rate, PRIOR_STRENGTH_POINTS),
        "prior_rate": round(prior_rate, 6),
        "prior_strength_points": PRIOR_STRENGTH_POINTS,
        "quality": round(min(1.0, points / 200.0), 6),
    }


def _population_priors(history: list[dict[str, Any]]) -> tuple[float, float]:
    serve_won = serve_points = return_won = return_points = 0
    for match in history:
        for stats in (match.get("players") or {}).values():
            if not isinstance(stats, dict):
                continue
            serve_points += int(stats.get("serve_points") or 0)
            serve_won += int(stats.get("serve_won") or 0)
            return_points += int(stats.get("return_points") or 0)
            return_won += int(stats.get("return_won") or 0)
    serve_prior = serve_won / serve_points if serve_points else 0.5
    return_prior = return_won / return_points if return_points else 0.5
    return serve_prior, return_prior


def _window_profile(
    player_history: list[dict[str, Any]],
    player_id: int,
    window: int,
    serve_prior: float,
    return_prior: float,
) -> dict[str, Any]:
    selected = player_history[-window:]
    agg = _aggregate(selected, player_id)
    return {
        "window_matches": window,
        "matches_used": agg["matches"],
        "serve": _metric_block(agg["serve_won"], agg["serve_points"], serve_prior),
        "return": _metric_block(agg["return_won"], agg["return_points"], return_prior),
    }


def build_chronological_profiles(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = [
        record for record in records
        if isinstance(record, dict)
        and isinstance(record.get("scheduled_time"), str)
        and isinstance(record.get("players"), dict)
    ]
    valid.sort(key=lambda row: (_dt(row["scheduled_time"]), str(row.get("match_id"))))

    history: list[dict[str, Any]] = []
    player_history: dict[int, list[dict[str, Any]]] = defaultdict(list)
    output: list[dict[str, Any]] = []
    index = 0
    while index < len(valid):
        stamp = valid[index]["scheduled_time"]
        group: list[dict[str, Any]] = []
        while index < len(valid) and valid[index]["scheduled_time"] == stamp:
            group.append(valid[index])
            index += 1

        serve_prior, return_prior = _population_priors(history)
        for record in group:
            target_surface = record.get("surface")
            row_players: dict[str, Any] = {}
            for player_id in sorted(int(pid) for pid in record["players"].keys()):
                prior_matches = player_history.get(player_id, [])
                same_surface = [m for m in prior_matches if target_surface is not None and m.get("surface") == target_surface]
                row_players[str(player_id)] = {
                    "all_surface": {
                        f"L{window}": _window_profile(prior_matches, player_id, window, serve_prior, return_prior)
                        for window in WINDOWS
                    },
                    "same_surface": {
                        "surface": target_surface,
                        "available": target_surface is not None,
                        "windows": {
                            f"L{window}": _window_profile(same_surface, player_id, window, serve_prior, return_prior)
                            for window in WINDOWS
                        } if target_surface is not None else {},
                    },
                }
            output.append({
                "version": PROFILE_VERSION,
                "match_id": record.get("match_id"),
                "scheduled_time": stamp,
                "surface": target_surface,
                "players": row_players,
                "prior_matches_total": len(history),
                "strictly_prior_only": True,
                "same_time_group_isolated": True,
                "shadow_only": True,
                "training_join_enabled": False,
            })

        history.extend(group)
        for record in group:
            for player_id in record["players"]:
                player_history[int(player_id)].append(record)
    return output


def build() -> dict[str, Any]:
    records = list(iter_cached_records() or ())
    profiles = build_chronological_profiles(records)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT_JSONL, "wt", encoding="utf-8") as handle:
        for row in profiles:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    players = {pid for row in profiles for pid in row.get("players", {})}
    summary = {
        "version": PROFILE_VERSION,
        "records": len(records),
        "profiles": len(profiles),
        "players": len(players),
        "windows": list(WINDOWS),
        "prior_strength_points": PRIOR_STRENGTH_POINTS,
        "strictly_prior_only": True,
        "same_time_group_isolated": True,
        "surface_profiles": True,
        "network_calls": 0,
        "shadow_only": True,
        "training_join_enabled": False,
        "artifact_path": str(OUT_JSONL.relative_to(ROOT)),
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    build()
