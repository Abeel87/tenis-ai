from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_performance_center_features():
    s=(ROOT/'frontend/performance-center-v77.js').read_text(encoding='utf-8')
    for x in ['95% CI','Market Lab','Early Hold · walk-forward','Według nawierzchni','Według wersji modelu','data-pc77-period','wilson','minSample']:
        assert x in s

def test_no_fake_model_accuracy():
    s=(ROOT/'frontend/performance-center-v77.js').read_text(encoding='utf-8')
    assert 'Consensus / Serve/Return / Form / Surface' in s
    assert 'N/D osobno' in s
