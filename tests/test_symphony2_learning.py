from copy import deepcopy
from datetime import datetime, timezone

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
            "fixture_line_verified": True,
            "model_scores": {"current": 70.0, "catboost": 71.0, "tabpfn": 69.0},
        }],
    }


def _match():
    return {
        "p1": "A", "p2": "B", "best_of": 3,
        "service_model": {"p1_hold": 0.78, "p2_hold": 0.74},
        "first_set_win": {"A": 0.56, "B": 0.44},
    }


def test_candidate_numeric_line_requires_fixture_level_provenance():
    allowed = {"set2_total"}
    base = {
        "market": "set2_total",
        "pick": "over",
        "line": 8.5,
        "result": "hit",
        "operator": "superbet.pl",
        "operator_line_verified": True,
    }
    assert learning._candidate_row_allowed(base, allowed) is False
    assert learning._candidate_row_allowed(
        {**base, "fixture_line_verified": True},
        allowed,
    ) is True




def test_line_market_missing_numeric_line_is_quarantined_before_feature_encoding():
    base = {
        "market": "set2_total",
        "pick": "over",
        "line": None,
        "result": "hit",
        "operator": "superbet.pl",
        "operator_line_verified": True,
        "fixture_line_verified": True,
    }
    assert learning._frozen_operator_row_allowed(base) is False
    assert learning._candidate_row_allowed(base, {"set2_total"}) is False

    entry = _entry(line=21.5)
    entry["playable_autolearn_signals_v912"][0]["line"] = None
    assert learning.build_training_rows([entry]) == []


def test_legacy_playable_numeric_line_without_fixture_proof_is_quarantined():
    entry = _entry(line=21.5)
    entry["playable_autolearn_signals_v912"][0].pop("fixture_line_verified")

    assert learning.build_training_rows([entry]) == []


def test_verified_playable_numeric_line_remains_eligible_for_training():
    rows = learning.build_training_rows([_entry(line=21.5)])

    assert len(rows) == 1
    assert rows[0]["line"] == 21.5
    assert rows[0]["training_source"] == "playable_frozen"


def test_training_rows_use_exact_frozen_operator_line():
    rows = learning.build_training_rows([_entry(line=21.5), _entry(result="miss", line=22.5)])
    assert [r["line"] for r in rows] == [21.5, 22.5]
    assert [r["target"] for r in rows] == [1, 0]
    assert "state_probability" in rows[0]


def test_side_market_training_quarantines_wrong_player_and_accepts_reordered_name():
    entry = {
        "id": "svrcina-darderi",
        "p1": "Dalibor Svrcina",
        "p2": "Luciano Darderi",
        "surface": "hard",
        "tour": "atp",
        "best_of": 3,
        "captured_at": "2026-09-01T10:00:00+00:00",
        "playable_signals_v912": [
            {
                "market": "p1_exactly_1_set", "pick": "no", "player": "Svrcina, Dalibor",
                "score": 70.5, "result": "hit", "operator": "superbet.pl",
                "operator_line_verified": True,
            },
            {
                "market": "p2_exactly_1_set", "pick": "no", "player": "Svrcina, Dalibor",
                "score": 66.9, "result": "miss", "operator": "superbet.pl",
                "operator_line_verified": True,
            },
        ],
    }
    before = deepcopy(entry)

    rows = learning.build_training_rows([entry])

    assert len(rows) == 1
    assert rows[0]["market"] == "p1_exactly_1_set"
    assert rows[0]["player_scope"] == "p1"
    assert rows[0]["target"] == 1
    assert entry == before


def test_history_layer_unions_unique_exact_rows_from_base_and_autolearn():
    entry = _entry(line=21.5)
    entry["playable_signals_v912"] = [{
        "market": "match_total", "pick": "under", "line": 22.5,
        "score": 65.0, "result": "miss", "operator": "superbet.pl",
        "operator_line_verified": True, "fixture_line_verified": True,
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
        "operator_line_verified": True, "fixture_line_verified": True,
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


def test_current_offer_requires_exact_operator_availability_and_both_line_proofs():
    match = {"superbet_market_v91": {
        "operator": "superbet.pl",
        "operator_verified": True,
        "status": "VERIFIED",
        "suspended": False,
        "canonical_selections": [
            {
                "market": "match_total", "pick": "over", "line": 15.5,
                "operator_available": True,
                "operator_line_verified": True,
                "fixture_line_verified": False,
            },
            {
                "market": "match_total", "pick": "over", "line": 18.5,
                "operator_available": True,
                "operator_line_verified": False,
                "fixture_line_verified": True,
            },
            {
                "market": "match_total", "pick": "over", "line": 20.5,
                "operator_line_verified": True,
                "fixture_line_verified": True,
            },
            {
                "market": "match_total", "pick": "over", "line": 21.5,
                "operator_available": True,
                "operator_line_verified": True,
                "fixture_line_verified": True,
            },
        ],
    }}
    rows = engine._current_offer(match)
    assert len(rows) == 1
    assert rows[0]["line"] == 21.5


def test_current_offer_treats_set_handicap_as_numeric_line_market():
    match = {"superbet_market_v91": {
        "operator": "superbet.pl",
        "operator_verified": True,
        "status": "VERIFIED",
        "suspended": False,
        "canonical_selections": [
            {
                "market": "set_handicap", "pick": "A", "line": -1.5,
                "operator_available": True,
                "operator_line_verified": True,
                "fixture_line_verified": False,
            },
            {
                "market": "set_handicap", "pick": "A", "line": -2.5,
                "operator_available": True,
                "operator_line_verified": True,
                "fixture_line_verified": True,
            },
        ],
    }}
    rows = engine._current_offer(match)
    assert len(rows) == 1
    assert rows[0]["market"] == "set_handicap"
    assert rows[0]["line"] == -2.5


def test_current_offer_rejects_wrong_operator_or_suspended_context():
    base = {
        "operator": "superbet.pl",
        "operator_verified": True,
        "status": "VERIFIED",
        "suspended": False,
        "canonical_selections": [{
            "market": "match_winner",
            "pick": "A",
            "operator_available": True,
        }],
    }
    assert len(engine._current_offer({"superbet_market_v91": dict(base)})) == 1
    assert engine._current_offer({
        "superbet_market_v91": {**base, "operator": "superbet.ro"}
    }) == []
    assert engine._current_offer({
        "superbet_market_v91": {**base, "suspended": True}
    }) == []


def test_current_symphony_feed_excludes_started_fixture_but_keeps_future_fixture():
    now = datetime(2026, 8, 31, 18, 30, tzinfo=timezone.utc)
    assert engine._is_current_pre_match_fixture({"scheduled_time": "2026-08-31T18:00:00Z"}, now) is False
    assert engine._is_current_pre_match_fixture({"scheduled_time": "2026-08-31T19:00:00+00:00"}, now) is True


def test_current_symphony_time_filter_does_not_mutate_model_raw_payload():
    match = {
        "scheduled_time": "2026-08-31T18:00:00Z",
        "raw_signals": [{"market": "match_total", "line": 99.5, "score": 99}],
        "match_over_under": {"99.5": {"over": 99.0, "under": 1.0}},
    }
    before = deepcopy(match)
    assert engine._is_current_pre_match_fixture(match, datetime(2026, 8, 31, 18, 30, tzinfo=timezone.utc)) is False
    assert match == before


def test_current_symphony_time_parser_handles_naive_utc_and_unknown_time_conservatively():
    now = datetime(2026, 8, 31, 18, 30, tzinfo=timezone.utc)
    assert engine._is_current_pre_match_fixture({"scheduled_time": "2026-08-31T19:00:00"}, now) is True
    assert engine._is_current_pre_match_fixture({"scheduled_time": "not-a-date"}, now) is False
    assert engine._is_current_pre_match_fixture({}, now) is False


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


def test_calibration_window_is_chronological_and_uses_later_unseen_evaluation():
    rows = [{"target": i % 2, "captured_ts": float(i)} for i in range(90)]
    fit_rows, eval_rows = learning._split_calibration_window(rows)
    assert len(fit_rows) >= learning.MIN_CALIBRATION_FIT_ROWS
    assert len(eval_rows) >= learning.MIN_CALIBRATION_EVAL_ROWS
    assert fit_rows[-1]["captured_ts"] < eval_rows[0]["captured_ts"]


def test_calibrator_reports_separate_fit_and_evaluation_samples():
    fit_raw = ([0.75, 0.25] * 20)
    fit_targets = ([1, 0] * 20)
    eval_raw = ([0.70, 0.30] * 10)
    eval_targets = ([1, 0] * 10)
    _, info = learning._accepted_calibrator(fit_raw, fit_targets, eval_raw, eval_targets)
    assert info["fit_rows"] == 40
    assert info["evaluation_rows"] == 20


def test_candidate_review_ready_gate_uses_only_labels_settled_by_cutoff(monkeypatch):
    history = [
        {
            "captured_at": "2026-08-01T10:00:00+00:00",
            "settled_at": "2026-08-01T13:00:00+00:00",
        },
        {
            "captured_at": "2026-08-02T09:00:00+00:00",
            "settled_at": "2026-08-03T13:00:00+00:00",
        },
        {
            "captured_at": "2026-08-02T09:30:00+00:00",
        },
    ]
    seen = []

    def fake_gate(rows):
        seen.extend(row["settled_at"] for row in rows)
        return {"set2_total"}

    monkeypatch.setattr(learning, "_candidate_review_ready_markets", fake_gate)
    cutoff = learning._date_key("2026-08-02T10:00:00+00:00")

    markets = learning._candidate_markets_as_of(history, cutoff)

    assert markets == {"set2_total"}
    assert seen == ["2026-08-01T13:00:00+00:00"]


def test_explicit_candidate_gate_does_not_recompute_from_future_history(monkeypatch):
    entry = _entry()
    entry["playable_autolearn_signals_v912"] = []
    entry["superbet_candidate_signals_v925"] = [{
        "market": "p1_wins_a_set",
        "pick": "yes",
        "player": "A",
        "score": 72.0,
        "result": "hit",
        "operator": "superbet.pl",
        "operator_line_verified": True,
        "candidate_version": "v925",
    }]

    def forbidden(_rows):
        raise AssertionError("explicit as-of candidate gate must not be recomputed")

    monkeypatch.setattr(learning, "_candidate_review_ready_markets", forbidden)

    assert learning.build_training_rows([entry], candidate_markets=set()) == []


def test_purged_time_split_excludes_labels_unavailable_at_training_cutoff():
    cutoff = 100.0
    rows = [
        {"captured_ts": 80.0, "settled_ts": 90.0, "target": 1},
        {"captured_ts": 85.0, "settled_ts": 120.0, "target": 0},
        {"captured_ts": 90.0, "settled_ts": 0.0, "target": 1},
        {"captured_ts": 110.0, "settled_ts": 130.0, "target": 0},
        {"captured_ts": 120.0, "settled_ts": 0.0, "target": 1},
    ]

    train, valid, purged = learning._purged_time_split(rows, cutoff)

    assert train == [rows[0]]
    assert valid == [rows[3]]
    assert purged == 3


def test_market_support_counts_only_rows_actually_used_for_model_fit(monkeypatch):
    canonical = []
    for i in range(300):
        canonical.append({
            "market": "match_total",
            "pick": "over",
            "surface": "hard",
            "tour": "atp",
            "player_scope": "none",
            "line": 21.5,
            "checkpoint": -1.0,
            "best_of": 3.0,
            "state_probability": 55.0,
            "base_score": 70.0,
            "current_score": 70.0,
            "catboost_score": 70.0,
            "tabpfn_score": 70.0,
            "adaptive_score": 70.0,
            "target": i % 2,
            "captured_ts": float(i + 1),
            "settled_ts": float(i + 1),
            "training_source": "playable_frozen",
        })
    with_candidate_holdout = list(canonical)
    for i in range(260, 280):
        with_candidate_holdout.append({
            **canonical[i],
            "market": "set2_total",
            "line": 8.5,
            "captured_ts": float(i + 1) + 0.1,
            "settled_ts": float(i + 1) + 0.1,
            "training_source": "candidate_review_ready",
        })
    with_candidate_holdout.sort(key=lambda row: row["captured_ts"])

    def fake_rows(_history, candidate_markets=None):
        if candidate_markets == set():
            return list(canonical)
        return list(with_candidate_holdout)

    class FakeCatBoost:
        def __init__(self, **_kwargs):
            pass

        def fit(self, x, y, cat_features=None):
            self.fit_rows = len(x)
            return self

        def predict_proba(self, x):
            return [[0.45, 0.55] for _ in x]

    monkeypatch.setattr(learning, "build_training_rows", fake_rows)
    monkeypatch.setattr(learning, "_candidate_markets_as_of", lambda _history, _cutoff: {"set2_total"})
    monkeypatch.setattr(learning, "CatBoostClassifier", FakeCatBoost)

    model = learning.train_operator_line_model([{"captured_at": "2026-08-01T00:00:00+00:00"}])

    assert model.status == "ready"
    assert model.metrics["candidate_gate_as_of"] is True
    assert model.trained_rows == 240
    assert model.validation_rows == 80
    assert model.market_support["match_total"] == 240
    assert model.market_support.get("set2_total", 0) == 0
    assert sum(model.market_support.values()) == model.trained_rows
    assert model.metrics["training_source_counts"] == {"playable_frozen": 240}
    assert sum(model.metrics["training_source_counts"].values()) == model.trained_rows
