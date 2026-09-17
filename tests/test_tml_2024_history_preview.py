import pandas as pd

from backend import tml_2024_history_preview as audit


def _row(index, *, player="Alice Smith", date=20250101, winner_id=101, source_tour="ATP"):
    tourney_date = int((pd.to_datetime(str(date), format="%Y%m%d") + pd.Timedelta(days=index)).strftime("%Y%m%d"))
    return {
        "tourney_id": f"T{date}-{index}",
        "match_num": index,
        "tourney_date": tourney_date,
        "tourney_name": "Test",
        "surface": "Hard",
        "winner_id": winner_id,
        "loser_id": 900 + index,
        "winner_name": player,
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
        "source_tour": source_tour,
    }


def _history(rows=4, *, player="Alice Smith", date=20250101):
    return pd.DataFrame([_row(i, player=player, date=date) for i in range(rows)])


def _results(schedule="2026-09-18T10:00:00+00:00"):
    return [{
        "id": "fixture-1",
        "scheduled_time": schedule,
        "p1": "Alice Smith",
        "p2": "Other Player",
        "p1_stats": {"matches": 4, "quality": "LOW", "history_identity_mode": "exact"},
        "p2_stats": {"matches": 0, "quality": "LOW", "history_identity_mode": "none"},
    }]


def _archives(frame):
    return {"atp_2024": frame}


def test_exact_baseline_key_can_reach_minimum_5():
    baseline = _history(4)
    archive = pd.DataFrame([_row(50, date=20240101)])

    report = audit.build_report(
        baseline_raw=baseline,
        results=_results(),
        archive_frames=_archives(archive),
    )

    assert report["policy"]["live_tennis_api_calls"] == 0
    assert report["policy"]["production_cache_writes"] == 0
    assert report["policy"]["uses_existing_baseline_history_key_only"] is True
    assert report["summary"]["short_history_players"] == 1
    assert report["summary"]["players_with_positive_2024_gain"] == 1
    assert report["summary"]["players_reaching_minimum_5"] == 1
    row = report["priority"]["reaches_minimum_5"][0]
    assert row["baseline_clean_pre_match_rows"] == 4
    assert row["augmented_clean_pre_match_rows"] == 5
    assert row["net_2024_clean_pre_match_rows"] == 1


def test_same_provider_id_under_different_name_is_not_used_as_alias():
    baseline = _history(4, player="Alice Smith")
    archive = pd.DataFrame([_row(50, player="A. Smith", date=20240101, winner_id=101)])

    report = audit.build_report(
        baseline_raw=baseline,
        results=_results(),
        archive_frames=_archives(archive),
    )

    assert report["policy"]["provider_id_matching"] is False
    assert report["summary"]["players_with_positive_2024_gain"] == 0
    assert report["summary"]["players_reaching_minimum_5"] == 0
    assert report["cases"][0]["augmented_clean_pre_match_rows"] == 4


def test_post_cutoff_archive_row_does_not_count():
    baseline = _history(4, date=20230101)
    archive = pd.DataFrame([_row(50, date=20250101)])

    report = audit.build_report(
        baseline_raw=baseline,
        results=_results(schedule="2024-06-01T10:00:00+00:00"),
        archive_frames=_archives(archive),
    )

    assert report["summary"]["players_with_positive_2024_gain"] == 0
    assert report["summary"]["players_reaching_minimum_5"] == 0


def test_duplicate_archive_match_does_not_inflate_count():
    baseline = _history(4)
    duplicate = baseline.iloc[[0]].copy()

    report = audit.build_report(
        baseline_raw=baseline,
        results=_results(),
        archive_frames=_archives(duplicate),
    )

    assert report["summary"]["players_with_positive_2024_gain"] == 0
    assert report["cases"][0]["augmented_clean_pre_match_rows"] == 4


def test_failed_source_is_reported_and_never_authorized():
    baseline = _history(4)
    status = [{
        "key": source["key"],
        "tour": source["tour"],
        "url": source["url"],
        "fetch_success": False,
        "rows": 0,
        "error": "RuntimeError",
    } for source in audit.TML_2024_SOURCES]

    report = audit.build_report(
        baseline_raw=baseline,
        results=_results(),
        archive_frames={},
        source_status=status,
    )

    assert report["summary"]["all_2024_sources_fetched"] is False
    assert report["decision"]["runtime_change"] is False
    assert report["decision"]["authorize_2024_archive"] is False
