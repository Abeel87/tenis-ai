from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "frontend" / "index.html"
GUARD = ROOT / "frontend" / "symphony-playable-detail-guard-v915.js"


def test_guard_is_loaded_after_base_symphony_surface():
    html = INDEX.read_text(encoding="utf-8")
    base = 'symphony-surface-v90.js?v=90e1'
    guard = 'symphony-playable-detail-guard-v915.js?v=915'
    assert base in html
    assert guard in html
    assert html.index(base) < html.index(guard)


def test_guard_requires_verified_superbet_playable_reprojection():
    js = GUARD.read_text(encoding="utf-8")
    assert "operator_reprojection" in js
    assert "verified_operator_match" in js
    assert "PLAYABLE_SUPERBET_ONLY" in js
    assert "compositions" in js
    # The defensive UI must not resurrect the stale RAW shortcut that caused
    # player aces/double-faults to appear in match detail.
    assert "row.full_composition" not in js
    assert "Brak świeżo zweryfikowanej oferty Superbet" in js
