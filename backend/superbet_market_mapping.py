from __future__ import annotations

"""Stable bounded OddsPapi batching + canonical Superbet line mapping.

Preserves the validated v9.1.5 behavior behind a non-versioned production
module. Prices remain discarded and model mathematics/training are untouched.
"""

import json
import sys
import time
from collections.abc import Callable

try:
    from . import superbet_market_core as base
except ImportError:
    import superbet_market_core as base

VERSION = "v9.1.5"
MAX_TOURNAMENT_IDS_PER_REQUEST = 5
BATCH_DELAY_SECONDS = 1.05
REFRESH_HOURS = 1
MONTHLY_REQUEST_CAP = 4000

LINE_MARKETS = {
    "match_total", "set1_total", "set2_total", "set3_total", "total_sets",
    "player_total_games", "match_total_aces", "match_game_handicap",
    "set1_game_handicap", "set2_game_handicap",
}
HANDICAP_MARKETS = {"match_game_handicap", "set1_game_handicap", "set2_game_handicap"}
WINNER_MARKETS = {
    "match_winner", "set1_winner", "set2_winner", "set3_winner", "most_aces",
    *HANDICAP_MARKETS,
}


def _tournament_ids(value) -> list[str]:
    if value is None:
        return []
    raw = value if isinstance(value, (list, tuple, set)) else str(value).split(",")
    out: list[str] = []
    seen = set()
    for item in raw:
        token = str(item or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _chunks(values: list[str], size: int = MAX_TOURNAMENT_IDS_PER_REQUEST):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def batched_request(original_request: Callable, path: str, api_key: str, quota: dict, **params):
    ids = _tournament_ids(params.get("tournamentIds"))
    if path != "odds-by-tournaments" or len(ids) <= MAX_TOURNAMENT_IDS_PER_REQUEST:
        return original_request(path, api_key, quota, **params)
    rows: list[dict] = []
    for batch_no, chunk in enumerate(_chunks(ids)):
        if batch_no:
            time.sleep(BATCH_DELAY_SECONDS)
        batch_params = dict(params)
        batch_params["tournamentIds"] = ",".join(chunk)
        payload = original_request(path, api_key, quota, **batch_params)
        rows.extend(base._flatten_payload(payload))
    return rows


def _winner_pick(outcome_name, bookmaker_outcome_id, p1, p2):
    outcome = base._norm(outcome_name)
    if outcome in {"1", "p1", "participant 1", "player 1"}: return p1
    if outcome in {"2", "p2", "participant 2", "player 2"}: return p2
    if outcome in {"x", "draw", "tie"}: return "draw"
    bookmaker = base._norm(bookmaker_outcome_id)
    if bookmaker in {"1", "p1", "participant 1", "player 1", "home"}: return p1
    if bookmaker in {"2", "p2", "participant 2", "player 2", "away"}: return p2
    if bookmaker in {"x", "draw", "tie"}: return "draw"
    n1, n2 = base._norm(p1), base._norm(p2)
    if n1 and (n1 in outcome or n1 in bookmaker): return p1
    if n2 and (n2 in outcome or n2 in bookmaker): return p2
    return str(outcome_name or bookmaker_outcome_id or "").strip() or None


def _selection_pick(market, outcome_name, bookmaker_outcome_id, p1, p2):
    if market in WINNER_MARKETS:
        return _winner_pick(outcome_name, bookmaker_outcome_id, p1, p2)
    return base._selection_pick(market, outcome_name, bookmaker_outcome_id, p1, p2)


def _handicap_side(outcome_name, bookmaker_outcome_id, pick, p1, p2):
    outcome = base._norm(outcome_name)
    if outcome in {"1", "p1", "participant 1", "player 1", "home"}: return "p1"
    if outcome in {"2", "p2", "participant 2", "player 2", "away"}: return "p2"
    bookmaker = base._norm(bookmaker_outcome_id)
    if bookmaker in {"1", "p1", "participant 1", "player 1", "home"}: return "p1"
    if bookmaker in {"2", "p2", "participant 2", "player 2", "away"}: return "p2"
    pick_norm = base._name_key(pick)
    if pick_norm and pick_norm == base._name_key(p1): return "p1"
    if pick_norm and pick_norm == base._name_key(p2): return "p2"
    return None


def _market_line(market: str, market_meta: dict, outcome_name, bookmaker_outcome_id, *, pick=None, p1=None, p2=None):
    if market not in LINE_MARKETS:
        return None, None
    catalogue_line = base._line(market_meta.get("handicap"))
    if catalogue_line is not None:
        if market in HANDICAP_MARKETS:
            side = _handicap_side(outcome_name, bookmaker_outcome_id, pick, p1, p2)
            if side == "p2": catalogue_line = -catalogue_line
        return catalogue_line, "oddspapi_market_handicap"
    text_line = base._line_from_text(bookmaker_outcome_id, outcome_name)
    if text_line is not None:
        return text_line, "bookmaker_outcome_id"
    return None, None


def _sanitize_fixture(row: dict, meta: dict):
    bookmaker_odds = row.get("bookmakerOdds") or {}
    book = bookmaker_odds.get(base.BOOKMAKER)
    if not isinstance(book, dict):
        book = next((value for key, value in bookmaker_odds.items() if "superbet" in str(key).casefold() and isinstance(value, dict)), None)
    if not isinstance(book, dict): return None
    raw_markets = book.get("markets") or {}
    if not isinstance(raw_markets, dict): return None
    p1 = str(row.get("participant1Name") or ""); p2 = str(row.get("participant2Name") or "")
    selections = []; recognized_markets = set()
    for market_id, market_data in raw_markets.items():
        if not isinstance(market_data, dict) or market_data.get("marketActive") is False: continue
        market_meta = meta.get(str(market_id), {})
        market_name = str(market_meta.get("marketName") or f"market {market_id}")
        canonical, checkpoint, player_side = base.canonical_market(market_name)
        if not canonical: continue
        recognized_markets.add(canonical)
        for outcome_id, outcome_data in (market_data.get("outcomes") or {}).items():
            if not isinstance(outcome_data, dict): continue
            outcome_meta = (market_meta.get("outcomes") or {}).get(str(outcome_id), {})
            outcome_name = outcome_meta.get("outcomeName") or outcome_meta.get("outcomeNameShort")
            for player_data in (outcome_data.get("players") or {}).values():
                if not isinstance(player_data, dict) or player_data.get("active") is False: continue
                boid = player_data.get("bookmakerOutcomeId")
                pick = _selection_pick(canonical, outcome_name, boid, p1, p2)
                line, line_source = _market_line(canonical, market_meta, outcome_name, boid, pick=pick, p1=p1, p2=p2)
                if canonical in LINE_MARKETS and line is None: continue
                if canonical in {"match_total","set1_total","set2_total","set3_total","total_sets","player_total_games","match_total_aces"} and pick not in {"over","under"}: continue
                if canonical in {"set1_exact_score","exact_match_score","game_state"} and not pick: continue
                player = p1 if player_side == "p1" else p2 if player_side == "p2" else player_data.get("playerName")
                selection = {"market":canonical,"pick":pick,"line":line,"checkpoint":checkpoint,"player":player,"market_name":market_name,"market_id":str(market_id),"outcome_id":str(outcome_id),"main_line":bool(player_data.get("mainLine",False)),"operator_available":True,"operator_line_verified":True}
                if line_source: selection["operator_line_source"] = line_source
                selections.append(selection)
    dedup = {}
    for selection in selections:
        sig=(selection.get("market"),base._norm(selection.get("pick")),base._line(selection.get("line")),int(selection.get("checkpoint") or 0),base._name_key(selection.get("player")))
        if sig not in dedup or selection.get("main_line"): dedup[sig]=selection
    selections=sorted(dedup.values(),key=lambda selection:(str(selection.get("market")),float(selection.get("line") or -999),str(selection.get("pick"))))
    return {"fixture_id":row.get("fixtureId"),"p1":p1,"p2":p2,"start_time":row.get("startTime"),"tournament":row.get("tournamentName"),"tournament_id":row.get("tournamentId"),"bookmaker":base.BOOKMAKER,"bookmaker_active":bool(book.get("bookmakerIsActive",True)),"suspended":bool(book.get("suspended",False)),"raw_markets":len(raw_markets),"recognized_markets":sorted(recognized_markets),"canonical_selections":selections}


def _stamp_runtime_adapter() -> None:
    availability = base._read(base.AVAILABILITY, {})
    if not isinstance(availability, dict): return
    availability = dict(availability)
    availability["runtime_adapter_version"] = VERSION
    availability["tournament_batch_limit"] = MAX_TOURNAMENT_IDS_PER_REQUEST
    availability["refresh_hours"] = REFRESH_HOURS
    quota = availability.get("quota_guard")
    if isinstance(quota, dict):
        quota = dict(quota); quota["monthly_cap"] = MONTHLY_REQUEST_CAP; availability["quota_guard"] = quota
    base._write(base.AVAILABILITY, availability)


def prepare() -> dict:
    original_request=base._request; original_sanitize_fixture=base._sanitize_fixture; original_availability_due=base._availability_due; original_refresh_hours=base.REFRESH_HOURS; original_monthly_cap=base.MONTHLY_REQUEST_CAP
    previous=base._read(base.AVAILABILITY, {}); force_parser_refresh=not isinstance(previous,dict) or previous.get("runtime_adapter_version") != VERSION
    def request(path: str, api_key: str, quota: dict, **params): return batched_request(original_request,path,api_key,quota,**params)
    base._request=request; base._sanitize_fixture=_sanitize_fixture
    if force_parser_refresh: base._availability_due=lambda _previous,_now: True
    base.REFRESH_HOURS=REFRESH_HOURS; base.MONTHLY_REQUEST_CAP=MONTHLY_REQUEST_CAP
    try: result=dict(base.prepare())
    finally:
        base._request=original_request; base._sanitize_fixture=original_sanitize_fixture; base._availability_due=original_availability_due; base.REFRESH_HOURS=original_refresh_hours; base.MONTHLY_REQUEST_CAP=original_monthly_cap
    _stamp_runtime_adapter(); result["runtime_adapter_version"]=VERSION; result["tournament_batch_limit"]=MAX_TOURNAMENT_IDS_PER_REQUEST; result["refresh_hours"]=REFRESH_HOURS; result["monthly_request_cap"]=MONTHLY_REQUEST_CAP; result["parser_refresh_forced"]=force_parser_refresh; return result


def finalize() -> dict:
    result=dict(base.finalize()); result["runtime_adapter_version"]=VERSION; return result


def main() -> None:
    mode=str(sys.argv[1] if len(sys.argv)>1 else "prepare").strip().casefold()
    if mode=="prepare": result=prepare()
    elif mode=="finalize": result=finalize()
    else: raise SystemExit("usage: superbet_market_mapping.py [prepare|finalize]")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
