from datetime import datetime

import pandas as pd

from backend import pbp_tml_dedup_audit as audit


def _row(*, pair=("alice smith", "bob jones"), score=((6, 4), (6, 3)), day="2026-09-10", surface="hard"):
    return {
        "pair": pair,
        "score": score,
        "day": pd.Timestamp(day).date(),
        "surface": surface,
        "tourney_id": "T1",
        "match_num": 1,
        "winner_name": "Alice Smith",
        "loser_name": "Bob Jones",
        "score_text": "6-4 6-3",
    }


def _dt(value="2026-09-15T10:00:00+00:00"):
    return datetime.fromisoformat(value)


def test_orientation_normalization_preserves_score_side():
    canonical = audit._canonical_pair_score(
        "Bob Jones",
        "Alice Smith",
        ((4, 6), (3, 6)),
    )
    assert canonical == (
        ("alice smith", "bob jones"),
        ((6, 4), (6, 3)),
    )


def test_unique_exact_clean_match_is_deterministic_duplicate():
    row = _row()
    category, matches = audit.classify_overlap(
        pair=row["pair"],
        score=row["score"],
        scheduled_dt=_dt(),
        surface="hard",
        clean_index={row["pair"]: [row]},
        raw_index={row["pair"]: [row]},
    )
    assert category == "deterministic_duplicate_clean_tml"
    assert matches == [row]


def test_raw_only_exact_match_is_reported_separately():
    row = _row()
    category, matches = audit.classify_overlap(
        pair=row["pair"],
        score=row["score"],
        scheduled_dt=_dt(),
        surface="hard",
        clean_index={},
        raw_index={row["pair"]: [row]},
    )
    assert category == "raw_only_duplicate_tml"
    assert matches == [row]


def test_pair_in_window_with_conflicting_score_is_ambiguous():
    row = _row(score=((6, 4), (3, 6), (6, 2)))
    category, matches = audit.classify_overlap(
        pair=row["pair"],
        score=((6, 4), (6, 3)),
        scheduled_dt=_dt(),
        surface="hard",
        clean_index={row["pair"]: [row]},
        raw_index={row["pair"]: [row]},
    )
    assert category == "ambiguous_pair_window_score_conflict"
    assert matches == [row]


def test_multiple_exact_rows_fail_closed_as_ambiguous():
    first = _row()
    second = {**_row(day="2026-09-11"), "match_num": 2}
    category, matches = audit.classify_overlap(
        pair=first["pair"],
        score=first["score"],
        scheduled_dt=_dt(),
        surface="hard",
        clean_index={first["pair"]: [first, second]},
        raw_index={first["pair"]: [first, second]},
    )
    assert category == "ambiguous_multiple_clean_exact"
    assert len(matches) == 2


def test_no_pair_window_match_is_unmatched_not_authorized_new_history():
    row = _row(day="2026-08-01")
    category, matches = audit.classify_overlap(
        pair=row["pair"],
        score=row["score"],
        scheduled_dt=_dt(),
        surface="hard",
        clean_index={row["pair"]: [row]},
        raw_index={row["pair"]: [row]},
    )
    assert category == "unmatched_in_tml_cache"
    assert matches == []


def test_report_keeps_runtime_and_history_gate_closed(monkeypatch, tmp_path):
    task006_report = {
        "summary": {"audited_unique_players": 1},
        "players": [{
            "player": "Alice Smith",
            "player_key": "alice smith",
            "stable_provider_id": 77,
            "provider_identity_conflict": False,
            "cutoff": "2026-09-17T10:00:00+00:00",
            "current_clean_history_matches": 3,
        }],
    }
    monkeypatch.setattr(audit.task006, "build_report", lambda **_: task006_report)
    raw = pd.DataFrame(columns=["winner_name", "loser_name", "tourney_date", "score"])
    monkeypatch.setattr(audit, "load_cached_history", lambda: raw)
    monkeypatch.setattr(
        audit,
        "clean_history",
        lambda frame: (frame.copy(), {"raw_rows": 0, "kept_rows": 0, "removed_rows": 0}),
    )
    observations = [{
        "player": "Alice Smith",
        "player_key": "alice smith",
        "current_clean_history_matches": 3,
        "stable_provider_id": 77,
        "match_id": 101,
        "scheduled_time": "2026-09-10T10:00:00+00:00",
        "scheduled_dt": _dt("2026-09-10T10:00:00+00:00"),
        "pair": ("alice smith", "bob jones"),
        "score": ((6, 4), (6, 3)),
        "surface": "hard",
        "side": 1,
        "p1": "Alice Smith",
        "p2": "Bob Jones",
    }, {
        "player": "Alice Smith",
        "player_key": "alice smith",
        "current_clean_history_matches": 3,
        "stable_provider_id": 77,
        "match_id": 102,
        "scheduled_time": "2026-09-11T10:00:00+00:00",
        "scheduled_dt": _dt("2026-09-11T10:00:00+00:00"),
        "pair": ("alice smith", "cora lee"),
        "score": ((6, 2), (6, 2)),
        "surface": "hard",
        "side": 1,
        "p1": "Alice Smith",
        "p2": "Cora Lee",
    }]
    monkeypatch.setattr(
        audit,
        "_collect_terminal_observations",
        lambda **_: (observations, {
            "cache_payload_files_scanned": 2,
            "cache_payloads_readable": 2,
            "cache_payloads_with_stable_identity": 2,
            "cache_payload_file_id_mismatches": 0,
        }),
    )

    report = audit.build_report(
        cache_root=tmp_path,
        pbp_root=tmp_path / "pbp_v7",
        results_path=tmp_path / "results.json",
    )
    assert report["summary"]["unmatched_in_tml_cache"] == 2
    assert report["summary"]["upper_bound_players_reaching_five_after_clean_dedup"] == 1
    assert report["policy"]["pbp_authorized_for_main_history"] is False
    assert report["policy"]["unmatched_pbp_authorized_as_new_history"] is False
    assert report["decision"]["runtime_change"] is False
    assert report["decision"]["history_gate_change"] is False
