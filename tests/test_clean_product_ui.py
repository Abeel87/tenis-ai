from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
STYLE = (ROOT / "frontend" / "style.css").read_text(encoding="utf-8")
PROJECT_UI = (ROOT / "frontend" / "project-ui.js").read_text(encoding="utf-8")
APP = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
ACCOUNT = (ROOT / "frontend" / "account.js").read_text(encoding="utf-8")


def test_clean_ui_uses_one_canonical_stylesheet_and_no_layered_shell():
    assert sorted(p.name for p in (ROOT / "frontend").glob("*.css")) == ["style.css"]
    assert INDEX.count('rel="stylesheet"') == 1
    assert 'href="style.css"' in INDEX
    for forbidden in (
        "app-shell.css",
        "neon.css",
        "project-ui.css",
        "project-readability.css",
        "ui-cleanup.css",
        "clean-core-v80.css",
    ):
        assert forbidden not in INDEX


def test_legacy_dom_mutators_are_not_loaded():
    for forbidden in (
        "app-shell.js",
        "navigation-tools.js",
        "clarity-labels.js",
        "ui-cleanup.js",
        "project-ui-quality.js",
        "ui-organizer.js",
    ):
        assert f'src="{forbidden}"' not in INDEX


def test_real_auth_screen_and_product_shell_are_structural_html():
    assert 'id="auth-screen"' in INDEX
    assert 'id="product-shell"' in INDEX
    assert 'id="auth-login"' in INDEX
    assert 'id="auth-register"' in INDEX
    assert 'data-tenis-ui-ready="0"' in INDEX
    assert "dataset.tenisAuthState=state" in ACCOUNT
    assert "dataset.tenisRole=" in ACCOUNT
    assert "#auth-login" in ACCOUNT and "#auth-register" in ACCOUNT


def test_clean_match_browser_is_not_legacy_accordion_or_overlay():
    assert 'class="p751-match-card match-tile"' in PROJECT_UI
    assert 'class="match-grid"' in PROJECT_UI
    assert 'class="p751-detail-screen match-page"' in PROJECT_UI
    assert "document.documentElement.dataset.tenisRoute='match'" in PROJECT_UI
    assert "app.innerHTML=detailHtml(m)" in PROJECT_UI
    assert "p751-match-overlay" not in PROJECT_UI
    assert "p751-bottom-nav" not in PROJECT_UI
    assert "p751-group" not in PROJECT_UI


def test_visible_recommendations_use_canonical_filtered_signals_api():
    assert "if(api?.signals)" in PROJECT_UI
    assert "api.signals(m,40)" in PROJECT_UI
    assert "market-quality.js" in INDEX
    assert "match-visibility.js" in INDEX


def test_critical_feature_modules_stay_loaded():
    for script in (
        "player-search.js",
        "community-hub.js",
        "community-admin.js",
        "symphony2.js",
        "player-intelligence-ui.js",
        "performance-dashboard.js",
        "player-dna-shadow.js",
        "market-quality.js",
        "match-visibility.js",
    ):
        assert f'src="{script}' in INDEX


def test_core_app_owns_view_state_instead_of_visual_overlay():
    assert "const VIEW_COPY" in APP
    assert "function updateViewChrome()" in APP
    assert "document.documentElement.dataset.tenisView=view" in APP
    assert "button[data-view]" in APP


def test_product_shell_does_not_flash_before_clean_renderer_ready():
    assert 'html[data-tenis-ui-ready="0"] #product-shell' in STYLE
    assert "dataset.tenisUiReady='1'" in PROJECT_UI


def test_simple_and_technical_admin_modes_survive_rebuild():
    assert 'html[data-tenis-ui-mode="technical"] .technical-status' in STYLE
    assert 'html[data-tenis-ui-mode="simple"] .phase11-technical' in STYLE
    assert 'html:not([data-tenis-role="admin"]) #tenis-ui-mode-toggle' in STYLE


def test_clean_ui_keeps_all_model_math_out_of_presentation_controller():
    for forbidden in (
        "recommended_leg_count=",
        "final_playable_authority=",
        "model_confidence=",
        "green_threshold=",
        "production_influence=",
    ):
        assert forbidden not in PROJECT_UI


def test_dynamic_match_modules_use_clean_in_app_detail_root():
    detail = (ROOT / "frontend" / "match-detail.js").read_text(encoding="utf-8")
    coverage = (ROOT / "frontend" / "superbet-model-coverage.js").read_text(encoding="utf-8")
    segregation = (ROOT / "frontend" / "market-segregation.js").read_text(encoding="utf-8")
    visibility = (ROOT / "frontend" / "match-visibility.js").read_text(encoding="utf-8")

    for source in (detail, coverage, segregation):
        assert "p751-match-overlay" not in source

    assert "const ROOT='#app[data-match-key] .p751-detail-screen';" in detail
    assert "const host=document.querySelector('#app[data-match-key]');" in coverage
    assert "#app[data-match-key] [data-superbet-model-coverage-v922]" in segregation
    assert "function style(){}" in coverage
    assert "function style(){}" in segregation
    assert ".signal-spotlight" in visibility
    assert ".match-group" in visibility


def test_canonical_stylesheet_owns_superbet_market_visuals():
    assert ".sbmc922-panel" in STYLE
    assert ".rp93g-tabs" in STYLE


def test_match_detail_extensions_do_not_watch_the_whole_document():
    coverage = (ROOT / "frontend" / "superbet-model-coverage.js").read_text(encoding="utf-8")
    segregation = (ROOT / "frontend" / "market-segregation.js").read_text(encoding="utf-8")
    assert "new MutationObserver(" not in coverage
    assert "new MutationObserver(" not in segregation
    assert "observe(document.body" not in segregation
    assert "tenis-ai:match-open" in coverage
    assert "tenis-ai:superbet-coverage-ready" in segregation


def test_admin_mode_is_owned_by_clean_project_controller():
    assert "tenis-ai-clean-ui-mode" in PROJECT_UI
    assert "setUiMode" in PROJECT_UI
    assert "syncUiMode" in PROJECT_UI
    assert 'id="tenis-ui-mode-toggle"' in INDEX


def test_no_frontend_runtime_can_recreate_layered_visual_ownership():
    for path in sorted((ROOT / "frontend").glob("*.js")):
        source = path.read_text(encoding="utf-8")
        assert "createElement('style')" not in source
        assert 'createElement("style")' not in source
        assert ".rel='stylesheet'" not in source
        assert '.rel="stylesheet"' not in source
        assert "#p751-match-overlay" not in source
        assert "p751-bottom-nav" not in source
        if "new MutationObserver(" in source:
            assert "observe(document.body" not in source
            assert "observe(document.documentElement" not in source

def test_retired_mobile_css_cannot_override_canonical_shell():
    assert "body{padding-bottom:94px!important}" not in STYLE
    assert "left:50%;bottom:0;transform:translateX(-50%)" not in STYLE
    assert ".player-search-shell{padding:11px!important;margin:9px 0!important}" not in STYLE
    assert "body{padding-left:10px!important;padding-right:10px!important}" not in STYLE
    assert 'html[data-tenis-view="matches"] #v79-health{display:none!important}' in STYLE
    assert '#player-search-input,.player-search-input-wrap input{' in STYLE
    assert '.signal-spotlight-grid{display:flex;grid-template-columns:none' in STYLE

def test_agreed_product_blueprint_is_the_visible_navigation_contract():
    assert 'data-tenis-product="blueprint"' in INDEX
    assert 'data-tenis-view="home"' in INDEX
    for view, label in (("home","Start"),("matches","Mecze"),("picks","Typy"),("players","Zawodnicy"),("account","Konto")):
        assert f'data-view="{view}"' in INDEX
        assert f'<b>{label}</b>' in INDEX
    assert 'class="legacy-view-hook" data-view="stats"' in INDEX
    assert 'id="tenis-admin-center-open"' in INDEX


def test_agreed_product_blueprint_has_real_product_routes():
    assert "let view='home';" in APP
    assert 'function renderProductHome()' in APP
    assert 'function renderProductPicks()' in APP
    assert 'function renderProductPlayers()' in APP
    assert 'function renderProductAccount()' in APP
    assert 'window.TENIS_AI_APP_NAV=Object.freeze' in APP


def test_match_detail_uses_agreed_four_section_information_architecture():
    for tab in ('summary','path','stats','h2h'):
        assert f'data-match-tab="{tab}"' in PROJECT_UI
        assert f'data-match-panel="{tab}"' in PROJECT_UI
    for label in ('Podsumowanie','Przebieg','Statystyki','H2H'):
        assert label in PROJECT_UI
    assert '${topStrip(rows)}' not in PROJECT_UI
    assert 'data-player-dna-tab-slot' in PROJECT_UI
    assert 'data-player-stats-tab-slot' in PROJECT_UI


def test_blueprint_keeps_one_visual_owner_and_role_aware_admin_center():
    assert 'TENIS AI AGREED PRODUCT BLUEPRINT' in STYLE
    assert '.legacy-view-hook{display:none!important}' in STYLE
    assert '[data-tenis-role="admin"] #tenis-admin-center-open' in STYLE
    assert '.match-detail-tabs' in STYLE
    assert '.product-home-hero' in STYLE

