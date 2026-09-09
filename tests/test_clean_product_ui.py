from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
STYLE = (ROOT / "frontend" / "style.css").read_text(encoding="utf-8")
PROJECT_UI = (ROOT / "frontend" / "project-ui.js").read_text(encoding="utf-8")
APP = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
ACCOUNT = (ROOT / "frontend" / "account.js").read_text(encoding="utf-8")


def test_clean_ui_uses_one_canonical_stylesheet_and_no_layered_shell():
    assert INDEX.count('rel="stylesheet"') == 1
    assert 'href="style.css"' in INDEX
    for forbidden in (
        "app-shell.css",
        "neon.css",
        "project-ui.css",
        "project-readability.css",
        "ui-cleanup.css",
        "clean-core-v80.css",
        "model-guide.css",
        "multi-model.css",
        "neuro-shadow.css",
        "player-search.css",
        "shadow-signals-v894.css",
    ):
        assert forbidden not in INDEX



def test_canonical_stylesheet_is_the_only_physical_frontend_css_owner():
    css_files = sorted(p.name for p in (ROOT / "frontend").glob("*.css"))
    assert css_files == ["style.css"]


def test_neuro_has_no_legacy_navigation_or_dynamic_css_bridge():
    meta = (ROOT / "frontend" / "app-meta.js").read_text(encoding="utf-8")
    neuro = (ROOT / "frontend" / "neuro-shadow.js").read_text(encoding="utf-8")
    assert "loadStyle(" not in meta
    assert "neuro-shadow.css" not in meta
    assert 'id="neuro-open"' in INDEX
    assert "#p751-bottom-nav" not in neuro
    assert "#p751-match-overlay" not in neuro
    assert "#app[data-match-key]" in neuro
    assert not (ROOT / "frontend" / "shadow-signals-v894.js").exists()


def test_match_loading_does_not_restore_retired_shadow_signal_center():
    loading = (ROOT / "frontend" / "match-loading.js").read_text(encoding="utf-8")
    assert "shadow-signals-v894.css" not in loading
    assert "shadow-signals-v894.js" not in loading
    assert "data-shadow-signals-v894" not in loading


def test_legacy_dom_mutators_are_not_loaded():
    for forbidden in (
        "app-shell.js",
        "navigation-tools.js",
        "clarity-labels.js",
        "ui-cleanup.js",
        "project-ui-quality.js",
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


def test_shadow_early_hold_and_integrity_use_clean_runtime_only():
    shadow = (ROOT / "frontend" / "shadow-lab-v78e6.js").read_text(encoding="utf-8")
    early = (ROOT / "frontend" / "early-hold-paths.js").read_text(encoding="utf-8")
    integrity = (ROOT / "frontend" / "integrity-status.js").read_text(encoding="utf-8")

    assert 'id="shadow-open"' in INDEX
    assert "#p751-bottom-nav" not in shadow
    assert "#p751-match-overlay" not in shadow
    assert "data-shadow-filter" in shadow
    assert 'class="match-grid"' in shadow
    assert "#app[data-match-key]" in shadow

    assert "p751-match-overlay" not in early
    assert "#app[data-match-key]" in early

    assert "createElement('link')" not in integrity
    assert "shadow-lab-v78e6.css" not in integrity
    assert "data-shadow-v78e6" not in integrity

    for selector in (
        ".shadow-summary",
        ".shadow-match-tile",
        ".shadow-detail-note",
        ".eh771-player",
        ".integrity-v78a-chip",
    ):
        assert selector in STYLE


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
