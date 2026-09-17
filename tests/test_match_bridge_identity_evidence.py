from __future__ import annotations

from datetime import date

from backend.match_bridge_identity_evidence import build_repeat_match_bridge


def live(match_id, winner, loser, *, tournament="Test Open", surface="hard", score=((6, 4), (6, 3)), day=date(2026, 9, 10)):
    from backend.match_bridge_identity_evidence import _player_key
    return {
        "id": str(match_id),
        "winner": winner,
        "loser": loser,
        "winner_key": _player_key(winner),
        "loser_key": _player_key(loser),
        "tournament": tournament,
        "tournament_key": "test open",
        "match_day": day,
        "surface": surface,
        "score": score,
    }


def tml(row_id, winner, loser, *, tournament="Test Open", surface="hard", score=((6, 4), (6, 3)), day=date(2026, 9, 8)):
    from backend.match_bridge_identity_evidence import _player_key
    return {
        "id": str(row_id),
        "winner": winner,
        "loser": loser,
        "winner_key": _player_key(winner),
        "loser_key": _player_key(loser),
        "tournament": tournament,
        "tournament_key": "test open",
        "tournament_day": day,
        "surface": surface,
        "score": score,
    }


def test_requires_two_distinct_meetings_and_two_exact_anchors():
    report = build_repeat_match_bridge(
        live_records=[
            live("l1", "Anchor One", "A. Player"),
            live("l2", "Anchor Two", "A. Player", score=((6, 2), (6, 4))),
        ],
        tml_rows=[
            tml("t1", "Anchor One", "Alice Player"),
            tml("t2", "Anchor Two", "Alice Player", score=((6, 2), (6, 4))),
        ],
        current_players=["A. Player"],
        history_keys=["Alice Player"],
        existing_resolutions={"a player": (None, "none")},
    )
    assert report["summary"]["current_history_candidates_audit_only"] == 1
    row = report["current_history_candidates"][0]
    assert row["current_key"] == "a player"
    assert row["history_key"] == "alice player"
    assert row["meetings"] == 2
    assert row["distinct_anchors"] == 2
    assert report["policy"]["runtime_alias_authorized"] is False


def test_single_meeting_is_not_promoted():
    report = build_repeat_match_bridge(
        live_records=[live("l1", "Anchor One", "A. Player")],
        tml_rows=[tml("t1", "Anchor One", "Alice Player")],
        current_players=["A. Player"],
        history_keys=["Alice Player"],
        existing_resolutions={"a player": (None, "none")},
    )
    assert report["summary"]["unique_match_bridges"] == 1
    assert report["summary"]["repeated_bridge_pairs"] == 0
    assert report["current_history_candidates"] == []


def test_ambiguous_match_level_evidence_fails_closed():
    report = build_repeat_match_bridge(
        live_records=[
            live("l1", "Anchor One", "A. Player"),
            live("l2", "Anchor Two", "A. Player", score=((6, 2), (6, 4))),
        ],
        tml_rows=[
            tml("t1a", "Anchor One", "Alice Player"),
            tml("t1b", "Anchor One", "Alice Player"),
            tml("t2", "Anchor Two", "Alice Player", score=((6, 2), (6, 4))),
        ],
        current_players=["A. Player"],
        history_keys=["Alice Player"],
        existing_resolutions={"a player": (None, "none")},
    )
    assert report["summary"]["ambiguous_live_matches"] == 1
    assert report["summary"]["unique_match_bridges"] == 1
    assert report["current_history_candidates"] == []


def test_alias_collision_fails_closed():
    report = build_repeat_match_bridge(
        live_records=[
            live("l1", "Anchor One", "A. Player", score=((6, 1), (6, 2))),
            live("l2", "Anchor Two", "A. Player", score=((6, 2), (6, 3))),
            live("l3", "Anchor Three", "A. Player", score=((6, 3), (6, 4))),
            live("l4", "Anchor Four", "A. Player", score=((7, 5), (6, 4))),
        ],
        tml_rows=[
            tml("t1", "Anchor One", "Alice Player", score=((6, 1), (6, 2))),
            tml("t2", "Anchor Two", "Alice Player", score=((6, 2), (6, 3))),
            tml("t3", "Anchor Three", "Alicia Player", score=((6, 3), (6, 4))),
            tml("t4", "Anchor Four", "Alicia Player", score=((7, 5), (6, 4))),
        ],
        current_players=["A. Player"],
        history_keys=["Alice Player", "Alicia Player"],
        existing_resolutions={"a player": (None, "none")},
    )
    assert report["summary"]["repeated_bridge_pairs"] == 2
    assert report["summary"]["collision_current_keys"] == 1
    assert report["current_history_candidates"] == []


def test_exact_tournament_is_required_not_similarity():
    mismatch_live = live("l1", "Anchor One", "A. Player")
    mismatch_live["tournament_key"] = "test open qualifier"
    report = build_repeat_match_bridge(
        live_records=[
            mismatch_live,
            live("l2", "Anchor Two", "A. Player", score=((6, 2), (6, 4))),
        ],
        tml_rows=[
            tml("t1", "Anchor One", "Alice Player"),
            tml("t2", "Anchor Two", "Alice Player", score=((6, 2), (6, 4))),
        ],
        current_players=["A. Player"],
        history_keys=["Alice Player"],
        existing_resolutions={"a player": (None, "none")},
    )
    assert report["summary"]["unique_match_bridges"] == 1
    assert report["current_history_candidates"] == []
    assert report["policy"]["fuzzy_matching"] is False
    assert report["policy"]["similarity_thresholds"] is False


def test_existing_resolution_is_never_overridden():
    report = build_repeat_match_bridge(
        live_records=[
            live("l1", "Anchor One", "A. Player"),
            live("l2", "Anchor Two", "A. Player", score=((6, 2), (6, 4))),
        ],
        tml_rows=[
            tml("t1", "Anchor One", "Alice Player"),
            tml("t2", "Anchor Two", "Alice Player", score=((6, 2), (6, 4))),
        ],
        current_players=["A. Player"],
        history_keys=["Alice Player"],
        existing_resolutions={"a player": ("already resolved", "exact")},
    )
    assert report["summary"]["collision_free_repeated_pairs"] == 1
    assert report["current_history_candidates"] == []
