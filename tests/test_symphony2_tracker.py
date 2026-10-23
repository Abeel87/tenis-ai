from copy import deepcopy
from datetime import datetime, timezone

import pytest

from backend import symphony2_tracker as tracker
from backend.symphony2_tracker import capture, settle, performance_stats

NOW = datetime(2026, 8, 31, 9, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW
    monkeypatch.setattr(tracker, "datetime", Clock)


def _evidence():
    return {
        "id": 123, "p1": "A", "p2": "B",
        "scheduled_time": "2026-08-31T10:00:00Z",
        "status": "settled", "settled_at": "2026-08-31T12:00:00Z",
        "settlement_source": "Live Tennis API /matches/{id}",
        "settlement_version": "v7.8E5-retirement-partial",
    }


def _terminal():
    return {**_evidence(), "result": {
        "status": "completed", "p1": "A", "p2": "B", "winner": "A",
        "sets": [[6, 3], [7, 6]], "number_of_sets": 2,
        "total_games": 22, "match_score": "2:0", "first_set_score": "6:3",
    }}


def _current():
    return {
        "version": "symphony2-runtime-1",
        "matches": [{
            "id": 123,
            "p1": "A",
            "p2": "B",
            "scheduled_time": "2026-08-31T10:00:00Z",
            "recommended_leg_count": 2,
            "compositions": {
                "2": {
                    "legs": 2,
                    "score": 77.0,
                    "joint_probability": None,
                    "joint_status": "PENDING_EXACT_SHARED_STATE_ENGINE",
                    "dependency_diagnostics": {
                        "status": "EXACT_SHARED_STATE_DIAGNOSTIC_ONLY",
                        "ranking_influence": False,
                        "threshold_classification_enabled": False,
                        "joint_probability": 42.0,
                        "weakest_supervised_leg_selection_id": "b",
                        "weakest_state_leg_selection_id": "b",
                        "per_leg": [
                            {
                                "selection_id": "a",
                                "conditional_probability_given_other_legs": 80.0,
                                "joint_mass_removed_by_leg_pp": 10.0,
                            },
                            {
                                "selection_id": "b",
                                "conditional_probability_given_other_legs": 70.0,
                                "joint_mass_removed_by_leg_pp": 18.0,
                            },
                        ],
                        "pairs": [
                            {
                                "left_selection_id": "a",
                                "right_selection_id": "b",
                                "exact_pair_joint_probability": 42.0,
                                "redundancy_score": 0.6,
                                "conflict_score": 0.4,
                            }
                        ],
                    },
                    "selection": [
                        {"selection_id": "a", "market": "match_total", "pick": "over", "line": 21.5, "operator_model_probability": 72.0, "fixture_line_verified": True},
                        {"selection_id": "b", "market": "set1_total", "pick": "under", "line": 10.5, "operator_model_probability": 69.0, "fixture_line_verified": True},
                    ],
                }
            },
        }],
    }


def test_capture_starts_clean_and_deduplicates():
    doc, count = capture(_current(), {})
    assert count == 1
    assert doc["legacy_symphony_results_imported"] is False
    assert len(doc["entries"]) == 1

    again, count2 = capture(_current(), doc)
    assert count2 == 0
    assert len(again["entries"]) == 1


def test_exact_operator_signature_settles_composition():
    doc, _ = capture(_current(), {})
    base = [{
        **_evidence(),
        "playable_autolearn_signals_v912": [
            {"market": "match_total", "pick": "over", "line": 21.5, "result": "hit"},
            {"market": "set1_total", "pick": "under", "line": 10.5, "result": "hit"},
        ],
    }]
    settled, count = settle(doc, base)
    assert count == 1
    assert settled["entries"][0]["result"] == "hit"
    stats = performance_stats(settled)
    assert stats["compositions_settled"] == 1
    assert stats["composition_accuracy"] == 100.0
    assert stats["legacy_symphony_stats_used"] is False


def test_different_line_never_settles_prediction():
    doc, _ = capture(_current(), {})
    base = [{
        **_evidence(),
        "playable_signals_v912": [
            {"market": "match_total", "pick": "over", "line": 22.5, "result": "hit"},
            {"market": "set1_total", "pick": "under", "line": 10.5, "result": "hit"},
        ],
    }]
    settled, count = settle(doc, base)
    assert count == 0
    assert settled["entries"][0]["result"] == "pending"
    assert settled["entries"][0]["selection"][0]["result"] == "pending"


def test_capture_rejects_unverified_line():
    current = _current()
    current["matches"][0]["compositions"]["2"]["selection"][0]["fixture_line_verified"] = False
    doc, count = capture(current, {})
    assert count == 0
    assert doc["entries"] == []


def test_capture_rejects_missing_verification_bit():
    current = _current()
    current["matches"][0]["compositions"]["2"]["selection"][0].pop("fixture_line_verified")
    doc, count = capture(current, {})
    assert count == 0
    assert doc["entries"] == []



def test_capture_freezes_dependency_diagnostics_without_later_rewrite():
    current = _current()
    original = current["matches"][0]["compositions"]["2"]["dependency_diagnostics"]

    doc, count = capture(current, {})

    assert count == 1
    entry = doc["entries"][0]
    assert entry["dependency_evidence_status"] == "FROZEN_PREMATCH_EXACT_SHARED_STATE"
    assert entry["dependency_diagnostics"] == original

    # Mutating the live current document after capture must not rewrite the
    # prospective evidence already frozen in Symphony history.
    original["pairs"][0]["redundancy_score"] = 0.99
    assert entry["dependency_diagnostics"]["pairs"][0]["redundancy_score"] == 0.6

    again, count2 = capture(current, doc)
    assert count2 == 0
    assert again["entries"][0]["dependency_diagnostics"]["pairs"][0]["redundancy_score"] == 0.6


def test_settlement_preserves_frozen_dependency_evidence():
    doc, _ = capture(_current(), {})
    frozen = doc["entries"][0]["dependency_diagnostics"]
    base = [{
        **_evidence(),
        "playable_autolearn_signals_v912": [
            {"market": "match_total", "pick": "over", "line": 21.5, "result": "hit"},
            {"market": "set1_total", "pick": "under", "line": 10.5, "result": "miss"},
        ],
    }]

    settled, count = settle(doc, base)

    assert count == 1
    assert settled["entries"][0]["result"] == "miss"
    assert settled["entries"][0]["dependency_diagnostics"] == frozen


def test_performance_stats_reports_prospective_dependency_evidence_counts():
    doc, _ = capture(_current(), {})
    pending_stats = performance_stats(doc)
    evidence = pending_stats["dependency_evidence"]
    assert evidence["predictions_with_frozen_diagnostics"] == 1
    assert evidence["settled_predictions_with_frozen_diagnostics"] == 0
    assert evidence["pair_observations_frozen"] == 1
    assert evidence["settled_pair_observations"] == 0
    assert evidence["prospective_only"] is True
    assert evidence["threshold_calibration_enabled"] is False
    assert evidence["ranking_influence"] is False

    base = [{
        **_evidence(),
        "playable_autolearn_signals_v912": [
            {"market": "match_total", "pick": "over", "line": 21.5, "result": "hit"},
            {"market": "set1_total", "pick": "under", "line": 10.5, "result": "hit"},
        ],
    }]
    settled, _ = settle(doc, base)
    settled_evidence = performance_stats(settled)["dependency_evidence"]
    assert settled_evidence["settled_predictions_with_frozen_diagnostics"] == 1
    assert settled_evidence["settled_pair_observations"] == 1


def test_legacy_history_without_dependency_block_remains_valid():
    current = _current()
    current["matches"][0]["compositions"]["2"].pop("dependency_diagnostics")

    doc, count = capture(current, {})

    assert count == 1
    entry = doc["entries"][0]
    assert entry["dependency_diagnostics"] is None
    assert entry["dependency_evidence_status"] == "NOT_AVAILABLE"
    evidence = performance_stats(doc)["dependency_evidence"]
    assert evidence["predictions_with_frozen_diagnostics"] == 0



def test_prospective_pair_calibration_uses_frozen_exact_joint_and_settled_results():
    current = _current()
    current["matches"][0]["compositions"]["2"]["joint_probability"] = 42.0
    doc, _ = capture(current, {})
    base = [{
        **_evidence(),
        "playable_autolearn_signals_v912": [
            {"market": "match_total", "pick": "over", "line": 21.5, "result": "hit"},
            {"market": "set1_total", "pick": "under", "line": 10.5, "result": "hit"},
        ],
    }]

    settled, _ = settle(doc, base)
    calibration = performance_stats(settled)["dependency_evidence"]["settlement_calibration"]

    assert calibration["status"] == "PROSPECTIVE_SETTLEMENT_CALIBRATION_DIAGNOSTIC_ONLY"
    assert calibration["prospective_only"] is True
    assert calibration["threshold_selection_enabled"] is False
    assert calibration["ranking_influence"] is False

    composition = calibration["composition_joint"]
    assert composition["settled"] == 1
    assert composition["hits"] == 1
    assert composition["observed_hit_rate"] == 100.0
    assert composition["mean_predicted_probability"] == 42.0
    assert composition["brier"] == 0.3364

    pair = calibration["exact_pair_joint"]
    assert pair["settled"] == 1
    assert pair["hits"] == 1
    assert pair["observed_hit_rate"] == 100.0
    assert pair["mean_predicted_probability"] == 42.0
    assert pair["brier"] == 0.3364

    bucket = calibration["by_redundancy_decile"]["0.6-0.7"]
    assert bucket["settled"] == 1
    assert bucket["hits"] == 1
    assert calibration["score_source"] == "FROZEN_PREMATCH_EXACT_SHARED_STATE"


def test_pair_calibration_marks_joint_miss_when_either_settled_leg_misses():
    doc, _ = capture(_current(), {})
    base = [{
        **_evidence(),
        "playable_autolearn_signals_v912": [
            {"market": "match_total", "pick": "over", "line": 21.5, "result": "hit"},
            {"market": "set1_total", "pick": "under", "line": 10.5, "result": "miss"},
        ],
    }]

    settled, _ = settle(doc, base)
    pair = performance_stats(settled)["dependency_evidence"]["settlement_calibration"]["exact_pair_joint"]

    assert pair["settled"] == 1
    assert pair["hits"] == 0
    assert pair["misses"] == 1
    assert pair["observed_hit_rate"] == 0.0
    assert pair["mean_predicted_probability"] == 42.0
    assert pair["brier"] == 0.1764


def test_pair_calibration_excludes_void_or_pending_leg_pairs():
    doc, _ = capture(_current(), {})
    base = [{
        **_evidence(),
        "playable_autolearn_signals_v912": [
            {"market": "match_total", "pick": "over", "line": 21.5, "result": "hit"},
            {"market": "set1_total", "pick": "under", "line": 10.5, "result": "void"},
        ],
    }]

    settled, _ = settle(doc, base)
    calibration = performance_stats(settled)["dependency_evidence"]["settlement_calibration"]

    assert settled["entries"][0]["result"] == "hit"
    assert calibration["exact_pair_joint"]["settled"] == 0
    assert calibration["by_redundancy_decile"] == {}
    assert calibration["composition_joint"]["settled"] == 0


def test_terminal_match_settles_frozen_legs_without_upstream_selected_signals():
    doc, _ = capture(_current(), {})
    original = deepcopy(doc)
    resolved, count = settle(doc, [_terminal()])
    assert count == 1
    assert resolved["entries"][0]["result"] == "hit"
    assert [x["result"] for x in resolved["entries"][0]["selection"]] == ["hit", "hit"]
    assert resolved["entries"][0]["selection"][0]["settlement_owner"] == "signal_settlement.settle_signal_live"
    assert doc == original
    assert resolved["entries"][0]["dependency_diagnostics"] == original["entries"][0]["dependency_diagnostics"]


def test_completed_loss_still_backfills_unresolved_legs_without_rewriting_loss():
    doc, _ = capture(_current(), {})
    entry = doc["entries"][0]
    entry.update(result="miss", settled_at="original-terminal-time")
    entry["selection"][0]["result"] = "miss"
    resolved, count = settle(doc, [_terminal()])
    assert count == 0
    entry = resolved["entries"][0]
    assert entry["result"] == "miss"
    assert entry["settled_at"] == "original-terminal-time"
    assert [x["result"] for x in entry["selection"]] == ["miss", "hit"]
    again, count = settle(resolved, [_terminal()])
    assert again == resolved
    assert count == 0


@pytest.mark.parametrize("change", [
    {"id": 124}, {"scheduled_time": "2026-08-31T11:00:00Z"},
    {"p1": "Other"}, {"p1": "B", "p2": "A"},
    {"settlement_source": None}, {"settlement_version": None},
    {"settled_at": "2026-08-31T09:59:59Z"}, {"status": "pending"},
    {"result": {"status": "completed"}},
])
def test_terminal_match_requires_exact_identity_and_terminal_provenance(change):
    doc, _ = capture(_current(), {})
    resolved, count = settle(doc, [{**_terminal(), **change}])
    assert count == 0
    assert resolved["entries"][0]["result"] == "pending"
    assert all(x["result"] == "pending" for x in resolved["entries"][0]["selection"])
    assert resolved["entries"][0]["settlement_pending_reason"]


def test_ambiguous_match_and_conflicting_operator_labels_fail_closed():
    doc, _ = capture(_current(), {})
    evidence = _terminal()
    resolved, count = settle(doc, [evidence, deepcopy(evidence)])
    assert count == 0
    assert resolved["entries"][0]["result"] == "pending"
    evidence = _evidence()
    leg = doc["entries"][0]["selection"][0]
    evidence["playable_signals_v912"] = [{**leg, "result": "hit"}]
    evidence["playable_autolearn_signals_v912"] = [{**leg, "result": "miss"}]
    resolved, count = settle(doc, [evidence])
    assert count == 0
    assert resolved["entries"][0]["selection"][0]["result"] == "pending"


def test_final_scores_never_invent_checkpoint_results():
    current = _current()
    current["matches"][0]["compositions"]["2"]["selection"][0].update(
        market="game_state", checkpoint=6, pick="3:3", line=None)
    doc, _ = capture(current, {})
    resolved, count = settle(doc, [_terminal()])
    assert count == 0
    assert resolved["entries"][0]["selection"][0]["result"] == "pending"
    assert resolved["entries"][0]["selection"][1]["result"] == "hit"


@pytest.mark.parametrize("scheduled", [None, "bad-date", "2026-08-31T08:59:59Z", "2026-08-31T09:00:00Z"])
def test_capture_requires_proven_future_start(scheduled):
    current = _current()
    current["matches"][0]["scheduled_time"] = scheduled
    doc, count = capture(current, {})
    assert count == 0
    assert doc["entries"] == []


def test_calibration_excludes_incomplete_and_nonprematch_evidence():
    current = _current()
    current["matches"][0]["compositions"]["2"]["joint_probability"] = 42.0
    doc, _ = capture(current, {})
    entry = doc["entries"][0]
    entry["result"] = "miss"
    entry["selection"][0]["result"] = "miss"
    stats = performance_stats(doc)
    assert stats["compositions_settled"] == 1  # Operational loss is still real.
    assert stats["compositions_with_unresolved_legs"] == 1
    assert stats["dependency_evidence"]["settlement_calibration"]["composition_joint"]["settled"] == 0
    entry["selection"][1]["result"] = "hit"
    entry["captured_at"] = entry["scheduled_time"]
    calibration = performance_stats(doc)["dependency_evidence"]["settlement_calibration"]
    assert calibration["composition_joint"]["settled"] == 0
    assert calibration["exact_pair_joint"]["settled"] == 0


def test_nonprematch_legacy_capture_does_not_gain_new_settlement_evidence():
    doc, _ = capture(_current(), {})
    doc["entries"][0]["captured_at"] = doc["entries"][0]["scheduled_time"]
    resolved, count = settle(doc, [_terminal()])
    assert count == 0
    assert resolved["entries"][0]["settlement_pending_reason"] == "NOT_PROVEN_PREMATCH"
    assert all(x["result"] == "pending" for x in resolved["entries"][0]["selection"])
