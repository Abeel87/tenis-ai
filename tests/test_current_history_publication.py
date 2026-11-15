import gzip
import json
import sys
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import history_coverage_audit as coverage
import model_core

NOW = datetime(2026, 11, 15, 9, tzinfo=timezone.utc)


def sources(tmp_path, *, omit=False):
    root = tmp_path / 'pbp_v7'
    (root / 'matches').mkdir(parents=True)
    match = {'id': 999, 'p1': 'Alexander Donski', 'p1_id': 324,
             'p2': 'Calvin Hemery', 'p2_id': 517,
             'scheduled_time': '2026-11-15T10:30:00Z'}
    players = {}
    for side, pid in [('p1', 324), ('p2', 517)]:
        name = match[side]
        sample, summaries = [], []
        for i in range(5):
            mid = pid * 100 + i
            stamp = f'2026-11-{13-i:02d}T12:00:00Z'
            opponent = f'Opponent {pid} {i}'
            payload = {'match': {'id': mid, 'scheduled_time': stamp,
                       'event_status': 'finished', 'surface': 'hard', 'winner': 2,
                       'players': {'p1': {'id': pid, 'name': name},
                                   'p2': {'id': 10000+i, 'name': opponent}},
                       'score': {'sets': [0, 2], 'games': [[2, 2], [6, 6]]}}}
            with gzip.open(root / 'matches' / f'{mid}.json.gz', 'wt') as f:
                json.dump(payload, f)
            summaries.append({'id': mid, 'scheduled_time': stamp})
            sample.append({'player': name, 'opponent': opponent, 'won': 0,
                           'date': '2026-11-09', 'date_precision': 'tournament',
                           'score_text': '6-2 6-2', 'surface': 'hard',
                           'tourney_id': f'T{pid}', 'match_num': i})
        match[side+'_stats'] = {'history_sample': sample[1:] if omit and side=='p1' else sample}
        players[model_core._key(name)] = {'player_id': pid, 'player': name,
                                        'fetched_at': NOW.isoformat(), 'matches': summaries}
    (root/'players.json').write_text(json.dumps({'players': players}))
    return root, match


def test_missing_recent_result_blocks_publication_without_changing_probability(tmp_path):
    root, match = sources(tmp_path, omit=True)
    match['match_win'] = {'Alexander Donski': 55.7, 'Calvin Hemery': 44.3}
    before = deepcopy(match)
    result = coverage.attach_current_history_evidence([match], pbp_root=root, now=NOW)[0]
    assert result['history_input']['recommendation_allowed'] is False
    assert result['history_input']['players']['p1']['status'] == 'MISSING_RECENT_RESULTS'
    assert result['history_input']['players']['p1']['missing_match_ids'] == [32400]
    assert result['history_input']['players']['p1']['recent_observed'][0]['won'] is False
    assert result['match_win'] == before['match_win']
    assert match == before


def test_verified_results_match_tournament_week_without_false_age_block(tmp_path):
    root, match = sources(tmp_path)
    result = coverage.attach_current_history_evidence([match], pbp_root=root, now=NOW)[0]
    assert result['history_input']['recommendation_allowed'] is True
    assert result['history_input']['players']['p1']['status'] == 'CHECKED'


def test_missing_or_stale_source_is_unknown_not_approved(tmp_path):
    root, match = sources(tmp_path)
    index = json.loads((root/'players.json').read_text())
    index['players']['alexander donski']['fetched_at'] = '2026-11-01T00:00:00Z'
    (root/'players.json').write_text(json.dumps(index))
    result = coverage.attach_current_history_evidence([match], pbp_root=root, now=NOW)[0]
    assert result['history_input']['recommendation_allowed'] is False
    assert result['history_input']['players']['p1']['status'] == 'STALE_PROVIDER_INDEX'
    (root/'players.json').unlink()
    assert coverage.attach_current_history_evidence([match], pbp_root=root, now=NOW)[0]['history_input']['recommendation_allowed'] is False


def test_foreign_player_or_conflicting_result_cannot_certify_history(tmp_path):
    root, match = sources(tmp_path)
    path = root/'matches/32400.json.gz'
    with gzip.open(path, 'rt') as f:
        payload = json.load(f)
    payload['match']['players']['p1']['id'] = 123
    with gzip.open(path, 'wt') as f:
        json.dump(payload, f)
    result = coverage.attach_current_history_evidence([match], pbp_root=root, now=NOW)[0]
    assert result['history_input']['recommendation_allowed'] is False
    assert result['history_input']['players']['p1']['status'] == 'UNVERIFIED_PROVIDER_RESULTS'


def test_unknown_model_sample_cannot_be_certified_by_current_cache(tmp_path):
    root, match = sources(tmp_path)
    match['p1_stats'].pop('history_sample')
    result = coverage.attach_current_history_evidence([match], pbp_root=root, now=NOW)[0]
    assert result['history_input']['recommendation_allowed'] is False
    assert result['history_input']['players']['p1']['status'] == 'MODEL_SAMPLE_UNAVAILABLE'


def test_same_week_round_order_is_deterministic_and_dates_are_explicit():
    frame = pd.DataFrame([
        {'tourney_date': 20261109, 'tourney_name': 'Orleans', 'tourney_id':'O',
         'round': rnd, 'match_num': mid, 'surface':'Hard', 'score':'6-4 6-4',
         'winner_name': 'Calvin Hemery' if won else 'Pedro Martinez',
         'loser_name': f'Opponent {mid}' if won else 'Calvin Hemery'}
        for rnd, mid, won in [('R32', 3, True), ('QF', 26, False), ('R16', 19, True)]
    ])
    normalized = model_core.normalize_matches(frame)
    player = normalized[normalized.player == 'Calvin Hemery']
    sorted_rows = model_core.sort_player_history(player)
    assert sorted_rows['round'].tolist() == ['QF', 'R16', 'R32']
    assert sorted_rows['date_precision'].tolist() == ['tournament'] * 3
    assert model_core.sort_player_history(player.sample(frac=1, random_state=5))['won'].tolist() == [0, 1, 1]


def test_duplicate_sample_or_score_conflict_cannot_pass(tmp_path):
    root, match = sources(tmp_path)
    match['p1_stats']['history_sample'].append(deepcopy(match['p1_stats']['history_sample'][0]))
    assert not coverage.attach_current_history_evidence([match], pbp_root=root, now=NOW)[0]['history_input']['recommendation_allowed']
    match['p1_stats']['history_sample'].pop()
    match['p1_stats']['history_sample'][0]['score_text'] = '6-1 6-1'
    assert not coverage.attach_current_history_evidence([match], pbp_root=root, now=NOW)[0]['history_input']['recommendation_allowed']


def test_model_cache_changes_when_same_size_history_is_corrected():
    import player_intelligence_v85 as profiles
    original = pd.DataFrame({'date': pd.to_datetime(['2026-11-09']), 'won': [1]})
    corrected = original.assign(won=0)
    assert profiles._source_fingerprint(original) != profiles._source_fingerprint(corrected)


def test_blocked_history_cannot_publish_even_with_old_recommended_composition():
    import symphony2_engine as engine
    match = {'id': 123, 'history_input': {'recommendation_allowed': False}, 'match_win': {'A': 55.7}}
    leg = {'market': 'match_winner', 'pick': 'A', 'fixture_line_verified': True}
    current = {'generated_at': NOW.isoformat(), 'matches': [{'id': 123, 'match_key': '123',
        'recommended_leg_count': 2, 'compositions': {'2': {'selection': [leg, {**leg, 'market': 'set1_winner'}]}}}]}
    out = engine._project_final_playable([match], current)[0]
    assert out['symphony2_playable']['status'] == 'HISTORY_INPUT_UNVERIFIED'
    assert out['symphony2_playable']['signals'] == []
    assert out['symphony2_playable']['playable'] is False
    assert out['match_win'] == match['match_win']
    approved = {**match, 'history_input': {'recommendation_allowed': True}}
    assert engine._project_final_playable([approved], current)[0]['symphony2_playable']['playable'] is True


def test_blocked_fixture_is_not_scored_and_run_always_checks_history(monkeypatch):
    from types import SimpleNamespace
    import symphony2_engine as engine
    monkeypatch.setattr(engine, 'train_operator_line_model', lambda rows: SimpleNamespace(status='OK', metrics={}, trained_rows=0))
    monkeypatch.setattr(engine, '_operator_context', lambda m: True)
    monkeypatch.setattr(engine, '_is_current_pre_match_fixture', lambda *args: True)
    monkeypatch.setattr(engine, 'build_outcomes', lambda m: (_ for _ in ()).throw(AssertionError('must not score blocked inputs')))
    current, _ = engine.build([{'id': 123, 'history_input': {'recommendation_allowed': False}}], [])
    assert current['matches'][0]['scored_selections'] == []
    assert current['matches'][0]['compositions'] == {}
    inputs = [{'id': 123, 'p1': 'Unknown A', 'p2': 'Unknown B'}]
    monkeypatch.setattr(engine, '_read', lambda path, fallback: inputs if path == engine.RESULTS else fallback)
    written = {}
    monkeypatch.setattr(engine, '_write', lambda path, value: written.update({path: value}))
    engine.run()
    assert written[engine.RESULTS][0]['history_input']['recommendation_allowed'] is False
    assert written[engine.RESULTS][0]['symphony2_playable']['signals'] == []


def test_partial_match_score_does_not_certify_finished_label(tmp_path):
    root, match = sources(tmp_path)
    path = root/'matches/32400.json.gz'
    with gzip.open(path, 'rt') as f:
        payload = json.load(f)
    payload['match']['score']['games'] = [[0, 0], [1, 1]]
    with gzip.open(path, 'wt') as f:
        json.dump(payload, f)
    row = coverage.attach_current_history_evidence([match], pbp_root=root, now=NOW)[0]
    assert row['history_input']['players']['p1']['status'] == 'UNVERIFIED_PROVIDER_RESULTS'
    assert not row['history_input']['recommendation_allowed']
