from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_player_trends_uses_canonical_runtime_path():
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")
    runtime = (FRONTEND / "player-trends.js").read_text(encoding="utf-8")
    assert 'src="player-trends.js"' in index
    assert 'href="player-trends.css"' in index
    assert "TENIS_AI_PLAYER_TRENDS_V81" in runtime
    assert "tendencies_v71" in runtime
    assert "early_hold_v7" in runtime


def test_retired_player_trends_paths_stay_deleted():
    assert not (FRONTEND / "player-trends-v71.js").exists()
    assert not (FRONTEND / "player-trends-v71.css").exists()
