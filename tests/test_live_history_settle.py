from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from live_history_settle import final_from_match, settle_entry
from datetime import datetime, timezone


def _run_transport(monkeypatch, tmp_path, outcomes, *, budget=2, matches=1):
    import json
    import live_history_settle as live
    rows = [{"match_id": i + 1, "p1": "A", "p2": "B", "status": "pending",
             "scheduled_time": "2026-01-01T12:00:00Z",
             "signals": [{"market": "match_win", "pick": "A", "result": "pending"}]}
            for i in range(matches)]
    for name in ("HISTORY_PATH", "STATE_PATH", "META_PATH", "STATS_PATH", "SHADOW_STATS_PATH"):
        monkeypatch.setattr(live, name, tmp_path / (name + ".json"))
    live.HISTORY_PATH.write_text(json.dumps(rows))
    monkeypatch.setenv("LIVE_TENNIS_API_KEY", "not-a-real-key")
    monkeypatch.setattr(live, "quota_budget", lambda *args: (budget, {}))
    monkeypatch.setattr(live, "request_interval_seconds", lambda *args, **kwargs: 0)
    monkeypatch.setattr(live.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(live, "history_stats", lambda rows: {})
    monkeypatch.setattr(live, "build_shadow_stats", lambda rows: {})
    counted, requested = [], []
    monkeypatch.setattr(live, "record_calls", lambda module, count: counted.append(count))
    pending = iter(outcomes)
    def get(url, **kwargs):
        requested.append(url)
        result = next(pending)
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(live.requests, "get", get)
    live.main()
    return (json.loads(live.META_PATH.read_text()), json.loads(live.HISTORY_PATH.read_text()),
            counted, requested)


def _response(status, payload=None):
    from types import SimpleNamespace
    return SimpleNamespace(status_code=status, headers={}, json=lambda: payload)


def test_result_fetch_timeout_attempts_cannot_exceed_quota(monkeypatch, tmp_path):
    import requests
    meta, history, counted, requested = _run_transport(
        monkeypatch, tmp_path, [requests.Timeout("secret must not be logged")] * 3,
        budget=2, matches=3)
    assert len(requested) == sum(counted) == meta["history_live_settle_calls"] == 2
    assert all(row["status"] == "pending" for row in history)
    assert meta["history_live_settle_error_details"][0]["reason"] == "Timeout"
    assert "secret" not in str(meta)


def test_transient_result_fetch_recovers_within_same_budget(monkeypatch, tmp_path):
    terminal = {"winner": 1, "score": {"games": [[6, 6], [4, 3]]}}
    meta, history, counted, requested = _run_transport(
        monkeypatch, tmp_path, [_response(503), _response(200, terminal)])
    assert len(requested) == sum(counted) == meta["history_live_settle_calls"] == 2
    assert meta["history_live_settle_errors"] == 0
    assert meta["history_live_settle_retries"] == 1
    assert history[0]["status"] == "settled"
    assert history[0]["result"]["winner"] == "A"


def test_missing_result_is_reported_without_retry_or_invented_outcome(monkeypatch, tmp_path):
    meta, history, counted, requested = _run_transport(monkeypatch, tmp_path, [_response(404)])
    assert len(requested) == sum(counted) == 1
    assert history[0]["status"] == "pending"
    assert meta["history_live_settle_errors"] == 1
    assert meta["history_live_settle_error_details"] == [{"match_id": 1, "reason": "HTTP_404"}]


def test_gone_result_defers_repeated_fetches_without_inventing_settlement(monkeypatch, tmp_path):
    import json
    from datetime import timedelta
    import live_history_settle as live
    meta, history, counted, requested = _run_transport(monkeypatch, tmp_path, [_response(410)])
    state = json.loads(live.STATE_PATH.read_text())
    state["matches"]["1"]["last_checked_at"] = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    live.STATE_PATH.write_text(json.dumps(state))
    live.main()
    meta = json.loads(live.META_PATH.read_text())
    assert len(requested) == sum(counted) == 1
    assert meta["history_live_settle_calls"] == 0
    assert meta["history_live_settle_gone_deferred"] == 1
    assert meta["history_live_settle_deferred_details"][0]["reason"] == "HTTP_410_RECHECK_BACKOFF"
    assert json.loads(live.HISTORY_PATH.read_text())[0]["status"] == "pending"


def test_gone_result_rechecks_after_backoff_and_recovers(monkeypatch, tmp_path):
    import json
    from datetime import timedelta
    import live_history_settle as live
    terminal = {"winner": 1, "score": {"games": [[6, 6], [4, 3]]}}
    _, _, counted, requested = _run_transport(monkeypatch, tmp_path, [_response(410), _response(200, terminal)])
    state = json.loads(live.STATE_PATH.read_text())
    state["matches"]["1"]["last_checked_at"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    live.STATE_PATH.write_text(json.dumps(state))
    live.main()
    assert len(requested) == sum(counted) == 2
    assert json.loads(live.HISTORY_PATH.read_text())[0]["status"] == "settled"
    assert json.loads(live.STATE_PATH.read_text())["matches"]["1"]["last_status_code"] == 200

def entry(): return {'p1':'A','p2':'B','status':'pending','signals':[]}
def test_completed_score():
    m={'winner':1,'event_status':None,'score':{'sets':[2,0],'games':[[6,6],[4,3]]}}
    f=final_from_match(m,entry());assert f['winner']=='A';assert f['match_score']=='2:0';assert f['first_set_score']=='6:4';assert f['total_games']==19

def test_completed_payload_with_winner_score_contradiction_fails_closed():
    m={'winner':2,'event_status':None,'score':{'sets':[2,0],'games':[[6,6],[4,3]]}}
    assert final_from_match(m,entry()) is None

def test_live_not_final():
    m={'winner':None,'score':{'sets':[1,0],'games':[[6,2],[4,1]]}}
    assert final_from_match(m,entry()) is None

def test_walkover_void():
    f=final_from_match({'event_status':'Walk Over','winner':1,'score':None},entry());assert f['status']=='void'


def test_reconcile_all_layers_is_idempotent_and_keeps_frozen_forecasts():
    from copy import deepcopy
    from signal_settlement import SIGNAL_LAYERS, reconcile_settled
    match = {'p1':'A','p2':'B','status':'settled','settled_at':'original',
             'result':{'status':'completed','winner':'A','sets':[[6,2],[6,4]],'total_games':18}}
    for layer in SIGNAL_LAYERS:
        match[layer] = [
            {'market':'match_total','pick':'over','line':17.5,'result':'pending',
             'model_scores':{'ensemble':79}, 'adaptive_prod_v79':{'final_score':75},'captured_at':'frozen'},
            {'market':'game_state','checkpoint':6,'pick':'3:3','result':'pending'},
            {'market':'game_state','checkpoint':4,'pick':'2:2','result':'hit','settlement_source':'PBP'},
        ]
    original = deepcopy(match)
    result = reconcile_settled([match])[0]
    assert match == original
    assert result['settled_at'] == 'original'
    for layer in SIGNAL_LAYERS:
        assert [s['result'] for s in result[layer]] == ['hit','unverifiable','hit']
        assert result[layer][0]['model_scores'] == match[layer][0]['model_scores']
        assert result[layer][0]['adaptive_prod_v79'] == match[layer][0]['adaptive_prod_v79']
        assert result[layer][0]['captured_at'] == 'frozen'
        assert result[layer][2] == match[layer][2]
    assert reconcile_settled([result]) == [result]


def test_historical_and_live_settlement_share_all_layers():
    import pandas as pd
    from unittest.mock import patch
    from history_tracker import settle_history
    from signal_settlement import SIGNAL_LAYERS
    now = datetime(2026,8,27,12,tzinfo=timezone.utc)
    match = {**entry(), 'scheduled_time':'2026-08-26T12:00:00Z'}
    for layer in SIGNAL_LAYERS:
        match[layer] = [{'market':'match_win','pick':'A','result':'pending'}]
    final = {'status':'completed','winner':'A','sets':[[6,2],[6,4]],'total_games':18}
    with patch('history_tracker.find_final_result', return_value=final):
        historic = settle_history([match], pd.DataFrame(), now=now)[0]
    live = settle_entry(match, final, now)
    assert historic['status'] == live['status'] == 'settled'
    assert historic['settlement_source'] == 'historical match result'
    assert historic['settlement_version'] == 'history-tracker-result-1'
    assert historic['settled_at'] == now.isoformat()
    for layer in SIGNAL_LAYERS:
        assert historic[layer][0]['result'] == live[layer][0]['result'] == 'hit'


def test_standalone_report_refresh_preserves_shadow_experiments(tmp_path):
    import json
    from refresh_settlement_reports import refresh
    keys = ('player_model_shadow_v89', 'ensemble_player_learning_v891', 'surface_elo_integration_v893')
    experiments = {key: {'production_influence': False, 'generated_at': 'original',
                         'holdout': {'n': 89, 'brier': .21}} for key in keys}
    (tmp_path / 'model_telemetry_v84c.json').write_text(json.dumps(experiments))
    (tmp_path / 'results.json').write_text('[]')
    (tmp_path / 'history.json').write_text('[]')
    refresh(tmp_path)
    telemetry = json.loads((tmp_path / 'model_telemetry_v84c.json').read_text())
    for key in keys:
        assert telemetry[key] == experiments[key]
    assert 'player_intelligence_v85' in telemetry
