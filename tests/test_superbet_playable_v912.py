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
            "operator_verified": True,
            "canonical_selections": [a20, u20, sw1, sw2, st],
            "model_signals": [m20, mu20, msw1, msw2, mst],
        },
    }


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


def test_model_generated_individual_aces_and_df_remain_raw_analysis_only():
    original = _match()
    raw_props = deepcopy(original["serve_props_v72"])
    view, _ = project_match_for_display(original)
    assert view["serve_props_v72"] == raw_props
    assert "1.5" in view["serve_props_v72"]["p1"]["aces"]["lines"]
    assert not any(x.get("market") in {"player_aces", "player_double_faults"} for x in view["superbet_playable_v912"]["signals"])


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
    assert "feedActive=verified>0" in js
    assert "nie jest to stan oferty na żywo" in js
    assert "brak bieżących danych nie oznacza skuteczności 0%" in js
