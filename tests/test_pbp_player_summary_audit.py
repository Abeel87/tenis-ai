import json
from pathlib import Path

from backend import pbp_player_summary_audit as audit


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _results(matches=4, scheduled="2026-09-17T12:00:00Z"):
    return [
        {
            "id": 9001,
            "scheduled_time": scheduled,
            "p1": "Alice Example",
            "p2": "Other Player",
            "p1_stats": {
                "matches": matches,
                "history_identity_mode": "exact",
                "history_player_key": "alice example",
            },
            "p2_stats": {"matches": 0, "history_identity_mode": "none"},
        }
    ]


def _summary(mid=101, scheduled="2026-09-10T10:00:00Z", **extra):
    row = {
        "id": mid,
        "scheduled_time": scheduled,
        "is_doubles": False,
        "tape": {
            "coverage": "from_start",
            "starts_at_love": True,
            "completeness": 1.0,
            "rows": 120,
        },
    }
    row.update(extra)
    return row


def test_summary_only_supply_is_upper_bound_not_runtime_history(tmp_path):
    cache = tmp_path / "cache"
    index = cache / "pbp_v7" / "players.json"
    results = tmp_path / "results.json"
    _write_json(results, _results(matches=4))
    _write_json(
        index,
        {
            "players": {
                "alice example": {
                    "player": "Alice Example",
                    "player_id": 77,
                    "matches": [_summary()],
                }
            }
        },
    )

    report = audit.build_report(cache_root=cache, index_path=index, results_path=results)

    assert report["policy"]["network_calls"] == 0
    assert report["policy"]["summary_metadata_authorized_as_history"] is False
    assert report["summary"]["short_history_players"] == 1
    assert report["summary"]["short_players_with_exact_index_identity"] == 1
    assert report["summary"]["summary_only_observations"] == 1
    assert report["summary"]["upper_bound_players_reaching_five"] == 1
    row = report["players"][0]
    assert row["summary_only"] == 1
    assert row["summary_only_metadata_only"] == 1
    assert row["upper_bound_reaches_five"] is True
    assert report["decision"]["runtime_change"] is False


def test_existing_local_tape_is_not_counted_as_summary_only(tmp_path):
    cache = tmp_path / "cache"
    index = cache / "pbp_v7" / "players.json"
    results = tmp_path / "results.json"
    _write_json(results, _results(matches=4))
    _write_json(
        index,
        {
            "players": {
                "alice example": {
                    "player": "Alice Example",
                    "player_id": 77,
                    "matches": [_summary(mid=101)],
                }
            }
        },
    )
    tape = cache / "pbp_v7" / "matches" / "101.json.gz"
    tape.parent.mkdir(parents=True, exist_ok=True)
    tape.write_bytes(b"already-cached")

    report = audit.build_report(cache_root=cache, index_path=index, results_path=results)
    row = report["players"][0]

    assert row["with_local_tape"] == 1
    assert row["summary_only"] == 0
    assert row["upper_bound_reaches_five"] is False


def test_post_cutoff_summary_is_rejected(tmp_path):
    cache = tmp_path / "cache"
    index = cache / "pbp_v7" / "players.json"
    results = tmp_path / "results.json"
    _write_json(results, _results(matches=3, scheduled="2026-09-17T12:00:00Z"))
    _write_json(
        index,
        {
            "players": {
                "alice example": {
                    "player": "Alice Example",
                    "player_id": 77,
                    "matches": [_summary(mid=102, scheduled="2026-09-18T10:00:00Z")],
                }
            }
        },
    )

    report = audit.build_report(cache_root=cache, index_path=index, results_path=results)
    row = report["players"][0]

    assert row["valid_pre_cutoff_summaries"] == 0
    assert row["summary_only"] == 0
    assert row["rejection_counts"]["not_pre_cutoff"] == 1


def test_index_identity_mismatch_fails_closed(tmp_path):
    cache = tmp_path / "cache"
    index = cache / "pbp_v7" / "players.json"
    results = tmp_path / "results.json"
    _write_json(results, _results(matches=4))
    _write_json(
        index,
        {
            "players": {
                "alice example": {
                    "player": "Different Name",
                    "player_id": 77,
                    "matches": [_summary()],
                }
            }
        },
    )

    report = audit.build_report(cache_root=cache, index_path=index, results_path=results)
    row = report["players"][0]

    assert row["index_identity_ok"] is False
    assert row["index_identity_reason"] == "entry_player_name_mismatch"
    assert row["summary_only"] == 0
    assert row["upper_bound_reaches_five"] is False


def test_summary_with_stats_is_reported_but_never_authorized(tmp_path):
    cache = tmp_path / "cache"
    index = cache / "pbp_v7" / "players.json"
    results = tmp_path / "results.json"
    _write_json(results, _results(matches=2))
    _write_json(
        index,
        {
            "players": {
                "alice example": {
                    "player": "Alice Example",
                    "player_id": 77,
                    "matches": [
                        _summary(
                            mid=103,
                            stats={"serve_points_won": 0.6},
                            score={"sets": [2, 0], "games": [12, 8]},
                        )
                    ],
                }
            }
        },
    )

    report = audit.build_report(cache_root=cache, index_path=index, results_path=results)
    row = report["players"][0]

    assert row["summary_only_with_stats_or_profiles"] == 1
    assert row["summary_only_metadata_only"] == 0
    assert report["policy"]["summary_metadata_authorized_as_history"] is False
    assert report["decision"]["authorize_summary_as_history"] is False
