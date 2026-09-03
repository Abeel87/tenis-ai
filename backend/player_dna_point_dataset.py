from __future__ import annotations

"""Build a compact SHADOW point-event dataset from cached PBP tapes.

This is the first Player DNA data layer. It consumes only canonical point events,
keeps missing winner/server rows out of the trainable subset, and never feeds
Current Engine, Symfonia 2.0 or Superbet PLAYABLE.
"""

import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from canonical_point_event import canonical_point_events

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT_DIR = ROOT / "data" / "derived" / "player_dna"
OUT_JSONL = OUT_DIR / "point_events.jsonl.gz"
OUT_SUMMARY = ROOT / "frontend" / "data" / "player_dna_point_dataset_summary.json"
DATASET_VERSION = "player-dna-point-dataset-v1"


def _read(path: Path) -> dict[str, Any] | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def compact_observation(event: dict[str, Any]) -> dict[str, Any]:
    winner = event.get("point_winner")
    server = event.get("server")
    receiver = event.get("receiver")
    quality = event.get("quality") if isinstance(event.get("quality"), dict) else {}
    return {
        "dataset_version": DATASET_VERSION,
        "schema_version": event.get("schema_version"),
        "match_id": event.get("match_id"),
        "event_index": event.get("event_index"),
        "transition_kind": event.get("transition_kind"),
        "score_before": event.get("score_before"),
        "score_after": event.get("score_after"),
        "server": server,
        "receiver": receiver,
        "point_winner": winner,
        "server_won": bool(winner == server) if winner in (1, 2) and server in (1, 2) else None,
        "receiver_won": bool(winner == receiver) if winner in (1, 2) and receiver in (1, 2) else None,
        "is_tiebreak_before": bool(event.get("is_tiebreak_before")),
        "is_tiebreak_after": bool(event.get("is_tiebreak_after")),
        "timestamp_after": event.get("timestamp_after"),
        "point_source": event.get("point_source"),
        "server_source": event.get("server_source"),
        "trainable_basic": bool(quality.get("trainable_basic")),
    }


def observations_from_payload(payload: dict[str, Any], match_id: Any) -> list[dict[str, Any]]:
    return [compact_observation(event) for event in canonical_point_events(payload, match_id=match_id)]


def iter_cached_observations() -> Iterable[dict[str, Any]]:
    if not CACHE.exists():
        return
    for path in sorted(CACHE.glob("*.json.gz")):
        payload = _read(path)
        if payload is None:
            continue
        match_id = path.name.removesuffix(".json.gz")
        for obs in observations_from_payload(payload, match_id):
            yield obs


def build() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    trainable = 0
    matches: set[str] = set()
    transition_kinds: Counter[str] = Counter()
    server_sources: Counter[str] = Counter()
    point_sources: Counter[str] = Counter()
    server_points: Counter[str] = Counter()
    server_wins: Counter[str] = Counter()

    with gzip.open(OUT_JSONL, "wt", encoding="utf-8") as handle:
        for obs in iter_cached_observations() or ():
            total += 1
            matches.add(str(obs.get("match_id")))
            transition_kinds[str(obs.get("transition_kind"))] += 1
            server_sources[str(obs.get("server_source"))] += 1
            point_sources[str(obs.get("point_source"))] += 1
            if obs.get("trainable_basic"):
                trainable += 1
                side = str(obs.get("server"))
                server_points[side] += 1
                if obs.get("server_won") is True:
                    server_wins[side] += 1
            handle.write(json.dumps(obs, ensure_ascii=False, separators=(",", ":")) + "\n")

    hold_proxy = {
        side: round(server_wins[side] / n, 6) if n else None
        for side, n in sorted(server_points.items())
    }
    summary = {
        "version": DATASET_VERSION,
        "source": "canonical-point-event-v1 over restored data/cache/pbp_v7/matches",
        "network_calls": 0,
        "shadow_only": True,
        "matches": len(matches),
        "events": total,
        "trainable_basic": trainable,
        "trainable_basic_rate": round(trainable / total, 6) if total else 0.0,
        "transition_kinds": dict(transition_kinds.most_common()),
        "server_sources": dict(server_sources.most_common()),
        "point_sources": dict(point_sources.most_common()),
        "server_point_win_rate_by_match_side": hold_proxy,
        "dataset_path": str(OUT_JSONL.relative_to(ROOT)),
        "identity_status": "MATCH_SIDE_ONLY; stable player identity join is a separate gate",
        "note": "No player identity is guessed from side=1/2. This file is a compact point observation layer, not a production model.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    build()
