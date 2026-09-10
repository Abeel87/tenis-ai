from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_stale_raw_playable_v921_is_removed():
    assert not (FRONTEND / "raw-playable-separation-v921.js").exists()
    assert not (FRONTEND / "data" / "symphony_match_cards_v90.json").exists()


