"""Self Evolution SHADOW admin UI: accurate CI evidence, no invented training gain."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "frontend"


def test_admin_only_route_and_single_canonical_shell():
    app = (FRONT / "app.js").read_text(encoding="utf-8")
    index = (FRONT / "index.html").read_text(encoding="utf-8")
    assert "link('#admin/evolution','Self Evolution'" in app
    assert "link('#admin/evolution','Self Evolution · SHADOW" in app
    assert "window.TenisSelfEvolutionUI?.panel()" in app
    assert "window.TenisSelfEvolutionUI?.mount()" in app
    assert "!['dashboard','users','evolution'].includes(parts[1])" in app
    assert "if(!admin())return empty('Brak uprawnień administratora.')" in app
    assert 'self-evolution-ui.js' not in index
    assert not (FRONT / 'self-evolution-ui.js').exists()
    assert app.index('window.TenisSelfEvolutionUI={') < app.index('function render()')
    assert index.count('rel="stylesheet"') == 1


def test_workflow_status_requires_actual_main_execution():
    ui = (FRONT / "app.js").read_text(encoding="utf-8").split("/* Tenis AI: canonical mobile presentation.")[0]
    assert "window.TenisAccount?.authenticated===true&&window.TenisAccount.role==='admin'" in ui
    assert "r.head_branch==='main'" in ui
    assert "['schedule','workflow_dispatch'].includes(r.event)" in ui
    assert "run.status!=='completed'" in ui
    assert "run.conclusion!=='success'" in ui
    assert "self-evolution-shadow-" in ui and "self-evolution-memory" in ui
    assert "superbet-quote-evidence-" in ui
    assert "Brak potwierdzonego artefaktu" in ui
    assert "Wynik Brier: N/D" in ui
    assert "Nowy Champion: N/D" in ui
    assert "NIEPOTWIERDZONE" in ui
    assert "ROI" in ui and "PROD" in ui


def test_no_production_data_or_secrets_were_connected():
    ui = (FRONT / "app.js").read_text(encoding="utf-8").split("/* Tenis AI: canonical mobile presentation.")[0]
    assert "https://api.github.com/repos/" in ui
    assert "Authorization" not in ui
    assert "localStorage" not in ui
    assert "supabase" not in ui.lower()
    assert "model_probability" not in ui
    assert "ineed" not in ui.lower()
    assert "economic_roi" not in ui
    assert "POST" not in ui and "PUT" not in ui and "DELETE" not in ui
    assert "fetch(API+path" in ui


def test_pwa_precaches_admin_research_panel_and_retains_fresh_data_policy():
    sw = (FRONT / "sw.js").read_text(encoding="utf-8")
    assert "'app.js'" in sw
    assert "self-evolution-ui.js" not in sw
    assert "tenis-ai-mobile-presentation-20261010-evolution-bundled" in sw
    assert "u.pathname.includes('/data/')" in sw
    assert "fetch(r,{cache:'no-store'})" in sw
