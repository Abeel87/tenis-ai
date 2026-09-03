from pathlib import Path


def test_point_event_semantics_gate_stays_unresolved_until_real_cache_review():
    text = Path('docs/POINT_EVENT_SEMANTICS_GATE.md').read_text(encoding='utf-8')
    assert 'UNRESOLVED_UNTIL_REVIEWED' in text
    assert 'no new point-level model may affect production' in text
