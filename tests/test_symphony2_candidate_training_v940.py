from backend import symphony2_learning as learning


def _entry(layer, result='hit', market='any_set_to_nil'):
    return {
        'id': 1,
        'p1': 'A',
        'p2': 'B',
        'scheduled_time': '2026-08-01T10:00:00+00:00',
        layer: [{
            'market': market,
            'pick': 'yes',
            'score': 75.0,
            'result': result,
            'operator': 'superbet.pl',
            'operator_line_verified': True,
            'candidate_version': 'v9.2.5',
        }],
    }


def test_candidate_layer_requires_review_ready_market(monkeypatch):
    history = [_entry(learning.CANDIDATE_LAYER)]
    monkeypatch.setattr(learning, '_candidate_review_ready_markets', lambda rows: {'any_set_to_nil'})
    rows = learning.build_training_rows(history)
    assert len(rows) == 1
    assert rows[0]['market'] == 'any_set_to_nil'
    assert rows[0]['training_source'] == 'candidate_review_ready'


def test_candidate_layer_is_blocked_without_gate(monkeypatch):
    history = [_entry(learning.CANDIDATE_LAYER)]
    monkeypatch.setattr(learning, '_candidate_review_ready_markets', lambda rows: set())
    assert learning.build_training_rows(history) == []


def test_candidate_must_be_exact_operator_verified(monkeypatch):
    row = _entry(learning.CANDIDATE_LAYER)
    row[learning.CANDIDATE_LAYER][0]['operator_line_verified'] = False
    monkeypatch.setattr(learning, '_candidate_review_ready_markets', lambda rows: {'any_set_to_nil'})
    assert learning.build_training_rows([row]) == []


def test_playable_duplicate_keeps_priority(monkeypatch):
    candidate = _entry(learning.CANDIDATE_LAYER)
    playable = dict(candidate[learning.CANDIDATE_LAYER][0])
    playable.pop('candidate_version', None)
    playable['score'] = 81.0
    candidate['playable_signals_v912'] = [playable]
    monkeypatch.setattr(learning, '_candidate_review_ready_markets', lambda rows: {'any_set_to_nil'})
    rows = learning.build_training_rows([candidate])
    assert len(rows) == 1
    assert rows[0]['base_score'] == 81.0
    assert rows[0]['training_source'] == 'playable_frozen'
