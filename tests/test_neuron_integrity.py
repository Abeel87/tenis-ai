from datetime import datetime, timezone
from pathlib import Path
import json

import numpy as np
import pandas as pd
import pytest

from backend import neuron as n


def history(days=40):
    return pd.DataFrame([
        {'tourney_date': (pd.Timestamp('2026-07-01') + pd.Timedelta(days=i)).strftime('%Y%m%d'),
         'tourney_name': 'Integrity fixture', 'surface': 'Hard', 'source_tour': 'ATP',
         'winner_name': 'Audit Alpha' if i % 2 else 'Audit Beta',
         'loser_name': 'Audit Beta' if i % 2 else 'Audit Alpha',
         'winner_rank': 10, 'loser_rank': 20, 'score': '6-4 6-4'}
        for i in range(days)
    ])


def test_snapshot_rejects_same_day_and_future_state():
    st = n.State()
    row = history(1).iloc[0]
    st.update(row, pd.Timestamp('2026-07-02'))
    for day in ('2026-07-01', '2026-07-02'):
        with pytest.raises(ValueError, match='HISTORY_NOT_STRICTLY_PREMATCH'):
            st.snap(n.key(row['winner_name']), pd.Timestamp(day), 'hard')


def test_current_features_do_not_invent_score_for_unknown_players():
    with pytest.raises(ValueError, match='NO_PLAYER_HISTORY'):
        n.current_features(n.State(), {'p1': 'Unknown One', 'p2': 'Unknown Two',
                                      'scheduled_time': '2099-01-01T12:00:00Z'})


def test_current_features_reject_already_started_fixture():
    _, st, _ = n.build(history(), False)
    with pytest.raises(ValueError, match='MATCH_NOT_PREMATCH'):
        n.current_features(st, {'p1': 'Audit Alpha', 'p2': 'Audit Beta',
                               'scheduled_time': '2020-01-01T12:00:00Z'})


def test_rejected_training_preserves_last_accepted_model(tmp_path, monkeypatch):
    model = tmp_path / 'neuron_model.json'
    report = tmp_path / 'neuron_metrics.json'
    model.write_text('{"previous": "accepted model"}')
    report.write_text('{"previous": "accepted report"}')
    before = (model.read_bytes(), report.read_bytes())
    monkeypatch.setattr(n, 'MODEL', model)
    monkeypatch.setattr(n, 'METRICS', report)
    monkeypatch.setattr(n, 'ROOT', tmp_path)
    monkeypatch.setattr(n, 'load_history', lambda: (history(), [], {'fresh_sources': 11, 'missing_sources': 0}))
    result = n.train()
    assert result['quality_gate']['passed'] is False
    assert (model.read_bytes(), report.read_bytes()) == before
    candidate = json.loads((tmp_path / 'artifacts/neuron/candidate_metrics.json').read_text())
    assert candidate['training_status'] == 'REJECTED_KEEP_PREVIOUS'
    assert (tmp_path / 'artifacts/neuron/training_dataset.npz').exists()
    with pytest.raises(RuntimeError, match='CANDIDATE_REJECTED'):
        n.quality_gate()


def test_history_cutoff_and_canonical_completion_hygiene():
    raw = history(3)
    raw.loc[0, 'score'] = '6-4 2-1 RET'
    (a, b, c, y, days), st, meta = n.build(raw, cutoff='2026-07-03')
    assert len(y) == 2
    assert days.tolist() == ['2026-07-02', '2026-07-02']
    assert meta['hygiene']['removed_rows'] == 1
    assert meta['excluded_same_day_or_future'] == 1
    assert st.latest_date == pd.Timestamp('2026-07-02')


@pytest.mark.parametrize('missing', [None, float('nan'), pd.NA, ''])
def test_missing_names_are_not_a_synthetic_nan_player(missing):
    assert n.key(missing) == ''


@pytest.mark.parametrize('start', ['', None, 'nonsense', '2026-07-05T12:00:00'])
def test_scoring_needs_a_real_timezone_aware_start(start):
    _, st, _ = n.build(history(2), False)
    with pytest.raises(ValueError, match='MISSING_OR_INVALID_START'):
        n.current_features(st, {'p1': 'Audit Alpha', 'p2': 'Audit Beta', 'scheduled_time': start})


def test_safe_current_features_preserve_existing_snapshot_values():
    _, st, _ = n.build(history(2), False)
    fixture = {'p1': 'Audit Alpha', 'p2': 'Audit Beta', 'surface': 'Hard', 'tour': 'ATP',
               'scheduled_time': '2026-07-05T12:00:00Z'}
    now = datetime(2026, 7, 4, tzinfo=timezone.utc)
    a, b, c = n.current_features(st, fixture, now=now)
    np.testing.assert_array_equal(a, st.snap('audit alpha', pd.Timestamp('2026-07-04'), 'hard'))
    np.testing.assert_array_equal(b, st.snap('audit beta', pd.Timestamp('2026-07-04'), 'hard'))
    assert len(c) == len(n.CF)


def frozen_rows():
    rows = [{'status': 'SHADOW_SCORE', 'match_id': 42, 'p1': 'Audit Alpha', 'p2': 'Audit Beta',
             'scheduled_time': '2026-10-21T12:00:00+00:00', 'p1_win_probability': .8,
             'elo_p1_win_probability': .6, 'feature_snapshot': {'A': [1., None], 'B': [2.], 'C': [.5]}}]
    return n.freeze_predictions({}, rows, 'neuron-test', '2026-10-19T10:00:00Z',
                                '2026-10-20T10:00:00Z', 'source-hash')


def terminal_history():
    return [{'match_key': 'id:42', 'match_id': 42, 'scheduled_time': '2026-10-21T12:00:00Z',
             'p1': 'Audit Alpha', 'p2': 'Audit Beta', 'status': 'settled',
             'settled_at': '2026-10-21T14:00:00Z', 'settlement_source': 'synthetic_exact_source',
             'settlement_version': 'test-1',
             'result': {'status': 'completed', 'p1': 'Audit Alpha', 'p2': 'Audit Beta',
                        'winner': 'Audit Alpha', 'sets': [[6, 4], [6, 4]]}}]


def test_freeze_is_idempotent_and_never_rewrites_an_earlier_forecast():
    existing = frozen_rows()
    row = next(iter(existing.values()))
    later = {**row, 'status': 'SHADOW_SCORE', 'p1_win_probability': .2}
    result = n.freeze_predictions(existing, [later], 'neuron-test', row['model_trained_at'],
                                  '2026-10-21T10:00:00Z', 'different-history')
    assert result == existing
    assert next(iter(result.values()))['p1_win_probability'] == .8


def test_exact_outcome_evaluates_frozen_neuron_and_elo_on_the_same_fixture():
    rows = frozen_rows()
    original = json.loads(json.dumps(rows))
    settled = n.settle_predictions(rows, terminal_history(), datetime(2026, 10, 22, tzinfo=timezone.utc))
    assert rows == original
    row = next(iter(settled.values()))
    assert row['settlement']['result'] == 'hit'
    assert n.frozen_prediction(row) == n.frozen_prediction(next(iter(rows.values())))
    report = n.summarize_predictions(settled)
    assert report['settled_matches'] == 1
    assert report['neuron']['brier'] == pytest.approx(.04)
    assert report['elo']['brier'] == pytest.approx(.16)
    assert report['automatic_promotion'] is False
    assert n.settle_predictions(settled, [], datetime(2026, 10, 23, tzinfo=timezone.utc)) == settled


@pytest.mark.parametrize('change,reason', [
    ({'scheduled_time': '2026-10-21T13:00:00Z'}, 'EXACT_MATCH_ID_SCHEDULE_CONFLICT'),
    ({'settlement_source': ''}, 'MISSING_SETTLEMENT_PROVENANCE'),
    ({'settled_at': '2099-01-01T00:00:00Z'}, 'INVALID_SETTLEMENT_TIME'),
    ({'settled_at': '2026-10-21T14:00:00'}, 'INVALID_SETTLEMENT_TIME'),
])
def test_unproven_outcomes_remain_missing(change, reason):
    evidence = terminal_history()
    evidence[0].update(change)
    rows = n.settle_predictions(frozen_rows(), evidence, datetime(2026, 10, 22, tzinfo=timezone.utc))
    assert next(iter(rows.values()))['settlement']['reason'] == reason
    assert n.summarize_predictions(rows)['neuron'] is None


def test_conflicting_participants_and_duplicate_history_fail_closed():
    evidence = terminal_history()
    evidence[0]['result']['p2'] = 'Different Person'
    rows = n.settle_predictions(frozen_rows(), evidence)
    assert next(iter(rows.values()))['settlement']['reason'] == 'EXACT_PARTICIPANT_CONFLICT'
    rows = n.settle_predictions(frozen_rows(), terminal_history() * 2)
    assert next(iter(rows.values()))['settlement']['reason'] == 'AMBIGUOUS_EXACT_HISTORY_MATCH'


def test_ledger_refuses_corruption_instead_of_resetting_history(tmp_path, monkeypatch):
    monkeypatch.setattr(n, 'ROOT', tmp_path)
    rows = frozen_rows()
    n.save_predictions(rows)
    assert n.load_predictions() == rows
    path = tmp_path / 'data/neuron_predictions/2026-10.json'
    document = json.loads(path.read_text())
    document['predictions'][0]['p1_win_probability'] = .1
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match='IMMUTABLE'):
        n.load_predictions()


def test_duplicate_versions_do_not_inflate_independent_fixture_count():
    rows = frozen_rows()
    row = next(iter(rows.values()))
    second = {**row, 'status': 'SHADOW_SCORE'}
    rows = n.freeze_predictions(rows, [second], 'neuron-second', '2026-10-20T11:00:00Z',
                                '2026-10-20T12:00:00Z', 'other-source')
    rows = n.settle_predictions(rows, terminal_history(), datetime(2026, 10, 22, tzinfo=timezone.utc))
    report = n.summarize_predictions(rows)
    assert report['forecast_snapshots'] == 2
    assert report['settled_matches'] == 1
    assert all(item['settled_matches'] == 1 for item in report['by_model'].values())


def test_no_results_are_reported_as_missing_not_zero_accuracy():
    report = n.summarize_predictions(frozen_rows())
    assert report['neuron'] is None and report['elo'] is None
    assert report['pending_matches'] == 1 and report['settled_matches'] == 0


@pytest.mark.parametrize('change,reason', [
    ({'model_trained_at': '2026-10-21T10:00:00Z'}, 'INVALID_FROZEN_MODEL_TIME'),
    ({'match_key': 'id:43'}, 'INVALID_FROZEN_IDENTITY'),
    ({'pick': 'Audit Beta'}, 'INVALID_FROZEN_IDENTITY'),
])
def test_ledger_rejects_invalid_identity_or_model_time_even_with_valid_checksum(change, reason):
    row = next(iter(frozen_rows().values()))
    row.update(change)
    row['snapshot_sha256'] = n.digest(n.frozen_prediction(row))
    with pytest.raises(ValueError, match=reason):
        n.validate_prediction(row)


def test_same_model_identity_ignores_refresh_metadata_but_detects_weights():
    a = {'W1': [[1.]], 'generated_at': '2026-10-22'}
    assert n.model_identity(a) == n.model_identity({**a, 'generated_at': '2026-10-25'})
    assert n.model_identity(a) != n.model_identity({**a, 'W1': [[2.]]})


def test_scoring_does_not_modify_model_or_training_metrics(tmp_path, monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 25, 10, tzinfo=timezone.utc)
    model = json.loads(Path('frontend/data/neuron_model.json').read_text())
    data = tmp_path / 'frontend/data'; data.mkdir(parents=True)
    model_path = data / 'neuron_model.json'; report_path = data / 'neuron_metrics.json'
    model_path.write_text(json.dumps(model)); report_path.write_text('{"training": "unchanged"}')
    raw = history()
    future = raw.iloc[-1:].copy(); future['tourney_date'] = '20261026'
    raw = pd.concat([raw, future], ignore_index=True)
    fixtures = [{'id': 1, 'p1': 'Audit Alpha', 'p2': 'Audit Beta', 'scheduled_time': '2026-10-25T12:00:00Z'},
                {'id': 2, 'p1': 'New One', 'p2': 'New Two', 'scheduled_time': '2026-10-25T12:00:00Z'},
                {'id': 3, 'p1': 'Audit Alpha', 'p2': 'Audit Beta', 'scheduled_time': '2026-10-25T09:00:00Z'}]
    (data / 'results.json').write_text(json.dumps(fixtures))
    for name, value in {'ROOT': tmp_path, 'DATA': data, 'MODEL': model_path, 'METRICS': report_path,
                        'CURRENT': data / 'neuron_current.json', 'datetime': Clock}.items():
        monkeypatch.setattr(n, name, value)
    monkeypatch.setattr(n, 'load_history', lambda: (raw, [], {'fresh_sources': 11, 'missing_sources': 0}))
    before = model_path.read_bytes(), report_path.read_bytes()
    result = n.current()
    assert (model_path.read_bytes(), report_path.read_bytes()) == before
    assert [row['status'] for row in result['matches']] == ['SHADOW_SCORE', 'NO_SCORE', 'NO_SCORE']
    assert result['excluded_same_day_or_future'] == 1
    assert result['no_score_reasons'] == {'NO_PLAYER_HISTORY': 1, 'MATCH_NOT_PREMATCH': 1}
    assert result['prospective']['forecast_snapshots'] == 1
    assert n.current()['prospective']['forecast_snapshots'] == 1
