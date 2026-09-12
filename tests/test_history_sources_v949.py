import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from update import TML_SOURCES


def test_recent_atp_qualifying_sources_are_in_history_feed():
    by_key = {source['key']: source for source in TML_SOURCES}

    assert by_key['atp_quali_2026'] == {
        'key': 'atp_quali_2026',
        'tour': 'ATP',
        'url': 'https://stats.tennismylife.org/data/atp_quali/2026_atp_quali.csv',
        'refresh_hours': 12,
    }
    assert by_key['atp_quali_2025'] == {
        'key': 'atp_quali_2025',
        'tour': 'ATP',
        'url': 'https://stats.tennismylife.org/data/atp_quali/2025_atp_quali.csv',
        'refresh_hours': None,
    }


def test_qualifying_history_keeps_recent_horizon_only():
    qualifying = {source['key'] for source in TML_SOURCES if '_quali_' in source['key']}

    assert qualifying == {'atp_quali_2025', 'atp_quali_2026'}
