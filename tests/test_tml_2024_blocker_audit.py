from __future__ import annotations

import pandas as pd

from backend import tml_2024_blocker_audit as audit


def _match_row(*, tour: str, date: str, tourney: str, winner: str, loser: str, score: str, winner_id=None, loser_id=None):
    return {
        "source_tour": tour,
        "tourney_date": date,
        "tourney_name": tourney,
        "winner_name": winner,
        "loser_name": loser,
        "score": score,
        "winner_id": winner_id,
        "loser_id": loser_id,
    }


def test_id_conflicts_distinguish_baseline_only_from_archive_introduced():
    baseline = pd.DataFrame([
        _match_row(tour="ATP", date="20250101", tourney="A", winner="Alex One", loser="X", score="6-0 6-0", winner_id="A1"),
        _match_row(tour="ATP", date="20250102", tourney="B", winner="Alex One", loser="Y", score="6-0 6-0", winner_id="A2"),
        _match_row(tour="ATP", date="20250103", tourney="C", winner="Beth Two", loser="Z", score="6-0 6-0", winner_id="B1"),
    ])
    archive = pd.DataFrame([
        _match_row(tour="ATP", date="20240101", tourney="D", winner="Alex One", loser="Q", score="6-0 6-0", winner_id="A1"),
        _match_row(tour="ATP", date="20240102", tourney="E", winner="Beth Two", loser="R", score="6-0 6-0", winner_id="B2"),
    ])
    rows = audit._classify_id_conflicts(baseline, archive, {"alex one", "beth two"})
    by_player = {row["player_key"]: row for row in rows}

    assert by_player["alex one"]["classification"] == "baseline_only"
    assert by_player["alex one"]["archive_involved"] is False
    assert by_player["beth two"]["classification"] == "archive_introduced"
    assert by_player["beth two"]["archive_new_ids"] == ["B2"]


def test_score_conflicts_distinguish_baseline_only_from_archive_introduced():
    baseline = pd.DataFrame([
        _match_row(tour="ATP", date="20250101", tourney="A", winner="A", loser="B", score="6-0 6-0"),
        _match_row(tour="ATP", date="20250101", tourney="A", winner="A", loser="B", score="6-1 6-1"),
        _match_row(tour="ATP", date="20250102", tourney="B", winner="C", loser="D", score="6-0 6-0"),
    ])
    archive = pd.DataFrame([
        _match_row(tour="ATP", date="20250101", tourney="A", winner="A", loser="B", score="6-0 6-0"),
        _match_row(tour="ATP", date="20250102", tourney="B", winner="C", loser="D", score="6-2 6-2"),
        _match_row(tour="CH", date="20240103", tourney="C", winner="E", loser="F", score="6-0 6-0"),
        _match_row(tour="CH", date="20240103", tourney="C", winner="E", loser="F", score="6-3 6-3"),
    ])
    rows = audit._classify_score_conflicts(baseline, archive)
    by_identity = {tuple(row["identity"]): row for row in rows}

    assert by_identity[("ATP", "20250101", "A", "A", "B")]["classification"] == "baseline_only"
    assert by_identity[("ATP", "20250102", "B", "C", "D")]["classification"] == "archive_introduced"
    assert by_identity[("CH", "20240103", "C", "E", "F")]["classification"] == "archive_introduced"


def test_date_blocker_reports_exact_source_and_year():
    archive = pd.DataFrame([
        {
            **_match_row(tour="ATP", date="20240101", tourney="A", winner="A", loser="B", score="6-0 6-0"),
            "source_key": "atp_2024",
            "source_row_number": 2,
        },
        {
            **_match_row(tour="ATP", date="20231231", tourney="B", winner="C", loser="D", score="6-0 6-0"),
            "source_key": "atp_2024",
            "source_row_number": 3,
        },
    ])
    report = audit._date_blocker_details(archive)

    assert report["total_out_of_2024_rows"] == 1
    assert report["rows"][0]["tourney_date"] == "20231231"
    assert report["rows"][0]["parsed_year"] == 2023
    source = next(row for row in report["sources"] if row["source_key"] == "atp_2024")
    assert source["out_of_2024_rows"] == 1
    assert source["years"] == {"2023": 1}


def test_archive_dedupe_removes_baseline_overlap_and_internal_duplicate():
    baseline = pd.DataFrame([
        _match_row(tour="ATP", date="20240101", tourney="A", winner="A", loser="B", score="6-0 6-0"),
    ])
    archive = pd.DataFrame([
        _match_row(tour="ATP", date="20240101", tourney="A", winner="A", loser="B", score="6-0 6-0"),
        _match_row(tour="ATP", date="20240102", tourney="B", winner="C", loser="D", score="6-1 6-1"),
        _match_row(tour="ATP", date="20240102", tourney="B", winner="C", loser="D", score="6-1 6-1"),
    ])
    deduped, stats = audit._dedupe_archive(archive, baseline)

    assert len(deduped) == 1
    assert stats["removed_baseline_overlaps"] == 1
    assert stats["removed_internal_duplicates"] == 1
    assert stats["rows_after_dedupe"] == 1
