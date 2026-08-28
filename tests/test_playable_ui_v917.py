from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "frontend" / "playable-ui-coherence-v917.js").read_text(encoding="utf-8")
LOADER = (ROOT / "frontend" / "match-list-visibility-v916.js").read_text(encoding="utf-8")


def test_v917_requires_fresh_verified_superbet_context():
    assert "operator_verified===true" in UI
    assert "x.status==='VERIFIED'" in UI
    assert "x.suspended!==true" in UI
    assert "if(!active(match)||!row||typeof row!=='object')return false" in UI


def test_v917_matches_exact_operator_selection_not_just_market_family():
    assert "availability(match).has(signature(row))" in UI
    assert "Number(line).toFixed(6)" in UI
    assert "rowCheckpoint" in UI
    assert "rowPlayer" in UI
    assert "canonical_selections" in UI


def test_v917_actionable_surfaces_share_one_gate():
    assert "playableSignals(match,60)" in UI  # home card / Top
    assert "api.buildRows(match).filter(row=>isPlayable(match,row))" in UI  # Decision Center
    assert "legs.every(leg=>isPlayable(match,leg))" in UI  # compact Symphony
    assert "Brak Superbet PLAYABLE" in UI
    assert "Brak świeżo zweryfikowanej oferty Superbet" in UI


def test_v917_missing_score_is_nd_not_zero():
    assert "return finite(v)?`${Math.round(Number(v))}/100`:'N/D'" in UI
    assert "N/D · brak PLAYABLE" in UI


def test_v917_loader_runs_after_existing_frontend_scripts():
    assert "playable-ui-coherence-v917.js?v=917" in LOADER
    assert "setTimeout(loadPlayableUiV917,0)" in LOADER
