from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_compact_publication_stage_runs_deep_symphony_tracker():
    source = (ROOT / "scripts" / "compact_frontend_data_v853.py").read_text(encoding="utf-8")
    assert "symphony_model_tracker_v93" in source
    assert "track_deep_symphony_stats()" in source
    assert "symphony_model_stats" in source
