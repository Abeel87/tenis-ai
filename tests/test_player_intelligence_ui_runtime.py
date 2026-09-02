from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_player_intelligence_ui_has_one_canonical_runtime_owner():
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")

    assert (FRONTEND / "player-intelligence-ui.js").is_file()
    assert 'src="player-intelligence-ui.js"' in index

    for retired in (
        "player-intelligence-v851-ui.js",
        "player-intelligence-v851b-ui.js",
    ):
        assert not (FRONTEND / retired).exists(), retired
        assert retired not in index


def test_player_intelligence_model_generation_remains_separate():
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")

    assert (FRONTEND / "player-intelligence-v85.js").is_file()
    assert (FRONTEND / "player-intelligence-v85.css").is_file()
    assert 'src="player-intelligence-v85.js"' in index
    assert 'href="player-intelligence-v85.css"' in index
