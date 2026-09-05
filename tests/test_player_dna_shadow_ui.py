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


def test_player_dna_match_detail_reads_published_trajectory_lazily_and_stays_shadow_only():
    js = (ROOT / "frontend" / "player-dna-shadow.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "player-dna-shadow.css").read_text(encoding="utf-8")

    assert "data/player_dna_current_simulation.json" in js
    assert "loadSimulation(force=false)" in js
    assert "player-dna-match-trajectory" in js
    assert "SHADOW_TRAJECTORY_FOUNDATION" in js
    assert "UNVALIDATED_MATCH_LEVEL" in js
    assert "ranking scenariuszy, nie jeden pewny skrypt" in js
    assert "p1_serves_first" in js
    assert "p2_serves_first" in js
    assert "Pierwszy serwujący jest przed meczem nieznany" in js
    assert "zero wpływu na PROD, Symfonię 2.0 i Superbet PLAYABLE" in js
    assert ".pds-trajectory-panel" in css
    assert ".pds-trajectory-grid" in css


def test_player_dna_match_detail_prefers_storyline_families_and_keeps_exact_paths_diagnostic():
    js = (ROOT / "frontend" / "player-dna-shadow.js").read_text(encoding="utf-8")

    assert "match_storylines" in js
    assert "probability_scope==='MATCH_SCORE_FAMILY'" in js
    assert "najbardziej prawdopodobnym reprezentantem tej rodziny" in js
    assert "dokładne pełne ścieżki pozostają diagnostyką SHADOW" in js
    assert "full_match_top_game_paths" in js
    assert "match_top_set_paths" in js
    assert "first_set_top_game_paths" in js
    assert "Pełne ścieżki meczu pojawią się po publikacji nowego raportu trajektorii" in js
    assert "Hold-calibrated DNA pozostaje kandydatem" in js


def test_player_dna_shadow_ui_exposes_dynamic_prospective_ledger_without_promotion():
    js = (ROOT / "frontend" / "player-dna-shadow.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "player-dna-shadow.css").read_text(encoding="utf-8")

    assert "dynamic_lean_evidence" in js
    assert "SHADOW_DYNAMIC_LEAN_PROSPECTIVE_LEDGER_ONLY" in js
    assert "CONSENSUS_DYNAMIC_CANDIDATE" in js
    assert "DYNAMIC_MIN_SETTLED_MARKET_OBSERVATIONS=150" in js
    assert "DYNAMIC_MIN_SETTLED_PER_MARKET=30" in js
    assert "candidate_markets_seen" in js
    assert "profile_reference_brier" in js
    assert "dynamic_candidate_brier" in js
    assert "brier_gain_dynamic_vs_profile" in js
    assert "Gotowa próbka nie oznacza jeszcze pozytywnego verdictu" in js
    assert "performance verdict jest zablokowany" in js
    assert "nie ma auto-promocji" in js
    assert ".pds-dynamic" in css
    assert ".pds-dynamic-support" in css


def test_player_dna_dynamic_ui_keeps_profile_reference_as_benchmark_and_reports_readiness():
    js = (ROOT / "frontend" / "player-dna-shadow.js").read_text(encoding="utf-8")

    assert "PROFILE jest zamrożonym benchmarkiem" in js
    assert "Market observations" in js
    assert "Candidate teraz" in js
    assert "Ledger integrity" in js
    assert "Próg per rynek" in js
    assert "ready_for_performance_verdict" in js
    assert "current_dynamic_candidate_market_slots" in js
    assert "current_rows_with_dynamic_candidates" in js
    assert "zero wpływu na PROD, Symfonię 2.0 i Superbet PLAYABLE" in js
