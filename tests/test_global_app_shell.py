from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
ACCOUNT = (ROOT / "frontend" / "account.js").read_text(encoding="utf-8")
SHELL = (ROOT / "frontend" / "app-shell.js").read_text(encoding="utf-8")
SHELL_CSS = (ROOT / "frontend" / "app-shell.css").read_text(encoding="utf-8")
ORGANIZER = (ROOT / "frontend" / "ui-organizer.js").read_text(encoding="utf-8")


def test_app_shell_is_wired_after_account_and_before_ui_organizer():
    assert 'data-tenis-auth-state="pending"' in INDEX
    assert '<link rel="stylesheet" href="app-shell.css">' in INDEX
    assert '<script src="app-shell.js"></script>' in INDEX
    assert INDEX.index('account.js?v=853') < INDEX.index('app-shell.js')
    assert INDEX.index('app-shell.js') < INDEX.index('ui-organizer.js')


def test_account_exposes_resolved_auth_contract_for_shell():
    assert "authReady=false" in ACCOUNT
    assert "get configured(){return configured}" in ACCOUNT
    assert "get authReady(){return authReady}" in ACCOUNT
    assert "authReady=true" in ACCOUNT
    assert "notify('tenis-ai-auth-change'" in ACCOUNT


def test_shell_uses_existing_three_roles_and_login_gate():
    assert "admin: 'ADMIN'" in SHELL
    assert "moderator: 'MODERATOR'" in SHELL
    assert "user: 'UŻYTKOWNIK'" in SHELL
    assert "id = 'tenis-login-gate'" in SHELL
    assert "data-auth-mode=\"register\"" in SHELL
    assert "dataset.tenisRole" in SHELL
    assert "dataset.tenisAuthState" in SHELL


def test_shell_is_presentation_only_and_does_not_load_or_recalculate_model_data():
    assert "fetch(" not in SHELL
    assert "results.json" not in SHELL
    assert "history.json" not in SHELL
    assert "first_set_win" not in SHELL
    assert "model_confidence" not in SHELL


def test_guest_content_is_hidden_and_authenticated_shell_is_mobile_first():
    assert 'html[data-tenis-auth-state="guest"] body > :not(#tenis-login-gate)' in SHELL_CSS
    assert 'html[data-tenis-auth-state="authenticated"] .tenis-login-gate' in SHELL_CSS
    assert ".tenis-shell-ready .main-tabs" in SHELL_CSS
    assert "@media (max-width:760px)" in SHELL_CSS
    assert "position:fixed;" in SHELL_CSS
    assert "bottom:8px;" in SHELL_CSS


def test_admin_technical_mode_contract_remains_owned_by_ui_organizer():
    assert "return accountRole() === 'admin';" in ORGANIZER
    assert "const next = isAdmin() && requested === 'technical' ? 'technical' : 'simple';" in ORGANIZER
    assert 'html:not([data-tenis-role="admin"]) #tenis-ui-mode-toggle' in SHELL_CSS


def test_simple_match_browser_hides_only_presentation_noise():
    assert "function decorateMatchBrowser()" in SHELL
    assert "renderMatches.__tenisShellWrapped" in SHELL
    assert "Siła " in SHELL
    assert "🎯 Typ na 1. set:" in SHELL
    assert "tenis-technical-detail" in SHELL
    assert 'html[data-tenis-ui-mode="simple"] .tenis-technical-detail' in SHELL_CSS
    assert "first_set_win" not in SHELL
    assert "model_confidence" not in SHELL
