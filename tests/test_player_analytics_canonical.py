from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
INDEX = (FRONTEND / "index.html").read_text(encoding="utf-8")
RUNTIME = (FRONTEND / "player-analytics.js").read_text(encoding="utf-8")


def test_player_analytics_stays_descriptive_not_prediction_runtime():
    assert "function indexes(d,ui)" in RUNTIME
    assert "return {serve,ret,form,early,mental,surface,g,p,surf,ps}" in RUNTIME
    assert "TENIS_AI_PLAYER_ANALYTICS" in RUNTIME
    lowered = RUNTIME.lower()
    for token in ("model_weight", "threshold=", "fit(", "train(", "settlement"):
        assert token not in lowered
