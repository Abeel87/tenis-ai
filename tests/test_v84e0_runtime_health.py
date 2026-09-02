from pathlib import Path

from scripts.runtime_health import audit


def test_v84e0_runtime_health_contract():
    failures, warnings, metrics = audit(Path.cwd())
    assert not failures, failures
    assert 'results.json' in metrics
    assert isinstance(metrics.get('direct_results_readers'), list)
    assert 'sw.js' not in metrics.get('direct_results_readers', [])
    assert 'sw.js' in metrics.get('service_worker_data_routes', [])


def test_shared_data_runtime_is_loaded_before_heavy_consumers():
    index = Path('frontend/index.html').read_text(encoding='utf-8')
    assert index.index('app.js') < index.index('data-runtime.js')
    assert index.index('data-runtime.js') < index.index('dynamic-weights-v84d1.js')
    assert index.index('data-runtime.js') < index.index('symphony2.js?v=210')
    assert 'runtime-health-v84e0.js' not in index
    assert 'scenario-dynamic-v84d3.js' not in index


def test_v84e0_removes_minute_full_pool_scan():
    dynamic = Path('frontend/dynamic-weights-v84d1.js').read_text(encoding='utf-8')
    assert 'setInterval(()=>schedule(0),60000)' not in dynamic
