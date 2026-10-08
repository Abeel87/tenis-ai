from datetime import datetime, timedelta, timezone
import backend.ai_evolution as evolution
import backend.prediction_ledger_shadow as ledger


def fixture(days=18, per_day=8, future_labels=False):
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows, history = [], []
    for day in range(days):
        when = base + timedelta(days=day, hours=12)
        for j in range(per_day):
            mid = str(day * 100 + j + 10000)
            rows.append({
                "mode": "SHADOW_ONLY", "prediction_id": "p_" + mid,
                "match_key": "id:" + mid, "candidate_key": "winner|1",
                "scheduled_time": when.isoformat(),
                "captured_at": (when - timedelta(hours=2)).isoformat(),
                "score_semantics": "probability_0_1",
                "model_scores": {
                    "current": {"available": True, "value": .52},
                    "catboost": {"available": True, "value": .78 if j % 2 == 0 else .22},
                    "tabpfn": {"available": True, "value": .5},
                },
            })
            history.append({
                "match_key": "id:" + mid, "result": "hit" if j % 2 == 0 else "miss",
                "settled_at": (when + timedelta(days=40) if future_labels and day == 0
                               else when + timedelta(hours=3)).isoformat(),
            })
    return {"schema_version": ledger.SCHEMA_VERSION, "mode": "SHADOW_ONLY", "rows": rows}, history


def setup_mock(monkeypatch):
    monkeypatch.setattr(evolution.settlement, "_history_index",
                        lambda history: {h["match_key"]: [h] for h in history})
    monkeypatch.setattr(evolution.settlement, "_settlement_fact",
                        lambda row, indexed: ({"status": "SETTLED", **indexed[row["match_key"]][0]}
                                              if row["match_key"] in indexed
                                              else {"status": "N/D", "result": None}))


def run(source, history, now=None):
    return evolution.build_report(
        source, history, now=now or datetime(2026, 10, 1, tzinfo=timezone.utc),
        min_predictions=(16, 8, 8), min_matches=(16, 8, 8))


def test_search_and_chronological_holdout(monkeypatch):
    setup_mock(monkeypatch)
    result = run(*fixture())
    assert result["status"] == "TRAINED_SHADOW_ONLY"
    assert result["challenger"]["model_weights"]["catboost"] > .4
    h = result["challenger"]["evaluation"]["holdout"]
    assert h["challenger_brier"] < h["current_brier"]
    assert result["folds"]["train"]["matches"] == 80
    assert result["folds"]["validation"]["matches"] == 32
    assert result["folds"]["holdout"]["matches"] == 32
    assert result["production_influence"] is False
    assert result["real_betting_enabled"] is False
    assert result["auto_promote"] is False
    assert result["roi"] is None


def test_future_settlement_not_used(monkeypatch):
    setup_mock(monkeypatch)
    result = run(*fixture(future_labels=True), now=datetime(2026, 9, 30, tzinfo=timezone.utc))
    assert result["input_contract"]["rejected_reasons"]["SETTLEMENT_AFTER_AS_OF"] == 8


def test_ambiguous_and_after_start_fail_closed(monkeypatch):
    setup_mock(monkeypatch)
    source, history = fixture()
    source["rows"][0]["captured_at"] = source["rows"][0]["scheduled_time"]
    source["rows"].append(dict(source["rows"][1]))
    result = run(source, history)
    assert result["input_contract"]["rejected_reasons"]["NOT_FROZEN_PREMATCH"] == 1
    assert result["input_contract"]["rejected_reasons"]["AMBIGUOUS_IDENTITY"] == 2


def test_no_data_does_not_claim_training(monkeypatch):
    setup_mock(monkeypatch)
    result = run(*fixture(days=4))
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["challenger"] is None


def test_settlement_embargo(monkeypatch):
    setup_mock(monkeypatch)
    source, history = fixture()
    history[0]["settled_at"] = datetime(2026, 9, 25, tzinfo=timezone.utc).isoformat()
    result = run(source, history)
    assert result["folds"]["train"]["predictions"] == 79


def test_missing_probability_is_not_zero(monkeypatch):
    setup_mock(monkeypatch)
    source, history = fixture()
    source["rows"][0]["model_scores"]["tabpfn"] = {"available": False, "value": None}
    result = run(source, history)
    assert result["input_contract"]["rejected_reasons"]["NO_COMMON_PROBABILITY"] == 1


def test_incompatible_schema_rejected():
    try:
        evolution.build_report({"schema_version": "wrong", "mode": "SHADOW_ONLY", "rows": []}, [],
                               now=datetime(2026, 10, 1, tzinfo=timezone.utc))
    except ValueError as exc:
        assert "schema" in str(exc)
    else:
        raise AssertionError("Expected fail-closed schema check")
