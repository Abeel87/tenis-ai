from __future__ import annotations

import json

from scripts.prune_results_payload_v854 import prune_results, prune_rows


def _profile(name: str):
    return {
        "player": name,
        "available": True,
        "all": {"10": {"sample_matches": 10, "metrics": {"match_win": {"hits": 6, "n": 10, "pct": 60.0}}}},
        "surface": {"10": {"sample_matches": 7, "metrics": {"match_win": {"hits": 5, "n": 7, "pct": 71.4}}}},
        "recent_matches": [{"opponent": "X", "won": True}] * 20,
        "recent_surface_matches": [{"opponent": "Y", "won": False}] * 7,
        "trend": {"all": {"match_win": 5.0}, "surface": {"match_win": 8.0}},
    }


def test_v854_prunes_only_duplicated_raw_tendency_rows():
    rows = [{
        "id": 123,
        "p1": "Alpha",
        "p2": "Beta",
        "match_win": {"p1": 0.61, "p2": 0.39},
        "superbet_market_v91": {"operator_verified": True, "prices_used": False},
        "tendencies_v71": {"version": "v7.1", "p1": _profile("Alpha"), "p2": _profile("Beta")},
    }]

    stats = prune_rows(rows)

    assert stats["affected_profiles"] == 2
    assert stats["removed_fields"] == 4
    assert stats["removed_items"] == 54
    for side in ("p1", "p2"):
        profile = rows[0]["tendencies_v71"][side]
        assert "recent_matches" not in profile
        assert "recent_surface_matches" not in profile
        assert profile["all"]["10"]["metrics"]["match_win"]["pct"] in (60.0, 60)
        assert profile["surface"]["10"]["sample_matches"] == 7
        assert profile["trend"]
    assert rows[0]["match_win"] == {"p1": 0.61, "p2": 0.39}
    assert rows[0]["superbet_market_v91"]["prices_used"] is False


def test_v854_file_prune_is_idempotent_and_compact(tmp_path):
    path = tmp_path / "results.json"
    payload = [{"id": 1, "tendencies_v71": {"p1": _profile("A"), "p2": _profile("B")}}]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    first = prune_results(path)
    after_first = path.read_bytes()
    second = prune_results(path)
    after_second = path.read_bytes()

    assert first["status"] == "ok"
    assert first["saved_bytes"] > 0
    assert second["removed_fields"] == 0
    assert after_first == after_second
    assert b"recent_matches" not in after_first
    assert b"recent_surface_matches" not in after_first
