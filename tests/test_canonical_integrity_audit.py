from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.history_tracker import is_current_match
from backend.model import _match_distribution_conditional
from backend.superbet_candidate_settlement import LAYER as CANDIDATE_LAYER, capture_candidates
from backend.superbet_market_context import mapped_sanitize
from backend.superbet_playable import _filter_shadow_feed, _history_signal, operator_availability
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


def test_inactive_superbet_bookmaker_is_fail_closed_at_fixture_context_boundary():
    meta = {
        "1229": {
            "marketName": "Total Games Over Under",
            "outcomes": {"o": {"outcomeName": "Over"}},
        }
    }
    raw = {
        "fixtureId": "inactive-1",
        "participant1Name": "Alpha",
        "participant2Name": "Beta",
        "startTime": "2026-09-02T12:00:00Z",
        "bookmakerOdds": {
            "superbet.pl": {
                "bookmakerIsActive": False,
                "suspended": False,
                "markets": {
                    "1229": {
                        "marketActive": True,
                        "outcomes": {
                            "o": {"players": {"0": {"active": True, "bookmakerOutcomeId": "20.5/over"}}}
                        },
                    }
                },
            }
        },
    }
    fixture = mapped_sanitize(raw, meta)
    assert fixture is not None
    assert fixture["bookmaker_active"] is False
    assert fixture["suspended"] is True


def test_playable_line_market_requires_explicit_operator_line_verification():
    match = {
        "superbet_market_v91": {
            "status": "VERIFIED",
            "operator_verified": True,
            "canonical_selections": [
                {"market": "set1_total", "pick": "over", "line": 9.5, "operator_available": True},
                {"market": "match_winner", "pick": "Alpha", "operator_available": True},
            ],
        }
    }
    available = operator_availability(match)
    assert ("set1_total", "over", 9.5, 0, "") not in available
    assert any(sig[0] == "match_winner" for sig in available)


def test_candidate_evidence_requires_future_snapshot_and_verified_numeric_line():
    now = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
    future = (now + timedelta(hours=2)).isoformat()
    history = [{
        "match_key": "id:501", "match_id": 501, "id": 501,
        "scheduled_time": future, "status": "pending", "p1": "A", "p2": "B",
    }]
    base_ctx = {
        "status": "VERIFIED", "operator_verified": True,
        "coverage_shadow_signals": [
            {"market": "set_handicap", "pick": "A", "line": -1.5, "score": 72,
             "operator_available": True, "operator_line_verified": False},
        ],
        "model_signals": [],
    }
    results = [{"id": 501, "scheduled_time": future, "p1": "A", "p2": "B", "superbet_market_v91": base_ctx}]
    captured, stats = capture_candidates(history, results, now=now)
    assert stats["captured"] == 0
    assert CANDIDATE_LAYER not in captured[0]

    verified = dict(base_ctx)
    verified["coverage_shadow_signals"] = [
        {"market": "set_handicap", "pick": "A", "line": -1.5, "score": 72,
         "operator_available": True, "operator_line_verified": True},
    ]
    results[0] = {**results[0], "superbet_market_v91": verified}
    captured, stats = capture_candidates(history, results, now=now)
    assert stats["captured"] == 1
    assert captured[0][CANDIDATE_LAYER][0]["operator_line_verified"] is True

    late_history = [{**history[0], "scheduled_time": (now + timedelta(minutes=3)).isoformat()}]
    late_results = [{**results[0], "scheduled_time": late_history[0]["scheduled_time"]}]
    captured, stats = capture_candidates(late_history, late_results, now=now)
    assert stats["captured"] == 0
    assert CANDIDATE_LAYER not in captured[0]
