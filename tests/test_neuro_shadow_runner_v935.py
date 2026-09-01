import json

from backend.neuro_shadow_runner_v935 import (
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    capture_file,
    capture_matches,
)
from backend.neuro_shadow_history_v935 import load_history


def _match():
    return {
        "id": 123,
        "p1": "Alpha",
        "p2": "Beta",
        "scheduled_time": "2026-09-01T10:00:00Z",
        "surface": "hard",
        "tour": "ATP",
        "best_of": 3,
        "service_model": {"p1_hold": 78.0, "p2_hold": 72.0},
        "second_set_context": {"p1_unconditional": 55.0},
        "superbet_market_v91": {
            "operator_verified": True,
            "canonical_selections": [
                {
                    "market": "set2_total",
                    "pick": "over",
                    "line": 9.5,
                    "player": None,
                    "market_id": "m1",
                    "outcome_id": "o1",
                    "operator_available": True,
                    "operator_line_verified": True,
                },
                {
                    "market": "future_unknown",
                    "pick": "x",
                    "line": None,
                    "player": None,
                    "market_id": "m2",
                    "outcome_id": "o2",
                    "operator_available": True,
                    "operator_line_verified": True,
                },
            ],
        },
    }


def test_runner_is_hard_shadow_only():
    assert PRODUCTION_INFLUENCE is False
    assert PLAYABLE_INFLUENCE is False
    assert SYMPHONY_PROD_INFLUENCE is False


def test_capture_uses_verified_canonical_context_only(tmp_path):
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"
    unverified = _match()
    unverified["id"] = 124
    unverified["superbet_market_v91"]["operator_verified"] = False

    result = capture_matches([_match(), unverified], history_path=history, stats_path=stats)

    assert result["matches_seen"] == 2
    assert result["matches_with_verified_operator"] == 1
    assert result["adapted_predictions"] == 1
    assert result["added_predictions"] == 1
    rows = load_history(history)
    assert len(rows) == 1
    assert rows[0]["market"] == "set2_total"
    assert rows[0]["operator_playable"] is False


def test_repeated_capture_keeps_first_forecast(tmp_path):
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"
    first = capture_matches([_match()], history_path=history, stats_path=stats)
    second = capture_matches([_match()], history_path=history, stats_path=stats)
    assert first["added_predictions"] == 1
    assert second["added_predictions"] == 0
    assert len(load_history(history)) == 1


def test_capture_file_handles_real_results_shape(tmp_path):
    results = tmp_path / "results.json"
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"
    results.write_text(json.dumps([_match()]), encoding="utf-8")
    result = capture_file(results, history_path=history, stats_path=stats)
    assert result["added_predictions"] == 1
    assert history.exists()
    assert stats.exists()


def test_missing_or_bad_results_is_safe_noop(tmp_path):
    history = tmp_path / "history.json"
    stats = tmp_path / "stats.json"
    missing = capture_file(tmp_path / "missing.json", history_path=history, stats_path=stats)
    assert missing["matches_seen"] == 0
    bad = tmp_path / "bad.json"
    bad.write_text("not-json", encoding="utf-8")
    invalid = capture_file(bad, history_path=history, stats_path=stats)
    assert invalid["matches_seen"] == 0
