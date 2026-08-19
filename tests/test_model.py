import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import pandas as pd
from model import parse_first_set, normalize_matches, analyse_match


def test_parse_set():
    assert parse_first_set('7-6(5) 6-4') == (7, 6)


def sample_rows():
    rows = []
    for i in range(10):
        rows.append({
            'tourney_date': 20260801-i, 'surface': 'Hard', 'winner_name': 'Alpha', 'loser_name': 'Beta', 'score': '6-4 6-4',
            'w_svpt': 60, 'w_1stIn': 38, 'w_1stWon': 30, 'w_2ndWon': 12, 'w_SvGms': 10, 'w_bpSaved': 3, 'w_bpFaced': 4,
            'l_svpt': 62, 'l_1stIn': 39, 'l_1stWon': 25, 'l_2ndWon': 10, 'l_SvGms': 10, 'l_bpSaved': 4, 'l_bpFaced': 6,
        })
    return rows


def test_no_fake_historical_lead_after6_but_model_states_exist():
    long = normalize_matches(pd.DataFrame(sample_rows()))
    r = analyse_match(long, {'tour':'atp','tournament':'X','surface':'hard','p1':'Alpha','p2':'Beta','scheduled_time':''})
    assert r['score_lead_after6'] is None
    assert r['score_first_set'] is not None
    assert r['game_states']['2']['1:1'] is not None
    assert r['game_states']['6']['3:3'] is not None


def test_over_under_are_complements():
    long = normalize_matches(pd.DataFrame(sample_rows()))
    r = analyse_match(long, {'tour':'atp','tournament':'X','surface':'hard','p1':'Alpha','p2':'Beta','scheduled_time':''})
    for line, m in r['over_under'].items():
        assert round(m['over'] + m['under'], 6) == 100.0


def test_match_over_under_are_complements():
    long = normalize_matches(pd.DataFrame(sample_rows()))
    r = analyse_match(long, {'tour':'atp','tournament':'X','surface':'hard','p1':'Alpha','p2':'Beta','scheduled_time':''})
    assert r['match_over_under'] is not None
    assert r['expected_match_games'] is not None
    for line, m in r['match_over_under'].items():
        assert round(m['over'] + m['under'], 6) == 100.0


def test_first_set_winner_has_both_players():
    long = normalize_matches(pd.DataFrame(sample_rows()))
    r = analyse_match(long, {'tour':'atp','tournament':'X','surface':'hard','p1':'Alpha','p2':'Beta','scheduled_time':''})
    assert set(r['first_set_win']) == {'Alpha', 'Beta'}
    assert round(sum(r['first_set_win'].values()), 6) == 100.0
