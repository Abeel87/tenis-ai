from backend.neuro_shadow_tracker import (
    PLAYABLE_INFLUENCE,
    PRODUCTION_INFLUENCE,
    SYMPHONY_PROD_INFLUENCE,
    prediction_key,
    register_predictions,
    settle_prediction,
    summarize,
)


def _match():
    return {
        "match_id": "m-1",
        "p1": "Alpha",
        "p2": "Beta",
        "scheduled_time": "2026-09-01T12:00:00Z",
        "surface": "hard",
        "tour": "ATP",
    }


def _row(market="set2_winner", pick="Alpha", probability=0.7, *, line=None, player=None, source_model="state_distribution"):
    return {
        "market": market,
        "pick": pick,
        "line": line,
        "player": player,
        "probability": probability,
        "mode": "SHADOW",
        "operator": "Superbet",
        "operator_playable": False,
        "source_market_id": "sm1",
        "source_outcome_id": "so1",
        "adapter_version": "test",
        "source_model": source_model,
    }


def test_tracker_is_hard_shadow_only():
    assert PRODUCTION_INFLUENCE is False
    assert PLAYABLE_INFLUENCE is False
    assert SYMPHONY_PROD_INFLUENCE is False


def test_register_deduplicates_and_rejects_non_shadow_rows():
    row = _row()
    rows = register_predictions(_match(), [row, dict(row)], created_at="2026-09-01T00:00:00Z")
    assert len(rows) == 1
    assert rows[0]["operator_playable"] is False
    assert rows[0]["production_influence"] is False
    assert rows[0]["source_model"] == "state_distribution"
    bad = dict(row, mode="PROD")
    assert register_predictions(_match(), [bad]) == []


def test_prediction_identity_preserves_zero_line_instead_of_collapsing_to_none():
    zero = _row("match_game_handicap", "Alpha", 0.6, line=0.0)
    missing = _row("match_game_handicap", "Alpha", 0.6, line=None)
    assert prediction_key(_match(), zero) != prediction_key(_match(), missing)
    rows = register_predictions(_match(), [zero, missing])
    assert len(rows) == 2
    assert {row["line"] for row in rows} == {0.0, None}


def test_prediction_identity_preserves_zero_match_id():
    match = _match()
    match["match_id"] = 0
    row = _row()
    assert prediction_key(match, row).startswith("0|")
    saved = register_predictions(match, [row])[0]
    assert saved["match_id"] == 0


def test_feature_snapshot_is_deep_frozen_at_registration():
    row = _row()
    row["feature_snapshot"] = {
        "numeric": {"state_probability": 0.61},
        "metadata": {"surface": "hard"},
    }
    saved = register_predictions(_match(), [row])[0]
    row["feature_snapshot"]["numeric"]["state_probability"] = 0.99
    row["feature_snapshot"]["metadata"]["surface"] = "clay"
    assert saved["feature_snapshot"]["numeric"]["state_probability"] == 0.61
    assert saved["feature_snapshot"]["metadata"]["surface"] == "hard"


def test_hit_and_miss_receive_brier_and_log_loss():
    hit = register_predictions(_match(), [_row(probability=0.8)])[0]
    hit = settle_prediction(hit, {
        "status": "completed",
        "p1": "Alpha",
        "p2": "Beta",
        "sets": [[6, 4], [6, 3]],
    }, settled_at="2026-09-01T14:00:00Z")
    assert hit["settlement"] == "hit"
    assert hit["settled_at"] == "2026-09-01T14:00:00Z"
    assert abs(hit["brier"] - 0.04) < 1e-12
    assert hit["log_loss"] > 0

    miss = register_predictions(_match(), [_row(probability=0.8, pick="Beta")])[0]
    miss = settle_prediction(miss, {
        "status": "completed",
        "p1": "Alpha",
        "p2": "Beta",
        "sets": [[6, 4], [6, 3]],
    })
    assert miss["settlement"] == "miss"
    assert abs(miss["brier"] - 0.64) < 1e-12


def test_void_and_unverifiable_are_excluded_from_scoring():
    rows = [
        {**_row(probability=0.6), "settlement": "void"},
        {**_row(probability=0.6), "settlement": "unverifiable"},
    ]
    stats = summarize(rows)
    assert stats["scored"] == 0
    assert stats["overall"]["n"] == 0
    assert stats["void"] == 1
    assert stats["unverifiable"] == 1


def test_summary_reports_calibration_and_market_metrics():
    rows = []
    for probability, settlement in ((0.8, "hit"), (0.7, "miss"), (0.2, "miss")):
        row = _row(probability=probability)
        row["settlement"] = settlement
        row["brier"] = (probability - (1.0 if settlement == "hit" else 0.0)) ** 2
        import math
        y = 1.0 if settlement == "hit" else 0.0
        row["log_loss"] = -(y * math.log(probability) + (1-y)*math.log(1-probability))
        rows.append(row)
    stats = summarize(rows)
    assert stats["scored"] == 3
    assert stats["overall"]["hits"] == 1
    assert stats["overall"]["misses"] == 2
    assert stats["by_market"]["set2_winner"]["n"] == 3
    assert stats["calibration"]
