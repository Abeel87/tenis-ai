from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p): return (ROOT/p).read_text(encoding="utf-8")

def test_no_old_profile_polling_or_global_observers():
    a=read("frontend/player-analytics-v76.js"); ad=read("frontend/adaptive-learning-v79.js"); c=read("frontend/clean-core-v80.js")
    assert "setInterval(inject,700)" not in a
    assert "obs.observe(panel,{childList:true,subtree:true})" not in a
    assert "TENIS_AI_PLAYER_ANALYTICS_V801" in a
    assert "observer.observe(document.documentElement" not in ad
    assert "observer.observe(document.documentElement" not in c

def test_profile_returns_and_history_opens_postmatch():
    r=read("frontend/restore-v762.js"); u=read("frontend/ui-v751.js"); p=read("frontend/player-search.js")
    assert "TENIS_AI_PLAYER_PROFILE_RETURN_KEY" in r
    assert "o.dataset.matchKey=String(k)" in u
    assert "data-player-history-key" in p
    assert "TENIS_AI_CLEAN_CORE?.openPostMatch" in p
    assert "TENIS_AI_PROJECT_UI?.openMatch" in p

def test_source_history_is_real_data():
    b=read("backend/player_trends.py"); a=read("frontend/player-analytics-v76.js")
    assert "def _recent_rows" in b
    assert '"recent_matches": _recent_rows(x, 20)' in b
    assert "Ostatnie mecze źródłowe" in a
    assert "Nie oznaczają, że Tenis AI wystawił wtedy typ" in a

def test_v801_cache():
    m=read("frontend/app-meta.js"); i=read("frontend/index.html"); sw=read("frontend/sw.js"); app=read("frontend/app.js")
    assert "appVersion: 'v8.0.1'" in m
    assert "cacheVersion: 'v801'" in m
    assert "tenis-ai-v801-player-profile" in sw
    assert "player-analytics-v76.js?v=801" in i
    assert "serviceWorker.register('sw.js?v=801')" in app
