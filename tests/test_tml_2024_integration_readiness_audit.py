import pandas as pd

from backend import tml_2024_integration_readiness_audit as audit


def _row(index, player, *, date=20250101, player_id=100, opponent=None):
    tourney_date = int((pd.to_datetime(str(date), format="%Y%m%d") + pd.Timedelta(days=index)).strftime("%Y%m%d"))
    opponent = opponent or f"Opponent {player} {index}"
    return {
        "tourney_id": f"T{date}-{player_id}-{index}",
        "match_num": index,
        "tourney_date": tourney_date,
        "tourney_name": "Test",
        "surface": "Hard",
        "winner_id": player_id,
        "loser_id": 90000 + index + player_id,
        "winner_name": player,
        "loser_name": opponent,
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
        "source_tour": "ATP",
    }


def _baseline(alice=4, bob=6):
    rows = [_row(i, "Alice Smith", player_id=101) for i in range(alice)]
    rows += [_row(20 + i, "Bob Jones", player_id=202) for i in range(bob)]
    return pd.DataFrame(rows)


def _match(p1="Alice Smith", p2="Bob Jones", *, stored_ready=False):
    return {
        "id": "fixture-1",
        "scheduled_time": "2026-09-18T10:00:00+00:00",
        "surface": "Hard",
        "p1": p1,
        "p2": p2,
        "model_ready": stored_ready,
    }


def _all_source_status():
    return [
        {"key": source["key"], "tour": source["tour"], "url": source["url"], "fetch_success": True, "rows": 1, "error": None}
        for source in audit.task014.TML_2024_SOURCES
    ]


def _archives_with(extra):
    frames = {source["key"]: pd.DataFrame([_row(70 + i, f"Unrelated {i}", date=20240101, player_id=500 + i)])
              for i, source in enumerate(audit.task014.TML_2024_SOURCES)}
    frames["atp_2024"] = pd.concat([frames["atp_2024"], pd.DataFrame([extra])], ignore_index=True)
    return frames


def test_exact_4_to_5_can_create_real_model_ready_match():
    archive_row = _row(5, "Alice Smith", date=20240101, player_id=101)
    report = audit.build_report(
        baseline_raw=_baseline(),
        results=[_match()],
        archive_frames=_archives_with(archive_row),
        source_status=_all_source_status(),
    )

    assert report["summary"]["baseline_runtime_parity_mismatches"] == 0
    assert report["summary"]["identity_stability_anomalies"] == 0
    assert report["summary"]["matches_new_both_minimum_5"] == 1
    assert report["summary"]["matches_new_model_ready"] == 1
    row = report["priority"]["new_model_ready"][0]
    assert row["sides"]["p1"]["baseline"]["matches"] == 4
    assert row["sides"]["p1"]["preview"]["matches"] == 5
    assert row["preview_recomputed_model_ready"] is True


def test_same_provider_id_with_alias_name_is_not_joined():
    alias_row = _row(5, "A. Smith", date=20240101, player_id=101)
    report = audit.build_report(
        baseline_raw=_baseline(),
        results=[_match()],
        archive_frames=_archives_with(alias_row),
        source_status=_all_source_status(),
    )

    assert report["policy"]["provider_id_matching"] is False
    assert report["summary"]["matches_new_model_ready"] == 0
    row = report["matches"][0]
    assert row["sides"]["p1"]["preview"]["matches"] == 4


def test_2024_cannot_introduce_identity_absent_from_baseline():
    new_player_row = _row(5, "New Player", date=20240101, player_id=303)
    report = audit.build_report(
        baseline_raw=_baseline(alice=0),
        results=[_match(p1="New Player")],
        archive_frames=_archives_with(new_player_row),
        source_status=_all_source_status(),
    )

    row = report["matches"][0]
    assert row["sides"]["p1"]["baseline"]["history_key"] is None
    assert row["sides"]["p1"]["preview"]["history_key"] is None
    assert row["sides"]["p1"]["preview"]["matches"] == 0
    assert report["summary"]["matches_new_model_ready"] == 0


def test_exact_duplicate_archive_match_does_not_inflate_profile():
    baseline = _baseline()
    duplicate = baseline.iloc[0].to_dict()
    report = audit.build_report(
        baseline_raw=baseline,
        results=[_match()],
        archive_frames=_archives_with(duplicate),
        source_status=_all_source_status(),
    )

    assert report["dedupe"]["archive_signatures_already_in_baseline"] >= 1
    assert report["matches"][0]["sides"]["p1"]["preview"]["matches"] == 4
    assert report["summary"]["matches_new_model_ready"] == 0


def test_missing_required_archive_column_is_schema_blocker():
    bad = pd.DataFrame([_row(5, "Alice Smith", date=20240101, player_id=101)]).drop(columns=["w_svpt"])
    frames = {source["key"]: bad.copy() for source in audit.task014.TML_2024_SOURCES}
    report = audit.build_report(
        baseline_raw=_baseline(),
        results=[_match()],
        archive_frames=frames,
        source_status=_all_source_status(),
    )

    assert report["summary"]["all_sources_schema_compatible"] is False
    assert report["summary"]["readiness_evidence_clean"] is False
    assert all("w_svpt" in row["missing_required_columns"] for row in report["schema"])


def test_task014_classification_invariant_is_rechecked():
    archive_row = _row(5, "Alice Smith", date=20240101, player_id=101)
    report = audit.build_report(
        baseline_raw=_baseline(),
        results=[_match()],
        archive_frames=_archives_with(archive_row),
        source_status=_all_source_status(),
    )

    assert report["summary"]["task014_invariant_anomalies"] == 0
    assert report["task014_consistency"]["invariant_anomalies"] == []
