import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

import pandas as pd
from model import (
    parse_first_set, parse_second_set, normalize_matches, analyse_match,
    _hold_from_point_probability,
)


def test_parse_sets():
    assert parse_first_set('7-6(5) 4-6 6-3') == (7, 6)
    assert parse_second_set('7-6(5) 4-6 6-3') == (4, 6)


def sample_rows():
    rows = []
    base = pd.Timestamp('2026-08-01')
    for i in range(12):
        day = int((base - pd.Timedelta(days=i)).strftime('%Y%m%d'))
        rows.append({
            'tourney_date': day, 'tourney_name': f'X{i}', 'source_tour': 'ATP', 'surface': 'Hard',
            'winner_name': 'Alpha', 'loser_name': 'Beta', 'winner_rank': 80+i, 'loser_rank': 140+i,
            'score': '6-4 4-6 6-3',
            'w_svpt': 60, 'w_1stIn': 38, 'w_1stWon': 30, 'w_2ndWon': 12, 'w_SvGms': 10, 'w_bpSaved': 3, 'w_bpFaced': 4,
            'l_svpt': 62, 'l_1stIn': 39, 'l_1stWon': 25, 'l_2ndWon': 10, 'l_SvGms': 10, 'l_bpSaved': 4, 'l_bpFaced': 6,
        })
    return rows


def result():
    long = normalize_matches(pd.DataFrame(sample_rows()))
    return analyse_match(long, {
        'tour':'atp','tournament':'X','surface':'hard','p1':'Alpha','p2':'Beta',
        'scheduled_time':'2026-08-19T15:00:00Z'
    })


def test_deduplicates_same_match():
    rows = sample_rows()
    d = pd.DataFrame(rows + [rows[0].copy()])
    long = normalize_matches(d)
    assert len(long) == len(rows) * 2


def test_second_set_context_history_is_normalized():
    long = normalize_matches(pd.DataFrame(sample_rows()))
    a = long[long.player == 'Alpha'].iloc[0]
    b = long[long.player == 'Beta'].iloc[0]
    assert a.second_set_won == 0.0
    assert b.second_set_won == 1.0
    assert a.second_after_first_win == 0.0
    assert b.second_after_first_loss == 1.0
    assert a.third_set_won == 1.0
    assert b.third_set_won == 0.0


def test_return_points_are_available():
    long = normalize_matches(pd.DataFrame(sample_rows()))
    assert long['return_points_won'].notna().all()


def test_point_to_hold_is_monotonic():
    assert _hold_from_point_probability(.65) > _hold_from_point_probability(.60) > _hold_from_point_probability(.55)


def test_no_fake_historical_lead_after6_but_model_states_exist():
    r = result()
    assert r['score_lead_after6'] is None
    assert r['score_first_set'] is not None
    assert r['game_states']['2']['1:1'] is not None
    assert r['game_states']['6']['3:3'] is not None


def test_over_under_are_complements():
    r = result()
    for m in r['over_under'].values():
        assert abs(m['over'] + m['under'] - 100.0) <= 0.2


def test_match_over_under_are_complements():
    r = result()
    assert r['match_over_under'] is not None
    assert r['expected_match_games'] is not None
    for m in r['match_over_under'].values():
        assert abs(m['over'] + m['under'] - 100.0) <= 0.2


def test_set_winner_markets_have_both_players():
    r = result()
    for key in ('first_set_win', 'second_set_win', 'third_set_win', 'match_win'):
        assert set(r[key]) == {'Alpha', 'Beta'}
        assert abs(sum(r[key].values()) - 100.0) <= 0.2


def test_total_sets_are_complements():
    r = result()
    assert set(r['total_sets']) == {'2 sety', '3 sety'}
    assert abs(sum(r['total_sets'].values()) - 100.0) <= 0.2


def test_exact_match_score_sums_to_100():
    r = result()
    assert set(r['exact_match_score']) == {'2:0', '2:1', '1:2', '0:2'}
    assert abs(sum(r['exact_match_score'].values()) - 100.0) <= 0.2


def test_model_confidence_and_surface_sample_exist():
    r = result()
    assert r['model_confidence'] is not None
    assert 0 <= r['model_confidence'] <= 100
    assert r['p1_stats']['surface_matches'] >= 5
    assert r['p1_stats']['rank'] is not None
