from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend.superbet_playable import _filter_shadow_feed
from backend.symphony2_engine import _is_current_pre_match_fixture

ROOT = Path(__file__).resolve().parents[1]
SYMPHONY_UI = (ROOT / "frontend" / "symphony2.js").read_text(encoding="utf-8")


def test_symphony_rejects_fixture_without_parseable_schedule():
    now = datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc)
    assert _is_current_pre_match_fixture({}, now) is False
    assert _is_current_pre_match_fixture({"scheduled_time": "not-a-date"}, now) is False


def test_shadow_playable_feed_fails_closed_without_verified_operator_match():
    feed = {
        "matches": [
            {
                "id": "shadow-only",
                "p1": "A",
                "p2": "B",
                "signals": [{"market": "match_winner", "pick": "A", "score": 91}],
            }
        ]
    }
    filtered = _filter_shadow_feed(feed, {})
    assert filtered["matches"] == []
    assert filtered["matches_count"] == 0


def test_symphony_ui_does_not_render_missing_numeric_values_as_real_zero():
    assert "const nfmt=v=>Number(v||0)" not in SYMPHONY_UI
    assert "Number(data?.matches_count||0)" not in SYMPHONY_UI
    assert "Number(x?.learning_support_rows||0)" not in SYMPHONY_UI
