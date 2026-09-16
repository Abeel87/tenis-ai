from __future__ import annotations

from pathlib import Path

from backend.training_archive_inventory import build_inventory, classify_path


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_classification_is_narrow_and_raw_only():
    assert classify_path("atp_matches_2025.csv.gz") == (
        "historical_csv_raw",
        True,
        "historical_csv_upstream",
    )
    assert classify_path("history/atp_matches_2024.csv.gz")[1] is True
    assert classify_path("pbp_v7/matches/123.json.gz") == (
        "pbp_match_raw",
        True,
        "live_tennis_api",
    )
    assert classify_path("pbp_v7/players.json") == (
        "pbp_state",
        True,
        "live_tennis_api_index",
    )
    assert classify_path("pbp_v7/terminal_refresh.json")[1] is True

    assert classify_path("pbp_v7/matches/123.json")[1] is False
    assert classify_path("pbp_v7/debug.json")[1] is False
    assert classify_path("tabpfn_models/model.bin")[1] is False
    assert classify_path("frontend/data/results.json")[1] is False


def test_inventory_hashes_candidates_and_counts_rebuildable_bytes(tmp_path: Path):
    cache = tmp_path / "cache"
    shared = b"same"
    _write(cache / "atp_matches_2025.csv.gz", shared)
    _write(cache / "pbp_v7" / "matches" / "123.json.gz", shared)
    _write(cache / "pbp_v7" / "players.json", b"players")
    _write(cache / "pbp_v7" / "terminal_refresh.json", b"refresh")
    _write(cache / "tabpfn_models" / "model.bin", b"model-cache")
    _write(cache / "other.json", b"rebuild")

    inventory = build_inventory(cache)
    summary = inventory["summary"]

    assert summary["total_cache_files"] == 6
    assert summary["archive_candidate_files"] == 4
    assert summary["rebuildable_files"] == 2
    assert summary["archive_candidate_bytes"] == (len(shared) * 2 + len(b"players") + len(b"refresh"))
    assert summary["rebuildable_bytes"] == len(b"model-cache") + len(b"rebuild")

    # The content-addressed archive can store identical bytes once even if two
    # logical raw inputs point at the same digest.
    assert summary["duplicate_groups"] == 1
    assert summary["duplicate_files"] == 1
    assert summary["dedupe_savings_bytes"] == len(shared)
    assert summary["unique_archive_objects"] == 3

    candidates = inventory["archive_candidates"]
    assert [row["logical_path"] for row in candidates] == sorted(row["logical_path"] for row in candidates)
    assert all(len(row["sha256"]) == 64 for row in candidates)
    assert all("frontend/data" not in row["logical_path"] for row in candidates)


def test_inventory_is_deterministic_for_same_cache(tmp_path: Path):
    cache = tmp_path / "cache"
    _write(cache / "history" / "atp_matches_2023.csv.gz", b"raw-history")
    _write(cache / "pbp_v7" / "matches" / "42.json.gz", b"raw-pbp")
    _write(cache / "scratch" / "response.json", b"temporary")

    assert build_inventory(cache) == build_inventory(cache)


def test_missing_cache_is_empty_not_fabricated(tmp_path: Path):
    inventory = build_inventory(tmp_path / "missing")
    assert inventory["summary"]["total_cache_files"] == 0
    assert inventory["summary"]["archive_candidate_files"] == 0
    assert inventory["archive_candidates"] == []
