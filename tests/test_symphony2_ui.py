from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "symphony2.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "style.css").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
APP_META = (ROOT / "frontend" / "app-meta.js").read_text(encoding="utf-8")
PLAYABLE_UI = (ROOT / "frontend" / "playable-ui.js").read_text(encoding="utf-8")
MATCH_DETAIL = (ROOT / "frontend" / "match-detail.js").read_text(encoding="utf-8")
ARCH = (ROOT / "SYMPHONY_2_ARCHITECTURE.md").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update-and-pages.yml").read_text(encoding="utf-8")


def test_single_symphony2_frontend_is_loaded():
    assert 'src="symphony2.js"' in INDEX
    assert 'href="style.css"' in INDEX
    assert 'href="symphony2.css"' not in INDEX
    assert ".s2-shell" in CSS
    assert ".s2-card" in CSS
    for legacy in (
        "symphony-v90.js", "symphony-v90.css", "symphony-stats-v90d.js",
        "symphony-stats-v90d.css", "symphony-surface-v90.js",
        "symphony-playable-detail-guard-v915.js",
    ):
        assert legacy not in INDEX


def test_stats_ui_reads_only_symphony2_stats():
    assert "./data/symphony2_stats.json" in JS
    assert "#pc77" in JS
    assert "symphony2-performance" in JS
    assert "Wyniki starej Symfonii i starego generatora nie są importowane" in JS
    assert "symphony_stats_v90d.json" not in JS
    assert "symphony_model_stats_v93.json" not in JS


def test_symphony_hub_explains_exact_superbet_probability_contract():
    assert "Finalny PLAYABLE to wyłącznie rekomendowana kompozycja" in JS
    assert "świeżej, dokładnej ofercie Superbet" in JS
    assert "operator_model_probability" in JS
    assert "joint_probability" in JS
    assert "learning_support_rows" in JS
    assert "#symphony2-hub" in JS
    assert "Ułóż Symfonię 2.0" in JS


def test_symphony_controls_follow_actual_published_compositions():
    assert "function availableLegCounts(data)" in JS
    assert "function eligibleMatchCount(data)" in JS
    assert "function countOptions(data)" in JS
    assert "function legOptions(data)" in JS
    assert "Object.keys(m?.compositions||{})" in JS
    assert '<option>6</option>' not in JS


def test_symphony_market_labels_are_human_readable():
    assert "p1_exactly_1set:'Zawodnik 1 · dokładnie 1 wygrany set'" in JS
    assert "p2_exactly_1set:'Zawodnik 2 · dokładnie 1 wygrany set'" in JS
    assert "any_set_to_nil:'Set do zera w meczu'" in JS
    assert "nie wygra dokładnie 1 seta" in JS
    assert "W meczu nie będzie seta do zera" in JS
    assert "zweryfikowana linia Superbet" in JS


def test_symphony2_owns_canonical_structural_control_without_retired_nav():
    assert "const NAV_SELECTOR='#symphony-open'" in JS
    assert 'id="symphony-open"' in INDEX
    assert "p751-bottom-nav" not in JS
    assert "data-p751-nav=\"scenarios\"" not in JS
    assert "TENIS_AI_SCENARIOS" not in JS
    assert "scenario-v82a-panel" not in JS


def test_symphony2_close_clears_its_own_control_state():
    assert "markNav('symphony2',false)" in JS
    assert "aria-pressed" in JS
    assert "markNav('matches',false)" not in JS


def test_symphony2_nav_binding_is_idempotent_and_event_driven():
    assert "new MutationObserver(" not in JS
    assert "if(nav.dataset.symphony2Nav!=='1'){" in JS
    assert "nav.dataset.symphony2Nav='1'" in JS
    assert "nav.addEventListener('click'" in JS
    assert "tenis-ai:match-open" in JS
    assert "tenis-ai:superbet-coverage-ready" in JS


def test_match_view_replaces_legacy_symphony_surfaces_with_symphony2():
    assert "symphony2-match-detail" in JS
    assert "cleanupLegacySymphony" in JS
    assert "data-symphony-match-mini" in JS
    assert "SYMFONIA 2.0 · PLAYABLE" in JS
    assert "RAW nie jest źródłem linii PLAYABLE" in JS
    assert ".s2-match-detail" in CSS


def test_match_view_compacts_full_superbet_offer_without_changing_data():
    assert "compactSuperbet" in JS
    assert "SUPERBET · REALNA OFERTA" in JS
    assert "Dokładne rynki i linie Superbet" in JS
    assert "Pokaż pełną ofertę" in JS
    assert "data-s2-offer-extra" in CSS


def test_no_runtime_reads_legacy_compact_card_feed():
    assert "symphony_match_cards_v90.json" not in JS
    assert "symphony_match_cards_v90.json" not in PLAYABLE_UI
    assert "patchSymphonyMinis" not in PLAYABLE_UI
    assert "reloadCompact" not in PLAYABLE_UI


def test_metadata_boots_symphony_live_ui_without_generator_bootstrap():
    assert "symphony2-live-ui.js" in APP_META
    assert "symphony2-live-ui-v201.js" not in APP_META
    assert "generator-quality-v888.js" not in APP_META
    assert "scenario-studio-v82a.js" not in APP_META


def test_nullable_symphony_numbers_are_not_coerced_to_zero():
    assert "const num=v=>v==null||v===''?null:" in JS
    assert "line=num(x?.line)" in JS
    assert "return line==null?core:" in JS


def test_symphony_actionable_ui_revalidates_prematch_at_render_time():
    assert "function rowPreMatch(row,match=null,now=Date.now())" in JS
    assert "scheduled<=Number(now)" in JS
    assert "TENIS_AI_PLAYABLE_UI_V917" in JS
    assert "api.active(match,now)!==true" in JS
    assert "function currentRows(data,now=Date.now())" in JS
    assert "currentRows(data).map(m=>" in JS
    assert "currentRows(data).filter(m=>" in JS
    assert "currentRows(data).forEach(m=>" in JS
    assert "matchSymphonyHtml(row,data,match)" in JS
    assert "SYMFONIA 2.0 · NIEAKTYWNA" in JS
    assert "Snapshot pre-match lub oferta operatora wygasła" in JS
    assert "Dane MODEL/RAW pozostają bez zmian." in JS



def test_symphony2_is_documented_as_single_final_playable_authority():
    assert "superbet_playable_v912" in ARCH
    assert "nie jest `P_final` Symfonii 2.0" in ARCH
    assert "nie jest authority finalnego PLAYABLE" in ARCH
    assert "symphony2_playable" in ARCH
    assert "AKTUALNA OFERTA SUPERBET -> SUPERVISED P(HIT) -> EXACT JOINT -> SYMFONIA 2.0 -> PLAYABLE" in ARCH
    assert "zerowym supportem jest `N/D` / unscored" in ARCH


def test_main_workflow_names_operator_projection_separately_from_final_playable():
    assert "Superbet exact-offer projection INJECT current real lines" in WORKFLOW
    assert "Superbet exact-offer projection PROJECT frontend + stats" in WORKFLOW
    assert "Superbet exact-offer projection Guard" in WORKFLOW
    assert "Superbet PLAYABLE PROJECT frontend + stats" not in WORKFLOW



def test_match_detail_does_not_equate_verified_offer_with_final_playable():
    assert "final PLAYABLE = Symfonia 2.0" in MATCH_DETAIL
    assert "zweryfikowana oferta Superbet jest osobną warstwą" in MATCH_DETAIL
    assert "SUPERBET PLAYABLE — realna, zweryfikowana oferta operatora" not in MATCH_DETAIL



def test_symphony_no_composition_state_is_not_labeled_playable():
    assert "SYMFONIA 2.0 · BRAK PLAYABLE" in JS
    assert "SYMFONIA 2.0 · PLAYABLE</small><h3>Brak kompozycji" not in JS


def test_symphony2_final_playable_never_falls_back_to_another_composition():
    assert "function finalPlayableLayer(row,match=null,data=null)" in JS
    assert "layer.final_playable_authority!==true" in JS
    assert "layer.playable!==true" in JS
    assert "published!==recommended" in JS
    assert "api.compositionPlayable(match,comp)!==true" in JS
    assert "projected.length!==legs.length" in JS
    assert "compositionFor(row)" not in JS
    assert "for(const k of keys)if(row.compositions" not in JS


def test_symphony2_alternative_sizes_are_explicitly_non_final_analysis():
    assert "WARIANT ANALITYCZNY · NIE FINAL PLAYABLE" in JS
    assert "FINAL PLAYABLE" in JS
    assert "Pozostałe rozmiary kompozycji są tylko wariantami analitycznymi." in JS
    assert "Realne linie Superbet · exact PLAYABLE" not in JS
