from backend.neuro_shadow_tracker_v935 import (
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


def test_void_does_not_receive_scoring_metrics():
    pred = register_predictions(_match(), [_row("set3_winner", "Alpha", 0.9)])[0]
    settled = settle_prediction(pred, {
        "status": "completed",
        "p1": "Alpha",
        "p2": "Beta",
        "sets": [[6, 4], [6, 3]],
    })
    assert settled["settlement"] == "void"
    assert "brier" not in settled
    assert "log_loss" not in settled


def test_push_void_is_excluded_from_metrics():
    pred = register_predictions(
        _match(), [_row("set2_total", "over", 0.6, line=9.0)]
    )[0]
    settled = settle_prediction(pred, {
        "status": "completed",
        "p1": "Alpha",
        "p2": "Beta",
        "sets": [[6, 4], [6, 3]],
    })
    assert settled["settlement"] == "void"
    report = summarize([settled])
    assert report["total"] == 1
    assert report["scored"] == 0
    assert report["status_counts"]["void"] == 1
    assert report["overall"]["brier"] is None


def test_summary_recomputes_metrics_instead_of_trusting_cached_fields():
    row = register_predictions(_match(), [_row(probability=0.8)])[0]
    row["settlement"] = "hit"
    row["brier"] = 999.0
    row["log_loss"] = 999.0
    report = summarize([row])
    assert abs(report["overall"]["brier"] - 0.04) < 1e-12
    assert 0 < report["overall"]["log_loss"] < 1


def test_calibration_boundary_probability_one_is_counted_once():
    rows = []
    for index, probability in enumerate((0.0, 0.2, 0.4, 0.8, 1.0), start=1):
        row = register_predictions(
            _match(),
            [dict(_row(probability=probability), source_outcome_id=f"so{index}")],
        )[0]
        row["settlement"] = "hit" if probability >= 0.5 else "miss"
        rows.append(row)
    report = summarize(rows, calibration_bins=5)
    assert sum(bucket["n"] for bucket in report["calibration"]) == len(rows)
    assert sum(1 for bucket in report["calibration"] if bucket["from"] <= 1.0 <= bucket["to"]) == 1


def test_summary_calculates_accuracy_brier_logloss_and_groups():
    base = register_predictions(
        _match(),
        [
            _row("set2_winner", "Alpha", 0.8),
            dict(_row("set2_winner", "Beta", 0.7), source_outcome_id="so2"),
        ],
    )
    final = {
        "status": "completed",
        "p1": "Alpha",
        "p2": "Beta",
        "sets": [[6, 4], [6, 3]],
    }
    settled = [settle_prediction(row, final) for row in base]
    report = summarize(settled, calibration_bins=5)
    assert report["scored"] == 2
    assert report["overall"]["accuracy"] == 0.5
    assert 0 <= report["overall"]["brier"] <= 1
    assert report["overall"]["log_loss"] > 0
    assert report["by_market"]["set2_winner"]["n"] == 2
    assert report["by_surface"]["hard"]["n"] == 2
    assert report["by_source_model"]["state_distribution"]["n"] == 2
    assert sum(bucket["n"] for bucket in report["calibration"]) == 2
