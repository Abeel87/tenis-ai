from datetime import datetime, timezone
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from degraded_history import capture_history


def test_capture_history_refreshes_candidate_stats_contract(tmp_path):
    results = tmp_path / "results.json"
    history = tmp_path / "history.json"
    stats = tmp_path / "history_stats.json"
    candidate_stats = tmp_path / "superbet_candidate_stats_v925.json"
    meta = tmp_path / "meta.json"

    results.write_text("[]", encoding="utf-8")

    capture_history(
        results_path=results,
        history_path=history,
        stats_path=stats,
        candidate_stats_path=candidate_stats,
        meta_path=meta,
        now=datetime(2026, 8, 31, 20, 0, tzinfo=timezone.utc),
    )

    report = json.loads(candidate_stats.read_text(encoding="utf-8"))
    supported = set(report["settlement_supported_markets"])
    assert {"match_game_handicap", "set1_game_handicap", "set2_game_handicap"} <= supported
    assert {"set2_total", "player_total_games"} <= supported
    assert report["contract"]["production_influence"] is False
    assert report["promotion_gate"]["auto_promote"] is False
