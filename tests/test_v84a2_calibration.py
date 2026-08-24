from pathlib import Path

from backend.autolearn_v84 import (
    VERSION,
    _apply_current_calibration,
    _fit_current_calibration,
    _prob_from_score,
    _raw_prob_from_score,
    tracking_stats,
)

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def _rows(score=80, hits=60, misses=40):
    return [
        {"base_score": score, "target": 1 if i < hits else 0, "match_key": f"id:{i}"}
        for i in range(hits + misses)
    ]

def test_raw_helper_remains_strength_fraction_only():
    assert abs(_raw_prob_from_score({"base_score": 76}) - 0.76) < 1e-9
    assert abs(_prob_from_score({"base_score": 76}) - 0.76) < 1e-9

def test_platt_stops_treating_80_score_as_literal_80_percent():
    cal = _fit_current_calibration(_rows(score=80, hits=60, misses=40))
    assert cal["status"] == "active"
    p = _prob_from_score({"base_score": 80}, cal)
    assert 0.54 <= p <= 0.66
    assert abs(p - 0.80) > 0.10

def test_calibration_is_monotonic():
    rows = []
    for i in range(100):
        rows.append({"base_score": 65, "target": 1 if i < 55 else 0, "match_key": f"lo:{i}"})
    for i in range(100):
        rows.append({"base_score": 85, "target": 1 if i < 80 else 0, "match_key": f"hi:{i}"})
    cal = _fit_current_calibration(rows)
    assert cal["status"] == "active"
    assert cal["a"] > 0
    assert _apply_current_calibration(0.85, cal) > _apply_current_calibration(0.65, cal)

def test_tracking_does_not_mix_old_probability_method():
    history = [{
        "autolearn_signals_v84": [
            {
                "result": "hit", "tracker_version": "v8.4A.1",
                "model_scores": {"current": 90, "catboost": 80, "ensemble": 85},
                "generator_selected": True,
            },
            {
                "result": "miss", "tracker_version": VERSION,
                "model_scores": {"current": 62, "catboost": 60, "ensemble": 61},
                "generator_selected": False,
            },
        ]
    }]
    scoped = tracking_stats(history, tracker_version=VERSION)
    allv = tracking_stats(history)
    assert scoped["current"]["n"] == 1
    assert allv["current"]["n"] == 2

def test_backend_declares_train_only_and_raw_validation_audit():
    s = read("backend/autolearn_v84.py")
    assert '"fit_scope": "train_only"' in s
    assert '"current_raw": _metrics(val, raw_base_val)' in s

def test_ui_explains_calibrated_engine():
    s = read("frontend/autolearn-v84.js")
    assert "Current Engine · kalibrowany" in s
    assert "Kalibracja Engine" in s
