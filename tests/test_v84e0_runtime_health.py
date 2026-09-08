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
    assert index.index('data-runtime.js') < index.index('src="symphony2.js"')
    assert 'runtime-health-v84e0.js' not in index
    assert 'scenario-dynamic-v84d3.js' not in index


def test_v84e0_removes_minute_full_pool_scan():
    dynamic = Path('frontend/dynamic-weights-v84d1.js').read_text(encoding='utf-8')
    assert 'setInterval(()=>schedule(0),60000)' not in dynamic


def test_history_payload_field_breakdown_diagnostic():
    import json
    from collections import Counter

    path = Path('frontend/data/history.json')
    history = json.loads(path.read_text(encoding='utf-8'))
    totals = Counter()
    present = Counter()
    for entry in history:
        if not isinstance(entry, dict):
            continue
        for key, value in entry.items():
            totals[key] += len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
            present[key] += 1
    top = [
        {
            'field': key,
            'mb': round(size / (1024 * 1024), 3),
            'present': present[key],
            'avg_kb': round(size / max(1, present[key]) / 1024, 2),
        }
        for key, size in totals.most_common(30)
    ]
    raise AssertionError({'entries': len(history), 'file_mb': round(path.stat().st_size / (1024 * 1024), 3), 'top_fields': top})
