from datetime import date

from backend.accuracy_lab_v86 import EloIndex, _choose_threshold, _elo_update, _wilson_lower


def test_wilson_prefers_evidence_not_tiny_perfect_sample():
    assert _wilson_lower(18, 20) > _wilson_lower(2, 2)


def test_threshold_optimizer_keeps_minimum_coverage():
    rows = [{"target": 1}] * 8 + [{"target": 0}] * 2 + [{"target": 1}] * 5 + [{"target": 0}] * 5
    probs = [0.90] * 8 + [0.88] * 2 + [0.70] * 5 + [0.60] * 5
    chosen = _choose_threshold(rows, probs, minimum_selected=5, minimum_coverage=0.20)
    assert chosen is not None
    assert 0.55 <= chosen["threshold"] <= 0.90
    assert chosen["selected_n"] >= 5


def test_elo_update_is_zero_sum():
    a, b = _elo_update(1500.0, 1500.0, 32.0)
    assert round(a + b, 8) == 3000.0
    assert a > 1500.0 and b < 1500.0


def test_elo_lookup_is_strictly_before_date():
    idx = EloIndex()
    day = date(2026, 8, 20).toordinal()
    idx._append(idx.overall, "p", day, 1520.0)
    assert idx.overall_before("p", day) == 1500.0
    assert idx.overall_before("p", day + 1) == 1520.0
