from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = (ROOT / "frontend" / "account.js").read_text(encoding="utf-8")
ORGANIZER = (ROOT / "frontend" / "ui-organizer.js").read_text(encoding="utf-8")
STYLE = (ROOT / "frontend" / "style.css").read_text(encoding="utf-8")
PLAYER_UI = (ROOT / "frontend" / "player-intelligence-ui.js").read_text(encoding="utf-8")
PLAYER_DNA_UI = (ROOT / "frontend" / "player-dna-shadow.js").read_text(encoding="utf-8")
PLAYER_BACKEND = (ROOT / "backend" / "player_intelligence_v85.py").read_text(encoding="utf-8")
MASTER = (ROOT / "TENIS_AI_MATCH_SIMULATION_MASTER_PLAN.md").read_text(encoding="utf-8")


def test_phase11_uses_existing_three_role_profile_contract():
    assert "created_at,role" in ACCOUNT
    assert "function accountRole()" in ORGANIZER
    assert "window.tenisAIAccount?.profile?.role" in ORGANIZER
    assert "window.tenisAICommunityHub?.profile?.role" in ORGANIZER
    assert "return accountRole() === 'admin';" in ORGANIZER


def test_phase11_simple_mode_is_default_and_technical_is_admin_only():
    assert "document.documentElement.dataset.tenisUiMode = 'simple';" in ORGANIZER
    assert "const next = isAdmin() && requested === 'technical' ? 'technical' : 'simple';" in ORGANIZER
    assert "if (!isAdmin()) {" in ORGANIZER
    assert "button?.remove();" in ORGANIZER
    assert "id = 'tenis-ui-mode-toggle'" in ORGANIZER
    assert "tenis-ai-auth-change" in ORGANIZER
    assert "data-tenis-ui-mode" in STYLE
    assert 'html[data-tenis-ui-mode="simple"] .phase11-technical' in STYLE
    assert 'html[data-tenis-ui-mode="technical"] .phase11-simple-only' in STYLE


def test_phase11_player_ui_exposes_real_backend_evidence_not_new_model_math():
    for token in (
        "function pack(p,k,w='10')",
        "rawMetric",
        "volatility",
        "coverageText",
        "trendText",
        "Dlaczego?",
        "RAW → korekta rywal/świeżość/shrinkage",
        "UI nie tworzy własnego confidence score",
        "Matchup edge P1",
        "Serwis P1 ↔ return P2",
        "Return P1 ↔ serwis P2",
    ):
        assert token in PLAYER_UI

    # Backend is the source of all values surfaced by Phase 11.
    for token in (
        '"raw": round(raw, 5)',
        '"adjusted": round(adjusted, 5)',
        '"n": n',
        '"volatility": round(vol, 5)',
        '"trend": _trend(usable)',
        '"coverage": round(coverage, 4)',
        '"reasons": reasons',
    ):
        assert token in PLAYER_BACKEND


def test_phase11_user_language_and_technical_language_are_separated():
    assert "🧬 Analiza zawodników" in PLAYER_UI
    assert "TRYB TESTOWY" in PLAYER_UI
    assert "PLAYER INTELLIGENCE v8.5" in PLAYER_UI
    assert "SHADOW diagnostic only" in PLAYER_UI
    assert "phase11-simple-only" in PLAYER_UI
    assert "phase11-technical" in PLAYER_UI

    assert "🧬 Najbardziej prawdopodobny przebieg" in PLAYER_DNA_UI
    assert "Kilka możliwych scenariuszy — nie jeden pewny wynik." in PLAYER_DNA_UI
    assert "UNVALIDATED_MATCH_LEVEL" in PLAYER_DNA_UI
    assert "phase11-simple-only" in PLAYER_DNA_UI
    assert "phase11-technical" in PLAYER_DNA_UI


def test_phase11_scenario_ui_keeps_top_paths_and_probability_context():
    assert "primary.slice(0,3)" in PLAYER_DNA_UI
    assert "path.probability" in PLAYER_DNA_UI
    assert "after_2_games" in PLAYER_DNA_UI
    assert "after_4_games" in PLAYER_DNA_UI
    assert "after_6_games" in PLAYER_DNA_UI
    assert "p1_serves_first" in PLAYER_DNA_UI
    assert "p2_serves_first" in PLAYER_DNA_UI


def test_phase11_master_plan_has_explicit_close_gate():
    assert "# Faza 11 — UI diagnostyczne" in MASTER
    assert "phase11_complete=true" in MASTER
    assert "phase12_ready=true" in MASTER
    assert "admin" in MASTER
    assert "moderator" in MASTER
    assert "user" in MASTER
