from datetime import datetime, timezone

from backend.game_state_tracking_v84e1 import (
    CHECKPOINTS,
    checkpoint_from_signal,
    current_signals,
    select_tracking_signals,
    settle_from_states,
)

def sample_match():
    return {
        "id": 1,
        "model_ready": True,
        "p1": "A",
        "p2": "B",
        "scheduled_time": "2026-08-25T12:00:00Z",
        "tournament": "Test",
        "tour": "atp",
        "surface": "hard",
        "quality": "HIGH",
        "model_confidence": 80,
        "game_states": {
            "2": {"1:1": 61.0, "2:0": 22.0, "0:2": 17.0},
            "4": {"2:2": 43.0, "3:1": 31.0, "1:3": 26.0},
            "6": {"3:3": 34.0, "4:2": 33.0, "2:4": 33.0},
        },
    }

def test_exact_current_signals_for_2_4_6():
    rows=current_signals(sample_match())
    assert [x["checkpoint"] for x in rows] == list(CHECKPOINTS)
    assert [x["key"] for x in rows] == [
        "state|2|1:1","state|4|2:2","state|6|3:3"
    ]

def test_state_alias_checkpoint_parser_is_strict():
    assert checkpoint_from_signal({"key":"state|2|1:1"}) == 2
    assert checkpoint_from_signal({"key":"game_state|4|2:2"}) == 4
    assert checkpoint_from_signal({"key":"state_6|3:3"}) == 6
    assert checkpoint_from_signal({"key":"state|3|2:1"}) is None

def test_bounded_tracking_reserves_states_even_below_55():
    normal=[
        {"key":f"normal|{i}","market":"set1_total","ensemble":90-i}
        for i in range(20)
    ]
    states=[
        {"key":"state|2|1:1","market":"game_state","checkpoint":2,"pick":"1:1","ensemble":54},
        {"key":"state|4|2:2","market":"game_state","checkpoint":4,"pick":"2:2","ensemble":43},
        {"key":"state|6|3:3","market":"game_state","checkpoint":6,"pick":"3:3","ensemble":34},
    ]
    picked=select_tracking_signals(normal+states,12)
    keys={x["key"] for x in picked}
    assert len(picked)==12
    assert {"state|2|1:1","state|4|2:2","state|6|3:3"} <= keys

def test_real_pbp_settlement_is_exact():
    states={"2":"1:1","4":"3:1","6":"3:3"}
    assert settle_from_states(
        {"key":"state|2|1:1","market":"game_state","pick":"1:1"},states
    )=="hit"
    assert settle_from_states(
        {"key":"state|4|2:2","market":"game_state","pick":"2:2"},states
    )=="miss"
    assert settle_from_states(
        {"key":"state|3|2:1","market":"game_state","pick":"2:1"},states
    ) is None

def test_autolearn_current_sources_receive_game_states():
    from backend import autolearn_v84 as a
    grouped=a._current_sources(sample_match())
    assert "state|2|1:1" in grouped
    row=a._feature_row(
        {
            "match_id":1,"id":1,"p1":"A","p2":"B",
            "scheduled_time":"2026-08-25T12:00:00Z",
            "tournament":"Test","tour":"atp","surface":"hard",
            "quality":"HIGH","model_confidence":80,
        },
        "state|2|1:1",
        grouped["state|2|1:1"],
        None,
    )
    assert row["market"]=="game_state"
    assert row["checkpoint"]==2

def test_pbp_upgrades_hidden_and_autolearn_lists(monkeypatch):
    import sys
    from pathlib import Path
    backend_dir = str(Path(__file__).resolve().parents[1] / "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    import pbp_tracker as p
    entry={
        "match_id":1,"p1":"A","p2":"B","signals":[],
        "game_state_learning_v84e1":[
            {"key":"state|2|1:1","market":"game_state","pick":"1:1",
             "checkpoint":2,"result":"unverifiable"}
        ],
        "autolearn_signals_v84":[
            {"key":"state|4|2:2","market":"game_state","pick":"2:2",
             "checkpoint":4,"result":"unverifiable"}
        ],
    }
    monkeypatch.setattr(p,"_read_gz",lambda path: {"cached":True})
    monkeypatch.setattr(
        p,"actual_from_tape",
        lambda payload,e: {"states":{"2":"1:1","4":"3:1","6":"3:3"}}
    )
    changed=p.upgrade_general_game_states(
        [entry],datetime(2026,8,25,tzinfo=timezone.utc)
    )
    assert changed==2
    assert entry["game_state_learning_v84e1"][0]["result"]=="hit"
    assert entry["autolearn_signals_v84"][0]["result"]=="miss"
