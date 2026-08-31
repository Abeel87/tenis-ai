from datetime import datetime, timezone
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from degraded_history import capture_history


def _match(start="2026-08-20T12:00:00Z"):
    return {
        "id": 987,
        "tour": "atp",
        "tournament": "Test",
        "surface": "hard",
        "scheduled_time": start,
        "p1": "Player One",
        "p2": "Player Two",
        "model_ready": True,
        "quality": "HIGH",
        "model_confidence": 90,
        "match_win": {"Player One": 80.0, "Player Two": 20.0},
        "first_set_win": {"Player One": 74.0, "Player Two": 26.0},
    }


def test_degraded_capture_creates_history_and_stats(tmp_path):
    results = tmp_path / "results.json"
    history = tmp_path / "history.json"
    stats = tmp_path / "history_stats.json"
    candidate_stats = tmp_path / "superbet_candidate_stats_v925.json"
    meta = tmp_path / "meta.json"

    results.write_text(json.dumps([_match()]), encoding="utf-8")
    meta.write_text(json.dumps({"degraded_reason": "history_source_unavailable"}), encoding="utf-8")

    info = capture_history(
        results_path=results,
        history_path=history,
        stats_path=stats,
        candidate_stats_path=candidate_stats,
        meta_path=meta,
        now=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
    )

    saved = json.loads(history.read_text(encoding="utf-8"))
    saved_meta = json.loads(meta.read_text(encoding="utf-8"))

    assert len(saved) == 1
    assert saved[0]["status"] == "pending"
    assert saved[0]["signals"]
    assert stats.exists()
    assert candidate_stats.exists()
    assert info["history_matches"] == 1
    assert saved_meta["history_capture_mode"] == "last-analysis"


def test_degraded_capture_never_backfills_after_match_start(tmp_path):
    results = tmp_path / "results.json"
    history = tmp_path / "history.json"
    stats = tmp_path / "history_stats.json"
    candidate_stats = tmp_path / "superbet_candidate_stats_v925.json"
    meta = tmp_path / "meta.json"

    results.write_text(json.dumps([_match("2026-08-20T09:00:00Z")]), encoding="utf-8")

    capture_history(
        results_path=results,
        history_path=history,
        stats_path=stats,
        candidate_stats_path=candidate_stats,
        meta_path=meta,
        now=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
    )

    saved = json.loads(history.read_text(encoding="utf-8"))
    assert saved == []
    assert candidate_stats.exists()
