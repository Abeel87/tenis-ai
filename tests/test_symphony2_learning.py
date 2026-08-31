from backend import symphony2_learning as learning
from backend import symphony2_engine as engine
from backend.symphony2_state import build_outcomes


def _entry(result="hit", line=21.5, market="match_total", pick="over"):
    return {
        "id": 1,
        "p1": "A", "p2": "B", "surface": "hard", "tour": "atp", "best_of": 3,
        "captured_at": "2026-08-01T10:00:00+00:00",
        "service_model": {"p1_hold": 0.78, "p2_hold": 0.74},
        "first_set_win": {"A": 0.56, "B": 0.44},
        "playable_autolearn_signals_v912": [{
            "market": market, "pick": pick, "line": line, "score": 72.0,
            "result": result, "operator": "superbet.pl", "operator_line_verified": True,
            "model_scores": {"current": 70.0, "catboost": 71.0, "tabpfn": 69.0},
        }],
    }


def _match():
    return {
        "p1": "A", "p2": "B", "best_of": 3,
        "service_model": {"p1_hold": 0.78, "p2_hold": 0.74},
        "first_set_win": {"A": 0.56, "B": 0.44},
    }


def test_training_rows_use_exact_frozen_operator_line():
    rows = learning.build_training_rows([_entry(line=21.5), _entry(result="miss", line=22.5)])
    assert [r["line"] for r in rows] == [21.5, 22.5]
    assert [r["target"] for r in rows] == [1, 0]
    assert "state_probability" in rows[0]


def test_history_layer_unions_unique_exact_rows_from_base_and_autolearn():
    entry = _entry(line=21.5)
    entry["playable_signals_v912"] = [{
        "market": "match_total", "pick": "under", "line": 22.5,
        "score": 65.0, "result": "miss", "operator": "superbet.pl",
        "operator_line_verified": True,
    }]
    rows = learning.build_training_rows([entry])
    assert {(r["pick"], r["line"], r["target"]) for r in rows} == {
        ("over", 21.5, 1), ("under", 22.5, 0),
    }


def test_history_layer_exact_duplicate_is_kept_once_and_richer_row_wins():
    entry = _entry(line=21.5)
    entry["playable_signals_v912"] = [{
        "market": "match_total", "pick": "over", "line": 21.5,
        "score": 61.0, "result": "hit", "operator": "superbet.pl",
        "operator_line_verified": True,
    }]
    rows = learning.build_training_rows([entry])
    assert len(rows) == 1
    assert rows[0]["base_score"] == 72.0
    assert rows[0]["current_score"] == 70.0


def test_history_layer_does_not_read_unrelated_raw_layers():
    entry = _entry()
    entry["playable_autolearn_signals_v912"] = []
    entry["playable_signals_v912"] = []
    entry["raw_signals"] = [{
        "market": "match_total", "pick": "over", "line": 12.5,
        "result": "hit", "score": 99.0,
    }]
    assert learning.build_training_rows([entry]) == []


def test_training_does_not_invent_line_from_raw_fields():
    entry = _entry()
    entry["match_over_under"] = {"12.5": {"over": 99.0, "under": 1.0}}
    rows = learning.build_training_rows([entry])
    assert len(rows) == 1
    assert rows[0]["line"] == 21.5


def test_current_offer_rejects_line_without_fixture_verification():
    match = {"superbet_market_v91": {
        "operator_verified": True, "status": "VERIFIED",
        "canonical_selections": [
            {"market": "match_total", "pick": "over", "line": 15.5, "operator_available": True},
            {"market": "match_total", "pick": "over", "line": 21.5, "operator_available": True, "fixture_line_verified": True},
        ],
    }}
    rows = engine._current_offer(match)
    assert len(rows) == 1
    assert rows[0]["line"] == 21.5


def test_supported_market_scores_verified_current_line_even_if_exact_number_was_not_repeated_in_history():
    class FakeModel:
        def predict_proba(self, x):
            assert float(x[0][learning.FEATURES.index("line")]) == 23.5
            return [[0.18, 0.82]]

    model = learning.OperatorLineModel(model=FakeModel(), status="ready", market_support={"match_total": 384})
    row = {name: 0 for name in learning.FEATURES}
    row.update({
        "market": "match_total", "pick": "over", "line": 23.5,
        "surface": "hard", "tour": "atp", "player_scope": "none",
    })
    diagnostics = model.predict_diagnostics(row)
    assert diagnostics["support"] == 384
    assert diagnostics["raw"] == 0.82
    assert diagnostics["final"] == 0.82


def test_composer_does_not_stack_two_lines_from_same_market():
    match = _match()
    outcomes = build_outcomes(match)
    rows = [
        {"market": "match_total", "pick": "over", "line": 20.5, "operator_model_probability": 80.0, "state_supported": True, "learning_support_rows": 150},
        {"market": "match_total", "pick": "over", "line": 21.5, "operator_model_probability": 79.0, "state_supported": True, "learning_support_rows": 150},
        {"market": "set1_tiebreak", "pick": "no", "operator_model_probability": 78.0, "state_supported": True, "learning_support_rows": 150},
    ]
    comps = engine._best_compositions(match, rows, outcomes)
    assert "2" in comps
    markets = [x["market"] for x in comps["2"]["selection"]]
    assert markets.count("match_total") == 1


def test_runtime_reports_true_shared_state_joint():
    match = _match()
    outcomes = build_outcomes(match)
    rows = [
        {"market": "match_total", "pick": "over", "line": 21.5, "operator_model_probability": 75.0, "state_supported": True, "learning_support_rows": 150},
        {"market": "set1_tiebreak", "pick": "no", "operator_model_probability": 80.0, "state_supported": True, "learning_support_rows": 150},
    ]
    comp = engine._best_compositions(match, rows, outcomes)["2"]
    assert comp["joint_probability"] is not None
    assert comp["joint_status"] == "EXACT_SHARED_STATE"


def test_low_market_support_does_not_distort_supervised_probability():
    class FakeModel:
        def predict_proba(self, x):
            return [[0.1, 0.9]]

    model = learning.OperatorLineModel(model=FakeModel(), status="ready", market_support={"match_total": 12})
    row = {name: 0 for name in learning.FEATURES}
    row.update({"market": "match_total", "pick": "over", "surface": "hard", "tour": "atp", "player_scope": "none"})
    diagnostics = model.predict_diagnostics(row)
    assert diagnostics["raw"] == 0.9
    assert diagnostics["calibrated"] == 0.9
    assert diagnostics["support"] == 12
    assert diagnostics["reliability"] == 0.1
    assert diagnostics["final"] == 0.9
    assert diagnostics["global_calibrator_applied"] is False


def test_zero_market_support_is_unscored_not_fake_fifty_percent():
    class FakeModel:
        def predict_proba(self, x):
            return [[0.1, 0.9]]

    model = learning.OperatorLineModel(model=FakeModel(), status="ready", market_support={})
    row = {name: 0 for name in learning.FEATURES}
    row.update({"market": "game_state", "pick": "2:2", "surface": "hard", "tour": "atp", "player_scope": "none"})
    diagnostics = model.predict_diagnostics(row)
    assert diagnostics["raw"] == 0.9
    assert diagnostics["support"] == 0
    assert diagnostics["final"] is None
    assert model.predict(row) is None
