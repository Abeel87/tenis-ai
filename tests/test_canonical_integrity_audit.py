from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend.history_tracker import is_current_match
from backend.model import _match_distribution_conditional
from backend.superbet_playable import _filter_shadow_feed, _history_signal
from backend.symphony2_engine import _is_current_pre_match_fixture

ROOT = Path(__file__).resolve().parents[1]
SYMPHONY_UI = (ROOT / "frontend" / "symphony2.js").read_text(encoding="utf-8")
PLAYABLE_BACKEND = (ROOT / "backend" / "superbet_playable.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update-and-pages.yml").read_text(encoding="utf-8")


def test_symphony_rejects_fixture_without_parseable_schedule():
    now = datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc)
    assert _is_current_pre_match_fixture({}, now) is False
    assert _is_current_pre_match_fixture({"scheduled_time": "not-a-date"}, now) is False


def test_main_results_reject_fixture_without_parseable_schedule():
    now = datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc)
    assert is_current_match({}, now=now) is False
    assert is_current_match({"scheduled_time": "not-a-date"}, now=now) is False


def test_shadow_playable_feed_fails_closed_without_verified_operator_match():
    feed = {
        "matches": [
            {
                "id": "shadow-only",
                "p1": "A",
                "p2": "B",
                "signals": [{"market": "match_winner", "pick": "A", "score": 91}],
            }
        ],
        "model_signal_counts": {"stale": 99},
    }
    filtered = _filter_shadow_feed(feed, {})
    assert filtered["matches"] == []
    assert filtered["matches_count"] == 0
    assert filtered["model_signal_counts"] == {}


def test_playable_projection_never_overwrites_raw_shadow_sources():
    assert "_write(SHADOW_CURRENT" not in PLAYABLE_BACKEND
    assert "_write(SHADOW_CENTER" not in PLAYABLE_BACKEND
    assert "raw_shadow_center = _read(SHADOW_CENTER" in PLAYABLE_BACKEND
    assert "shadow_center = _filter_shadow_feed(raw_shadow_center" in PLAYABLE_BACKEND


def test_playable_history_does_not_invent_zero_score_when_score_is_missing():
    row = _history_signal({"market": "match_winner", "pick": "A"}, "test")
    assert "score" not in row


def test_symphony_ui_does_not_render_missing_numeric_values_as_real_zero():
    assert "const nfmt=v=>Number(v||0)" not in SYMPHONY_UI
    assert "Number(data?.matches_count||0)" not in SYMPHONY_UI
    assert "Number(x?.learning_support_rows||0)" not in SYMPHONY_UI
    assert "const nfmt=v=>num(v)==null?'N/D':" in SYMPHONY_UI


def test_autolearn_uses_previous_telemetry_snapshot_before_current_run_telemetry_refresh():
    auto = WORKFLOW.index("AutoLearn Ensemble v8.4A")
    adaptive = WORKFLOW.index("Adaptive Learning v7.9B controlled PROD")
    telemetry = WORKFLOW.index("Model Telemetry v8.4C")
    assert auto < adaptive < telemetry


def test_current_engine_bo3_bo5_distributions_are_normalized_and_only_terminal_scores_exist():
    base_dist = {(6, 3): 0.35, (6, 4): 0.25, (4, 6): 0.20, (3, 6): 0.20}
    for best_of, expected_scores in (
        (3, {"2:0", "2:1", "0:2", "1:2"}),
        (5, {"3:0", "3:1", "3:2", "0:3", "1:3", "2:3"}),
    ):
        total_games, winner, total_sets, exact = _match_distribution_conditional(
            base_dist, 0.58, 0.56, 0.51, 0.54, best_of=best_of
        )
        assert set(exact) == expected_scores
        assert abs(sum(exact.values()) - 1.0) < 1e-9
        assert abs(sum(total_games.values()) - 1.0) < 1e-9
        assert abs(sum(winner.values()) - 1.0) < 1e-9
        assert abs(sum(total_sets.values()) - 1.0) < 1e-9
