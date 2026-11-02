from __future__ import annotations

import pandas as pd

import tml_2024_candidate_lock as task017
from history_hygiene_v78a import clean_history


def _row(date, tourney, winner, loser, score="6-4 6-4", **extra):
    row = {
        "tourney_date": date,
        "tourney_name": tourney,
        "surface": "Hard",
        "winner_name": winner,
        "loser_name": loser,
        "score": score,
        "winner_rank": 10,
        "loser_rank": 20,
        "source_tour": extra.pop("source_tour", "ATP"),
        "source_key": extra.pop("source_key", "atp_2024"),
        "winner_id": extra.pop("winner_id", "W1"),
        "loser_id": extra.pop("loser_id", "L1"),
    }
    for side in ("w", "l"):
        row.update({
            f"{side}_svpt": 60,
            f"{side}_1stIn": 36,
            f"{side}_1stWon": 25,
            f"{side}_2ndWon": 12,
            f"{side}_SvGms": 10,
            f"{side}_bpSaved": 3,
            f"{side}_bpFaced": 4,
        })
    row.update(extra)
    return row


def test_frame_hash_ignores_column_order_and_can_ignore_row_order():
    left = pd.DataFrame([{"b": 2, "a": 1}, {"b": 4, "a": 3}])
    reordered = left[["a", "b"]]
    reversed_rows = left.iloc[::-1].reset_index(drop=True)
    assert task017._frame_hash(left) == task017._frame_hash(reordered)
    assert task017._frame_hash(left) != task017._frame_hash(reversed_rows)
    assert task017._frame_hash(left, sort_rows=True) == task017._frame_hash(reversed_rows, sort_rows=True)


def test_task016_manifest_materialization_applies_year_hygiene_blockers_and_dedupe():
    baseline_raw = pd.DataFrame([_row("20250101", "Baseline", "Baseline A", "Baseline B")])
    baseline_clean, _ = clean_history(baseline_raw)
    manifest = {
        "task016_rules": {
            "year": 2024,
            "exclude_player_keys": ["blocked player"],
            "exclude_score_identities": [["ATP", "20240303", "Conflict", "Score Winner", "Score Loser"]],
        }
    }
    rows = [
        _row("20231231", "Wrong Year", "Old A", "Old B"),
        _row("20240101", "Retired", "Retired A", "Retired B", score="6-4 RET"),
        _row("20240202", "Blocked", "Blocked Player", "Other"),
        _row("20240303", "Conflict", "Score Winner", "Score Loser"),
        _row("20240404", "Keep", "Keep A", "Keep B"),
        _row("20240404", "Keep", "Keep A", "Keep B"),
    ]
    archive = pd.DataFrame(rows)
    archive["source_row_number"] = range(2, len(archive) + 2)
    candidate, details = task017._materialize_task016_manifest_candidate(
        baseline_clean=baseline_clean, archive_raw=archive, manifest=manifest
    )
    assert len(candidate) == 1
    assert candidate.iloc[0]["tourney_name"] == "Keep"
    assert details["excluded_row_reason_counts"] == {"resolution_change": 1, "score_conflict": 1}
    assert details["dedupe"]["removed_internal_duplicates"] == 1


def test_global_hardening_removes_only_proven_id_shadow_and_visible_resolution_rows():
    candidate = pd.DataFrame([
        _row("20240101", "ID New", "Ivan Denisov", "Other A", source_tour="CH", source_key="ch_2024", winner_id="D09V"),
        _row("20240102", "ID Baseline", "Ivan Denisov", "Other B", source_tour="CH", source_key="ch_2024", winner_id="DB63"),
        _row("20240103", "Shadow", "Nicolas Alvarez", "Other C", source_tour="CH", source_key="ch_2024"),
        _row("20240104", "Visible", "Alexandre Reco", "Other D", source_tour="CH", source_key="ch_2024"),
        _row("20240105", "Keep", "Safe Player", "Other E", source_tour="CH", source_key="ch_2024"),
    ])
    manifest = {
        "global_hardening": {
            "exclude_archive_id_evidence": [
                {"namespace": "CH", "player_key": "ivan denisov", "archive_new_ids": ["D09V"]}
            ],
            "exclude_exact_shadow_player_keys": ["nicolas alvarez"],
            "exclude_visible_resolution_player_keys": ["alexandre reco"],
        }
    }
    hardened, details = task017._apply_global_hardening(candidate, manifest)
    assert list(hardened["tourney_name"]) == ["ID Baseline", "Keep"]
    assert details["removed_rows"] == 3
    assert details["reason_counts"] == {
        "archive_id_conflict": 1,
        "exact_shadow": 1,
        "visible_resolution_change": 1,
    }
    assert details["visible_resolution_evidence_matches"] == {"alexandre reco": 1}
    assert details["all_evidence_matched"] is True


def test_exact_shadow_collision_detects_new_exact_key_that_was_baseline_variant():
    baseline = pd.DataFrame([_row("20250101", "Baseline", "Carlos Alcaraz Garfia", "Other Player")])
    candidate = pd.DataFrame([_row("20240202", "Archive", "Carlos Alcaraz", "Different Player")])
    collisions = task017._exact_shadow_collisions(baseline, candidate)
    assert len(collisions) == 1
    assert collisions[0]["archive_exact_key"] == "carlos alcaraz"
    assert collisions[0]["baseline_variant_candidates"] == ["carlos alcaraz garfia"]


def test_archive_only_exclusions_are_frozen_and_require_actual_row_evidence():
    candidate = pd.DataFrame([
        _row("20240101", "Old only", "Archive Only", "Known Player"),
        _row("20240102", "Keep", "Known Player", "Other Known"),
    ])
    manifest = {"global_hardening": {"exclude_baseline_absent_player_keys": ["archive only"]}}
    hardened, details = task017._apply_global_hardening(candidate, manifest)
    assert list(hardened["tourney_name"]) == ["Keep"]
    assert details["baseline_absent_evidence_matches"] == {"archive only": 1}
    assert details["reason_counts"] == {"archive_only_identity": 1}
    assert details["all_evidence_matched"] is True

    manifest["global_hardening"]["exclude_baseline_absent_player_keys"].append("not in archive")
    _, details = task017._apply_global_hardening(candidate, manifest)
    assert details["unmatched_baseline_absent_evidence"] == ["not in archive"]
    assert details["all_evidence_matched"] is False


def test_current_identity_review_checks_all_archive_players_without_name_expansion():
    baseline = pd.DataFrame([_row("20260101", "Current", "Carlos Alcaraz Garfia", "Known Player")])
    candidate = pd.DataFrame([
        _row("20240101", "Old", "Carlos Alcaraz", "Known Player"),
        _row("20240102", "Other", "Archive Only", "Known Player"),
    ])
    assert task017._archive_only_player_keys(baseline, candidate) == ["archive only", "carlos alcaraz"]


def test_lock_safety_rejects_archive_only_player_even_when_no_visible_fixture_uses_it():
    baseline = pd.DataFrame([_row("20260101", "Current", "Known Player", "Other Known")])
    archive = _row("20240101", "Old", "Archive Only", "Other Known", winner_id="A_ONLY")
    sources = task017.task014.TML_2024_SOURCES
    frames = {s["key"]: pd.DataFrame([archive]) if s["key"] == "atp_2024" else pd.DataFrame() for s in sources}
    counts = {s["key"]: int(s["key"] == "atp_2024") for s in sources}
    manifest = {
        "sources": [{k: s[k] for k in ("key", "tour", "url")} for s in sources],
        "task016_expected_shape": {"candidate_rows": 1, "source_counts": counts},
        "global_hardening": {"require_current_baseline_identity": True},
    }
    args = dict(results=[], archive_frames=frames, manifest=manifest,
                source_status=[{"fetch_success": True} for _ in sources])
    rejected = task017.build_report(baseline_raw=baseline, **args)
    assert rejected["summary"]["visible_resolution_changes"] == 0
    assert rejected["summary"]["archive_only_players"] == 1
    assert rejected["summary"]["candidate_lock_safety_verified"] is False

    current = _row("20260102", "Current 2", "Archive Only", "Other Known", winner_id="A_ONLY")
    verified = task017.build_report(baseline_raw=pd.concat([baseline, pd.DataFrame([current])]), **args)
    assert verified["summary"]["archive_only_players"] == 0
    assert verified["summary"]["candidate_lock_safety_verified"] is True


def test_task016_frozen_shape_is_independent_of_current_results_drift():
    candidate = pd.DataFrame([
        _row("20240101", "A", "A Player", "B Player", source_key="atp_2024"),
        _row("20240102", "B", "C Player", "D Player", source_key="ch_2024", source_tour="CH"),
    ])
    manifest = {
        "task016_expected_shape": {
            "candidate_rows": 2,
            "source_counts": {
                "atp_2024": 1,
                "atp_quali_2024": 0,
                "ch_2024": 1,
                "wta_2024": 0,
            },
        }
    }
    assert task017._task016_frozen_shape_matches(manifest, candidate) is True


def test_expectation_check_locks_only_stable_candidate_and_source_fingerprints():
    candidate = pd.DataFrame([_row("20240202", "Keep", "A Player", "B Player")])
    source_fp = [
        {"source_key": "atp_2024", "logical_sha256": "abc"},
        {"source_key": "atp_quali_2024", "logical_sha256": "def"},
        {"source_key": "ch_2024", "logical_sha256": "ghi"},
        {"source_key": "wta_2024", "logical_sha256": "jkl"},
    ]
    discovery = task017._expectation_check(manifest={"expected": {}}, candidate=candidate, source_fingerprints=source_fp)
    assert discovery["locked"] is False
    assert discovery["matches"] is False

    locked = task017._expectation_check(
        manifest={"expected": discovery["current"]}, candidate=candidate, source_fingerprints=source_fp
    )
    assert locked["locked"] is True
    assert locked["matches"] is True
    assert set(locked["current"]) == {
        "candidate_rows", "source_counts", "candidate_logical_sha256", "source_logical_sha256"
    }
