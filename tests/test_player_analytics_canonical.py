from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
INDEX = (FRONTEND / "index.html").read_text(encoding="utf-8")
RUNTIME = (FRONTEND / "player-analytics.js").read_text(encoding="utf-8")


def test_player_analytics_uses_canonical_runtime_paths():
    assert (FRONTEND / "player-analytics.js").is_file()
    assert (FRONTEND / "player-analytics.css").is_file()
    assert 'src="player-analytics.js"' in INDEX
    assert 'href="player-analytics.css"' in INDEX
    assert not (FRONTEND / "player-analytics-v76.js").exists()
    assert not (FRONTEND / "player-analytics-v76.css").exists()
    assert "player-analytics-v76.js" not in INDEX
    assert "player-analytics-v76.css" not in INDEX


def test_player_analytics_stays_descriptive_not_prediction_runtime():
    assert "Descriptive analytics only" in RUNTIME
    assert "NOT win probabilities" in RUNTIME
    assert "TENIS_AI_PLAYER_ANALYTICS_V801" in RUNTIME
    lowered = RUNTIME.lower()
    for token in ("model_weight", "threshold=", "fit(", "train(", "settlement"):
        assert token not in lowered
