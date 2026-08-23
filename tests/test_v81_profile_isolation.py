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

def test_early_hold_keeps_normal_runtime_outside_profile():
    s = read("frontend/early-hold-paths-v771.js")
    assert "setInterval(refresh,900)" in s
    assert "decorateOverlay()" in s
    assert "if(profileActive())return" in s
    assert "TENIS_AI_EARLY_HOLD_PATHS_V81" in s

def test_serve_props_only_skips_profile_mutations():
    s = read("frontend/serve-props-v72.js")
    assert "obs.observe(document.body,{childList:true,subtree:true})" in s
    assert "if(window.TENIS_AI_PLAYER_PROFILE_ACTIVE)return" in s
    assert "TENIS_AI_SERVE_PROPS_V81" in s
    assert "po.observe(profile,{childList:true,subtree:true})" not in s

def test_player_trends_has_explicit_mount_without_subtree_observer():
    s = read("frontend/player-trends-v71.js")
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
