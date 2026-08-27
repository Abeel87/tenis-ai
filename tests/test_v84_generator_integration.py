from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(p): return (ROOT/p).read_text(encoding="utf-8")


def test_v84_assets_are_loaded_without_touching_v82a_pin():
    h=read("frontend/index.html")
    assert 'autolearn-v84.css?v=84a1' in h
    assert 'autolearn-v84.js?v=84a1' in h
    assert 'scenario-studio-v82a.js?v=82a6' in h
    assert h.index('autolearn-v84.js?v=84a1') < h.index('scenario-studio-v82a.js?v=82a6')


def test_generator_uses_autolearn_and_does_not_force_requested_count():
    s=read("frontend/scenario-studio-v82a.js")
    assert "function autoLearnSnapshot(m,s)" in s
    assert "TENIS_AI_AUTOLEARN_V84" in s
    assert "AI znalazło ${selectedMatches}/${mc}" in s
    assert "const selectedMatches=ranked.length" in s
    assert "if(candidates.length<mc)" not in s


def test_live_settlement_reuses_existing_api_call_for_autolearn():
    s=read("backend/live_history_settle.py")
    assert 'settle_layers(x, final' in s
    from signal_settlement import SIGNAL_LAYERS
    assert 'autolearn_signals_v84' in SIGNAL_LAYERS


def test_tabpfn_is_explicit_v2_and_fail_open():
    s=read("backend/tabpfn_challenger_v84.py")
    assert "create_default_for_version" in s
    assert "ModelVersion.V2" in s
    assert '"status": "unavailable"' in s


def test_workflow_runs_autolearn_without_live_api_key():
    w=read(".github/workflows/update-and-pages.yml")
    assert "Optional TabPFN V2 runtime v8.4A" in w
    assert "AutoLearn Ensemble v8.4A" in w
    assert "python backend/autolearn_v84.py" in w
    assert "AutoLearn Integration Guard v8.4A" in w
