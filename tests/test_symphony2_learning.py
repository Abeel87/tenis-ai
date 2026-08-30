from backend import symphony2_learning as learning
from backend import symphony2_engine as engine


def _entry(result="hit", line=21.5, market="match_total", pick="over"):
    return {
        "id": 1,
        "p1": "A",
        "p2": "B",
        "surface": "hard",
        "tour": "atp",
        "best_of": 3,
        "captured_at": "2026-08-01T10:00:00+00:00",
        "playable_autolearn_signals_v912": [
            {
                "market": market,
                "pick": pick,
                "line": line,
                "score": 72.0,
                "result": result,
                "operator": "superbet.pl",
                "operator_line_verified": True,
                "model_scores": {"current": 70.0, "catboost": 71.0, "tabpfn": 69.0},
            }
        ],
    }


def test_training_rows_use_exact_frozen_operator_line():
    rows = learning.build_training_rows([_entry(line=21.5), _entry(result="miss", line=22.5)])
    assert [r["line"] for r in rows] == [21.5, 22.5]
    assert [r["target"] for r in rows] == [1, 0]


def test_training_does_not_invent_line_from_raw_fields():
    entry = _entry()
    entry["match_over_under"] = {"12.5": {"over": 99.0, "under": 1.0}}
    rows = learning.build_training_rows([entry])
    assert len(rows) == 1
    assert rows[0]["line"] == 21.5


def test_current_offer_rejects_line_without_fixture_verification():
    match = {
        "superbet_market_v91": {
            "operator_verified": True,
            "status": "VERIFIED",
            "canonical_selections": [
                {"market": "match_total", "pick": "over", "line": 15.5, "operator_available": True},
                {"market": "match_total", "pick": "over", "line": 21.5, "operator_available": True, "fixture_line_verified": True},
            ],
        }
    }
    rows = engine._current_offer(match)
    assert len(rows) == 1
    assert rows[0]["line"] == 21.5


def test_composer_does_not_stack_two_lines_from_same_market():
    rows = [
        {"market": "match_total", "pick": "over", "line": 20.5, "operator_model_probability": 80.0},
        {"market": "match_total", "pick": "over", "line": 21.5, "operator_model_probability": 79.0},
        {"market": "set1_tiebreak", "pick": "no", "operator_model_probability": 78.0},
    ]
    comps = engine._best_compositions(rows)
    assert "2" in comps
    markets = [x["market"] for x in comps["2"]["selection"]]
    assert markets.count("match_total") == 1


def test_runtime_never_calls_independent_product_joint_probability():
    rows = [
        {"market": "match_total", "pick": "over", "line": 21.5, "operator_model_probability": 75.0},
        {"market": "set1_tiebreak", "pick": "no", "operator_model_probability": 80.0},
    ]
    comp = engine._best_compositions(rows)["2"]
    assert comp["joint_probability"] is None
    assert comp["joint_status"] == "PENDING_EXACT_SHARED_STATE_ENGINE"
