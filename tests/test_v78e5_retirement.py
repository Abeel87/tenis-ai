from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from live_history_settle import final_from_match, settle_entry, settle_signal_live

def _entry():
    return {"p1":"Player A","p2":"Player B","status":"pending","signals":[],"shadow_signals":[]}

def test_retirement_keeps_completed_set_and_voids_match_markets():
    final=final_from_match({"winner":1,"event_status":"Retired","score":{"games":[[6,1],[4,4]]}},_entry())
    assert final["status"]=="retired"
    assert final["winner"]=="Player A"
    assert final["sets"]==[[6,4],[1,4]]
    assert final["completed_sets"]==[True,False]
    assert settle_signal_live({"market":"set1_winner","pick":"Player A"},final)=="hit"
    assert settle_signal_live({"market":"set1_total","pick":"over","line":8.5},final)=="hit"
    assert settle_signal_live({"market":"exact_set1","pick":"6:4"},final)=="hit"
    assert settle_signal_live({"market":"set2_winner","pick":"Player B"},final)=="void"
    assert settle_signal_live({"market":"match_winner","pick":"Player A"},final)=="void"
    assert settle_signal_live({"market":"match_total","pick":"under","line":22.5},final)=="void"

def test_retirement_entry_is_settled_not_whole_match_void():
    e=_entry()
    e["signals"]=[{"market":"set1_total","pick":"over","line":8.5,"result":"pending"}]
    e["shadow_signals"]=[{"market":"set1_winner","pick":"Player A","result":"pending"}]
    final=final_from_match({"winner":1,"event_status":"Retired","score":{"games":[[6,1],[4,4]]}},e)
    settled=settle_entry(e,final,datetime(2026,8,22,8,0,tzinfo=timezone.utc))
    assert settled["status"]=="settled"
    assert settled["result"]["status"]=="retired"
    assert settled["signals"][0]["result"]=="hit"
    assert settled["shadow_signals"][0]["result"]=="hit"

def test_completed_set_line_push_and_invalid_pick_after_later_retirement():
    final = {"status":"retired", "sets":[[6,4],[1,4]], "completed_sets":[True,False]}
    for pick in ("over", "under"):
        assert settle_signal_live({"market":"set1_total","pick":pick,"line":10},final)=="void"
    assert settle_signal_live({"market":"set1_total","pick":"unknown","line":12.5},final)=="unverifiable"
