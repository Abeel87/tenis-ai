from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from pbp_enrich import extract_first_set_games, enrich_match


def _row(a, b, points, server):
    return {
        "games": [[a], [b]],
        "points": list(points),
        "server": server,
        "sets": [0, 0],
    }


def synthetic_tape():
    rows = []
    # Six games, p1 serves first; all holds -> 3:3.
    game_scores = [(0,0),(1,0),(1,1),(2,1),(2,2),(3,2),(3,3)]
    for g in range(6):
        a,b = game_scores[g]
        server = 1 if g % 2 == 0 else 2
        rows.append(_row(a,b,("0","0"),server))
        rows.append(_row(a,b,("15","0"),server))
        na,nb = game_scores[g+1]
        next_server = 2 if server == 1 else 1
        rows.append(_row(na,nb,("0","0"),next_server))
    # Continue to 6:4 for p1.
    for before, after, server in [
        ((3,3),(4,3),1),
        ((4,3),(4,4),2),
        ((4,4),(5,4),1),
        ((5,4),(6,4),2),  # break to finish
    ]:
        rows.append(_row(*before,("15","15"),server))
        rows.append(_row(*after,("0","0"),3-server))
    return {
        "match": {"players":{"p1":{"name":"A"},"p2":{"name":"B"}}},
        "meta":{"coverage":"from_start","point_source":"observed"},
        "tape":rows,
    }


def profile(name):
    return {
        "player":name,"matches":8,"surface_matches":6,"ready":True,"quality":"HIGH","ehs":80,
        "hold1":82.0,"hold2":80.0,"hold3":78.0,
        "after2_11":75.0,"after4_22":60.0,"after6_33":50.0,"sequence_11_22_33":45.0,
    }


def test_extract_first_set_games():
    x=extract_first_set_games(synthetic_tape())
    assert x is not None
    assert x["checkpoints"]["2"] == "1:1"
    assert x["checkpoints"]["4"] == "2:2"
    assert x["checkpoints"]["6"] == "3:3"
    assert x["service_games"][1]["1"] == 1.0
    assert x["service_games"][2]["3"] == 1.0


def test_enrich_produces_joint_not_product_placeholder():
    m={
        "p1":"A","p2":"B","model_ready":True,
        "service_model":{"p1_hold":75.0,"p2_hold":74.0},
        "first_set_win":{"A":55.0,"B":45.0},
    }
    enrich_match(m,profile("A"),profile("B"))
    assert m["early_hold_v7"]["ready"] is True
    assert m["game_states"]["6"]["3:3"] > 0
    assert 0 <= m["score_lead_after6"] <= 100
    assert 0 <= m["score_joint_builder"] <= m["score_lead_after6"]
    assert m["service_model"]["pbp_adjusted"] is True


def test_nd_under_five_matches():
    p=profile("A")
    p.update({"matches":4,"ready":False,"ehs":None})
    m={"p1":"A","p2":"B","model_ready":True,"service_model":{"p1_hold":75,"p2_hold":75}}
    enrich_match(m,p,profile("B"))
    assert m["early_hold_v7"]["ready"] is False
    assert "score_joint_builder" not in m


class FakeAPI:
    def __init__(self):
        self.calls = []
    def get(self, path, params=None):
        self.calls.append((path, params))
        if path.startswith("/matches/"):
            return {
                "id": 99,
                "players": {
                    "p1": {"id": 101, "name": "Jessica Pegula"},
                    "p2": {"id": 202, "name": "Amanda Anisimova"},
                },
            }
        if path == "/history/matches":
            assert isinstance(params["player"], int)
            return {"data": [], "meta": {"has_more": False}}
        raise AssertionError(path)


def test_resolve_current_player_ids_and_numeric_history_filter(tmp_path, monkeypatch):
    import pbp_enrich as mod
    api=FakeAPI()
    counters={"match_detail_calls":0,"match_detail_errors":0}
    ids=mod.resolve_current_player_ids(api,[{
        "id":99,"p1":"Jessica Pegula","p2":"Amanda Anisimova"
    }],counters)
    assert ids[mod._key("Jessica Pegula")] == 101
    assert ids[mod._key("Amanda Anisimova")] == 202

    index={"players":{}}
    now=mod.datetime.now(mod.timezone.utc)
    mod._refresh_player_index(api,index,"Jessica Pegula",101,now,now)
    history_calls=[c for c in api.calls if c[0]=="/history/matches"]
    assert history_calls
    assert history_calls[-1][1]["player"] == 101



def _cached_stats_payload(profile_games, *, final_games=(6, 4)):
    return {
        "tape": [
            {"sets": [1, 0], "games": [5, 4], "points": [40, 30]},
            {"sets": [2, 0], "games": list(final_games), "points": [0, 0]},
        ],
        "profiles": [
            {
                "created_at": "2026-09-06T20:00:00Z",
                "input_state": {
                    "score": {"sets": [2, 0] if list(profile_games) == list(final_games) else [1, 0], "games": list(profile_games)},
                    "stats": {"p1": {}, "p2": {}},
                },
            }
        ],
    }


class RefreshAPI:
    def __init__(self, response=None, error=None, call_cap=10):
        self.response = response
        self.error = error
        self.calls = 0
        self.call_cap = call_cap

    def get(self, path, params=None):
        self.calls += 1
        assert path.startswith("/history/matches/")
        assert params == {"sequence": "clean"}
        if self.error is not None:
            raise self.error
        return self.response


def test_stale_cached_tape_is_revalidated_and_terminalized(tmp_path, monkeypatch):
    import pbp_enrich as mod

    monkeypatch.setattr(mod, "CACHE", tmp_path / "pbp")
    cached = _cached_stats_payload([5, 4])
    refreshed = _cached_stats_payload([6, 4])
    path = mod._match_cache_path(123)
    mod._write_gzip_json(path, cached)

    api = RefreshAPI(response=refreshed)
    counters = {}
    state = {"matches": {}}
    now = mod.datetime(2026, 9, 7, 10, 0, tzinfo=mod.timezone.utc)

    payload, hit = mod._get_tape(
        api,
        123,
        scheduled_time="2026-09-06T20:00:00Z",
        now=now,
        counters=counters,
        refresh_state=state,
    )

    assert hit is False
    assert api.calls == 1
    assert mod._cache_has_terminal_stats(payload) is True
    assert counters["tape_stale_refresh_attempts"] == 1
    assert counters["tape_stale_refresh_successes"] == 1
    assert counters["tape_stale_refresh_terminalized"] == 1
    assert state["matches"]["123"]["last_result"] == "terminal_stats"
    assert mod._cache_has_terminal_stats(mod._read_gzip_json(path)) is True

    # A now-terminal cache is never fetched again just because it was old.
    payload2, hit2 = mod._get_tape(
        api,
        123,
        scheduled_time="2026-09-06T20:00:00Z",
        now=now,
        counters=counters,
        refresh_state=state,
    )
    assert hit2 is True
    assert api.calls == 1
    assert mod._cache_has_terminal_stats(payload2) is True


def test_failed_stale_refresh_falls_back_to_cache_and_respects_cooldown(tmp_path, monkeypatch):
    import pbp_enrich as mod

    monkeypatch.setattr(mod, "CACHE", tmp_path / "pbp")
    cached = _cached_stats_payload([5, 4])
    mod._write_gzip_json(mod._match_cache_path(456), cached)

    api = RefreshAPI(error=RuntimeError("provider_down"))
    counters = {}
    state = {"matches": {}}
    now = mod.datetime(2026, 9, 7, 10, 0, tzinfo=mod.timezone.utc)

    payload, hit = mod._get_tape(
        api,
        456,
        scheduled_time="2026-09-06T20:00:00Z",
        now=now,
        counters=counters,
        refresh_state=state,
    )

    assert hit is True
    assert payload == cached
    assert api.calls == 1
    assert counters["tape_stale_refresh_errors"] == 1
    assert state["matches"]["456"]["last_result"] == "error:RuntimeError"

    # Same cached payload is not hammered again inside the 72h cooldown.
    payload2, hit2 = mod._get_tape(
        api,
        456,
        scheduled_time="2026-09-06T20:00:00Z",
        now=now + mod.timedelta(hours=1),
        counters=counters,
        refresh_state=state,
    )
    assert hit2 is True
    assert payload2 == cached
    assert api.calls == 1


def test_terminal_or_too_recent_cache_does_not_consume_refresh_budget(tmp_path, monkeypatch):
    import pbp_enrich as mod

    monkeypatch.setattr(mod, "CACHE", tmp_path / "pbp")
    terminal = _cached_stats_payload([6, 4])
    stale = _cached_stats_payload([5, 4])
    mod._write_gzip_json(mod._match_cache_path(1), terminal)
    mod._write_gzip_json(mod._match_cache_path(2), stale)

    api = RefreshAPI(response=terminal)
    counters = {}
    state = {"matches": {}}
    now = mod.datetime(2026, 9, 7, 10, 0, tzinfo=mod.timezone.utc)

    _, terminal_hit = mod._get_tape(
        api,
        1,
        scheduled_time="2026-09-06T20:00:00Z",
        now=now,
        counters=counters,
        refresh_state=state,
    )
    _, recent_hit = mod._get_tape(
        api,
        2,
        scheduled_time="2026-09-07T06:00:00Z",
        now=now,
        counters=counters,
        refresh_state=state,
    )

    assert terminal_hit is True
    assert recent_hit is True
    assert api.calls == 0
    assert counters.get("tape_stale_refresh_attempts", 0) == 0
