from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_community_profile_fix_has_no_global_mutation_observer():
    js = read("frontend/community-fix.js")
    assert "RUNTIME_FIX='v8.8.22'" in js
    assert "new MutationObserver(" not in js
    assert "observer.observe(document.body" not in js
    assert "#account-button" in js
    assert "tenis-ai-auth-change" in js
    assert "improveProfileEditor" in js


def test_profile_editor_owner_already_has_targeted_hooks():
    js = read("frontend/community.js")
    assert "function enhanceOwnProfile" in js
    assert "#account-button')?.addEventListener('click',enhanceOwnProfile)" in js
    assert "tenis-ai-auth-change" in js
    assert "profile-editor" in js
