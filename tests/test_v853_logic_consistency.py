from pathlib import Path

from backend import specialist_learning_v79b as specialist


ROOT = Path(__file__).resolve().parents[1]


def _stats(fatigue):
    return {
        "won": .7,
        "first_set_won": .7,
        "second_set_won": .7,
        "third_set_won": .7,
        "fatigue_load": fatigue,
        "days_since_last": 3,
    }


def test_form_uses_model_fatigue_scale():
    fresh = specialist.strength_form(_stats(0.0))
    tired = specialist.strength_form(_stats(0.18))
    assert round(fresh - tired, 6) == 0.06


def test_learning_does_not_emit_first_set_11_5():
    match = {
        "p1": "A", "p2": "B",
        "p1_stats": _stats(0), "p2_stats": _stats(0),
        "service_model": {"p1_hold": 70, "p2_hold": 70},
        "over_under": {
            "10.5": {"over": 55, "under": 45},
            "11.5": {"over": 55, "under": 45},
        },
    }
    signals = specialist.total_signals(match, "form")
    assert any(s.get("line") == 10.5 for s in signals)
    assert all(s.get("line") != 11.5 for s in signals)


