from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
BROWSER = (FRONTEND / "match-browser.js").read_text(encoding="utf-8")
PLAYABLE = (FRONTEND / "playable-ui.js").read_text(encoding="utf-8")


def test_playable_and_data_filters_share_one_visible_match_predicate():
    assert "if(state.qualityOnly&&!hasAnalysis(m))return false" in BROWSER
    assert "if(state.mode==='playable'&&!isPlayable(m))return false" in BROWSER
    assert "const isPlayable=m=>playableSignals(m).length>0" in BROWSER
    assert "const playableSignals=m=>" in BROWSER


def test_superbet_top_uses_only_cards_left_visible_by_match_browser():
    assert "Top SUPERBET must be derived from the exact set that Match Browser leaves" in PLAYABLE
    assert ".p751-group:not([hidden]) .p751-match-card[data-p751-open]:not([hidden])" in PLAYABLE
    assert "queueMicrotask(()=>window.TENIS_AI_PLAYABLE_UI_V917?.patchHome?.())" in BROWSER


def test_empty_state_is_driven_by_same_filtered_groups():
    assert "const shownGroups=groups.filter(g=>!g.hidden)" in BROWSER
    assert "if(!shownGroups.length)" in BROWSER
    assert "Brak meczów dla tego zestawu filtrów." in BROWSER


def test_model_raw_remains_independent_from_playable_filtering():
    assert "MODEL/RAW analytics stay independent" in PLAYABLE
    assert "page.dataset.playableUiV917='raw-preserved'" in PLAYABLE
