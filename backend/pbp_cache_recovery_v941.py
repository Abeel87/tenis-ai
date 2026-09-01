from __future__ import annotations

"""Recover PBP profile supply from the already-restored cache, with zero network calls.

The normal PBP pass can legitimately exhaust its bounded API budget before every
current player profile is rebuilt.  The cache, however, may already contain a
player index and point-by-point tapes from earlier successful runs.  This helper
rebuilds only from that cache so granular Early Hold evidence is not silently
zeroed just because the live-call budget reached zero.

No thresholds or model formulas are changed.  The same ``pbp_enrich.build_profile``
and ``pbp_enrich.enrich_match`` code paths are reused with an API object whose
call cap is exactly zero.
"""

from typing import Any

try:
    from . import pbp_enrich as core
except ImportError:  # pragma: no cover - direct script/import from backend cwd
    import pbp_enrich as core

VERSION = "v9.4.1-pbp-cache-recovery"


def _cached_player_ids(index: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, entry in (index.get("players") or {}).items():
        if not isinstance(entry, dict):
            continue
        try:
            if entry.get("player_id") is not None:
                out[str(key)] = int(entry["player_id"])
        except (TypeError, ValueError):
            continue
    return out


def recover_rows_from_cache(rows: list[dict], *, now=None) -> tuple[list[dict], dict[str, Any]]:
    """Return rows enriched from existing PBP cache and a deterministic report.

    This function never performs an external request: ``API.call_cap`` is zero.
    Missing cache entries stay N/D rather than being guessed.
    """
    now = now or core.datetime.now(core.timezone.utc)
    index = core._read_json(core.INDEX_PATH, {"players": {}})
    if not isinstance(index, dict):
        index = {"players": {}}
    index.setdefault("players", {})

    player_ids = _cached_player_ids(index)
    api = core.API("", 0)
    counters = {
        "tape_downloads": 0,
        "tape_cache_hits": 0,
        "tape_errors": 0,
        "match_detail_calls": 0,
        "match_detail_errors": 0,
    }

    targets = [m for m in rows if m.get("model_ready") and m.get("service_model")]
    targets.sort(key=lambda m: m.get("scheduled_time") or "")

    profiles: dict[str, dict] = {}
    seen: set[str] = set()
    for match in targets:
        for side in ("p1", "p2"):
            name = match.get(side)
            key = core._key(name)
            if not name or not key or key in seen:
                continue
            seen.add(key)
            player_id = player_ids.get(key)
            if player_id is None:
                continue
            as_of = core._parse_dt(match.get("scheduled_time")) or now
            profile = core.build_profile(
                api,
                index,
                str(name),
                player_id,
                str(match.get("surface") or "").lower(),
                as_of,
                now,
                counters,
            )
            # Keep profiles with actual cached observations even when the strict
            # full-EHS gate is not ready; v9.4.0 per-market evidence can use them.
            if int(profile.get("trend_matches") or profile.get("matches") or 0) > 0:
                profiles[key] = profile

    strict_ready_matches = 0
    supplied_matches = 0
    for match in rows:
        if not match.get("model_ready") or not match.get("service_model"):
            continue
        p1 = profiles.get(core._key(match.get("p1")))
        p2 = profiles.get(core._key(match.get("p2")))
        if not p1 and not p2:
            continue

        existing = match.get("early_hold_v7") or {}
        # Never replace a richer live-built profile with a missing cache profile.
        p1_final = p1 or existing.get("p1") or {
            "player": match.get("p1"), "matches": 0, "ready": False, "ehs": None, "quality": "N/D"
        }
        p2_final = p2 or existing.get("p2") or {
            "player": match.get("p2"), "matches": 0, "ready": False, "ehs": None, "quality": "N/D"
        }
        core.enrich_match(match, p1_final, p2_final)
        supplied_matches += 1
        if (match.get("early_hold_v7") or {}).get("ready"):
            strict_ready_matches += 1

    report = {
        "version": VERSION,
        "mode": "CACHE_ONLY_ZERO_NETWORK",
        "api_calls": api.calls,
        "target_matches": len(targets),
        "cached_player_ids": len(player_ids),
        "profiles_recovered": len(profiles),
        "matches_with_recovered_supply": supplied_matches,
        "strict_ready_matches": strict_ready_matches,
        "tape_cache_hits": counters["tape_cache_hits"],
        "tape_errors": counters["tape_errors"],
    }
    return rows, report
