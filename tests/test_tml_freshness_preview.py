import json
from pathlib import Path

import pandas as pd

from backend import tml_freshness_preview as audit


def _history(rows=4):
    out = []
    for index in range(rows):
        out.append({
            "tourney_id": f"T{index}",
            "match_num": index,
            "tourney_date": 20260901 + index,
            "tourney_name": "Test",
            "surface": "Hard",
            "winner_name": "Alice Smith",
            "loser_name": f"Opponent {index}",
            "score": "6-4 6-4",
            "w_svpt": 60,
            "w_1stIn": 36,
            "w_1stWon": 26,
            "w_2ndWon": 12,
            "w_SvGms": 10,
            "w_bpSaved": 2,
            "w_bpFaced": 3,
            "l_svpt": 60,
            "l_1stIn": 36,
            "l_1stWon": 20,
            "l_2ndWon": 10,
            "l_SvGms": 10,
            "l_bpSaved": 1,
            "l_bpFaced": 3,
        })
    return pd.DataFrame(out)


def _write_cache(root: Path, frame: pd.DataFrame):
    root.mkdir(parents=True, exist_ok=True)
    frame.to_csv(root / "atp_2026.csv.gz", index=False, compression="gzip")
    (root / "manifest.json").write_text(json.dumps({
        "sources": {"atp_2026": {"fetched_at": "2026-09-17T00:00:00+00:00", "rows": len(frame)}}
    }), encoding="utf-8")


def _write_results(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([{
        "id": "fixture-1",
        "scheduled_time": "2026-09-18T10:00:00+00:00",
        "p1": "Alice Smith",
        "p2": "Other Player",
        "p1_stats": {"matches": 4, "quality": "LOW", "history_identity_mode": "exact"},
        "p2_stats": {"matches": 0, "quality": "LOW", "history_identity_mode": "none"},
    }]), encoding="utf-8")


def test_signature_uses_match_identity_columns():
    frame = _history(1)
    signature = next(iter(audit._signatures(frame)))
    assert signature[0] == "T0"
    assert "Alice Smith" in signature
    assert "6-4 6-4" in signature


def test_preview_can_reach_minimum_without_writing_cache(tmp_path):
    cache = tmp_path / "cache"
    baseline = _history(4)
    fresh = _history(5)
    _write_cache(cache, baseline)
    results = tmp_path / "results.json"
    _write_results(results)
    original = (cache / "atp_2026.csv.gz").read_bytes()

    report = audit.build_report(
        cache_root=cache,
        results_path=results,
        downloader=lambda url: fresh.copy(),
    )

    assert report["policy"]["live_tennis_api_calls"] == 0
    assert report["policy"]["production_cache_writes"] == 0
    assert report["decision"]["runtime_change"] is False
    assert report["summary"]["refresh_attempts"] == 7
    assert report["summary"]["refresh_success"] == 7
    assert report["summary"]["players_reaching_minimum_5"] == 1
    row = report["priority"]["reaches_minimum_5"][0]
    assert row["player"] == "Alice Smith"
    assert row["baseline_clean_pre_match_rows"] == 4
    assert row["preview_clean_pre_match_rows"] == 5
    assert row["identity_stable"] is True
    assert (cache / "atp_2026.csv.gz").read_bytes() == original


def test_preview_fails_identity_change_closed(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    baseline = _history(4)
    _write_cache(cache, baseline)
    results = tmp_path / "results.json"
    _write_results(results)

    # Baseline uses the exact same stored/current resolver path as TASK 005.
    # Preview independently resolves the fresh history and must fail closed if
    # that key is no longer identical.
    monkeypatch.setattr(
        audit.task005,
        "_resolved_key",
        lambda clean_long, case: ("alice smith", "exact"),
    )
    monkeypatch.setattr(
        audit,
        "_resolved_key",
        lambda long_df, player: ("different key", "expanded-name"),
    )

    report = audit.build_report(cache_root=cache, results_path=results, downloader=lambda url: _history(5))
    assert report["summary"]["identity_changed_fail_closed"] == 1
    assert report["summary"]["players_reaching_minimum_5"] == 0


def test_provider_outage_is_reported_without_mutation(tmp_path):
    cache = tmp_path / "cache"
    baseline = _history(4)
    _write_cache(cache, baseline)
    results = tmp_path / "results.json"
    _write_results(results)

    def broken(url):
        raise RuntimeError("offline")

    report = audit.build_report(cache_root=cache, results_path=results, downloader=broken)
    assert report["summary"]["refresh_success"] == 0
    assert report["summary"]["refresh_failures"] == 7
    assert report["summary"]["players_reaching_minimum_5"] == 0
    assert report["policy"]["fresh_data_authorized_for_runtime"] is False
