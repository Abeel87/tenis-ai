from __future__ import annotations

"""Canonical strict current-fixture Superbet market context.

Production composes stable market core, mapping, raw-family audit and fixture
matching modules. It never invents a PLAYABLE line: line markets are emitted
only when the exact active current-fixture variant carries verifiable line
evidence. MODEL/RAW lines and nearest-line substitutions remain forbidden.
"""

import json
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone

try:
    from . import superbet_fixture_matching as fixture_matching
    from . import superbet_market_audit as audit_runtime
    from . import superbet_market_core as base
    from . import superbet_market_mapping as mapping
except ImportError:
    import superbet_fixture_matching as fixture_matching
    import superbet_market_audit as audit_runtime
    import superbet_market_core as base
    import superbet_market_mapping as mapping

VERSION = "v9.2.4"
STRICT_FIXTURE_LINE_VERSION = "v9.3.4-core"
NEW_LINE_MARKETS = {"set_handicap"}
NEW_HANDICAP_MARKETS = {"set_handicap"}
DIRECT_SIDECAR = base.OUT / "superbet_direct_current.json"
DIRECT_MAX_AGE_HOURS = mapping.REFRESH_HOURS * 1.8
DIRECT_SOURCE = "superbet_direct_public_event_json"
DIRECT_HANDICAP_MARKETS = {
    "match_game_handicap",
    "set1_game_handicap",
    "set2_game_handicap",
    "set3_game_handicap",
    "set_handicap",
}

NEW_MARKETS = {
    "any_set_to_nil", "set2_exact_score", "set2_game_state", "exact_sets",
    "match_games_parity", "set1_games_parity", "set2_games_parity",
    "p1_exactly_1_set", "p1_exactly_2_sets", "p2_exactly_1_set",
    "p2_exactly_2_sets", "p1_wins_a_set", "p2_wins_a_set", "set_handicap",
}

_ORIGINAL_CANONICAL = base.canonical_market
_ORIGINAL_SELECTION_PICK = mapping._selection_pick


def canonical_market(market_name: str):
    existing = _ORIGINAL_CANONICAL(market_name)
    if existing[0]: return existing
    n = base._norm(market_name); cp = base._checkpoint_from_market(market_name)
    table = {
        "any set to nil": ("any_set_to_nil", None, None),
        "correct score second set": ("set2_exact_score", None, None),
        "exact sets": ("exact_sets", None, None),
        "odd even games": ("match_games_parity", None, None),
        "odd even games first set": ("set1_games_parity", None, None),
        "odd even games second set": ("set2_games_parity", None, None),
        "participant 1 to exactly win one set": ("p1_exactly_1_set", None, "p1"),
        "participant 1 to exactly win two sets": ("p1_exactly_2_sets", None, "p1"),
        "participant 2 to exactly win one set": ("p2_exactly_1_set", None, "p2"),
        "participant 2 to exactly win two sets": ("p2_exactly_2_sets", None, "p2"),
        "participant 1 to win a set": ("p1_wins_a_set", None, "p1"),
        "participant 2 to win a set": ("p2_wins_a_set", None, "p2"),
        "set handicap": ("set_handicap", None, None),
    }
    if n in table: return table[n]
    if "correct score second set after" in n and cp: return "set2_game_state", cp, None
    return None, None, None


def _yes_no(*values):
    words=set(base._norm(" ".join(str(v or "") for v in values)).split())
    if words & {"yes","tak","true"}: return "yes"
    if words & {"no","nie","false"}: return "no"
    return None


def _parity(*values):
    words=set(base._norm(" ".join(str(v or "") for v in values)).split())
    if "odd" in words or "nieparzyste" in words:return "odd"
    if "even" in words or "parzyste" in words:return "even"
    return None


def _small_integer(*values):
    for value in values:
        nums=re.findall(r"(?<!\d)([1-5])(?!\d)",str(value or ""))
        if nums:return str(int(nums[0]))
    return None


def selection_pick(market,outcome_name,bookmaker_outcome_id,p1,p2):
    if market in {"set2_exact_score","set2_game_state"}:return base._score_from_text(outcome_name,bookmaker_outcome_id)
    if market in {"match_games_parity","set1_games_parity","set2_games_parity"}:return _parity(outcome_name,bookmaker_outcome_id)
    if market=="exact_sets":return _small_integer(outcome_name,bookmaker_outcome_id)
    if market in {"any_set_to_nil","p1_exactly_1_set","p1_exactly_2_sets","p2_exactly_1_set","p2_exactly_2_sets","p1_wins_a_set","p2_wins_a_set"}:return _yes_no(outcome_name,bookmaker_outcome_id)
    if market=="set_handicap":return mapping._winner_pick(outcome_name,bookmaker_outcome_id,p1,p2)
    return _ORIGINAL_SELECTION_PICK(market,outcome_name,bookmaker_outcome_id,p1,p2)


def _fixture_numeric(holder: dict,*fields):
    if not isinstance(holder,dict):return None,None
    for field in fields:
        value=base._line(holder.get(field))
        if value is not None:return value,field
    return None,None


def _orient_line(market,value,outcome_name,bookmaker_outcome_id,pick,p1,p2):
    if value is None:return None
    if market in mapping.HANDICAP_MARKETS:
        side=mapping._handicap_side(outcome_name,bookmaker_outcome_id,pick,p1,p2)
        if side=="p2":return -value
        return value
    return abs(value)


def _fixture_line_for_selection(market: str,market_data: dict,market_meta: dict,outcome_data: dict,carrier_data: dict,outcome_name,bookmaker_outcome_id,*,pick=None,p1=None,p2=None):
    if market not in mapping.LINE_MARKETS:return None,None
    for holder,prefix in ((carrier_data,"player"),(outcome_data,"outcome")):
        value,field=_fixture_numeric(holder,"handicap","line")
        if value is not None:return _orient_line(market,value,outcome_name,bookmaker_outcome_id,pick,p1,p2),f"oddspapi_fixture_{prefix}_{field}"
    value,field=_fixture_numeric(market_data,"handicap","line")
    if value is not None:return _orient_line(market,value,outcome_name,bookmaker_outcome_id,pick,p1,p2),f"oddspapi_fixture_market_{field}"
    text_line=base._line_from_text(bookmaker_outcome_id,outcome_name,market_data.get("bookmakerMarketId") if isinstance(market_data,dict) else None,outcome_data.get("bookmakerOutcomeId") if isinstance(outcome_data,dict) else None)
    if text_line is not None:return _orient_line(market,text_line,outcome_name,bookmaker_outcome_id,pick,p1,p2),"oddspapi_fixture_text_line"
    if isinstance(market_data,dict) and market_data.get("marketActive") is not False:
        catalogue_line=base._line((market_meta or {}).get("handicap"))
        if catalogue_line is not None:return _orient_line(market,catalogue_line,outcome_name,bookmaker_outcome_id,pick,p1,p2),"oddspapi_active_fixture_market_id_handicap"
    return None,None


def _selection_carriers(outcome_data: dict) -> list[dict]:
    if not isinstance(outcome_data,dict) or outcome_data.get("active") is False:return []
    players=outcome_data.get("players") or {}
    active_players=[player for player in players.values() if isinstance(player,dict) and player.get("active") is not False] if isinstance(players,dict) else []
    return active_players or [outcome_data]


def _selection_is_valid(market: str,pick) -> bool:
    if market in {"match_total","set1_total","set2_total","set3_total","total_sets","player_total_games","match_total_aces"}:return pick in {"over","under"}
    if market in {"set1_exact_score","set2_exact_score","exact_match_score","game_state","set2_game_state"}:return bool(pick)
    if market in NEW_MARKETS:return bool(pick)
    return bool(pick)


def mapped_sanitize(row: dict,meta: dict):
    bookmaker_odds=row.get("bookmakerOdds") or {}; book=bookmaker_odds.get(base.BOOKMAKER)
    if not isinstance(book,dict):book=next((value for key,value in bookmaker_odds.items() if "superbet" in str(key).casefold() and isinstance(value,dict)),None)
    if not isinstance(book,dict):return None
    raw_markets=book.get("markets") or {}
    if not isinstance(raw_markets,dict):return None
    bookmaker_active=book.get("bookmakerIsActive") is not False
    p1=str(row.get("participant1Name") or "");p2=str(row.get("participant2Name") or "");selections=[];recognized_markets=set();suppressed_without_fixture_line=0
    for raw_market_id,market_data in raw_markets.items():
        if not isinstance(market_data,dict) or market_data.get("marketActive") is False:continue
        market_id=str(raw_market_id);market_meta=meta.get(market_id,{}) if isinstance(meta,dict) else {};market_name=str(market_meta.get("marketName") or f"market {market_id}");market,checkpoint,player_side=canonical_market(market_name)
        if not market:continue
        recognized_markets.add(market);outcomes=market_data.get("outcomes") or {}
        if not isinstance(outcomes,dict):continue
        for raw_outcome_id,outcome_data in outcomes.items():
            if not isinstance(outcome_data,dict):continue
            outcome_id=str(raw_outcome_id);outcome_meta=(market_meta.get("outcomes") or {}).get(outcome_id,{}) if isinstance(market_meta,dict) else {};outcome_name=outcome_meta.get("outcomeName") or outcome_meta.get("outcomeNameShort")
            for carrier in _selection_carriers(outcome_data):
                boid=carrier.get("bookmakerOutcomeId") or outcome_data.get("bookmakerOutcomeId");pick=selection_pick(market,outcome_name,boid,p1,p2)
                if not _selection_is_valid(market,pick):continue
                line=None;line_source=None
                if market in mapping.LINE_MARKETS:
                    line,line_source=_fixture_line_for_selection(market,market_data,market_meta,outcome_data,carrier,outcome_name,boid,pick=pick,p1=p1,p2=p2)
                    if line is None:suppressed_without_fixture_line+=1;continue
                player=p1 if player_side=="p1" else p2 if player_side=="p2" else carrier.get("playerName") or outcome_data.get("playerName")
                selection={"market":market,"pick":pick,"line":line,"checkpoint":checkpoint,"player":player,"market_name":market_name,"market_id":market_id,"outcome_id":outcome_id,"main_line":bool(carrier.get("mainLine",outcome_data.get("mainLine",False))),"operator_available":True,"operator_line_verified":True}
                if market in mapping.LINE_MARKETS:
                    selection["operator_line_source"]=line_source;selection["fixture_line_verified"]=True;selection["fixture_line_contract_version"]=STRICT_FIXTURE_LINE_VERSION
                selections.append(selection)
    dedup={}
    for selection in selections:
        sig=(selection.get("market"),base._norm(selection.get("pick")),base._line(selection.get("line")),int(selection.get("checkpoint") or 0),base._name_key(selection.get("player")))
        if sig not in dedup or selection.get("main_line"):dedup[sig]=selection
    selections=sorted(dedup.values(),key=lambda selection:(str(selection.get("market")),float(selection.get("line") if selection.get("line") is not None else -999),str(selection.get("pick"))))
    return {"fixture_id":row.get("fixtureId"),"p1":p1,"p2":p2,"start_time":row.get("startTime"),"tournament":row.get("tournamentName"),"tournament_id":row.get("tournamentId"),"bookmaker":base.BOOKMAKER,"bookmaker_active":bookmaker_active,"suspended":bool(book.get("suspended",False) or not bookmaker_active),"raw_markets":len(raw_markets),"recognized_markets":sorted(recognized_markets),"canonical_selections":selections,"market_mapping_version":VERSION,"fixture_line_contract_version":STRICT_FIXTURE_LINE_VERSION,"suppressed_line_selections_without_fixture_evidence":suppressed_without_fixture_line}



def _direct_selection_without_price(row: dict) -> dict | None:
    """Project a Direct sidecar selection into the canonical price-free contract."""
    if not isinstance(row, dict) or row.get("prices_used") is not False:
        return None
    market = str(row.get("market") or "").strip()
    pick = row.get("pick")
    if not market or pick in {None, ""}:
        return None

    line_markets = set(mapping.LINE_MARKETS) | set(NEW_LINE_MARKETS)
    line = row.get("line")
    if market in line_markets:
        if (
            line is None
            or row.get("operator_line_verified") is not True
            or row.get("fixture_line_verified") is not True
        ):
            return None

    out = {
        "market": market,
        "pick": pick,
        "line": line,
        "checkpoint": row.get("checkpoint"),
        "player": row.get("player"),
        "set_no": row.get("set_no"),
        "market_name": row.get("operator_market_name") or row.get("raw_label"),
        "market_id": (
            str(row.get("operator_market_id"))
            if row.get("operator_market_id") is not None
            else None
        ),
        "outcome_id": (
            str(row.get("operator_outcome_id"))
            if row.get("operator_outcome_id") is not None
            else None
        ),
        "main_line": False,
        "operator_available": row.get("operator_available") is not False,
        "operator_line_verified": row.get("operator_line_verified") is True,
        "fixture_line_verified": row.get("fixture_line_verified") is True,
        "operator_line_source": DIRECT_SOURCE,
        "operator_offer_source": DIRECT_SOURCE,
        "direct_source": True,
        "prices_used": False,
    }
    if not out["operator_available"]:
        return None
    return out


def _safe_direct_source_rows(row: dict) -> tuple[list[dict], int]:
    """Suppress malformed Direct handicap variants before canonical projection."""
    raw_rows = [
        item for item in (row.get("canonical_selections") or [])
        if isinstance(item, dict)
    ]
    safe = [
        item for item in raw_rows
        if str(item.get("market") or "") not in DIRECT_HANDICAP_MARKETS
    ]
    groups: dict[tuple, list[dict]] = {}
    for item in raw_rows:
        market = str(item.get("market") or "")
        if market not in DIRECT_HANDICAP_MARKETS:
            continue
        specifiers = (
            item.get("operator_specifiers")
            if isinstance(item.get("operator_specifiers"), dict)
            else {}
        )
        variant = item.get("operator_special_bet_value")
        if variant in {None, ""}:
            variant = specifiers.get("hcp")
        key = (
            market,
            str(item.get("operator_market_id") or ""),
            str(variant or ""),
            int(item.get("set_no") or 0),
        )
        groups.setdefault(key, []).append(item)

    p1_key = base._name_key(row.get("p1"))
    p2_key = base._name_key(row.get("p2"))
    suppressed = 0
    for items in groups.values():
        by_player = {}
        for item in items:
            player_key = base._name_key(item.get("player") or item.get("pick"))
            if player_key:
                by_player[player_key] = item
        p1_row = by_player.get(p1_key)
        p2_row = by_player.get(p2_key)
        p1_line = base._line(p1_row.get("line")) if p1_row else None
        p2_line = base._line(p2_row.get("line")) if p2_row else None
        mirrored = (
            p1_line is not None
            and p2_line is not None
            and abs(float(p1_line) + float(p2_line)) <= 1e-9
        )
        if not mirrored:
            suppressed += 1
            continue
        safe.extend(items)
    return safe, suppressed


def _direct_fixture_from_sidecar(row: dict) -> dict | None:
    if not isinstance(row, dict):
        return None
    if row.get("direct_match_verified") is not True or row.get("prices_used") is not False:
        return None
    event_id = str(row.get("event_id") or "").strip()
    p1 = str(row.get("p1") or "").strip()
    p2 = str(row.get("p2") or "").strip()
    start_time = row.get("operator_start_time") or row.get("scheduled_time")
    if not event_id or not p1 or not p2 or not start_time:
        return None

    source_rows, suppressed_handicap_variants = _safe_direct_source_rows(row)
    selections = []
    for raw in source_rows:
        item = _direct_selection_without_price(raw)
        if item is not None:
            selections.append(item)
    if not selections:
        return None

    dedup = {}
    for selection in selections:
        sig = (
            selection.get("market"),
            base._norm(selection.get("pick")),
            base._line(selection.get("line")),
            int(selection.get("checkpoint") or 0),
            base._name_key(selection.get("player")),
            int(selection.get("set_no") or 0),
        )
        dedup.setdefault(sig, selection)
    selections = list(dedup.values())
    return {
        "fixture_id": event_id,
        "p1": p1,
        "p2": p2,
        "start_time": start_time,
        "tournament": None,
        "tournament_id": None,
        "bookmaker": base.BOOKMAKER,
        "bookmaker_active": True,
        "suspended": False,
        "raw_markets": len(row.get("market_counts") or {}),
        "recognized_markets": sorted({
            str(selection.get("market") or "")
            for selection in selections
            if selection.get("market")
        }),
        "canonical_selections": selections,
        "operator_offer_source": DIRECT_SOURCE,
        "direct_source": True,
        "direct_handicap_semantics_guard": True,
        "suppressed_direct_handicap_variants": suppressed_handicap_variants,
        "prices_used": False,
    }


def _overlay_direct_fallback(results: list[dict], availability: dict, now=None) -> dict:
    """Add fresh Direct fixtures only where current canonical provider has no safe match."""
    now = now or datetime.now(timezone.utc)
    availability = dict(availability) if isinstance(availability, dict) else {}
    diagnostic = {
        "mode": "CURRENT_PROVIDER_FIRST_DIRECT_FALLBACK",
        "sidecar_status": "UNAVAILABLE",
        "sidecar_generated_at": None,
        "sidecar_age_hours": None,
        "sidecar_matches_seen": 0,
        "fallback_fixtures_added": 0,
        "existing_provider_preferred": 0,
        "unsafe_sidecar_matches_rejected": 0,
        "suppressed_direct_handicap_variants": 0,
        "prices_in_canonical_availability": False,
        "prices_used": False,
        "canonical_context_activation": False,
        "downstream_playable_eligibility": False,
        "model_math_unchanged": True,
        "policy": "CURRENT_ODDSPAPI_FIXTURE_FIRST; DIRECT_ONLY_WHEN_NO_SAFE_CURRENT_FIXTURE",
    }

    sidecar = base._read(DIRECT_SIDECAR, {})
    if not isinstance(sidecar, dict):
        availability["direct_fallback"] = diagnostic
        return availability
    diagnostic["sidecar_status"] = sidecar.get("status")
    diagnostic["sidecar_generated_at"] = sidecar.get("generated_at")

    generated = base._parse_dt(sidecar.get("generated_at"))
    age_hours = (
        (now - generated).total_seconds() / 3600
        if generated is not None
        else None
    )
    diagnostic["sidecar_age_hours"] = (
        round(float(age_hours), 3) if age_hours is not None else None
    )
    if (
        sidecar.get("status") != "OK"
        or sidecar.get("prices_used") is not False
        or sidecar.get("production_influence") is not False
        or sidecar.get("playable_influence") is not False
        or sidecar.get("writes_canonical_context") is not False
        or age_hours is None
        or age_hours < 0
        or age_hours > DIRECT_MAX_AGE_HOURS
    ):
        availability["direct_fallback"] = diagnostic
        return availability

    fixtures = [
        dict(row)
        for row in (availability.get("fixtures") or [])
        if isinstance(row, dict)
    ]
    app_matches = [
        row for row in results
        if isinstance(row, dict)
        and row.get("p1")
        and row.get("p2")
        and row.get("scheduled_time")
    ]
    sidecar_matches = [
        row for row in (sidecar.get("matches") or [])
        if isinstance(row, dict)
    ]
    diagnostic["sidecar_matches_seen"] = len(sidecar_matches)

    for sidecar_match in sidecar_matches:
        direct_fixture = _direct_fixture_from_sidecar(sidecar_match)
        if direct_fixture is None:
            diagnostic["unsafe_sidecar_matches_rejected"] += 1
            continue

        app_match = next(
            (
                match
                for match in app_matches
                if fixture_matching.select_cached_fixture(match, [direct_fixture])
                is not None
            ),
            None,
        )
        if app_match is None:
            diagnostic["unsafe_sidecar_matches_rejected"] += 1
            continue

        existing = fixture_matching.select_cached_fixture(app_match, fixtures)
        if existing is not None:
            diagnostic["existing_provider_preferred"] += 1
            continue

        oriented = fixture_matching.select_cached_fixture(app_match, [direct_fixture])
        if oriented is None:
            diagnostic["unsafe_sidecar_matches_rejected"] += 1
            continue
        fixtures.append(dict(oriented))
        diagnostic["fallback_fixtures_added"] += 1
        diagnostic["suppressed_direct_handicap_variants"] += int(
            oriented.get("suppressed_direct_handicap_variants") or 0
        )

    if diagnostic["fallback_fixtures_added"] > 0:
        diagnostic["canonical_context_activation"] = True
        diagnostic["downstream_playable_eligibility"] = True
    availability["fixtures"] = fixtures
    availability["direct_fallback"] = diagnostic
    availability["operator_source_policy"] = (
        "CURRENT_ODDSPAPI_FIXTURE_FIRST_DIRECT_FALLBACK"
    )
    availability["contains_prices"] = False
    availability["prices_used"] = False
    return availability


@contextmanager
def _patched_runtime():
    old_line=set(mapping.LINE_MARKETS);old_handicap=set(mapping.HANDICAP_MARKETS);old_winner=set(mapping.WINNER_MARKETS);old_canonical=base.canonical_market;old_pick=mapping._selection_pick;old_sanitize=mapping._sanitize_fixture;old_best_fixture=base._best_fixture_for_match;old_best_cached=base._best_cached_fixture;old_availability_due=base._availability_due;old_refresh=base.refresh_availability
    fixture_matching.reset_telemetry()

    def refresh_with_direct(results, now=None):
        availability = old_refresh(results, now)
        merged = _overlay_direct_fallback(results, availability, now=now)
        if merged != availability:
            base._write(base.AVAILABILITY, merged)
        return merged

    try:
        base.canonical_market=canonical_market;mapping._selection_pick=selection_pick;mapping._sanitize_fixture=mapped_sanitize;base._best_fixture_for_match=fixture_matching.best_fixture_for_match;base._best_cached_fixture=fixture_matching.best_cached_fixture;base._availability_due=lambda previous,now:fixture_matching.availability_due(old_availability_due,previous,now);base.refresh_availability=refresh_with_direct;mapping.LINE_MARKETS.update(NEW_LINE_MARKETS);mapping.HANDICAP_MARKETS.update(NEW_HANDICAP_MARKETS);mapping.WINNER_MARKETS.update(NEW_HANDICAP_MARKETS);yield
    finally:
        base.canonical_market=old_canonical;mapping._selection_pick=old_pick;mapping._sanitize_fixture=old_sanitize;base._best_fixture_for_match=old_best_fixture;base._best_cached_fixture=old_best_cached;base._availability_due=old_availability_due;base.refresh_availability=old_refresh;mapping.LINE_MARKETS.clear();mapping.LINE_MARKETS.update(old_line);mapping.HANDICAP_MARKETS.clear();mapping.HANDICAP_MARKETS.update(old_handicap);mapping.WINNER_MARKETS.clear();mapping.WINNER_MARKETS.update(old_winner)


def _stamp_alias() -> dict:
    availability=base._read(base.AVAILABILITY,{})
    if not isinstance(availability,dict):return {}
    availability=dict(availability);audit=dict(availability.get("raw_family_audit_v923") or {})
    if audit:
        audit["version"]=VERSION;availability["raw_family_audit_v924"]=audit
    availability["market_mapping_version"]=VERSION;availability["runtime_adapter_version"]=VERSION;availability["fixture_discovery_contract"]={"bookmaker_neutral":True,"has_odds_filter":False,"bookmaker_filter":False,"operator_offer_checked_later":True};availability["fixture_line_contract"]={"version":STRICT_FIXTURE_LINE_VERSION,"current_fixture_evidence_required":True,"active_fixture_market_id_metadata_allowed":True,"catalogue_fallback_allowed":False,"model_line_fallback_allowed":False,"nearest_line_fallback_allowed":False,"prices_used":False};base._write(base.AVAILABILITY,availability);return audit


def prepare() -> dict:
    with _patched_runtime():
        result=dict(audit_runtime.prepare(STRICT_FIXTURE_LINE_VERSION)); audit=_stamp_alias(); matching=fixture_matching.stamp_availability()
    availability = base._read(base.AVAILABILITY, {})
    direct = availability.get("direct_fallback") if isinstance(availability, dict) else {}
    direct = direct if isinstance(direct, dict) else {}
    result["market_mapping_version"]=VERSION;result["fixture_line_contract_version"]=STRICT_FIXTURE_LINE_VERSION;result["raw_family_audit_v924"]=audit;result["fixture_matching_v927"]=matching;result["additional_external_requests"]=0
    result["operator_source_policy"] = availability.get("operator_source_policy") if isinstance(availability, dict) else None
    result["direct_fallback_fixtures_added"] = int(direct.get("fallback_fixtures_added") or 0)
    result["direct_existing_provider_preferred"] = int(direct.get("existing_provider_preferred") or 0)
    result["direct_canonical_context_activation"] = direct.get("canonical_context_activation") is True
    result["direct_downstream_playable_eligibility"] = direct.get("downstream_playable_eligibility") is True
    result["direct_prices_used"] = direct.get("prices_used")
    return result


def finalize() -> dict:
    with _patched_runtime():
        result=dict(audit_runtime.finalize(STRICT_FIXTURE_LINE_VERSION));audit=_stamp_alias()
    result["market_mapping_version"]=VERSION;result["fixture_line_contract_version"]=STRICT_FIXTURE_LINE_VERSION;result["raw_family_audit_v924"]=audit;result["additional_external_requests"]=0;return result


def main() -> None:
    mode=str(sys.argv[1] if len(sys.argv)>1 else "prepare").strip().casefold()
    if mode=="prepare":result=prepare()
    elif mode=="finalize":result=finalize()
    else:raise SystemExit("usage: superbet_market_context.py [prepare|finalize]")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
