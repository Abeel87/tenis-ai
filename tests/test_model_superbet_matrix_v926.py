from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "frontend" / "raw-playable-separation-v921.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "backend" / "superbet_line_projection_v926.py").read_text(encoding="utf-8")
WRAPPER = (ROOT / "backend" / "superbet_market_context_v913.py").read_text(encoding="utf-8")


def test_model_and_superbet_are_adjacent_but_logically_separate():
    for needle in (
        "MODEL ↔ 🎯 SUPERBET — porównanie obok siebie",
        "MODEL / RAW",
        "MODEL @ SUPERBET LINE",
        "SUPERBET",
        "PLAYABLE",
        "rp921-compare-row",
        "ctx.model_signals",
        "ctx.canonical_selections",
    ):
        assert needle in UI
    assert "bez używania kursu" in UI


def test_zero_is_not_presented_as_a_real_missing_model_signal():
    assert "val(r)!=null&&val(r)>0" in UI
    assert "strength.textContent='N/D'" in UI
    assert "Brak gotowego sygnału modelowego" in UI
    assert "N/D · brak wystarczających danych modelowych" in UI


def test_projection_is_downstream_and_price_free():
    assert "does not train or modify any model" in ADAPTER
    assert "prices_used" in ADAPTER
    assert "model_at_operator_line" in ADAPTER
    assert "projection.augment_results_file()" in WRAPPER
    assert 'VERSION = "v9.1.6"' in WRAPPER
