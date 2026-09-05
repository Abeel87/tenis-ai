from backend.player_dna_profiles import build_chronological_profiles, match_record_from_observations


def _record(match_id, stamp, surface, player_id=1, opponent_id=2, *, sp=10, sw=6, rp=10, rw=4):
    return {
        "match_id": match_id,
        "scheduled_time": stamp,
        "surface": surface,
        "players": {
            player_id: {"serve_points": sp, "serve_won": sw, "return_points": rp, "return_won": rw},
            opponent_id: {"serve_points": rp, "serve_won": rp - rw, "return_points": sp, "return_won": sp - sw},
        },
    }


def test_current_match_never_leaks_into_its_profile():
    records = [
        _record(1, "2026-01-01T10:00:00Z", "hard", sw=5, rw=3),
        _record(2, "2026-01-02T10:00:00Z", "hard", sw=9, rw=8),
    ]
    rows = build_chronological_profiles(records)
    first = rows[0]["players"]["1"]["all_surface"]["L5"]
    second = rows[1]["players"]["1"]["all_surface"]["L5"]
    assert first["matches_used"] == 0
    assert first["serve"]["points"] == 0
    assert second["matches_used"] == 1
    assert second["serve"]["points"] == 10
    assert second["serve"]["wins"] == 5


def test_same_timestamp_matches_are_isolated_from_each_other():
    records = [
        _record(1, "2026-01-01T10:00:00Z", "hard", player_id=1, opponent_id=2),
        _record(2, "2026-01-02T10:00:00Z", "hard", player_id=1, opponent_id=3, sw=7),
        _record(3, "2026-01-02T10:00:00Z", "hard", player_id=1, opponent_id=4, sw=8),
    ]
    rows = build_chronological_profiles(records)
    row2 = next(row for row in rows if row["match_id"] == 2)
    row3 = next(row for row in rows if row["match_id"] == 3)
    for row in (row2, row3):
        profile = row["players"]["1"]["all_surface"]["L5"]
        assert profile["matches_used"] == 1
        assert profile["serve"]["points"] == 10
        assert profile["serve"]["wins"] == 6
        assert row["same_time_group_isolated"] is True


def test_l5_l10_l20_use_exact_recent_match_windows():
    records = []
    for day in range(1, 13):
        records.append(_record(day, f"2026-01-{day:02d}T10:00:00Z", "hard", sw=day % 10))
    rows = build_chronological_profiles(records)
    target = rows[-1]["players"]["1"]["all_surface"]
    assert target["L5"]["matches_used"] == 5
    assert target["L10"]["matches_used"] == 10
    assert target["L20"]["matches_used"] == 11
    assert target["L5"]["serve"]["points"] == 50
    assert target["L10"]["serve"]["points"] == 100
    assert target["L20"]["serve"]["points"] == 110


def test_same_surface_profile_uses_only_prior_matching_surface():
    records = [
        _record(1, "2026-01-01T10:00:00Z", "clay", sw=3),
        _record(2, "2026-01-02T10:00:00Z", "hard", sw=8),
        _record(3, "2026-01-03T10:00:00Z", "clay", sw=7),
    ]
    rows = build_chronological_profiles(records)
    target = rows[-1]["players"]["1"]["same_surface"]
    assert target["available"] is True
    assert target["surface"] == "clay"
    l5 = target["windows"]["L5"]
    assert l5["matches_used"] == 1
    assert l5["serve"]["points"] == 10
    assert l5["serve"]["wins"] == 3


def test_sparse_profile_is_shrunk_toward_past_only_population_prior():
    records = [
        _record(1, "2026-01-01T10:00:00Z", "hard", sw=8, rw=2),
        _record(2, "2026-01-02T10:00:00Z", "hard", sw=10, rw=10),
    ]
    rows = build_chronological_profiles(records)
    target = rows[-1]["players"]["1"]["all_surface"]["L5"]
    serve = target["serve"]
    assert serve["raw_rate"] == 0.8
    assert serve["prior_rate"] == 0.8
    assert serve["shrunk_rate"] == 0.8
    assert serve["prior_strength_points"] == 50.0
    assert 0 < serve["quality"] < 1


def test_missing_surface_stays_explicit_and_does_not_coerce():
    records = [
        _record(1, "2026-01-01T10:00:00Z", None),
        _record(2, "2026-01-02T10:00:00Z", None),
    ]
    rows = build_chronological_profiles(records)
    surface = rows[-1]["players"]["1"]["same_surface"]
    assert surface == {"surface": None, "available": False, "windows": {}}
    assert rows[-1]["training_join_enabled"] is False
    assert rows[-1]["shadow_only"] is True


def test_point_orientation_uses_stable_server_and_receiver_ids():
    context = {
        "match_id": 42,
        "scheduled_time": "2026-01-01T10:00:00Z",
        "surface": "hard",
        "p1": {"id": 101},
        "p2": {"id": 202},
    }
    observations = [
        {"trainable_player_point": True, "server_player_id": 101, "receiver_player_id": 202, "server_won": True, "receiver_won": False},
        {"trainable_player_point": True, "server_player_id": 202, "receiver_player_id": 101, "server_won": False, "receiver_won": True},
        {"trainable_player_point": False, "server_player_id": 101, "receiver_player_id": 202, "server_won": False, "receiver_won": True},
    ]
    record = match_record_from_observations(context, observations)
    assert record["players"][101] == {"serve_points": 1, "serve_won": 1, "return_points": 1, "return_won": 1}
    assert record["players"][202] == {"serve_points": 1, "serve_won": 0, "return_points": 1, "return_won": 0}
