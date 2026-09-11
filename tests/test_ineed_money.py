from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import ineed_money as m

CFG = {
    "stake_tax_rate": .12, "high_win_tax_rate": .10, "high_win_tax_threshold_pln": 2280, "high_win_tax_trigger": "above",
    "minimum_stake": 2, "stake_rounding": .01, "fractional_kelly": .25,
    "max_single_bet_pct": .03, "max_match_exposure_pct": .03, "max_player_exposure_pct": .03,
    "max_market_exposure_pct": .15, "max_total_exposure_pct": .15, "minimum_net_ev": .05, "minimum_edge_pp": 4,
    "minimum_odds": 1.01, "maximum_odds": None, "odds_max_age_minutes": 108,
    "drawdown": {"caution": .1, "defensive": .2, "halted": .3},
    "risk_profiles": {"NORMAL":{"stake_multiplier":1,"exposure_multiplier":1,"minimum_net_ev":.05,"minimum_edge_pp":4},
                      "CAUTION":{"stake_multiplier":.67,"exposure_multiplier":.67,"minimum_net_ev":.07,"minimum_edge_pp":5},
                      "DEFENSIVE":{"stake_multiplier":.33,"exposure_multiplier":.33,"minimum_net_ev":.10,"minimum_edge_pp":6},
                      "HALTED":{"stake_multiplier":0,"exposure_multiplier":0,"minimum_net_ev":1,"minimum_edge_pp":100}},
    "version":"test"
}

def signal(p=70):
    return {"market":"match_winner","pick":"A","operator_model_probability":p,"learning_reliability":.9,"fixture_line_verified":True}

def result(sig=None):
    return [{"match_id":"1","p1":"A","p2":"B","symphony2_playable":{"playable":True,"final_playable_authority":True,"authority":m.FINAL_AUTHORITY,"operator":m.OPERATOR,"signals":[sig or signal()]}}]

def direct(ts=None, odds=2.0):
    ts = ts or datetime.now(timezone.utc).isoformat()
    return {"operator":m.OPERATOR,"status":"OK","generated_at":ts,"matches":[{"match_id":"1","p1":"A","p2":"B","direct_match_verified":True,"canonical_selections":[
        {"market":"match_winner","pick":"A","operator_available":True,"operator_price_verified":True,"operator_price":odds,"operator_selection_status":"active"},
        {"market":"match_winner","pick":"B","operator_available":True,"operator_price_verified":True,"operator_price":2.0,"operator_selection_status":"active"}]}]}

def state(open_bets=None, equity=200, peak=200):
    return {"experiment":{"starting_bankroll":200},"available_capital":equity-sum(float(x.get("stake") or 0) for x in (open_bets or [])),"active_exposure":0,"bankroll_equity":equity,"peak_bankroll":peak,"open_bets":open_bets or []}

def test_tax_economics():
    e=m.economics(70,2.0,CFG,[],1)
    assert round(e["effective_odds_after_tax"],2)==1.76
    assert round(e["expected_value_net"],3)==.232

def test_final_playable_qualifies():
    rows=m.evaluate(result(),direct(),CFG,state())
    assert rows[0]["status"]=="QUALIFIED"
    assert rows[0]["final_stake"]>=2

def test_non_final_ignored():
    r=result(); r[0]["symphony2_playable"]["authority"]="WRONG"
    assert m.evaluate(r,direct(),CFG,state())==[]

def test_stale_odds_expire():
    ts=(datetime.now(timezone.utc)-timedelta(hours=4)).isoformat()
    rows=m.evaluate(result(),direct(ts),CFG,state())
    assert rows[0]["status"]=="EXPIRED" and rows[0]["reason_code"]=="STALE_ODDS"

def test_drawdown_states():
    assert m.risk_state(95,100,CFG)[0]=="NORMAL"
    assert m.risk_state(89,100,CFG)[0]=="CAUTION"
    assert m.risk_state(79,100,CFG)[0]=="DEFENSIVE"
    assert m.risk_state(69,100,CFG)[0]=="HALTED"

def test_missing_quote_rejected():
    d=direct(); d["matches"][0]["canonical_selections"]=[]
    assert m.evaluate(result(),d,CFG,state())[0]["reason_code"]=="MARKET_NOT_AVAILABLE"

def test_low_odds_break_even_can_exceed_one():
    e=m.economics(80,1.05,CFG,[],1)
    assert e["break_even_probability"]>1

def test_match_exposure_guard():
    bet={"status":"PENDING","stake":6,"match_id":"1","market":"set1_total","placement_snapshot":{"p1":"X","p2":"Y"}}
    rows=m.evaluate(result(),direct(),CFG,state([bet]))
    assert rows[0]["reason_code"] in {"MATCH_EXPOSURE_LIMIT","STAKE_BELOW_MINIMUM"}

def test_player_correlation_guard():
    bet={"status":"PENDING","stake":6,"match_id":"other","market":"x","placement_snapshot":{"p1":"A","p2":"C"}}
    rows=m.evaluate(result(),direct(),CFG,state([bet]))
    assert rows[0]["reason_code"]=="CORRELATION_LIMIT"

def test_high_win_tax():
    assert m.payout_after_taxes(2000,2,CFG) < 2000*.88*2

def test_fingerprint_stable():
    a=m._stable_fingerprint("1",signal()); b=m._stable_fingerprint("1",signal())
    assert a==b
