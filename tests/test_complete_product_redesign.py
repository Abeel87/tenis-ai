from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
SHELL = (ROOT / "frontend" / "app-shell.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "app-shell.css").read_text(encoding="utf-8")


def test_complete_redesign_keeps_canonical_shell_as_final_visual_layer():
    assert INDEX.count('href="app-shell.css"') == 1
    assert INDEX.index('href="player-dna-shadow.css"') < INDEX.index('href="app-shell.css"')
    assert INDEX.index('href="app-shell.css"') < INDEX.index('</head>')


def test_complete_redesign_covers_all_major_product_surfaces():
    for token in (
        "function decorateStats()",
        "function decorateHistory()",
        "function decorateCommunity()",
        "function decoratePlayerProfiles()",
        "function decorateSymphony()",
        "function decoratePlayerDna()",
        "function decorateAdmin()",
        "function decorateAccount()",
        "function decorateProductSurfaces()",
    ):
        assert token in SHELL

    for selector in (
        ".tenis-performance-surface",
        ".tenis-player-profile-surface",
        ".tenis-symphony-surface",
        ".tenis-dna-surface",
        ".tenis-history-view",
        ".tenis-community-surface",
        ".tenis-admin-surface",
        ".tenis-account-surface",
    ):
        assert selector in CSS


def test_admin_control_center_is_role_gated_and_reuses_existing_actions():
    assert "role() === 'admin'" in SHELL
    assert "id = 'tenis-admin-center-open'" in SHELL
    assert "Control Center" in SHELL
    assert "TENIS_AI_UI_ORGANIZER_V853?.setMode?.(next)" in SHELL
    assert '#p751-bottom-nav [data-p751-nav="symphony2"]' in SHELL
    assert "#community-admin-open" in SHELL
    assert "#refresh" in SHELL


def test_redesign_preserves_simple_and_technical_modes():
    assert "const next = technicalMode() ? 'simple' : 'technical';" in SHELL
    assert "normalizeSimpleCopy" in SHELL
    assert 'html[data-tenis-ui-mode="simple"] .tenis-technical-surface' in CSS
    assert 'html[data-tenis-ui-mode="technical"] .tenis-technical-surface' in CSS


def test_shell_preserves_navigation_and_scroll_context():
    assert "tenis-ai-product-shell-state" in SHELL
    assert "function saveUiState()" in SHELL
    assert "function restoreUiState()" in SHELL
    assert "window.addEventListener('pagehide', saveUiState)" in SHELL
    assert "writeShellState({view:" in SHELL


def test_redesign_shell_does_not_fetch_or_recalculate_model_data():
    forbidden = (
        "fetch(",
        "results.json",
        "history.json",
        "symphony2_current.json",
        "first_set_win",
        "model_confidence",
        "recommended_leg_count",
        "final_playable_authority",
    )
    for token in forbidden:
        assert token not in SHELL


def test_existing_data_and_feature_modules_stay_loaded():
    for script in (
        "symphony2.js",
        "player-dna-shadow.js",
        "player-search.js",
        "performance-dashboard.js",
        "community-hub.js",
        "community-admin.js",
        "history-ui.js",
    ):
        assert f'src="{script}' in INDEX
