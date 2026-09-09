from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON = (ROOT / "frontend" / "superbet-model-coverage.js").read_text(encoding="utf-8")
LOADER = (ROOT / "frontend" / "match-visibility.js").read_text(encoding="utf-8")


def test_coverage_bridge_loads_after_playable_without_legacy_raw_panel():
    assert "function loadSuperbetModelCoverage()" in LOADER
    assert "script.src='superbet-model-coverage.js'" in LOADER
    assert "script.addEventListener('load',loadMarketSegregation,{once:true})" in LOADER
    assert "setTimeout(loadSuperbetModelCoverage,0)" in LOADER
    assert "superbet-model-coverage-v922.js" not in LOADER
    assert "raw-playable-separation-v921" not in LOADER


def test_real_superbet_rows_show_model_probability_or_explicit_uncovered_state():
    assert "MODEL ${approximate?'~':''}${fmt(signal.score)}" in ADDON
    assert "MODEL: niepokryty" in ADDON
    assert "Superbet ✓" in ADDON
    assert "push_probability" in ADDON
    assert "canonical_selections" in ADDON
    assert "model_signals" in ADDON
    assert "coverage_shadow_signals" in ADDON
    assert "SHADOW · " in ADDON
    assert "SUPERBET — pełna aktualna oferta" in ADDON


def test_ui_bridge_never_mutates_model_raw_ownership_fields():
    forbidden = [
        ".p751-top-pick",
        ".p751-strength",
        ".rp921-raw-card",
        "[data-rp921-match]",
        "setBars(",
        "model_weight",
        "threshold=",
        "supabase",
    ]
    lowered = ADDON.lower()
    for token in forbidden:
        assert token.lower() not in lowered
    assert "data-superbet-model-coverage-v922" in ADDON
    assert "MODEL/RAW pozostaje osobną warstwą" in ADDON


def test_addon_is_display_only_and_does_not_fetch_or_train():
    lowered = ADDON.lower()
    for token in ("fetch(", "xmlhttprequest", "fit(", "train(", "websocket"):
        assert token not in lowered
    assert "TENIS_AI_SUPERBET_MODEL_COVERAGE_V922" in ADDON
    assert "coverageKey" in ADDON

def test_full_offer_panel_is_fail_closed_on_operator_and_line_evidence():
    assert "row.operator_available!==true" in ADDON
    assert "const LINE_MARKETS=new Set([" in ADDON
    assert "return finite(row.line)&&row.operator_line_verified===true&&row.fixture_line_verified===true" in ADDON
    assert ".filter(operatorSelectionVerified)" in ADDON
    assert "const current=currentContextActive(match)" in ADDON
    assert "const selections=current?" in ADDON
    assert "operator_available!==false" not in ADDON


def test_full_offer_panel_runtime_rejects_missing_line_and_stale_context():
    import shutil
    import subprocess
    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for runtime UI tests")
    subprocess.run([node, "-e", r"""
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
let current=true;
class MutationObserver { observe(){} }
const win={TENIS_AI_PLAYABLE_UI_V917:{active:()=>current}};
const document={readyState:'loading',addEventListener(){}};
const ctx=vm.createContext({window:win,document,MutationObserver,queueMicrotask,console,setTimeout:()=>0});
vm.runInContext(fs.readFileSync('frontend/superbet-model-coverage.js','utf8'),ctx);
const api=win.TENIS_AI_SUPERBET_MODEL_COVERAGE_V922;
const line={market:'match_total',pick:'over',line:22.5,operator_available:true,operator_line_verified:true,fixture_line_verified:true};
const winner={market:'match_winner',pick:'Player A',line:null,operator_available:true};
const match=rows=>({superbet_market_v91:{canonical_selections:rows,model_signals:[],coverage_shadow_signals:[]}});
assert.match(api.panelHtml(match([line])),/22\.5/);
assert.match(api.panelHtml(match([winner])),/PLAYER A/);
assert.match(api.panelHtml(match([{...line,line:null}])),/Brak dostępnych selekcji w katalogu/);
assert.match(api.panelHtml(match([{...line,operator_available:undefined}])),/Brak dostępnych selekcji w katalogu/);
assert.match(api.panelHtml(match([{...line,operator_line_verified:undefined}])),/Brak dostępnych selekcji w katalogu/);
assert.match(api.panelHtml(match([{...line,fixture_line_verified:undefined}])),/Brak dostępnych selekcji w katalogu/);
current=false;
const stale=api.panelHtml(match([line]));
assert.match(stale,/Brak świeżej oferty Superbet/);
assert.ok(!stale.includes('sbmc922-line'));
"""], cwd=ROOT, check=True)

