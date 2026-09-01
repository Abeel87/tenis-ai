import json

from backend import pbp_cache_recovery_v941 as recovery


def _profile(name):
    metrics = {
        "hold1": {"n": 5, "pct": 80.0},
        "hold2": {"n": 5, "pct": 80.0},
        "hold3": {"n": 5, "pct": 80.0},
        "after2_11": {"n": 5, "pct": 70.0},
        "after4_22": {"n": 5, "pct": 60.0},
        "after6_33": {"n": 5, "pct": 50.0},
        "sequence_11_22_33": {"n": 5, "pct": 40.0},
        "set1_win": {"n": 5, "pct": 55.0},
        "set1_over_8.5": {"n": 5, "pct": 75.0},
        "set1_over_9.5": {"n": 5, "pct": 50.0},
    }
    return {
        "player": name,
        "player_id": 1,
        "matches": 5,
        "trend_matches": 5,
        "ready": True,
        "quality": "MEDIUM",
        "ehs": 80.0,
        "hold1": 80.0,
        "hold2": 80.0,
        "hold3": 80.0,
        "pbp_tendencies": {"all": {"5": {"metrics": metrics}}},
    }


def test_cache_recovery_uses_zero_network_and_restores_profiles(tmp_path, monkeypatch):
    index = tmp_path / "players.json"
    index.write_text(json.dumps({
        "players": {
            "alice": {"player_id": 1},
            "bob": {"player_id": 2},
        }
    }), encoding="utf-8")
    monkeypatch.setattr(recovery.core, "INDEX_PATH", index)

    seen_caps = []

    def fake_build_profile(api, index_data, player, player_id, surface, as_of, now, counters):
        seen_caps.append(api.call_cap)
        p = _profile(player)
        p["player_id"] = player_id
        return p

    monkeypatch.setattr(recovery.core, "build_profile", fake_build_profile)

    rows = [{
        "id": 1,
        "model_ready": True,
        "p1": "Alice",
        "p2": "Bob",
        "surface": "hard",
        "scheduled_time": "2026-09-02T10:00:00+00:00",
        "service_model": {"p1_hold": 75.0, "p2_hold": 74.0},
        "first_set_win": {"Alice": 55.0, "Bob": 45.0},
    }]

    out, report = recovery.recover_rows_from_cache(rows)

    assert report["api_calls"] == 0
    assert report["profiles_recovered"] == 2
    assert report["matches_with_recovered_supply"] == 1
    assert report["strict_ready_matches"] == 1
    assert seen_caps == [0, 0]
    assert out[0]["early_hold_v7"]["p1"]["trend_matches"] == 5
    assert out[0]["early_hold_v7"]["p2"]["trend_matches"] == 5


def test_missing_cached_player_stays_nd(tmp_path, monkeypatch):
    index = tmp_path / "players.json"
    index.write_text(json.dumps({"players": {}}), encoding="utf-8")
    monkeypatch.setattr(recovery.core, "INDEX_PATH", index)

    rows = [{
        "model_ready": True,
        "p1": "Alice",
        "p2": "Bob",
        "surface": "hard",
        "service_model": {"p1_hold": 75.0, "p2_hold": 74.0},
    }]
    out, report = recovery.recover_rows_from_cache(rows)
    assert report["api_calls"] == 0
    assert report["profiles_recovered"] == 0
    assert report["matches_with_recovered_supply"] == 0
    assert "early_hold_v7" not in out[0]
