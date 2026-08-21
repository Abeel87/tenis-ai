from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_registration_ux():
    js=(ROOT/'frontend/registration-ux-v752.js').read_text(encoding='utf-8')
    for x in ['Zasady rejestracji','3–24 znaki','Minimum 8 znaków','email rate limit exceeded','RATE_KEY','validateAll']:
        assert x in js
def test_installer():
    s=(ROOT/'install_v752.py').read_text(encoding='utf-8')
    assert 'registration-ux-v752.css' in s and 'registration-ux-v752.js' in s
