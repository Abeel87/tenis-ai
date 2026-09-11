import gzip
import json
from backend.match_detail_history import build, name_key


def test_export_existing_archives_without_model_or_history_writes(tmp_path):
    data = tmp_path / 'frontend/data'
    data.mkdir(parents=True)
    cache = tmp_path / 'data/cache'
    cache.mkdir(parents=True)
    fixtures = [{'p1': 'Łukasz Żuk', 'p2': 'João Silva', 'p1_id': 10, 'p2_id': 20}]
    original = json.dumps(fixtures)
    (data / 'results.json').write_text(original)
    (data / 'history.json').write_text('[{"untouched": true}]')
    csv = 'winner_name,loser_name,tourney_date,score,surface,winner_id,loser_id\n"Zuk, Lukasz","Silva, Joao",20240101,6-4 6-4,Hard,99,10\n'
    for name in ['archive', 'duplicate']:
        with gzip.open(cache / (name+'.csv.gz'), 'wt') as out:
            out.write(csv)
    result = build(tmp_path)
    assert len(result['matches']) == 1
    row = result['matches'][0]
    assert row['date_precision'] == 'tournament'
    assert row['result']['score_text'] == '6-4 6-4'
    assert row['external_ids']['p1'] == '99'
    assert 'p1_id' not in row  # foreign namespace must never match a provider ID
    assert (data / 'results.json').read_text() == original
    assert (data / 'history.json').read_text() == '[{"untouched": true}]'
    assert name_key('Łukasz Żuk') == name_key('Zuk, Lukasz')


def test_absent_cache_is_explicit_not_fabricated(tmp_path):
    (tmp_path / 'frontend/data').mkdir(parents=True)
    result = build(tmp_path)
    assert result['matches'] == []
    assert result['archive_available'] is False


def test_provider_aliases_use_canonical_ids_and_explicit_result(tmp_path):
    data = tmp_path / 'frontend/data'
    data.mkdir(parents=True)
    (data / 'results.json').write_text(json.dumps([{'p1': 'Known A', 'p2': 'Known B', 'p1_id': 10, 'p2_id': 20}]))
    cache = tmp_path / 'data/cache/pbp_v7/matches'
    cache.mkdir(parents=True)
    payload = {'match': {'id': 123, 'players': {'p1': {'id': 20, 'name': 'Alias B'}, 'p2': {'id': 10, 'name': 'Alias A'}},
                         'scheduled_time': '2024-01-02T10:00:00Z', 'event_status': 'Finished', 'winner': 2,
                         'score': {'games': [[4, 4], [6, 6]]}}}
    with gzip.open(cache / '123.json.gz', 'wt') as out:
        json.dump(payload, out)
    result = build(tmp_path)
    assert result['matches'][0]['p1_id'] == 20
    assert result['matches'][0]['result']['winner'] == 'Alias A'
    assert result['matches'][0]['result']['sets'] == [[4, 6], [4, 6]]


def test_same_meeting_from_archive_and_provider_is_not_counted_twice(tmp_path):
    data = tmp_path / 'frontend/data'
    data.mkdir(parents=True)
    (data / 'results.json').write_text(json.dumps([{'p1': 'Known A', 'p2': 'Known B', 'p1_id': 10, 'p2_id': 20}]))

    cache = tmp_path / 'data/cache'
    cache.mkdir(parents=True)
    csv = ('winner_name,loser_name,tourney_date,score,surface,winner_id,loser_id,tourney_name\n'
           'Known A,Known B,20240101,"6-4 7-6(4) 4-3 RET",Hard,external-a,external-b,Example\n')
    with gzip.open(cache / 'archive.csv.gz', 'wt') as out:
        out.write(csv)

    provider_cache = cache / 'pbp_v7/matches'
    provider_cache.mkdir(parents=True)
    provider = {'match': {'id': 123, 'players': {'p1': {'id': 20, 'name': 'Known B'}, 'p2': {'id': 10, 'name': 'Known A'}},
                          'scheduled_time': '2024-01-05T10:00:00Z', 'event_status': 'Retired', 'winner': None,
                          'score': {'games': [[4, 6, 3], [6, 7, 4]]}}}
    with gzip.open(provider_cache / '123.json.gz', 'wt') as out:
        json.dump(provider, out)

    result = build(tmp_path)
    assert len(result['matches']) == 1
    row = result['matches'][0]
    assert row['match_id'] == 123
    assert row['p1_id'] == 10
    assert row['p2_id'] == 20
    assert row['source'] == 'tennismylife+livetennisapi'
    assert row['result']['winner'] == 'Known A'
    assert row['result']['score_text'] == '6-4 7-6(4) 4-3 RET'
    assert result['sources'][-1] == {'file': 'pbp_v7/matches', 'matched_rows': 1}
