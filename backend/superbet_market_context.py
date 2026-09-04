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


@contextmanager
def _patched_runtime():
    old_line=set(mapping.LINE_MARKETS);old_handicap=set(mapping.HANDICAP_MARKETS);old_winner=set(mapping.WINNER_MARKETS);old_canonical=base.canonical_market;old_pick=mapping._selection_pick;old_sanitize=mapping._sanitize_fixture;old_best_fixture=base._best_fixture_for_match;old_best_cached=base._best_cached_fixture;old_availability_due=base._availability_due;old_fixture_horizon_days=base.FIXTURE_HORIZON_DAYS
    fixture_matching.reset_telemetry()
    try:
        base.canonical_market=canonical_market;mapping._selection_pick=selection_pick;mapping._sanitize_fixture=mapped_sanitize;base._best_fixture_for_match=fixture_matching.best_fixture_for_match;base._best_cached_fixture=fixture_matching.best_cached_fixture;base._availability_due=lambda previous,now:fixture_matching.availability_due(old_availability_due,previous,now);base.FIXTURE_HORIZON_DAYS=1;mapping.LINE_MARKETS.update(NEW_LINE_MARKETS);mapping.HANDICAP_MARKETS.update(NEW_HANDICAP_MARKETS);mapping.WINNER_MARKETS.update(NEW_HANDICAP_MARKETS);yield
    finally:
        base.canonical_market=old_canonical;mapping._selection_pick=old_pick;mapping._sanitize_fixture=old_sanitize;base._best_fixture_for_match=old_best_fixture;base._best_cached_fixture=old_best_cached;base._availability_due=old_availability_due;base.FIXTURE_HORIZON_DAYS=old_fixture_horizon_days;mapping.LINE_MARKETS.clear();mapping.LINE_MARKETS.update(old_line);mapping.HANDICAP_MARKETS.clear();mapping.HANDICAP_MARKETS.update(old_handicap);mapping.WINNER_MARKETS.clear();mapping.WINNER_MARKETS.update(old_winner)


def _stamp_alias() -> dict:
    availability=base._read(base.AVAILABILITY,{})
    if not isinstance(availability,dict):return {}
    availability=dict(availability);audit=dict(availability.get("raw_family_audit_v923") or {})
    if audit:
        audit["version"]=VERSION;availability["raw_family_audit_v924"]=audit
    availability["market_mapping_version"]=VERSION;availability["runtime_adapter_version"]=VERSION;availability["fixture_line_contract"]={"version":STRICT_FIXTURE_LINE_VERSION,"current_fixture_evidence_required":True,"active_fixture_market_id_metadata_allowed":True,"catalogue_fallback_allowed":False,"model_line_fallback_allowed":False,"nearest_line_fallback_allowed":False,"prices_used":False};base._write(base.AVAILABILITY,availability);return audit


def prepare() -> dict:
    with _patched_runtime():
        result=dict(audit_runtime.prepare(STRICT_FIXTURE_LINE_VERSION)); audit=_stamp_alias(); matching=fixture_matching.stamp_availability()
    result["market_mapping_version"]=VERSION;result["fixture_line_contract_version"]=STRICT_FIXTURE_LINE_VERSION;result["raw_family_audit_v924"]=audit;result["fixture_matching_v927"]=matching;result["additional_external_requests"]=0;return result


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
