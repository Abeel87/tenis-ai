import gzip
import json
from pathlib import Path

from backend import existing_history_source_inventory as audit


def _write_json_gz(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(value, handle)


def test_known_sources_remain_two_provider_families(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    with gzip.open(cache / "atp_2026.csv.gz", "wt", encoding="utf-8") as handle:
        handle.write("winner_name,loser_name,tourney_date,score\nA,B,20260901,6-4 6-4\n")
    _write_json_gz(
        cache / "pbp_v7/matches/123.json.gz",
        {"match": {"id": 123}, "points": []},
    )
    (cache / "pbp_v7/players.json").parent.mkdir(parents=True, exist_ok=True)
    (cache / "pbp_v7/players.json").write_text("{}", encoding="utf-8")

    report = audit.build_inventory(cache)

    assert report["policy"]["network_calls"] == 0
    assert report["summary"]["known_independent_provider_families"] == 2
    assert report["third_known_provider_families"] == []
    assert report["provider_counts"]["tennismylife"] == 1
    assert report["provider_counts"]["live_tennis_api_pbp"] == 1
    assert report["provider_counts"]["live_tennis_api_pbp_state"] == 1


def test_rebuildable_raw_like_json_is_flagged_not_authorized(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "unknown_matches.json").write_text(json.dumps({
        "rows": [{
            "winner_name": "Alice",
            "loser_name": "Bob",
            "tourney_date": "20260901",
            "score": "6-4 6-4",
        }]
    }), encoding="utf-8")

    report = audit.build_inventory(cache)

    assert report["summary"]["raw_like_unproven_files"] == 1
    assert report["raw_like_unproven"][0]["logical_path"] == "unknown_matches.json"
    assert report["decision"]["authorize_new_history_source"] is False
    assert report["policy"]["raw_like_is_not_proven_raw"] is True


def test_state_json_is_not_mistaken_for_raw_history(tmp_path):
    cache = tmp_path / "cache"
    path = cache / "pbp_v7/history_backfill_v83.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"cursor_date": "2024-01-01", "offset": 0}), encoding="utf-8")

    report = audit.build_inventory(cache)

    assert report["summary"]["raw_like_unproven_files"] == 0
    assert report["rebuildable_role_counts"]["state_or_scheduler"] == 1
    assert report["summary"]["third_known_provider_families"] == 0
