from __future__ import annotations

"""Build a compact SHADOW point-event dataset from cached PBP tapes.

This Player DNA data layer consumes canonical point events and separates broad
observability from strict one-point trainability. It never feeds Current Engine,
Symfonia 2.0 or Superbet PLAYABLE.
"""

import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.canonical_point_event import canonical_point_events
except ModuleNotFoundError:  # direct execution: python backend/player_dna_point_dataset.py
    from canonical_point_event import canonical_point_events

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT_DIR = ROOT / "data" / "derived" / "player_dna"
OUT_JSONL = OUT_DIR / "point_events.jsonl.gz"
OUT_SUMMARY = ROOT / "frontend" / "data" / "player_dna_point_dataset_summary.json"
DATASET_VERSION = "player-dna-point-dataset-v2"


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
        "atomic_transition": bool(quality.get("atomic_transition")),
        "atomic_reason": quality.get("atomic_reason"),
        "atomic_validator_version": quality.get("atomic_validator_version"),
        "trainable_point": bool(quality.get("trainable_point")),
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
    trainable_basic = 0
    trainable_point = 0
    matches: set[str] = set()
    transition_kinds: Counter[str] = Counter()
    server_sources: Counter[str] = Counter()
    point_sources: Counter[str] = Counter()
    atomic_reasons: Counter[str] = Counter()
    server_points: Counter[str] = Counter()
    server_wins: Counter[str] = Counter()

    with gzip.open(OUT_JSONL, "wt", encoding="utf-8") as handle:
        for obs in iter_cached_observations() or ():
            total += 1
            matches.add(str(obs.get("match_id")))
            transition_kinds[str(obs.get("transition_kind"))] += 1
            server_sources[str(obs.get("server_source"))] += 1
            point_sources[str(obs.get("point_source"))] += 1
            atomic_reasons[str(obs.get("atomic_reason"))] += 1
            if obs.get("trainable_basic"):
                trainable_basic += 1
            if obs.get("trainable_point"):
                trainable_point += 1
                side = str(obs.get("server"))
                server_points[side] += 1
                if obs.get("server_won") is True:
                    server_wins[side] += 1
            handle.write(json.dumps(obs, ensure_ascii=False, separators=(",", ":")) + "\n")

    point_win_proxy = {
        side: round(server_wins[side] / n, 6) if n else None
        for side, n in sorted(server_points.items())
    }
    summary = {
        "version": DATASET_VERSION,
        "source": "canonical-point-event-v2 over restored data/cache/pbp_v7/matches",
        "network_calls": 0,
        "shadow_only": True,
        "matches": len(matches),
        "events": total,
        "trainable_basic": trainable_basic,
        "trainable_basic_rate": round(trainable_basic / total, 6) if total else 0.0,
        "trainable_point": trainable_point,
        "trainable_point_rate": round(trainable_point / total, 6) if total else 0.0,
        "transition_kinds": dict(transition_kinds.most_common()),
        "server_sources": dict(server_sources.most_common()),
        "point_sources": dict(point_sources.most_common()),
        "atomic_reasons": dict(atomic_reasons.most_common()),
        "server_point_win_rate_by_match_side_trainable_point_only": point_win_proxy,
        "dataset_path": str(OUT_JSONL.relative_to(ROOT)),
        "identity_status": "stable provider identity resolver exists; dataset identity attachment is a separate gate",
        "note": "Only trainable_point rows are proven one-point transitions. trainable_basic remains diagnostic and must not be used for point training.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    build()
