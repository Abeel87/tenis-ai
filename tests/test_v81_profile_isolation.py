from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def read(p): return (ROOT / p).read_text(encoding="utf-8")

def test_v81_profile_mode_is_isolated():
    p = read("frontend/player-search.js")
    assert "TENIS_AI_PLAYER_PROFILE_ACTIVE=true" in p
    assert "TENIS_AI_PLAYER_PROFILE_ACTIVE=false" in p
    assert "TENIS_AI_PLAYER_TRENDS_V81?.mount" in p
    assert "TENIS_AI_SERVE_PROPS_V81?.mountProfile" in p
    assert "TENIS_AI_EARLY_HOLD_PATHS_V81?.mountProfile" in p
    assert "TENIS_AI_PLAYER_ANALYTICS_V801?.mount" in p

def test_early_hold_paths_is_event_driven_outside_profile():
    s = read("frontend/early-hold-paths.js")
    assert "version:'v8.8.16'" in s
    assert "decorateOverlay()" in s
    assert "if(profileActive())return" in s
    assert "TENIS_AI_EARLY_HOLD_PATHS_V81" in s
    assert "wrapProjectOpen" in s
    assert "[data-p751-open]" in s
    assert "setInterval(" not in s
    assert "new MutationObserver(" not in s
    assert "obs.observe(document.body" not in s

def test_serve_props_uses_targeted_refresh_without_body_observer():
    s = read("frontend/serve-props-v72.js")
    assert "new MutationObserver(" not in s
    assert "obs.observe(document.body" not in s
    assert "scheduleRefresh(document)" in s
    assert "requestAnimationFrame" in s
    assert "TENIS_AI_SERVE_PROPS_V81" in s
    assert "mountProfile" in s

def test_player_trends_has_explicit_mount_without_subtree_observer():
    s = read("frontend/player-trends.js")
    assert "TENIS_AI_PLAYER_TRENDS_V81" in s
    assert "obs.observe(panel,{childList:true,subtree:true})" not in s

def test_models_and_backend_are_not_part_of_patch():
    for p in [
        "backend/adaptive_learning_v79.py",
        "backend/specialist_learning_v79b.py",
        "backend/calibration_guard_v78d.py",
        "backend/shadow_lab_v78e6.py",
        "backend/pbp_tracker.py",
    ]:
        assert (ROOT / p).exists(), p
