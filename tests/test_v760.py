from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_frontend_has_pro_sections():
    s=(ROOT/'frontend/player-analytics-v76.js').read_text(encoding='utf-8')
    for x in ['Player Analytics PRO','SERWIS','RETURN','FORMA','EARLY','MENTAL','NAWIERZCHNIA','Nie są prawdopodobieństwem']:
        assert x in s

def test_installer_extends_backend_without_new_api():
    s=(ROOT/'install_v760.py').read_text(encoding='utf-8')
    for x in ['closeout_after_set1_win','comeback_set2_after_set1_loss','deciding_set_win','first_serve_won','second_serve_won','_trend_pack']:
        assert x in s
    assert 'requests.get' not in s
    assert 'LIVE_TENNIS_API_KEY' not in s

def test_match_detail_comparison_is_direct():
    s=(ROOT/'install_v760.py').read_text(encoding='utf-8')
    assert 'function analyticsPro76(m)' in s
    assert '${analyticsPro76(m)}' in s
    assert 'tenis-ai-v760-player-analytics-pro' in s
