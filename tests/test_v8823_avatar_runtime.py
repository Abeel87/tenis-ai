from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_avatar_fix_is_event_driven():
    js = read("frontend/avatar-fix.js")
    assert "RUNTIME_FIX='v8.8.23'" in js
    assert "tenis-ai-auth-change" in js
    assert "#account-button" in js
    assert "requestAnimationFrame(applyAvatar)" in js
    assert "new MutationObserver(" not in js
    assert "observer.observe(document.body" not in js
    assert "setTimeout(applyAvatar" not in js
