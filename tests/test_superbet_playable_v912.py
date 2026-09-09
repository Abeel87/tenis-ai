from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.signal_settlement import SIGNAL_LAYERS, settle_signal
from backend.superbet_candidate_settlement import (
    LAYER as V925_LAYER,
    build_candidate_stats,
    capture_candidates,
)
from backend.superbet_playable import (
    inject_match,
    is_operator_playable_signal,
    operator_availability,
    pre_match_operator_context_active,
    project_match_for_display,
    signal_signature,
)


ROOT = Path(__file__).resolve().parents[1]


def _selection(market, pick, line=None, checkpoint=None, score=75.0):
    row = {
        "market": market,
        "pick": pick,
        "operator_available": True,
        "operator_line_verified": True,
    }
    if line is not None:
        row["line"] = line
        row["fixture_line_verified"] = True
        row["operator_line_source"] = "oddspapi_fixture_market"
    if checkpoint is not None:
        row["checkpoint"] = checkpoint
    model = {
        **row,
        "key": f"superbet|{market}|{checkpoint or ''}||{line if line is not None else ''}|{pick}",
        "label": f"{market} {pick} {line if line is not None else ''}".strip(),
        "score": score,
        "symphony_raw_probability": score,
        "operator_line_source": "oddspapi_superbet_pl",
    }
    return row, model


def _match():
    a20, m20 = _selection("match_total", "over", 20.5, score=73.0)
    u20, mu20 = _selection("match_total", "under", 20.5, score=27.0)
    sw1, msw1 = _selection("set1_winner", "Player A", score=69.0)
    sw2, msw2 = _selection("set1_winner", "Player B", score=31.0)
    st, mst = _selection("set1_total", "over", 8.5, score=82.0)
    return {
        "id": 1,
        "p1": "Player A",
        "p2": "Player B",
        "scheduled_time": "2099-01-01T12:00:00Z",
        "model_ready": True,
        "match_over_under": {
            "18.5": {"over": 91.0, "under": 9.0},
            "20.5": {"over": 73.0, "under": 27.0},
        },
        "over_under": {
            "7.5": {"over": 94.0, "under": 6.0},
            "8.5": {"over": 82.0, "under": 18.0},
        },
        "first_set_win": {"Player A": 69.0, "Player B": 31.0},
        "autolearn_v84": {
            "signals": [
                {"key": "match_total|18.5|over", "market": "match_total", "pick": "over", "line": 18.5, "current": 91.0, "ensemble": 88.0},
                {"key": "match_total|20.5|over", "market": "match_total", "pick": "over", "line": 20.5, "current": 73.0, "ensemble": 71.0},
            ],
            "by_key": {},
        },
        "serve_props_v72": {
            "ready": True,
            "p1": {"aces": {"mean": 4.2, "lines": {"1.5": {"over": 90, "under": 10}}}, "double_faults": {"mean": 2.2, "lines": {"0.5": {"over": 88, "under": 12}}}},
            "p2": {"aces": {"mean": 3.2, "lines": {"1.5": {"over": 80, "under": 20}}}, "double_faults": {"mean": 3.0, "lines": {"0.5": {"over": 85, "under": 15}}}},
        },
        "superbet_market_v91": {
            "status": "VERIFIED",
            "operator": "superbet.pl",
            "operator_verified": True,
            "suspended": False,
            "canonical_selections": [a20, u20, sw1, sw2, st],
            "model_signals": [m20, mu20, msw1, msw2, mst],
        },
    }




def test_playable_is_strictly_prematch_while_operator_context_and_model_raw_survive():
    match = _match()
    scheduled = datetime(2099, 1, 1, 12, 0, tzinfo=timezone.utc)

    assert pre_match_operator_context_active(
        match, now=scheduled - timedelta(seconds=1)
    ) is True
    assert pre_match_operator_context_active(match, now=scheduled) is False
    assert pre_match_operator_context_active(
        match, now=scheduled + timedelta(minutes=30)
    ) is False

    started = deepcopy(match)
    started["scheduled_time"] = "2000-01-01T12:00:00Z"
    before = deepcopy(started)
    projected, info = inject_match(started)

    assert info["operator_context_verified"] is True
    assert info["active"] is False
    assert info["playable"] == 0
    assert projected["superbet_playable_v912"]["status"] == "NOT_PREMATCH"
    assert projected["superbet_playable_v912"]["signals"] == []
    assert started == before
    assert projected["match_over_under"] == before["match_over_under"]
    assert projected["autolearn_v84"] == before["autolearn_v84"]


def test_known_live_or_terminal_status_is_fail_closed_even_before_scheduled_start():
    scheduled = datetime(2099, 1, 1, 12, 0, tzinfo=timezone.utc)
    for field, status in (
        ("feed_status", "live"),
        ("event_status", "in_progress"),
        ("status", "completed"),
        ("status", "retired"),
        ("status", "cancelled"),
    ):
        match = _match()
        match[field] = status
        assert pre_match_operator_context_active(
            match, now=scheduled - timedelta(hours=1)
        ) is False
        projected, info = inject_match(match)
        assert info["operator_context_verified"] is True
        assert info["active"] is False
        assert info["playable"] == 0
        assert projected["superbet_playable_v912"]["status"] == "NOT_PREMATCH"
        assert projected["superbet_playable_v912"]["signals"] == []

    scheduled_match = _match()
    scheduled_match["feed_status"] = "not_started"
    assert pre_match_operator_context_active(
        scheduled_match, now=scheduled - timedelta(hours=1)
    ) is True


def test_missing_schedule_is_fail_closed_for_playable_only():
    match = _match()
    match.pop("scheduled_time")
    before = deepcopy(match)

    projected, info = inject_match(match)

    assert info["operator_context_verified"] is True
    assert info["active"] is False
    assert projected["superbet_playable_v912"]["status"] == "NOT_PREMATCH"
    assert projected["superbet_playable_v912"]["signals"] == []
    assert match == before


def test_signature_ignores_irrelevant_line_for_game_state():
    a = {"market": "game_state", "pick": "2:2", "checkpoint": 4, "line": None}
    b = {"market": "game_state", "pick": "2-2", "checkpoint": 4, "line": 4}
    assert signal_signature(a) == signal_signature(b)


def test_inject_builds_separate_operator_projection_without_mutating_raw_autolearn():
    original = _match()
    raw_auto = deepcopy(original["autolearn_v84"])
    match, info = inject_match(original)
    assert info["active"] is True
    assert match["autolearn_v84"] == raw_auto
    projection = match["superbet_playable_v912"]
    assert projection["raw_model_fields_preserved"] is True
    assert projection["playable"] is True
    assert any(x.get("market") == "set1_total" and x.get("line") == 8.5 for x in projection["signals"])
    raw18 = next(x for x in match["autolearn_v84"]["signals"] if x.get("line") == 18.5)
    assert "operator_playable" not in raw18


def test_normal_match_view_preserves_raw_ladders_and_exposes_playable_separately():
    original = _match()
    raw_ou = deepcopy(original["match_over_under"])
    raw_set1_ou = deepcopy(original["over_under"])
    raw_auto = deepcopy(original["autolearn_v84"])
    view, info = project_match_for_display(original)
    assert info["active"] is True
    assert view["match_over_under"] == raw_ou
    assert view["over_under"] == raw_set1_ou
    assert view["autolearn_v84"] == raw_auto
    lines = {x.get("line") for x in view["superbet_playable_v912"]["signals"] if x.get("market") == "match_total"}
    assert 20.5 in lines
    assert 18.5 not in lines
    exact = next(
        row for row in view["superbet_playable_v912"]["signals"]
        if row.get("market") == "match_total" and row.get("line") == 20.5
    )
    assert exact["operator_line_verified"] is True
    assert exact["fixture_line_verified"] is True


def test_model_generated_individual_aces_and_df_remain_raw_analysis_only():
    original = _match()
    raw_props = deepcopy(original["serve_props_v72"])
    view, _ = project_match_for_display(original)
    assert view["serve_props_v72"] == raw_props
    assert "1.5" in view["serve_props_v72"]["p1"]["aces"]["lines"]
    assert not any(x.get("market") in {"player_aces", "player_double_faults"} for x in view["superbet_playable_v912"]["signals"])


def test_wrong_operator_identity_is_fail_closed_at_playable_boundary():
    original = _match()
    original["superbet_market_v91"]["operator"] = "superbet.ro"
    raw = deepcopy(original["autolearn_v84"])

    view, info = project_match_for_display(original)

    assert info["active"] is False
    assert view["autolearn_v84"] == raw
    assert view["superbet_playable_v912"]["signals"] == []


def test_set_handicap_signature_keeps_exact_numeric_line_and_is_not_playable_without_promotion():
    a = {
        "market": "set_handicap",
        "pick": "Player A",
        "line": -1.5,
        "operator_available": True,
        "operator_line_verified": True,
        "fixture_line_verified": True,
    }
    b = {**a, "line": -2.5}
    assert signal_signature(a) != signal_signature(b)

    original = _match()
    original["superbet_market_v91"]["canonical_selections"].extend([a, b])
    original["superbet_market_v91"]["model_signals"].append({
        **a,
        "key": "set-handicap-a",
        "score": 80.0,
    })
    view, _ = project_match_for_display(original)

    assert not any(
        row.get("market") == "set_handicap"
        for row in view["superbet_playable_v912"]["signals"]
    )




def test_line_market_requires_numeric_line_and_set3_handicap_keeps_exact_identity_without_promotion():
    malformed = {
        "market": "match_total",
        "pick": "over",
        "line": None,
        "operator_available": True,
        "operator_line_verified": True,
        "fixture_line_verified": True,
    }
    original = _match()
    original["superbet_market_v91"]["canonical_selections"] = [malformed]
    assert operator_availability(original) == {}

    a = {
        "market": "set3_game_handicap",
        "pick": "Player A",
        "line": -1.5,
        "operator_available": True,
        "operator_line_verified": True,
        "fixture_line_verified": True,
    }
    b = {**a, "line": -2.5}
    assert signal_signature(a) != signal_signature(b)

    original = _match()
    original["superbet_market_v91"]["canonical_selections"].extend([a, b])
    original["superbet_market_v91"]["model_signals"].append({
        **a,
        "key": "set3-handicap-a",
        "score": 80.0,
    })
    view, _ = project_match_for_display(original)

    assert not any(
        row.get("market") == "set3_game_handicap"
        for row in view["superbet_playable_v912"]["signals"]
    )


def test_unverified_operator_context_is_fail_closed_but_raw_stays_available():
    original = _match()
    original["superbet_market_v91"]["operator_verified"] = False
    raw = deepcopy(original["autolearn_v84"])
    view, info = project_match_for_display(original)
    assert info["active"] is False
    assert view["autolearn_v84"] == raw
    assert view["superbet_playable_v912"]["playable"] is False
    assert view["superbet_playable_v912"]["signals"] == []
    assert is_operator_playable_signal(view, raw["signals"][1]) is False


def test_playable_history_layers_are_settled_and_total_sets_ou_is_supported():
    for name in (
        "playable_signals_v912", "playable_shadow_lab_v912",
        "playable_autolearn_signals_v912", "playable_shadow_models_v912",
        "superbet_candidate_signals_v925",
    ):
        assert name in SIGNAL_LAYERS
    signal = {"market": "total_sets", "pick": "over", "line": 2.5}
    final = {"status": "completed", "number_of_sets": 3, "sets": [[6, 4], [4, 6], [6, 3]]}
    assert settle_signal(signal, final) == "hit"


def test_v925_candidate_market_families_settle_only_from_valid_final_evidence():
    final = {
        "status": "completed",
        "p1": "Player A",
        "p2": "Player B",
        "sets": [[6, 0], [4, 6], [6, 3]],
        "number_of_sets": 3,
        "total_games": 25,
        "match_score": "2:1",
        "first_set_score": "6:0",
    }
    cases = [
        ({"market": "any_set_to_nil", "pick": "yes"}, "hit"),
        ({"market": "set2_exact_score", "pick": "4:6"}, "hit"),
        ({"market": "exact_sets", "pick": "3"}, "hit"),
        ({"market": "match_games_parity", "pick": "odd"}, "hit"),
        ({"market": "set1_games_parity", "pick": "even"}, "hit"),
        ({"market": "set2_games_parity", "pick": "even"}, "hit"),
        ({"market": "p1_exactly_1_set", "pick": "no"}, "hit"),
        ({"market": "p1_exactly_2_sets", "pick": "yes"}, "hit"),
        ({"market": "p2_exactly_1_set", "pick": "yes"}, "hit"),
        ({"market": "p2_exactly_2_sets", "pick": "no"}, "hit"),
        ({"market": "p1_wins_a_set", "pick": "yes"}, "hit"),
        ({"market": "p2_wins_a_set", "pick": "yes"}, "hit"),
        ({"market": "set_handicap", "pick": "Player A", "line": -0.5}, "hit"),
        ({"market": "set2_game_state", "pick": "2:2", "checkpoint": 4}, "unverifiable"),
    ]
    for signal, expected in cases:
        assert settle_signal(signal, final) == expected, signal


def test_v925_capture_freezes_candidates_as_non_playable_and_excludes_pbp_only():
    match = _match()
    match["superbet_market_v91"]["canonical_selections"].append({
        "market": "exact_sets",
        "pick": "3",
        "operator_available": True,
        "operator_line_verified": True,
    })
    match["superbet_market_v91"]["coverage_shadow_signals"] = [
        {
            "key": "candidate|exact_sets|3",
            "market": "exact_sets",
            "pick": "3",
            "score": 74.0,
            "coverage_status": "MODEL_DERIVED_DISPLAY_ONLY_PENDING_SETTLEMENT",
        },
        {
            "key": "candidate|set2_state|4|2:2",
            "market": "set2_game_state",
            "pick": "2:2",
            "checkpoint": 4,
            "score": 71.0,
        },
    ]
    now = datetime.now(timezone.utc)
    future = (now + timedelta(hours=2)).isoformat()
    match["scheduled_time"] = future
    history = [{"match_id": 1, "p1": "Player A", "p2": "Player B", "scheduled_time": future, "status": "pending"}]
    frozen, info = capture_candidates(history, [match], now=now)
    assert info["captured"] == 1
    assert info["pbp_only_excluded"] == 1
    rows = frozen[0][V925_LAYER]
    assert len(rows) == 1
    assert rows[0]["market"] == "exact_sets"
    assert rows[0]["operator_playable"] is False
    assert rows[0]["candidate_for_playable"] is True
    assert rows[0]["result"] == "pending"


def test_v925_candidate_freeze_rejects_wrong_operator_or_suspended_context():
    now = datetime.now(timezone.utc)
    future = (now + timedelta(hours=2)).isoformat()
    history = [{
        "match_id": 1,
        "p1": "Player A",
        "p2": "Player B",
        "scheduled_time": future,
        "status": "pending",
    }]
    match = _match()
    match["scheduled_time"] = future
    match["superbet_market_v91"]["coverage_shadow_signals"] = [{
        "key": "candidate|exact_sets|3",
        "market": "exact_sets",
        "pick": "3",
        "score": 74.0,
    }]
    match["superbet_market_v91"]["canonical_selections"].append({
        "market": "exact_sets",
        "pick": "3",
        "operator_available": True,
        "operator_line_verified": True,
    })

    wrong_operator = deepcopy(match)
    wrong_operator["superbet_market_v91"]["operator"] = "superbet.ro"
    frozen, info = capture_candidates(history, [wrong_operator], now=now)
    assert info["captured"] == 0
    assert not frozen[0].get(V925_LAYER)

    suspended = deepcopy(match)
    suspended["superbet_market_v91"]["suspended"] = True
    frozen, info = capture_candidates(history, [suspended], now=now)
    assert info["captured"] == 0
    assert not frozen[0].get(V925_LAYER)


def test_v925_numeric_candidate_requires_fixture_proof_and_preserves_direct_source():
    now = datetime.now(timezone.utc)
    future = (now + timedelta(hours=2)).isoformat()
    history = [{
        "match_id": 1,
        "p1": "Player A",
        "p2": "Player B",
        "scheduled_time": future,
        "status": "pending",
    }]

    def build_match(fixture_verified: bool, include_canonical: bool = True):
        match = _match()
        match["scheduled_time"] = future
        evidence = {
            "market": "match_game_handicap",
            "pick": "Player A",
            "line": -1.5,
            "operator_available": True,
            "operator_line_verified": True,
            "fixture_line_verified": fixture_verified,
            "operator_line_source": "superbet_direct_selected_shadow",
            "operator_offer_source": "superbet_direct_selected_shadow",
            "direct_source": True,
        }
        if include_canonical:
            match["superbet_market_v91"]["canonical_selections"].append(dict(evidence))
        match["superbet_market_v91"]["model_signals"].append({
            **evidence,
            "key": "direct|match_game_handicap|a|-1.5",
            "score": 74.0,
        })
        return match

    blocked, blocked_info = capture_candidates(
        history,
        [build_match(False)],
        now=now,
    )
    assert blocked_info["captured"] == 0
    assert not blocked[0].get(V925_LAYER)

    absent, absent_info = capture_candidates(
        history,
        [build_match(True, include_canonical=False)],
        now=now,
    )
    assert absent_info["captured"] == 0
    assert not absent[0].get(V925_LAYER)

    frozen, info = capture_candidates(
        history,
        [build_match(True)],
        now=now,
    )
    assert info["captured"] == 1
    row = frozen[0][V925_LAYER][0]
    assert row["market"] == "match_game_handicap"
    assert row["fixture_line_verified"] is True
    assert row["operator_line_verified"] is True
    assert row["operator_line_source"] == "superbet_direct_selected_shadow"
    assert row["operator_offer_source"] == "superbet_direct_selected_shadow"
    assert row["direct_source"] is True




def test_v925_line_market_missing_numeric_line_is_rejected_from_capture_and_stats():
    now = datetime.now(timezone.utc)
    future = (now + timedelta(hours=2)).isoformat()
    history = [{
        "match_id": 1,
        "p1": "Player A",
        "p2": "Player B",
        "scheduled_time": future,
        "status": "pending",
    }]
    match = _match()
    match["scheduled_time"] = future
    malformed = {
        "market": "set_handicap",
        "pick": "Player A",
        "line": None,
        "operator_available": True,
        "operator_line_verified": True,
        "fixture_line_verified": True,
    }
    match["superbet_market_v91"]["canonical_selections"].append(dict(malformed))
    match["superbet_market_v91"]["coverage_shadow_signals"] = [{
        **malformed,
        "key": "candidate|set_handicap|missing-line",
        "score": 75.0,
    }]

    frozen, info = capture_candidates(history, [match], now=now)
    assert info["captured"] == 0
    assert not frozen[0].get(V925_LAYER)

    stats = build_candidate_stats([{
        V925_LAYER: [{
            **malformed,
            "score": 75.0,
            "result": "hit",
            "operator": "superbet.pl",
        }]
    }])
    assert stats["line_provenance_quarantined_rows"] == 1
    assert "set_handicap" not in stats["by_market"]


def test_v925_stats_quarantine_legacy_numeric_lines_without_fixture_proof():
    legacy_rows = [{
        "market": "set2_total",
        "pick": "over",
        "line": 8.5,
        "score": 75.0,
        "result": "hit",
        "operator": "superbet.pl",
        "operator_line_verified": True,
    } for _ in range(40)]

    legacy_stats = build_candidate_stats([{V925_LAYER: legacy_rows}])
    assert legacy_stats["line_provenance_quarantined_rows"] == 40
    assert "set2_total" not in legacy_stats["by_market"]
    assert "set2_total" not in legacy_stats["review_ready_markets"]

    proven_rows = [
        {**row, "fixture_line_verified": True}
        for row in legacy_rows
    ]
    proven_stats = build_candidate_stats([{V925_LAYER: proven_rows}])
    assert proven_stats["line_provenance_quarantined_rows"] == 0
    assert proven_stats["by_market"]["set2_total"]["promotion_sample"] == 40
    assert proven_stats["by_market"]["set2_total"]["review_ready"] is True
    assert "set2_total" in proven_stats["review_ready_markets"]


def test_v925_promotion_gate_reports_readiness_but_never_auto_promotes():
    rows = []
    for i in range(40):
        rows.append({
            "market": "exact_sets",
            "score": 75.0,
            "result": "hit" if i < 30 else "miss",
        })
    stats = build_candidate_stats([{V925_LAYER: rows}])
    market = stats["by_market"]["exact_sets"]
    assert market["promotion_sample"] == 40
    assert market["promotion_accuracy"] == 75.0
    assert market["review_ready"] is True
    assert stats["review_ready_markets"] == ["exact_sets"]
    assert stats["promotion_gate"]["auto_promote"] is False
    assert stats["contract"]["playable_accuracy_unchanged"] is True


def test_playable_stats_ui_is_explicit_when_operator_feed_is_unverified():
    js = (ROOT / "frontend/superbet-playable-stats.js").read_text(encoding="utf-8")
    assert "FEED N/D" in js
    assert "Brak zweryfikowanej oferty Superbet" in js
    assert "feedActive=matches>0" in js
    assert "nie jest to stan oferty na żywo" in js
    assert "brak bieżących danych nie oznacza skuteczności 0%" in js


def test_master_plan_playable_requires_exact_verified_current_superbet_line():
    original = _match()

    # RAW/model can still expose its own neighboring 18.5 ladder, but the
    # operator currently offers only exact 20.5 for match_total.
    view, info = project_match_for_display(original)
    assert info["active"] is True
    playable_match_totals = [
        row
        for row in view["superbet_playable_v912"]["signals"]
        if row.get("market") == "match_total"
    ]
    assert {row.get("line") for row in playable_match_totals} == {20.5}
    assert not any(row.get("line") == 18.5 for row in playable_match_totals)

    raw_18 = next(
        row
        for row in original["autolearn_v84"]["signals"]
        if row.get("market") == "match_total" and row.get("line") == 18.5
    )
    assert is_operator_playable_signal(view, raw_18) is False

    # Even an exact numeric line must fail closed when that operator selection
    # is not line-verified.
    unverified = deepcopy(original)
    for row in unverified["superbet_market_v91"]["canonical_selections"]:
        if row.get("market") == "match_total" and row.get("line") == 20.5:
            row["operator_line_verified"] = False
    for row in unverified["superbet_market_v91"]["model_signals"]:
        if row.get("market") == "match_total" and row.get("line") == 20.5:
            row["operator_line_verified"] = False

    blocked, blocked_info = project_match_for_display(unverified)
    assert blocked_info["active"] is True
    assert not any(
        row.get("market") == "match_total"
        for row in blocked["superbet_playable_v912"]["signals"]
    )

    # A separately marked operator line is still not exact-current evidence
    # unless its fixture-level provenance is explicitly verified.
    missing_fixture_proof = deepcopy(original)
    for row in missing_fixture_proof["superbet_market_v91"]["canonical_selections"]:
        if row.get("market") == "match_total" and row.get("line") == 20.5:
            row["fixture_line_verified"] = False
    for row in missing_fixture_proof["superbet_market_v91"]["model_signals"]:
        if row.get("market") == "match_total" and row.get("line") == 20.5:
            row["fixture_line_verified"] = False

    blocked_fixture, fixture_info = project_match_for_display(missing_fixture_proof)
    assert fixture_info["active"] is True
    assert not any(
        row.get("market") == "match_total"
        for row in blocked_fixture["superbet_playable_v912"]["signals"]
    )

    # RAW model ladder is still preserved; bookmaker filtering never erases it.
    assert "18.5" in blocked["match_over_under"]
    assert "20.5" in blocked["match_over_under"]
    assert "18.5" in blocked_fixture["match_over_under"]
    assert "20.5" in blocked_fixture["match_over_under"]
