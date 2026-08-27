from backend.symphony_engine_v90 import build_report


def test_report_contract_is_analysis_only(monkeypatch):
    monkeypatch.setattr('backend.symphony_engine_v90._read', lambda path, fallback: [] if path.name == 'results.json' else {})
    report = build_report()
    assert report['production_influence'] is False
    assert report['shadow_auto_promotion'] is False
    assert report['contract']['does_not_modify_final_score'] is True
    assert report['contract']['shadow_weight_cap'] == 0.25
