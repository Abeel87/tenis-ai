from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_player_dna_shadow_ui_is_canonical_and_linked():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "player-dna-shadow.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "player-dna-shadow.css").read_text(encoding="utf-8")

    assert 'href="player-dna-shadow.css"' in index
    assert 'src="player-dna-shadow.js"' in index
    assert "player-dna-shadow-v" not in index
    assert "player-dna-shadow-v" not in js
    assert ".pds-panel" in css


def test_player_dna_shadow_ui_reads_only_published_shadow_evidence():
    js = (ROOT / "frontend" / "player-dna-shadow.js").read_text(encoding="utf-8")
    assert "data/player_dna_prospective_validation.json" in js
    assert "data/player_dna_hold_walk_forward.json" in js
    assert "SHADOW_UI_ONLY" in js
    assert "Winner markets: wyłączone" in js
    assert "zero wpływu na PROD, Symfonię 2.0 i Superbet PLAYABLE" in js


def test_player_dna_shadow_ui_uses_honest_prospective_sample_labels():
    js = (ROOT / "frontend" / "player-dna-shadow.js").read_text(encoding="utf-8")
    assert "const MIN_SETTLED=150" in js
    assert "Zamrożone typy" in js
    assert "próg pierwszej oceny prospective" in js
    assert "Brier: RAW vs hold-calibrated DNA" in js
    assert "Niżej = lepiej" in js
    assert "PROSPECTIVE ROBUST" in js
    assert "ZBIERAMY DANE" in js


def test_player_dna_shadow_ui_is_event_driven_not_polling():
    js = (ROOT / "frontend" / "player-dna-shadow.js").read_text(encoding="utf-8")
    assert "MutationObserver" not in js
    assert "setInterval(" not in js
    assert "tenis-ai:stats-ready" in js
    assert "tenis-ai:stats-dashboard-ready" in js


def test_player_dna_shadow_ui_exposes_settlement_health_without_guessing_cancellation():
    js = (ROOT / "frontend" / "player-dna-shadow.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "player-dna-shadow.css").read_text(encoding="utf-8")

    assert "settlement_observability" in js
    assert "LEDGER_INTEGRITY_OK" in js
    assert "Czekają &gt;6 h" in js
    assert "Latency median" in js
    assert "Zmiany godziny" in js
    assert "To nie jest automatycznie anulowany mecz" in js
    assert "snapshot pozostaje zamrożony" in js
    assert ".pds-health-grid" in css
