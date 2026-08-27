import json
from datetime import datetime, timezone

from backend import shadow_experiment_trends_v895 as trends


def test_shadow_guard_never_rewrites_trend_history():
    import subprocess
    import sys
    original = trends.REPORT.read_bytes()
    subprocess.run([sys.executable, 'scripts/verify_v894_shadow_signal_center.py'],
                   cwd=trends.ROOT, check=True, capture_output=True)
    assert trends.REPORT.read_bytes() == original


def test_trends_append_real_snapshots_once_and_never_mutate_model_reports(tmp_path, monkeypatch):
    for name in ('PLAYER', 'LEARNING', 'ELO', 'REPORT'):
        monkeypatch.setattr(trends, name, tmp_path / (name.lower() + '.json'))
    payload = {'generated_at': '2026-08-27T12:00:00Z', 'gate': {'status': 'watch'},
               'holdout': {'player_catboost_shadow': {'n': 30, 'selected_n': 0,
                                                     'accuracy': None, 'brier': .21}}}
    trends.PLAYER.write_text(json.dumps(payload))
    original = trends.PLAYER.read_bytes()
    now = datetime(2026, 8, 27, 13, tzinfo=timezone.utc)
    assert trends.run(now)['appended'] == 1
    assert trends.run(now)['appended'] == 0
    assert trends.PLAYER.read_bytes() == original
    report = json.loads(trends.REPORT.read_text())
    assert report['models']['catboost_player']['points'][0]['accuracy'] is None
    assert report['production_influence'] is False
    payload['generated_at'] = '2026-08-27T14:00:00Z'
    payload['holdout']['player_catboost_shadow']['brier'] = .20
    trends.PLAYER.write_text(json.dumps(payload))
    assert trends.run(now)['appended'] == 1
    points = json.loads(trends.REPORT.read_text())['models']['catboost_player']['points']
    assert [p['brier'] for p in points] == [.21, .20]
