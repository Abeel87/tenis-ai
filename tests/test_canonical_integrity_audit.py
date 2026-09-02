from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend.history_tracker import is_current_match
from backend.superbet_playable import _filter_shadow_feed, _history_signal
from backend.symphony2_engine import _is_current_pre_match_fixture

ROOT = Path(__file__).resolve().parents[1]
SYMPHONY_UI = (ROOT / "frontend" / "symphony2.js").read_text(encoding="utf-8")
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
