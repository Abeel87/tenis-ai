from __future__ import annotations

from backend import symphony_engine_v90 as core
from backend import symphony_scenario_lattice_v93 as deep


def _match():
    return {
        "id": 9301,
        "p1": "Alpha",
        "p2": "Beta",
        "best_of": 3,
        "model_ready": True,
        "service_model": {"p1_hold": 0.76, "p2_hold": 0.72},
        "first_set_win": {"Alpha": 57.0, "Beta": 43.0},
        "second_set_win": {"Alpha": 55.0, "Beta": 45.0},
        "third_set_win": {"Alpha": 54.0, "Beta": 46.0},
        "second_set_context": {
            "p1_if_p1_wins_set1": 52.0,
            "p1_if_p1_loses_set1": 59.0,
        },
        "autolearn_v84": {"signals": []},
    }


def _candidate(market, pick, line=None, checkpoint=None):
    return core.Candidate(
        key=f"{market}|{checkpoint or ''}|{line or ''}|{pick}",
        label=f"{market} {pick}",
        market=market,
        pick=pick,
        line=line,
        checkpoint=checkpoint,
        prod_score=80.0,
        shadow_scores={},
        path_probability=None,
        evidence_score=80.0,
        agreement=0.5,
        conflict=0.0,
    )


def test_deep_outcomes_retain_second_set_checkpoints_and_normalize():
    outcomes = deep._build_deep_outcomes(_match())
    assert outcomes
    assert abs(sum(row["prob"] for row in outcomes) - 1.0) < 1e-9
    assert all(row.get("set2_cp2") is not None for row in outcomes)
    assert all(row.get("set2_cp4") is not None for row in outcomes)
    assert all(row.get("set2_cp6") is not None for row in outcomes)
    assert all(row.get("set2") is not None for row in outcomes)
    assert all(row.get("p1_games") + row.get("p2_games") == row.get("total_games") for row in outcomes)


def test_deep_predicate_covers_set2_checkpoint_and_exact_score():
    pred = deep._deep_predicate(core._predicate)
    row = {
        "set2_cp4": (2, 2),
        "set2": (6, 4),
    }
    cp = pred(_match(), _candidate("set2_game_state", "2:2", checkpoint=4))
    exact = pred(_match(), _candidate("set2_exact_score", "6:4"))
    assert cp is not None and cp(row) is True
    assert exact is not None and exact(row) is True


def test_deep_predicate_covers_candidate_set_families_and_parity():
    pred = deep._deep_predicate(core._predicate)
    row = {
        "sets": (2, 1),
        "set_count": 3,
        "total_games": 31,
        "set1": (6, 4),
        "set2": (4, 6),
        "any_set_to_nil": False,
        "_set_margin_p1": 2,
        "_set_margin_p2": 1,
    }
    assert pred(_match(), _candidate("exact_sets", "3"))(row) is True
    assert pred(_match(), _candidate("match_games_parity", "odd"))(row) is True
    assert pred(_match(), _candidate("set1_games_parity", "even"))(row) is True
    assert pred(_match(), _candidate("p1_wins_a_set", "yes"))(row) is True
    assert pred(_match(), _candidate("p2_exactly_1_set", "yes"))(row) is True
    assert pred(_match(), _candidate("any_set_to_nil", "no"))(row) is True
    assert pred(_match(), _candidate("set_handicap", "Alpha", line=-0.5))(row) is True


def test_v924_candidate_rows_never_become_playable_inside_model_symphony():
    match = _match()
    match["superbet_market_v91"] = {
        "coverage_shadow_signals": [
            {
                "key": "superbet|set2_exact_score||||6:4",
                "market": "set2_exact_score",
                "pick": "6:4",
                "score": 71.0,
                "operator_line_verified": True,
                "coverage_status": "MODEL_DERIVED_DISPLAY_ONLY_PENDING_SETTLEMENT",
            },
            {
                "key": "superbet|most_aces||||Alpha",
                "market": "most_aces",
                "pick": "Alpha",
                "score": 80.0,
            },
        ]
    }
    rows = deep._candidate_only_rows(match)
    assert len(rows) == 1
    assert rows[0]["market"] == "set2_exact_score"
    assert rows[0]["scenario_candidate_only"] is True
    assert rows[0]["symphony_actionable"] is False
    assert rows[0]["operator_playable"] is False
    assert rows[0]["symphony_scenario_layer"] == "MODEL_DERIVED_SHADOW"


def test_story_detects_comeback_and_second_set_patterns():
    match = _match()
    story, text = deep._story_v93(match, (
        _candidate("match_winner", "Alpha"),
        _candidate("set1_winner", "Beta"),
        _candidate("set2_winner", "Alpha"),
    ))
    assert story == "COMEBACK_AFTER_SET1"
    assert "odwrócenie" in text

    story, _ = deep._story_v93(match, (
        _candidate("set2_game_state", "2:0", checkpoint=2),
        _candidate("set2_game_state", "2:2", checkpoint=4),
    ))
    assert story == "BREAK_REBREAK_SET2"


def test_contract_keeps_deep_symphony_separate_from_playable(monkeypatch):
    monkeypatch.setattr(core, "_read", lambda path, fallback: [] if path == core.RESULTS else {})
    report = deep.build_report()
    contract = report["contract"]
    assert report["mode"] == "MODEL_RAW_ANALYSIS_ONLY"
    assert contract["separate_from_superbet_playable"] is True
    assert contract["v925_promotion_gate_not_bypassed"] is True
    assert contract["bookmaker_prices_used"] is False
    assert contract["external_requests"] == 0
