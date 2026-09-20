from __future__ import annotations

import copy
from datetime import datetime, timezone

from backend import prediction_ledger_settlement_shadow as settlement
from backend import prediction_ledger_shadow


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def _scores(current=0.7, catboost=0.7, tabpfn=0.7):
    return {
        "current": {"available": current is not None, "value": current},
        "catboost": {"available": catboost is not None, "value": catboost},
        "tabpfn": {"available": tabpfn is not None, "value": tabpfn},
    }


def _row(
    prediction_id="pred_a",
    match_key="id:100",
    candidate_key="match_total|20.5|over",
    market="match_total",
    pick="over",
    line=20.5,
    scheduled="2026-09-20T10:00:00+00:00",
    captured="2026-09-20T09:00:00+00:00",
    scores=None,
):
    return {
        "schema_version": prediction_ledger_shadow.SCHEMA_VERSION,
        "prediction_id": prediction_id,
        "match_key": match_key,
        "candidate_key": candidate_key,
        "candidate_identity": candidate_key,
        "market": market,
        "pick": pick,
        "line": line,
        "scheduled_time": scheduled,
        "captured_at": captured,
        "model_scores": scores or _scores(),
    }


def _ledger(rows):
    return {
        "schema_version": prediction_ledger_shadow.SCHEMA_VERSION,
        "mode": "SHADOW_ONLY",
        "rows": rows,
    }


def _history_entry(
    match_id=100,
    scheduled="2026-09-20T10:00:00+00:00",
    settled_at="2026-09-20T11:30:00+00:00",
    status="completed",
    sets=None,
):
    sets = sets or [[6, 4], [6, 4]]
    final = {
        "status": status,
        "winner": "Player One",
        "sets": sets,
        "completed_sets": [True for _ in sets],
        "match_score": "2:0",
        "number_of_sets": len(sets),
        "total_games": sum(a + b for a, b in sets),
        "first_set_score": f"{sets[0][0]}:{sets[0][1]}",
        "p1": "Player One",
        "p2": "Player Two",
    }
    return {
        "match_key": f"id:{match_id}",
        "match_id": match_id,
        "scheduled_time": scheduled,
        "p1": "Player One",
        "p2": "Player Two",
        "status": "void" if status == "void" else "settled",
        "result": final,
        "settled_at": settled_at,
        "settlement_source": "Live Tennis API /matches/{id}",
        "settlement_version": "v7.8E5-retirement-partial",
    }


def _selection(rows=None):
    return {
        "schema_version": "prediction-ledger-selection-shadow-v1",
        "rows": rows or [],
    }


def _selection_row(prediction_id, playable=None, symphony=None):
    def fact(value, owner):
        if value is True:
            return {"value": True, "status": "MATCHED", "owner": owner}
        return {"value": None, "status": "N/D", "reason": "NO_EXACT_PREMATCH_EVIDENCE", "owner": owner}

    return {
        "prediction_id": prediction_id,
        "facts": {
            "playable": fact(playable, "superbet_playable"),
            "symphony_selected": fact(symphony, "symphony2_tracker"),
            "ineed_selected": {"value": None, "status": "N/D", "reason": "NO_LOCAL_PROSPECTIVE_OWNER_IN_BUILD"},
        },
    }


def _build(rows, history, selection_rows=None):
    return settlement.build_sidecar(
        _ledger(rows),
        history,
        _selection(selection_rows),
        now=NOW,
    )


def test_exact_completed_total_settles_without_mutating_source_ledger():
    ledger = _ledger([_row()])
    frozen = copy.deepcopy(ledger)
    doc = settlement.build_sidecar(ledger, [_history_entry()], _selection(), now=NOW)

    assert ledger == frozen
    assert doc["rows"][0]["settlement"]["status"] == "SETTLED"
    assert doc["rows"][0]["settlement"]["result"] == "miss"  # total games = 20, OVER 20.5 misses
    assert doc["source_ledger_mutated"] is False
    assert doc["network_fetch_enabled"] is False
    assert doc["production_influence"] is False


def test_same_match_id_with_different_schedule_fails_closed():
    row = _row()
    history = [_history_entry(scheduled="2026-09-20T10:30:00+00:00")]
    doc = _build([row], history)
    fact = doc["rows"][0]["settlement"]
    assert fact["status"] == "N/D"
    assert fact["reason"] == "EXACT_MATCH_ID_SCHEDULE_CONFLICT"


def test_duplicate_exact_history_identity_fails_closed():
    row = _row()
    entry = _history_entry()
    doc = _build([row], [entry, copy.deepcopy(entry)])
    fact = doc["rows"][0]["settlement"]
    assert fact["status"] == "N/D"
    assert fact["reason"] == "AMBIGUOUS_EXACT_HISTORY_MATCH"


def test_non_live_tennis_id_namespace_is_never_guessed():
    row = _row(match_key="players|one|two|2026-09-20", prediction_id="pred_names")
    doc = _build([row], [_history_entry()])
    fact = doc["rows"][0]["settlement"]
    assert fact["status"] == "N/D"
    assert fact["reason"] == "LEDGER_MATCH_KEY_NOT_EXACT_LIVE_TENNIS_ID"


def test_game_state_remains_unverifiable_without_checkpoint_tape():
    row = _row(
        prediction_id="pred_state",
        candidate_key="state|6|3:3",
        market="game_state",
        pick="3:3",
        line=None,
    )
    doc = _build([row], [_history_entry()])
    fact = doc["rows"][0]["settlement"]
    assert fact["status"] == "N/D"
    assert fact["reason"] == "CANONICAL_SCORER_UNVERIFIABLE"


def test_retired_match_total_uses_existing_owner_semantics_and_voids():
    row = _row(prediction_id="pred_retired")
    entry = _history_entry(status="retired", sets=[[6, 4], [2, 1]])
    entry["result"]["completed_sets"] = [True, False]
    doc = _build([row], [entry])
    fact = doc["rows"][0]["settlement"]
    assert fact["status"] == "SETTLED"
    assert fact["result"] == "void"


def test_retired_completed_set_can_settle_set1_total():
    row = _row(
        prediction_id="pred_set1",
        candidate_key="set1_total|9.5|over",
        market="set1_total",
        pick="over",
        line=9.5,
    )
    entry = _history_entry(status="retired", sets=[[6, 4], [2, 1]])
    entry["result"]["completed_sets"] = [True, False]
    doc = _build([row], [entry])
    assert doc["rows"][0]["settlement"]["result"] == "hit"


def test_missing_settlement_provenance_is_nd_not_inferred():
    row = _row()
    entry = _history_entry()
    entry.pop("settlement_version")
    doc = _build([row], [entry])
    fact = doc["rows"][0]["settlement"]
    assert fact["status"] == "N/D"
    assert fact["reason"] == "MISSING_SETTLEMENT_PROVENANCE"


def test_selection_population_is_positive_only_and_never_infers_false():
    rows = [
        _row(prediction_id="pred_play"),
        _row(prediction_id="pred_nd", match_key="id:101"),
    ]
    history = [_history_entry(), _history_entry(match_id=101)]
    selection_rows = [
        _selection_row("pred_play", playable=True, symphony=None),
        _selection_row("pred_nd", playable=None, symphony=None),
    ]
    doc = _build(rows, history, selection_rows)
    by_id = {row["prediction_id"]: row for row in doc["rows"]}

    assert by_id["pred_play"]["population_facts"]["PLAYABLE"] is True
    assert by_id["pred_nd"]["population_facts"]["PLAYABLE"] is None
    assert doc["summary"]["population_reports"]["PLAYABLE"]["rows"] == 1


def test_common_metrics_use_only_hit_miss_and_never_emit_ranking():
    rows = [
        _row(prediction_id="pred_hit", match_key="id:100", line=19.5, candidate_key="match_total|19.5|over"),
        _row(prediction_id="pred_miss", match_key="id:101", line=20.5, candidate_key="match_total|20.5|over"),
        _row(prediction_id="pred_void", match_key="id:102", line=20.5, candidate_key="match_total|20.5|over"),
        _row(prediction_id="pred_not_common", match_key="id:103", scores=_scores(tabpfn=None)),
    ]
    history = [
        _history_entry(match_id=100),  # total 20 -> OVER 19.5 hit
        _history_entry(match_id=101),  # total 20 -> OVER 20.5 miss
        _history_entry(match_id=102, status="void"),
        _history_entry(match_id=103),
    ]
    doc = _build(rows, history)
    report = doc["summary"]["population_reports"]["ALL"]

    assert report["common_model_rows"] == 3
    assert report["common_binary_settled_rows"] == 2
    assert report["common_void_rows"] == 1
    assert report["models"]["current"]["n"] == 2
    assert report["models"]["catboost"]["n"] == 2
    assert report["models"]["tabpfn"]["n"] == 2
    assert doc["metric_contract"]["ranking_enabled"] is False
    assert doc["metric_contract"]["automatic_winner_selection_enabled"] is False
    assert "ranking" not in report


def test_ledger_capture_after_start_is_never_settled():
    row = _row(captured="2026-09-20T10:00:00+00:00")
    doc = _build([row], [_history_entry()])
    fact = doc["rows"][0]["settlement"]
    assert fact["status"] == "N/D"
    assert fact["reason"] == "LEDGER_NOT_VALID_PREMATCH_EVIDENCE"
