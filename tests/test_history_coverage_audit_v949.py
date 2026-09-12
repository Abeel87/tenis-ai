from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from history_coverage_audit import classify_player_history


def _long(*rows):
    return pd.DataFrame(rows, columns=["player", "player_key", "date"])


def test_reports_no_safe_identity_candidate_without_merging_token_hint():
    raw = _long(("Nicole Melichar", "nicole melichar", pd.Timestamp("2026-01-01")))
    item = classify_player_history(
        player="Nicole Melichar-Martinez",
        stats={"matches": 0, "quality": "LOW", "history_identity_mode": "none"},
        scheduled_time="2026-09-12T10:00:00Z",
        raw_long=raw,
        clean_long=raw,
    )
    assert item["reason"] == "no_safe_identity_candidate"
    assert item["raw"]["resolved_key"] is None
    assert "nicole melichar" in item["token_hints_raw"]["same_first_token"]


def test_reports_rows_removed_by_hygiene_before_any_identity_recovery():
    raw = _long(("Example Player", "example player", pd.Timestamp("2026-01-01")))
    clean = _long()
    item = classify_player_history(
        player="Example Player",
        stats={"matches": 0, "quality": "LOW", "history_identity_mode": "none"},
        scheduled_time="2026-09-12T10:00:00Z",
        raw_long=raw,
        clean_long=clean,
    )
    assert item["reason"] == "history_removed_by_hygiene"


def test_reports_future_only_history_without_relaxing_pre_match_cutoff():
    future = _long(("Future Player", "future player", pd.Timestamp("2026-09-13")))
    item = classify_player_history(
        player="Future Player",
        stats={"matches": 0, "quality": "LOW", "history_identity_mode": "exact"},
        scheduled_time="2026-09-12T10:00:00Z",
        raw_long=future,
        clean_long=future,
    )
    assert item["reason"] == "post_cutoff_only"
    assert item["pre_match"]["resolved_key"] is None


def test_reports_insufficient_sample_without_lowering_minimum_five():
    history = _long(("Thin Sample", "thin sample", pd.Timestamp("2026-01-01")))
    item = classify_player_history(
        player="Thin Sample",
        stats={"matches": 4, "quality": "LOW", "history_identity_mode": "exact"},
        scheduled_time="2026-09-12T10:00:00Z",
        raw_long=history,
        clean_long=history,
    )
    assert item["reason"] == "insufficient_pre_match_sample"


def test_reports_ambiguous_initial_as_ambiguous_not_a_merge():
    history = _long(
        ("Alexandra Panova", "alexandra panova", pd.Timestamp("2026-01-01")),
        ("Alina Panova", "alina panova", pd.Timestamp("2026-01-02")),
    )
    item = classify_player_history(
        player="A. Panova",
        stats={"matches": 0, "quality": "LOW", "history_identity_mode": "ambiguous"},
        scheduled_time="2026-09-12T10:00:00Z",
        raw_long=history,
        clean_long=history,
    )
    assert item["reason"] == "ambiguous_identity"
    assert sorted(item["raw"]["variant_candidates"]) == ["alexandra panova", "alina panova"]
