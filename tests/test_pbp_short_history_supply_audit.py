import gzip
import json

from backend import pbp_short_history_supply_audit as audit


def _task005_report(player="Alice Smith", clean=3):
    return {
        "summary": {"insufficient_player_cases": 1, "unique_insufficient_players": 1},
        "cases": [{
            "player": player,
            "scheduled_time": "2026-09-17T10:00:00+00:00",
            "clean_pre_match_rows": clean,
            "category": "genuine_short_clean_history",
        }],
    }


def _payload(mid=101, player="Alice Smith", player_id=77, when="2026-09-10T10:00:00+00:00"):
    return {
        "match": {
            "id": mid,
            "scheduled_time": when,
            "players": {
                "p1": {"id": player_id, "name": player},
                "p2": {"id": 999, "name": "Opponent"},
            },
        },
        "tape": [],
        "profiles": [],
    }


def _write_payload(root, payload, filename_mid=None):
    matches = root / "matches"
    matches.mkdir(parents=True, exist_ok=True)
    mid = filename_mid if filename_mid is not None else payload["match"]["id"]
    path = matches / f"{mid}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return path


def _prepare(tmp_path, monkeypatch, *, player="Alice Smith", clean=3, index=None):
    pbp_root = tmp_path / "pbp_v7"
    pbp_root.mkdir()
    (pbp_root / "players.json").write_text(
        json.dumps(index or {"players": {}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        audit.short_history,
        "build_report",
        lambda **_: _task005_report(player, clean),
    )
    return pbp_root


def test_exact_payload_identity_counts_without_players_index(tmp_path, monkeypatch):
    pbp_root = _prepare(tmp_path, monkeypatch)
    _write_payload(pbp_root, _payload())
    monkeypatch.setattr(audit.pbp, "_cache_has_terminal_stats", lambda payload: True)
    monkeypatch.setattr(
        audit.pbp,
        "extract_first_set_games",
        lambda payload: {"games": [1, 2, 3]},
    )

    report = audit.build_report(
        cache_root=tmp_path,
        pbp_root=pbp_root,
        results_path=tmp_path / "results.json",
    )
    row = report["players"][0]

    assert row["pbp_index_present"] is False
    assert row["payload_provider_ids"] == [77]
    assert row["provider_identity_conflict"] is False
    assert row["payload_identity_valid"] == 1
    assert row["terminal_tapes"] == 1
    assert row["first_set_extractable"] == 1
    assert report["summary"]["cache_payload_files_scanned"] == 1
    assert report["summary"]["players_with_terminal_tape"] == 1
    assert report["policy"]["network_calls"] == 0
    assert report["policy"]["pbp_authorized_for_main_history"] is False
    assert report["decision"]["runtime_change"] is False


def test_no_fuzzy_player_name_fallback(tmp_path, monkeypatch):
    pbp_root = _prepare(tmp_path, monkeypatch, player="Alice Smith", clean=2)
    _write_payload(pbp_root, _payload(player="Alice Smyth"))

    report = audit.build_report(
        cache_root=tmp_path,
        pbp_root=pbp_root,
        results_path=tmp_path / "results.json",
    )
    row = report["players"][0]

    assert row["payload_provider_ids"] == []
    assert row["exact_payload_matches"] == 0
    assert row["terminal_tapes"] == 0


def test_payload_file_id_mismatch_fails_closed(tmp_path, monkeypatch):
    pbp_root = _prepare(tmp_path, monkeypatch)
    _write_payload(pbp_root, _payload(mid=101), filename_mid=999)
    monkeypatch.setattr(audit.pbp, "_cache_has_terminal_stats", lambda payload: True)

    report = audit.build_report(
        cache_root=tmp_path,
        pbp_root=pbp_root,
        results_path=tmp_path / "results.json",
    )
    row = report["players"][0]

    assert row["pre_cutoff_candidates"] == 1
    assert row["payload_identity_valid"] == 0
    assert row["invalid_payload_identity"] == 1
    assert row["terminal_tapes"] == 0
    assert report["summary"]["cache_payload_file_id_mismatches"] == 1


def test_conflicting_provider_ids_for_same_exact_key_fail_closed(tmp_path, monkeypatch):
    pbp_root = _prepare(tmp_path, monkeypatch)
    _write_payload(pbp_root, _payload(mid=101, player_id=77))
    _write_payload(pbp_root, _payload(mid=102, player_id=88, when="2026-09-11T10:00:00+00:00"))
    monkeypatch.setattr(audit.pbp, "_cache_has_terminal_stats", lambda payload: True)

    report = audit.build_report(
        cache_root=tmp_path,
        pbp_root=pbp_root,
        results_path=tmp_path / "results.json",
    )
    row = report["players"][0]

    assert row["payload_provider_ids"] == [77, 88]
    assert row["provider_identity_conflict"] is True
    assert row["payload_identity_valid"] == 0
    assert row["terminal_tapes"] == 0
    assert report["summary"]["players_with_provider_identity_conflict"] == 1


def test_index_id_conflict_with_payload_fails_closed(tmp_path, monkeypatch):
    index = {"players": {"alice smith": {"player_id": 55, "matches": []}}}
    pbp_root = _prepare(tmp_path, monkeypatch, index=index)
    _write_payload(pbp_root, _payload(player_id=77))
    monkeypatch.setattr(audit.pbp, "_cache_has_terminal_stats", lambda payload: True)

    report = audit.build_report(
        cache_root=tmp_path,
        pbp_root=pbp_root,
        results_path=tmp_path / "results.json",
    )
    row = report["players"][0]

    assert row["pbp_index_present"] is True
    assert row["pbp_index_player_id"] == 55
    assert row["provider_identity_conflict"] is True
    assert row["terminal_tapes"] == 0


def test_upper_bound_is_explicitly_not_authorization(tmp_path, monkeypatch):
    pbp_root = _prepare(tmp_path, monkeypatch, clean=3)
    _write_payload(pbp_root, _payload(mid=101))
    _write_payload(pbp_root, _payload(mid=102, when="2026-09-11T10:00:00+00:00"))
    monkeypatch.setattr(audit.pbp, "_cache_has_terminal_stats", lambda payload: True)
    monkeypatch.setattr(audit.pbp, "extract_first_set_games", lambda payload: None)

    report = audit.build_report(
        cache_root=tmp_path,
        pbp_root=pbp_root,
        results_path=tmp_path / "results.json",
    )

    assert report["players"][0]["upper_bound_reaches_five_if_all_terminal_are_distinct"] is True
    assert report["summary"]["upper_bound_players_reaching_five"] == 1
    assert report["policy"]["pbp_authorized_for_main_history"] is False
    assert report["policy"]["cross_source_deduplication_proven"] is False
    assert report["decision"]["history_gate_change"] is False
