from __future__ import annotations

"""Stable zero-request audit of raw Superbet market families.

Uses only the already-fetched OddsPapi fixture response and cached market
catalogue. It stores no prices and makes no additional external request.
"""

import math
from collections import defaultdict

try:
    from . import superbet_market_core as base
    from . import superbet_market_mapping as mapping
except ImportError:
    import superbet_market_core as base
    import superbet_market_mapping as mapping

VERSION = "v9.2.3"
MAX_HANDICAP_SAMPLES = 16
MAX_MARKET_ID_SAMPLES = 5


def _num(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _superbet_markets(row: dict) -> dict:
    bookmaker_odds = row.get("bookmakerOdds") or {}
    book = bookmaker_odds.get(base.BOOKMAKER)
    if not isinstance(book, dict):
        book = next((value for key, value in bookmaker_odds.items() if "superbet" in str(key).casefold() and isinstance(value, dict)), None)
    markets = (book or {}).get("markets") if isinstance(book, dict) else None
    return markets if isinstance(markets, dict) else {}


def _raw_families(row: dict, meta: dict) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for market_id, market_data in _superbet_markets(row).items():
        if not isinstance(market_data, dict) or market_data.get("marketActive") is False:
            continue
        market_meta = meta.get(str(market_id), {}) if isinstance(meta, dict) else {}
        name = str(market_meta.get("marketName") or f"market {market_id}")
        market_type = market_meta.get("marketType")
        period = market_meta.get("period")
        player_prop = market_meta.get("playerProp")
        canonical, checkpoint, player_side = base.canonical_market(name)
        signature = (name, str(market_type or ""), str(period or ""), player_prop)
        family = grouped.setdefault(signature, {
            "market_name": name, "market_type": market_type, "period": period,
            "player_prop": player_prop, "canonical": canonical,
            "checkpoints": set(), "player_sides": set(), "active_market_variants": 0,
            "handicaps": set(), "sample_market_ids": [],
        })
        family["active_market_variants"] += 1
        if checkpoint is not None: family["checkpoints"].add(int(checkpoint))
        if player_side: family["player_sides"].add(str(player_side))
        handicap = _num(market_meta.get("handicap"))
        if handicap is not None and len(family["handicaps"]) < MAX_HANDICAP_SAMPLES: family["handicaps"].add(handicap)
        if len(family["sample_market_ids"]) < MAX_MARKET_ID_SAMPLES: family["sample_market_ids"].append(str(market_id))
    out = []
    for family in grouped.values():
        row_out = dict(family)
        row_out["checkpoints"] = sorted(family["checkpoints"])
        row_out["player_sides"] = sorted(family["player_sides"])
        row_out["handicaps"] = sorted(family["handicaps"])
        row_out["recognized"] = bool(family.get("canonical"))
        out.append(row_out)
    return sorted(out, key=lambda item: (str(item.get("market_name")), str(item.get("period"))))


def sanitize_with_audit(row: dict, meta: dict, original_sanitize):
    sanitized = original_sanitize(row, meta)
    if not isinstance(sanitized, dict): return sanitized
    families = _raw_families(row, meta)
    unknown = [dict(item) for item in families if not item.get("recognized")]
    sanitized = dict(sanitized)
    sanitized["raw_market_family_count"] = len(families)
    sanitized["unrecognized_market_family_count"] = len(unknown)
    sanitized["raw_market_families"] = families
    sanitized["unrecognized_market_families"] = unknown
    sanitized["raw_family_audit_version"] = VERSION
    return sanitized


def _family_key(item: dict) -> tuple:
    return (str(item.get("market_name") or ""), str(item.get("market_type") or ""), str(item.get("period") or ""), item.get("player_prop"))


def build_audit(fixtures) -> dict:
    aggregate: dict[tuple, dict] = {}
    fixture_count = 0
    for fixture in fixtures if isinstance(fixtures, list) else []:
        if not isinstance(fixture, dict): continue
        families = fixture.get("raw_market_families") or []
        if families: fixture_count += 1
        for item in families:
            if not isinstance(item, dict): continue
            key = _family_key(item)
            row = aggregate.setdefault(key, {
                "market_name": item.get("market_name"), "market_type": item.get("market_type"),
                "period": item.get("period"), "player_prop": item.get("player_prop"),
                "canonical": item.get("canonical"), "recognized": bool(item.get("recognized")),
                "fixture_count": 0, "active_market_variants": 0, "handicaps": set(),
                "checkpoints": set(), "sample_market_ids": [],
            })
            row["fixture_count"] += 1
            row["active_market_variants"] += int(item.get("active_market_variants") or 0)
            row["recognized"] = row["recognized"] or bool(item.get("recognized"))
            row["canonical"] = row.get("canonical") or item.get("canonical")
            for value in item.get("handicaps") or []:
                if len(row["handicaps"]) < MAX_HANDICAP_SAMPLES:
                    number = _num(value)
                    if number is not None: row["handicaps"].add(number)
            for value in item.get("checkpoints") or []:
                try: row["checkpoints"].add(int(value))
                except (TypeError, ValueError): pass
            for value in item.get("sample_market_ids") or []:
                token = str(value)
                if token not in row["sample_market_ids"] and len(row["sample_market_ids"]) < MAX_MARKET_ID_SAMPLES: row["sample_market_ids"].append(token)
    families = []
    for item in aggregate.values():
        out = dict(item); out["handicaps"] = sorted(item["handicaps"]); out["checkpoints"] = sorted(item["checkpoints"]); families.append(out)
    families.sort(key=lambda item: (not bool(item.get("recognized")), str(item.get("market_name"))))
    unrecognized = [dict(item) for item in families if not item.get("recognized")]
    return {
        "version": VERSION, "fixtures_with_family_audit": fixture_count,
        "unique_raw_market_families": len(families), "unique_unrecognized_market_families": len(unrecognized),
        "families": families, "unrecognized_families": unrecognized,
        "additional_external_requests": 0, "prices_used": False,
        "contract": {"uses_existing_odds_response_only": True, "stores_prices": False, "does_not_request_extra_tennis_data": True},
    }


def stamp_audit(version: str | None = None) -> dict:
    availability = base._read(base.AVAILABILITY, {})
    if not isinstance(availability, dict): return {}
    availability = dict(availability)
    audit = build_audit(availability.get("fixtures") or [])
    if version: audit["version"] = version
    availability["raw_family_audit_v923"] = audit
    availability["raw_family_audit_version"] = version or VERSION
    availability["runtime_adapter_version"] = version or VERSION
    base._write(base.AVAILABILITY, availability)
    return audit


def prepare(runtime_version: str = VERSION) -> dict:
    original_sanitize = mapping._sanitize_fixture
    original_version = mapping.VERSION
    def audited_sanitize(row: dict, meta: dict): return sanitize_with_audit(row, meta, original_sanitize)
    mapping._sanitize_fixture = audited_sanitize
    mapping.VERSION = runtime_version
    try: result = dict(mapping.prepare())
    finally:
        mapping._sanitize_fixture = original_sanitize
        mapping.VERSION = original_version
    audit = stamp_audit(runtime_version)
    result["raw_family_audit_version"] = runtime_version
    result["raw_family_audit"] = audit
    result["additional_external_requests"] = 0
    return result


def finalize(runtime_version: str = VERSION) -> dict:
    result = dict(mapping.finalize())
    audit = stamp_audit(runtime_version)
    result["raw_family_audit_version"] = runtime_version
    result["raw_family_audit"] = audit
    result["additional_external_requests"] = 0
    return result
