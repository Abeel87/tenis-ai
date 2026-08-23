from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(path): return (ROOT/path).read_text(encoding='utf-8')

def test_v80_is_central_version():
    meta=read('frontend/app-meta.js'); idx=read('frontend/index.html'); sw=read('frontend/sw.js'); app=read('frontend/app.js')
    assert "appVersion: 'v8.0.1'" in meta
    assert "cacheVersion: 'v801'" in meta
    assert 'clean-core-v80.js?v=801' in idx
    assert 'clean-core-v80.css?v=801' in idx
    assert "tenis-ai-v801-player-profile" in sw
    assert "serviceWorker.register('sw.js?v=801')" in app

def test_history_has_one_v8_runtime_owner():
    idx=read('frontend/index.html'); clean=read('frontend/clean-core-v80.js')
    assert 'history-days-v732.js' not in idx
    assert 'history-days-v732.css' not in idx
    assert not (ROOT/'frontend/history-days-v732.js').exists()
    assert not (ROOT/'frontend/history-days-v732.css').exists()
    assert 'renderHistory=function(){renderHistoryV80()}' in clean
    assert 'data-v80-history-open' in clean

def test_postmatch_explains_models_and_learning():
    clean=read('frontend/clean-core-v80.js')
    for text in ['RAPORT PO MECZU','Co weszło','Co nie weszło','Modele — wynik tego meczu','Dlaczego model się pomylił','adaptive_review_v79','learning_signals_v79b','TRAFIONY','NIETRAFIONY']:
        assert text in clean
    for model in ['Consensus','Early Hold','Serve/Return','Form','Surface']:
        assert model in clean

def test_old_header_override_is_gone():
    ui=read('frontend/ui-v751.js')
    assert 'Tenis AI v7.8D · Calibration Guard' not in ui
    assert 'TENIS_AI_META' in ui

def test_root_legacy_install_artifacts_removed():
    assert not list(ROOT.glob('install_v*.py'))
    assert not list(ROOT.glob('V*_README.txt'))
    assert not list(ROOT.glob('tenis-ai-v*.zip'))
    for name in ['PREDEPLOY_TESTS.txt','TESTS.txt','TESTS_PREUPDATE.txt','v7.4-admin-moderator.txt']:
        assert not (ROOT/name).exists()

def test_learning_backend_is_preserved():
    for path in ['backend/adaptive_learning_v79.py','backend/specialist_learning_v79b.py','backend/calibration_guard_v78d.py','backend/shadow_lab_v78e6.py','backend/pbp_tracker.py']:
        assert (ROOT/path).exists(), path

def test_active_legacy_bridges_keep_required_features():
    ui=read('frontend/ui-v751.js')
    restore=read('frontend/restore-v762.js')
    analytics=read('frontend/player-analytics-v76.js')
    assert 'matchGamesPreview' in ui and 'matchGamesLines' in ui
    assert 'Siła sygnału' in ui and 'data-shadow-open' in ui
    assert '.p751-names > b, .p751-matchup > b' in restore
    assert 'Player Analytics PRO' in analytics

