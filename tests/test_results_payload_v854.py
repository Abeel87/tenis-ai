from __future__ import annotations

import json
from pathlib import Path

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


def _autolearn():
    signals = [
        {"key": "match_win|alpha", "market": "match_winner", "pick": "Alpha", "ensemble": 0.67},
        {"key": "set1_total|9.5|over", "market": "set1_total", "pick": "over", "line": 9.5, "ensemble": 0.64},
    ]
    return {
        "status": "active",
        "weights": {"current": 0.7, "catboost": 0.3},
        "signals": signals,
        "by_key": {row["key"]: row for row in signals},
    }


def test_v854_prunes_tendency_rows_and_only_verified_autolearn_index():
    rows = [{
        "id": 123,
        "p1": "Alpha",
        "p2": "Beta",
        "match_win": {"p1": 0.61, "p2": 0.39},
        "superbet_market_v91": {"operator_verified": True, "prices_used": False},
        "autolearn_v84": _autolearn(),
        "tendencies_v71": {"version": "v7.1", "p1": _profile("Alpha"), "p2": _profile("Beta")},
    }]
    original_signals = json.loads(json.dumps(rows[0]["autolearn_v84"]["signals"]))

    stats = prune_rows(rows)

    assert stats["affected_profiles"] == 2
    assert stats["removed_fields"] == 4
    assert stats["removed_items"] == 54
    assert stats["autolearn_by_key"]["removed_verified_indexes"] == 1
    assert stats["autolearn_by_key"]["mismatches_preserved"] == 0
    assert stats["autolearn_by_key"]["estimated_value_bytes_removed"] > 0
    for side in ("p1", "p2"):
        profile = rows[0]["tendencies_v71"][side]
        assert "recent_matches" not in profile
        assert "recent_surface_matches" not in profile
        assert profile["all"]["10"]["metrics"]["match_win"]["pct"] in (60.0, 60)
        assert profile["surface"]["10"]["sample_matches"] == 7
        assert profile["trend"]
    assert "by_key" not in rows[0]["autolearn_v84"]
    assert rows[0]["autolearn_v84"]["signals"] == original_signals
    assert rows[0]["autolearn_v84"]["weights"] == {"current": 0.7, "catboost": 0.3}
    assert rows[0]["match_win"] == {"p1": 0.61, "p2": 0.39}
    assert rows[0]["superbet_market_v91"] == {"operator_verified": True, "prices_used": False}


def test_v854_preserves_autolearn_index_if_it_is_not_exact_projection():
    auto = _autolearn()
    auto["by_key"]["match_win|alpha"] = {"key": "match_win|alpha", "ensemble": 0.99}
    rows = [{"id": 1, "autolearn_v84": auto}]
    original = json.loads(json.dumps(auto["by_key"]))

    stats = prune_rows(rows)

    assert stats["autolearn_by_key"]["removed_verified_indexes"] == 0
    assert stats["autolearn_by_key"]["mismatches_preserved"] == 1
    assert rows[0]["autolearn_v84"]["by_key"] == original
    assert len(rows[0]["autolearn_v84"]["signals"]) == 2


def test_v854_file_prune_is_idempotent_and_compact(tmp_path):
    path = tmp_path / "results.json"
    payload = [{
        "id": 1,
        "autolearn_v84": _autolearn(),
        "tendencies_v71": {"p1": _profile("A"), "p2": _profile("B")},
    }]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    first = prune_results(path)
    after_first = path.read_bytes()
    second = prune_results(path)
    after_second = path.read_bytes()

    assert first["status"] == "ok"
    assert first["saved_bytes"] > 0
    assert first["autolearn_by_key"]["removed_verified_indexes"] == 1
    assert second["removed_fields"] == 0
    assert second["autolearn_by_key"]["removed_verified_indexes"] == 0
    assert after_first == after_second
    assert b"recent_matches" not in after_first
    assert b"recent_surface_matches" not in after_first
    assert b'"by_key"' not in after_first
    assert b'"signals"' in after_first


def test_v854_frontend_keeps_signals_fallback_for_pruned_index():
    source = (Path(__file__).resolve().parents[1] / "frontend" / "autolearn-v84.js").read_text(encoding="utf-8")
    assert "a?.by_key?.[key]" in source
    assert "(a?.signals||[]).find" in source
