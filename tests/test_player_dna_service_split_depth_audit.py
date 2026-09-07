from backend.player_dna_service_split_depth_audit import (
    _profile_has_all_four_raw_both,
    _profile_is_terminal,
    audit_payloads,
)


def _score(games):
    return {"sets": [2, 0], "games": games}


def _raw_stats():
    side = {
        "firstServePointsAccuracy": "30/40 (75%)",
        "secondServePointsAccuracy": "12/20 (60%)",
        "firstReturnPoints": "10/30 (33%)",
        "secondReturnPoints": "8/20 (40%)",
    }
    return {"p1": dict(side), "p2": dict(side)}


def _profile(games, *, raw=True, created_at="2026-09-06T12:00:00Z"):
    return {
        "created_at": created_at,
        "input_state": {
            "score": _score(games),
            "stats": _raw_stats() if raw else {"p1": {}, "p2": {}},
        },
    }


def test_terminal_and_raw_helpers_are_strict():
    final = ('[2, 0]', '[6, 3]')
    good = _profile([6, 3])
    nonterminal = _profile([5, 3])
    missing_raw = _profile([6, 3], raw=False)

    assert _profile_is_terminal(good, final) is True
    assert _profile_is_terminal(nonterminal, final) is False
    assert _profile_has_all_four_raw_both(good) is True
    assert _profile_has_all_four_raw_both(missing_raw) is False


def test_audit_identifies_recoverable_terminal_snapshot_without_changing_selector(monkeypatch):
    # Identity is deliberately stubbed here; this test is about snapshot depth,
    # not provider identity parsing, which has its own canonical audit.
    monkeypatch.setattr(
        "backend.player_dna_service_split_depth_audit.player_identity_map",
        lambda payload: {1: {"id": 101}, 2: {"id": 202}},
    )
    monkeypatch.setattr(
        "backend.player_dna_service_split_depth_audit._final_tape_score",
        lambda payload: ('[2, 0]', '[6, 3]'),
    )

    payload = {
        "profiles": [
            _profile([6, 3], created_at="2026-09-06T12:00:00Z"),
            # A later stats-bearing profile regresses to a non-terminal score.
            # The audit may diagnose the earlier terminal snapshot, but it must
            # not silently change the canonical selector.
            _profile([5, 3], created_at="2026-09-06T12:01:00Z"),
        ]
    }

    report = audit_payloads([payload])
    counts = report["counts"]
    comparison = report["comparison"]

    assert counts["latest_terminal_all_four_raw_matches"] == 0
    assert counts["matches_with_any_terminal_all_four_raw"] == 1
    assert counts["recoverable_if_latest_rule_is_only_blocker"] == 1
    assert comparison["potentially_recoverable_matches"] == 1
    assert comparison["safe_selection_change_proven"] is False
    assert report["contract"]["canonical_profile_selection_changed"] is False
    assert report["contract"]["runtime_activation_enabled"] is False
