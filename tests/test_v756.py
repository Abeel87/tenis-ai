
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_direct_patch_present():
    s=(ROOT/'install_v756.py').read_text(encoding='utf-8')
    assert 'function matchGamesPreview(m)' in s
    assert 'function matchGamesLines(m)' in s
    assert '${matchGamesPreview(m)}' in s
    assert '${matchGamesLines(m)}' in s
    assert 'm.match_over_under' in s
    assert 'tenis-ai-v756-direct-match-games' in s
