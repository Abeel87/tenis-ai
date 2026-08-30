from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "symphony2.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_single_symphony2_frontend_is_loaded():
    assert "symphony2.js" in INDEX
    assert "symphony2.css" in INDEX
    for legacy in (
        "symphony-v90.js", "symphony-v90.css", "symphony-stats-v90d.js",
        "symphony-stats-v90d.css", "symphony-surface-v90.js",
        "symphony-playable-detail-guard-v915.js",
    ):
        assert legacy not in INDEX


def test_stats_ui_reads_only_symphony2_stats():
    assert "./data/symphony2_stats.json" in JS
    assert "#pc77" in JS
    assert "symphony2-performance" in JS
    assert "Wyniki starej Symfonii v9.x nie są importowane" in JS
    assert "symphony_stats_v90d.json" not in JS
    assert "symphony_model_stats_v93.json" not in JS


def test_generator_explains_exact_superbet_probability_contract():
    assert "dokładną aktualną ofertę Superbet" in JS
    assert "operator_model_probability" in JS
    assert "joint_probability" in JS
    assert "learning_support_rows" in JS
