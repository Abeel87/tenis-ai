from pathlib import Path
import importlib.util, sys
ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    backend_dir=str(Path(path).resolve().parent)
    if backend_dir not in sys.path:
        sys.path.insert(0,backend_dir)
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[name]=mod
    spec.loader.exec_module(mod)
    return mod

def test_frontend_bridge_and_ui():
    mm=(ROOT/'frontend/multi-model.js').read_text(encoding='utf-8')
    ui=(ROOT/'frontend/project-ui.js').read_text(encoding='utf-8')
    assert 'window.TENIS_AI_MODEL_API' in mm
    assert 'modelApi()?.active' in ui
    assert 'Si\u0142a sygna\u0142u' in ui
    assert 'zielonych' in ui
    assert 'Ocena sygna\u0142u' in ui
    assert 'data-sp-market="p772-' in ui
    assert 'tracker rozlicza te\u017c liczb\u0119 tie-break\u00f3w' in ui

def test_player_analytics_formula_parity():
    ui=(ROOT/'frontend/player-analytics.js').read_text(encoding='utf-8')
    for t in ["[scoreRange(av(g,'hold_rate'),60,90),.38]","[metric(g,'match_win'),.45]","[metric(p,'hold1'),.42]","[metric(surf,'match_win'),.40]","[metric(surf,'set1_win'),.15]"]:
        assert t in ui
    assert "pbp_tendencies?.[ui.scope]?.[ui.window]" in ui

def test_pbp_directional_summary_low_probability():
    mod=load('pbp_tracker_test',ROOT/'backend/pbp_tracker.py')
    rows=[{'prob':.20,'actual':False,'brier':.04},{'prob':.80,'actual':True,'brier':.04}]
    s=mod._summary(rows)
    assert s['accuracy']==100.0 and s['hits']==2 and s['avg_confidence']==80.0
    assert mod._signal_confidence(rows[0])==.8

def test_market_lab_outcomes_new_markets():
    mod=load('market_lab_tracker_test',ROOT/'backend/market_lab_tracker_v741.py')
    o=mod.outcomes({'sets':[[6,4],[7,6]]})
    assert o['tiebreak_count_1']==1 and o['tiebreak_count_0']==0
    assert o['set1_winner_p1_under_6.5']==1 and o['set1_winner_p1_over_6.5']==0
    assert o['set2_winner_p1_over_6.5']==1

def test_market_lab_green_means_positive_pick_not_easy_no():
    src=(ROOT/'backend/market_lab_tracker_v741.py').read_text(encoding='utf-8')
    assert 'if p>=.72:' in src
    assert 'directional_green_accuracy' in src

def test_market_lab_conditional_second_set():
    model=(ROOT/'backend/model.py').read_text(encoding='utf-8');lab=(ROOT/'backend/market_lab_v741.py').read_text(encoding='utf-8')
    assert "'second_set_context': second_set_context" in model
    assert 'def build_match(first,second_if_win,second_if_loss,third)' in lab
    assert 'second=second_if_win if w1 else second_if_loss' in lab
    assert 'second=mix_dist(second_if_win,second_if_loss,p1win(first))' in lab

def test_history_source_and_pwa():
    h=(ROOT/'backend/history_tracker.py').read_text(encoding='utf-8')
    sw=(ROOT/'frontend/sw.js').read_text(encoding='utf-8')
    idx=(ROOT/'frontend/index.html').read_text(encoding='utf-8')
    meta=(ROOT/'frontend/app-meta.js').read_text(encoding='utf-8')

    assert "source_model='early_hold_pbp'" in h

    # Verify the live PWA/cache and central metadata contracts without freezing
    # whitespace formatting around object properties.
    assert "const CACHE='tenis-ai-" in sw
    assert "symphony2-v210" in sw
    assert "appVersion: 'v8.0.1'" in meta
    assert "modelVersion:'v7.8D'" in meta
    assert "modelName:'AutoLearn Ensemble + Adaptive Learning'" in meta
    assert "productionModelName:'AutoLearn Ensemble + Dynamic Weights + Adaptive PROD'" in meta
    assert 'app-meta.js?v=' in idx
