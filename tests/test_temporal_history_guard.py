import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from model import analyse_match, normalize_matches


def _row(date, *, winner="Alpha", loser="Beta", w_svpt=60, w_1st_won=30):
    return {
        "tourney_date": date,
        "tourney_name": f"T-{date}",
        "source_tour": "ATP",
        "surface": "Hard",
        "winner_name": winner,
        "loser_name": loser,
        "winner_rank": 40,
        "loser_rank": 100,
        "score": "6-4 6-4",
        "w_svpt": w_svpt,
        "w_1stIn": 38,
        "w_1stWon": w_1st_won,
        "w_2ndWon": 14,
        "w_SvGms": 10,
        "w_bpSaved": 3,
        "w_bpFaced": 4,
        "l_svpt": 62,
        "l_1stIn": 39,
        "l_1stWon": 25,
        "l_2ndWon": 10,
        "l_SvGms": 10,
        "l_bpSaved": 4,
        "l_bpFaced": 6,
    }


def _match():
    return {
        "tour": "atp",
        "tournament": "Audit",
        "surface": "hard",
        "p1": "Alpha",
        "p2": "Beta",
        "scheduled_time": "2026-09-02T15:00:00Z",
    }


def test_undated_history_row_cannot_change_current_engine_prediction():
    valid = [_row(20260820 - i) for i in range(10)]
    baseline = normalize_matches(pd.DataFrame(valid))

    # Malformed source date + deliberately extreme serving values. Before the
    # temporal guard this NaT row was accepted as if it were safe pre-match
    # history and could alter player metrics/probabilities.
    poisoned = valid + [_row("bad-date", w_svpt=40, w_1st_won=38)]
    with_undated = normalize_matches(pd.DataFrame(poisoned))
    assert with_undated["date"].isna().any()

    expected = analyse_match(baseline, _match())
    actual = analyse_match(with_undated, _match())

    assert actual["p1_stats"]["matches"] == expected["p1_stats"]["matches"]
    assert actual["p2_stats"]["matches"] == expected["p2_stats"]["matches"]
    assert actual["first_set_win"] == expected["first_set_win"]
    assert actual["match_win"] == expected["match_win"]
