from datetime import datetime, timezone
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from history_tracker import (
    MODEL_VERSION,
    archive_predictions, extract_green_signals, history_stats, is_current_match,
    parse_final_row, settle_signal,
)


def sample_match():
    return {
        'id': 123, 'tour': 'atp', 'tournament': 'Test', 'surface': 'hard',
        'scheduled_time': '2026-08-20T12:00:00Z', 'p1': 'Player One', 'p2': 'Player Two',
        'model_ready': True, 'quality': 'HIGH', 'model_confidence': 88,
        'match_win': {'Player One': 76.0, 'Player Two': 24.0},
        'first_set_win': {'Player One': 70.0, 'Player Two': 30.0},
        'second_set_win': {'Player One': 74.0, 'Player Two': 26.0},
        'third_set_win': {'Player One': 73.0, 'Player Two': 27.0},
        'total_sets': {'2 sety': 81.0, '3 sety': 19.0},
        'exact_match_score': {'2:0': 62.0, '2:1': 14.0, '1:2': 12.0, '0:2': 12.0},
        'game_states': {'2': {'1:1': 75.0, '2:0': 15.0, '0:2': 10.0}},
        'over_under': {'8.5': {'over': 83.0, 'under': 17.0}},
        'match_over_under': {'22.5': {'over': 35.0, 'under': 65.0}},
        'exact_first_set': {'6:4': 19.0, '6:3': 18.0},
    }


def test_extract_green_signals_only_threshold_and_above():
    s = extract_green_signals(sample_match())
    labels = {(x['market'], x['pick']) for x in s}
    assert ('match_winner', 'Player One') in labels
    assert ('set2_winner', 'Player One') in labels
    assert ('game_state', '1:1') in labels
    assert ('set1_total', 'over') in labels
    assert ('set1_winner', 'Player One') not in labels


def test_archive_freezes_latest_pre_match_snapshot():
    now = datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)
    entries = archive_predictions([], [sample_match()], now=now)
    assert len(entries) == 1
    assert entries[0]['status'] == 'pending'
    assert entries[0]['signals']


def test_stale_match_filter():
    now = datetime(2026, 8, 20, 13, 0, tzinfo=timezone.utc)
    m = sample_match()
    assert not is_current_match(m, now=now, grace_minutes=30)


def test_parse_and_settle_normal_match():
    entry = {'p1': 'Player One', 'p2': 'Player Two'}
    row = pd.Series({'winner_name': 'Player One', 'loser_name': 'Player Two', 'score': '6-4 3-6 6-3'})
    final = parse_final_row(row, entry)
    final = {**final, **entry}
    assert final['match_score'] == '2:1'
    assert final['total_games'] == 28
    assert settle_signal({'market':'match_winner','pick':'Player One'}, final) == 'hit'
    assert settle_signal({'market':'set1_total','pick':'over','line':8.5}, final) == 'hit'
    assert settle_signal({'market':'exact_set1','pick':'6:4'}, final) == 'hit'
    assert settle_signal({'market':'game_state','pick':'1:1'}, final) == 'unverifiable'


def test_third_set_prediction_is_void_when_no_third_set():
    entry = {'p1': 'Player One', 'p2': 'Player Two'}
    row = pd.Series({'winner_name': 'Player One', 'loser_name': 'Player Two', 'score': '6-4 6-4'})
    final = {**parse_final_row(row, entry), **entry}
    assert settle_signal({'market':'set3_winner','pick':'Player One'}, final) == 'void'


def test_history_stats_excludes_void_and_unverifiable():
    entries = [{
        'model_version': MODEL_VERSION,
        'tour':'atp','signals':[
            {'label':'A','score':80,'result':'hit'},
            {'label':'A','score':75,'result':'miss'},
            {'label':'B','score':90,'result':'void'},
            {'label':'C','score':85,'result':'unverifiable'},
        ]
    }]
    stats = history_stats(entries)
    assert stats['overall']['settled'] == 2
    assert stats['overall']['hits'] == 1
    assert stats['overall']['accuracy'] == 50.0
    assert stats['excluded_signals'] == 2
