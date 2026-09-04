from __future__ import annotations

"""Build the compact SHADOW Player DNA point-event dataset.

Only strict atomic point transitions may be point-trainable. Stable identities
come solely from audited match.players.p1/p2 provider IDs. No name/fuzzy fallback
is allowed. This layer never feeds Current Engine, Symfonia 2.0 or PLAYABLE.
"""

import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.canonical_point_event import ORDERING_AUTHORITY, TIMESTAMP_ROLE, canonical_point_events
    from backend.player_identity import player_identity_map
except ModuleNotFoundError:  # direct execution
    from canonical_point_event import ORDERING_AUTHORITY, TIMESTAMP_ROLE, canonical_point_events
    from player_identity import player_identity_map

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT_DIR = ROOT / "data" / "derived" / "player_dna"
OUT_JSONL = OUT_DIR / "point_events.jsonl.gz"
OUT_SUMMARY = ROOT / "frontend" / "data" / "player_dna_point_dataset_summary.json"
DATASET_VERSION = "player-dna-point-dataset-v3"


def _read(path: Path) -> dict[str, Any] | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def compact_observation(event: dict[str, Any], identities: dict[int, dict[str, Any]] | None = None) -> dict[str, Any]:
    winner = event.get("point_winner")
    server = event.get("server")
    receiver = event.get("receiver")
    quality = event.get("quality") if isinstance(event.get("quality"), dict) else {}
    p1 = identities.get(1) if identities else None
    p2 = identities.get(2) if identities else None
    server_identity = identities.get(server) if identities and server in (1, 2) else None
    receiver_identity = identities.get(receiver) if identities and receiver in (1, 2) else None
    identity_valid = p1 is not None and p2 is not None
    trainable_point = bool(quality.get("trainable_point"))
    return {
        "dataset_version": DATASET_VERSION,
        "schema_version": event.get("schema_version"),
        "match_id": event.get("match_id"),
        "event_index": event.get("event_index"),
        "ordering_authority": event.get("ordering_authority"),
        "timestamp_role": event.get("timestamp_role"),
        "provider_row_order_preserved": event.get("provider_row_order_preserved") is True,
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
        "trainable_point": trainable_point,
        "identity_valid": identity_valid,
        "p1_player_id": p1.get("id") if p1 else None,
        "p2_player_id": p2.get("id") if p2 else None,
        "server_player_id": server_identity.get("id") if server_identity else None,
        "receiver_player_id": receiver_identity.get("id") if receiver_identity else None,
        "trainable_player_point": bool(trainable_point and server_identity is not None and receiver_identity is not None),
    }


def observations_from_payload(payload: dict[str, Any], match_id: Any) -> list[dict[str, Any]]:
    identities = player_identity_map(payload)
    return [compact_observation(event, identities) for event in canonical_point_events(payload, match_id=match_id)]


def iter_cached_observations() -> Iterable[dict[str, Any]]:
    if not CACHE.exists():
        return
    for path in sorted(CACHE.glob("*.json.gz")):
        payload = _read(path)
        if payload is None:
            continue
        match_id = path.name.removesuffix(".json.gz")
        yield from observations_from_payload(payload, match_id)


def build() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    total = trainable_basic = trainable_point = trainable_player_point = 0
    matches: set[str] = set()
    identity_matches: set[str] = set()
    transition_kinds: Counter[str] = Counter()
    server_sources: Counter[str] = Counter()
    point_sources: Counter[str] = Counter()
    atomic_reasons: Counter[str] = Counter()
    player_points: Counter[int] = Counter()
    player_wins: Counter[int] = Counter()

    with gzip.open(OUT_JSONL, "wt", encoding="utf-8") as handle:
        for obs in iter_cached_observations() or ():
            total += 1
            match_id = str(obs.get("match_id"))
            matches.add(match_id)
            if obs.get("identity_valid"):
                identity_matches.add(match_id)
            transition_kinds[str(obs.get("transition_kind"))] += 1
            server_sources[str(obs.get("server_source"))] += 1
            point_sources[str(obs.get("point_source"))] += 1
            atomic_reasons[str(obs.get("atomic_reason"))] += 1
            trainable_basic += int(bool(obs.get("trainable_basic")))
            trainable_point += int(bool(obs.get("trainable_point")))
            if obs.get("trainable_player_point"):
                trainable_player_point += 1
                pid = int(obs["server_player_id"])
                player_points[pid] += 1
                if obs.get("server_won") is True:
                    player_wins[pid] += 1
            handle.write(json.dumps(obs, ensure_ascii=False, separators=(",", ":")) + "\n")

    summary = {
        "version": DATASET_VERSION,
        "source": "canonical-point-event-v2 + pbp-player-identity-v1 over restored cache",
        "network_calls": 0,
        "shadow_only": True,
        "matches": len(matches),
        "events": total,
        "trainable_basic": trainable_basic,
        "trainable_point": trainable_point,
        "trainable_player_point": trainable_player_point,
        "trainable_player_point_rate": round(trainable_player_point / total, 6) if total else 0.0,
        "identity_matches": len(identity_matches),
        "identity_match_rate": round(len(identity_matches) / len(matches), 6) if matches else 0.0,
        "players_with_trainable_points": len(player_points),
        "transition_kinds": dict(transition_kinds.most_common()),
        "server_sources": dict(server_sources.most_common()),
        "point_sources": dict(point_sources.most_common()),
        "atomic_reasons": dict(atomic_reasons.most_common()),
        "dataset_path": str(OUT_JSONL.relative_to(ROOT)),
        "identity_status": "PROVIDER_BACKED_P1_P2_IDS; no name/fuzzy fallback",
        "ordering_contract": {
            "authority": ORDERING_AUTHORITY,
            "timestamp_role": TIMESTAMP_ROLE,
            "provider_row_order_preserved": True,
            "timestamp_sorting_forbidden": True,
        },
        "note": "Only trainable_player_point combines proven one-point atomicity with explicit stable provider identity. Still SHADOW-only; no production model consumes it.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    build()
