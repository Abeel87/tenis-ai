from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from live_history_settle import final_from_match, settle_entry
from datetime import datetime, timezone

def entry(): return {'p1':'A','p2':'B','status':'pending','signals':[]}
def test_completed_score():
    m={'winner':1,'event_status':None,'score':{'sets':[2,0],'games':[[6,6],[4,3]]}}
    f=final_from_match(m,entry());assert f['winner']=='A';assert f['match_score']=='2:0';assert f['first_set_score']=='6:4';assert f['total_games']==19

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
