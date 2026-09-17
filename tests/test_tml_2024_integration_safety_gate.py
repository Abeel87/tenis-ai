from __future__ import annotations

import pandas as pd

from backend import tml_2024_history_preview as task014
from backend import tml_2024_integration_safety_gate as audit


def _row(
    *,
    date: int,
    winner: str,
    loser: str,
    winner_id: int,
    loser_id: int,
    tourney: str,
    score: str = "6-4 6-4",
) -> dict:
    row = {
        "tourney_date": date,
        "tourney_name": tourney,
        "surface": "Hard",
        "winner_name": winner,
        "loser_name": loser,
        "score": score,
        "winner_rank": 100,
        "loser_rank": 120,
        "winner_id": winner_id,
        "loser_id": loser_id,
    }
    for side in ("w", "l"):
        row.update({
            f"{side}_svpt": 60,
            f"{side}_1stIn": 36,
            f"{side}_1stWon": 26,
            f"{side}_2ndWon": 12,
            f"{side}_SvGms": 10,
            f"{side}_bpSaved": 3,
            f"{side}_bpFaced": 4,
        })
    return row


def _baseline() -> pd.DataFrame:
    rows = []
    for i in range(4):
        row = _row(
            date=20250101 + i,
            winner="Alpha Player",
            loser=f"Alpha Opponent {i}",
            winner_id=101,
            loser_id=1000 + i,
            tourney=f"Alpha {i}",
        )
        row["source_tour"] = "ATP"
        rows.append(row)
    for i in range(5):
        row = _row(
            date=20250201 + i,
            winner="Beta Player",
            loser=f"Beta Opponent {i}",
            winner_id=202,
            loser_id=2000 + i,
            tourney=f"Beta {i}",
        )
        row["source_tour"] = "ATP"
        rows.append(row)
    return pd.DataFrame(rows)


def _archives() -> dict[str, pd.DataFrame]:
    frames = {}
    for i, source in enumerate(task014.TML_2024_SOURCES):
        if source["key"] == "atp_2024":
            row = _row(
                date=20240115,
                winner="Alpha Player",
                loser="Archive Opponent",
                winner_id=101,
                loser_id=3001,
                tourney="Archive Alpha",
            )
        else:
            row = _row(
                date=20240210 + i,
                winner=f"Archive Winner {i}",
                loser=f"Archive Loser {i}",
                winner_id=4000 + i,
                loser_id=5000 + i,
                tourney=f"Archive {i}",
            )
        frames[source["key"]] = pd.DataFrame([row])
    return frames


def _results() -> list[dict]:
    return [{
        "id": "current-1",
        "scheduled_time": "2026-09-17T12:00:00Z",
        "p1": "Alpha Player",
        "p2": "Beta Player",
        "p1_stats": {
            "matches": 4,
            "history_identity_mode": "exact",
            "history_player_key": "alpha player",
        },
        "p2_stats": {
            "matches": 5,
            "history_identity_mode": "exact",
            "history_player_key": "beta player",
        },
    }]


def test_schema_status_requires_model_history_columns():
    good = _archives()["atp_2024"]
    assert audit.source_schema_status(good)["model_schema_compatible"] is True
    bad = good.drop(columns=["w_svpt"])
    status = audit.source_schema_status(bad)
    assert status["model_schema_compatible"] is False
    assert status["missing_model_history_columns"] == ["w_svpt"]


def test_date_status_rejects_rows_outside_2024():
    frame = _archives()["atp_2024"].copy()
    frame.loc[0, "tourney_date"] = 20231231
    status = audit.source_date_status(frame)
    assert status["out_of_2024_rows"] == 1
    assert status["only_2024"] is False


def test_compare_resolution_maps_fails_closed_on_changed_key():
    before = {"a": {"player": "A", "resolved_key": "alpha", "mode": "exact"}}
    after = {"a": {"player": "A", "resolved_key": "adam", "mode": "alias"}}
    changes = audit.compare_resolution_maps(before, after)
    assert len(changes) == 1
    assert changes[0]["baseline_resolved_key"] == "alpha"
    assert changes[0]["augmented_resolved_key"] == "adam"


def test_same_namespace_multiple_ids_for_current_key_is_conflict():
    frame = pd.DataFrame([
        {**_row(date=20240101, winner="Alpha Player", loser="X", winner_id=101, loser_id=1, tourney="A"), "source_tour": "ATP"},
        {**_row(date=20240201, winner="Alpha Player", loser="Y", winner_id=999, loser_id=2, tourney="B"), "source_tour": "ATP"},
    ])
    conflicts = audit._current_key_id_conflicts(frame, {"alpha player"})
    assert len(conflicts) == 1
    assert conflicts[0]["ids"] == ["101", "999"]


def test_full_gate_counts_safe_four_to_five_and_match_ready_delta():
    frames = _archives()
    status = [{"key": source["key"], "fetch_success": True, "error": None} for source in task014.TML_2024_SOURCES]
    report = audit.build_report(
        baseline_raw=_baseline(),
        results=_results(),
        archive_frames=frames,
        source_status=status,
    )
    summary = report["summary"]
    assert summary["all_2024_sources_fetched"] is True
    assert summary["all_sources_model_schema_compatible"] is True
    assert summary["all_source_rows_within_2024"] is True
    assert summary["baseline_resolution_changes"] == 0
    assert summary["current_player_same_namespace_id_conflicts"] == 0
    assert summary["match_identity_score_conflicts"] == 0
    assert summary["players_reaching_minimum_5"] == 1
    assert summary["newly_model_ready_matches"] == 1
    assert summary["integration_safety_gate_passed"] is True
    assert report["decision"]["runtime_change"] is False
    assert report["decision"]["authorize_2024_archive"] is False


def test_exact_duplicate_archive_row_does_not_create_score_conflict():
    frames = _archives()
    duplicate = frames["atp_2024"].iloc[[0]].copy()
    frames["atp_2024"] = pd.concat([frames["atp_2024"], duplicate], ignore_index=True)
    status = [{"key": source["key"], "fetch_success": True, "error": None} for source in task014.TML_2024_SOURCES]
    report = audit.build_report(
        baseline_raw=_baseline(),
        results=_results(),
        archive_frames=frames,
        source_status=status,
    )
    assert report["summary"]["archive_internal_duplicate_rows"] == 1
    assert report["summary"]["match_identity_score_conflicts"] == 0
    assert report["summary"]["newly_model_ready_matches"] == 1
