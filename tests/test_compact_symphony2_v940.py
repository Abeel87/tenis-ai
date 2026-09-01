import json
from pathlib import Path

from scripts.compact_frontend_data_v853 import prune_symphony2_publication


def test_prune_removes_only_zero_support_rows(tmp_path: Path):
    path = tmp_path / 'symphony2_current.json'
    payload = {
        'current_offer': {'exact_operator_selections': 3, 'zero_support_offer_selections': 1},
        'matches': [{
            'id': 1,
            'scored_selections': [
                {'market': 'match_total', 'operator_model_probability': 0.61, 'fixture_line_verified': True},
                {'market': 'any_set_to_nil', 'operator_model_probability': None},
            ],
            'compositions': {'2': {'selection': [{'market': 'match_total'}], 'joint_probability': 0.55}},
        }],
    }
    path.write_text(json.dumps(payload), encoding='utf-8')

    report = prune_symphony2_publication(path)
    out = json.loads(path.read_text(encoding='utf-8'))

    assert report['removed_zero_support_rows'] == 1
    assert report['kept_scored_rows'] == 1
    assert out['matches'][0]['scored_selections'][0]['market'] == 'match_total'
    assert out['matches'][0]['compositions'] == payload['matches'][0]['compositions']
    assert out['current_offer'] == payload['current_offer']
    assert out['publication_prune_v940']['model_math_changed'] is False
