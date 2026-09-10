from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(path): return (ROOT/path).read_text(encoding='utf-8')


def test_root_legacy_install_artifacts_removed():
    assert not list(ROOT.glob('install_v*.py'))
    assert not list(ROOT.glob('V*_README.txt'))
    assert not list(ROOT.glob('tenis-ai-v*.zip'))
    for name in ['PREDEPLOY_TESTS.txt','TESTS.txt','TESTS_PREUPDATE.txt','v7.4-admin-moderator.txt']:
        assert not (ROOT/name).exists()

def test_learning_backend_is_preserved():
    for path in ['backend/adaptive_learning_v79.py','backend/specialist_learning_v79b.py','backend/calibration_guard_v78d.py','backend/shadow_lab_v78e6.py','backend/pbp_tracker.py']:
        assert (ROOT/path).exists(), path

