from __future__ import annotations

import pandas as pd

from backend.tml_internal_id_alias_audit import build_report


def _row(date, winner, winner_id, loser, loser_id, *, tour="ATP", score="6-4 6-4"):
    return {
        "tourney_date": date,
        "tourney_name": f"T-{date}-{winner}-{loser}",
        "surface": "Hard",
        "winner_name": winner,
        "winner_id": winner_id,
        "loser_name": loser,
        "loser_id": loser_id,
        "score": score,
        "source_tour": tour,
    }


def _results(matches=4):
    return [{
        "id": "fixture-1",
        "scheduled_time": "2026-09-10T12:00:00Z",
        "p1": "Alice Smith",
        "p2": "Opponent Now",
        "p1_stats": {
            "matches": matches,
            "quality": "LOW",
            "history_identity_mode": "exact",
        },
        "p2_stats": {"matches": 10, "quality": "HIGH", "history_identity_mode": "exact"},
    }]


def _baseline():
    return [
        _row("20260901", "Alice Smith", 101, "Opp One", 201),
        _row("20260902", "Opp Two", 202, "Alice Smith", 101),
        _row("20260903", "Alice Smith", 101, "Opp Three", 203),
        _row("20260904", "Opp Four", 204, "Alice Smith", 101),
    ]


def test_same_namespace_alias_is_candidate_and_can_reach_gate():
    rows = _baseline() + [_row("20260905", "A Smith", 101, "Opp Five", 205)]
    report = build_report(pd.DataFrame(rows), _results())
    case = report["cases"][0]
    assert case["net_new_candidate_matches"] == 1
    assert case["projected_matches_upper_bound"] == 5
    assert case["could_reach_minimum_5"] is True
    assert case["candidate_aliases"][0]["namespace"] == "ATP"
    assert report["decision"]["authorize_aliases"] is False


def test_same_numeric_id_in_different_tml_namespace_is_not_joined():
    rows = _baseline() + [_row("20260905", "A Smith", 101, "Opp Five", 205, tour="CH")]
    report = build_report(pd.DataFrame(rows), _results())
    case = report["cases"][0]
    assert case["net_new_candidate_matches"] == 0
    assert case["projected_matches_upper_bound"] == 4
    assert case["could_reach_minimum_5"] is False


def test_ambiguous_anchor_name_to_multiple_ids_rejects_namespace():
    rows = _baseline()
    rows[3] = _row("20260904", "Opp Four", 204, "Alice Smith", 999)
    rows.append(_row("20260905", "A Smith", 101, "Opp Five", 205))
    report = build_report(pd.DataFrame(rows), _results())
    case = report["cases"][0]
    assert case["net_new_candidate_matches"] == 0
    assert case["rejected_namespaces"][0]["reason"] == "anchor_name_maps_to_multiple_ids"


def test_post_cutoff_alias_is_not_used_as_identity_or_supply():
    rows = _baseline() + [_row("20260912", "A Smith", 101, "Opp Five", 205)]
    report = build_report(pd.DataFrame(rows), _results())
    case = report["cases"][0]
    assert case["net_new_candidate_matches"] == 0
    assert case["projected_matches_upper_bound"] == 4


def test_policy_is_audit_only_and_never_cross_provider():
    report = build_report(pd.DataFrame(_baseline()), _results())
    policy = report["policy"]
    assert policy["network_calls"] == 0
    assert policy["fuzzy_matching"] is False
    assert policy["cross_provider_id_comparison"] is False
    assert policy["cross_tml_namespace_id_comparison"] is False
    assert policy["minimum_match_gate"] == 5
    assert policy["minimum_match_gate_changed"] is False
    assert policy["identity_resolver_changed"] is False
    assert policy["model_math_changed"] is False
    assert policy["runtime_change_authorized"] is False
