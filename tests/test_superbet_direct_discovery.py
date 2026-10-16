"""Regression cases from the public v3 tennis catalogue observed 2026-10-16."""
import json
from pathlib import Path

from backend import superbet_direct as direct
from backend import ineed_runner as runner
from tests.test_superbet_direct import _direct_event_payload

URL = 'https://superbet.pl/kursy/tenis/alexander-bublik-vs-tommy-paul-14809301'
MATCH = {'id': 'app-1', 'p1': 'Tommy Paul', 'p2': 'Alexander Bublik',
         'scheduled_time': '2026-09-04T16:30:00Z'}


def test_current_v3_nested_fixture_catalogue_is_discovered():
    payload = {'events': [{'event_id': 15375776, 'fixture': {
        'event_name': 'Niels Lootsma·Aleksandar Mitev', 'sport_id': 2,
        'utc_date': '2026-10-16T10:10:00Z'}}]}
    expected = ['https://superbet.pl/kursy/tenis/niels-lootsma-vs-aleksandar-mitev-15375776']
    assert runner.event_urls_from_payload(payload) == expected
    assert direct.event_urls_from_payload(payload) == expected


def test_catalogue_rejects_foreign_sport_and_mismatched_url_id():
    payload = {'events': [
        {'event_id': 15375776, 'fixture': {'sport_id': 1, 'event_name': 'One Team·Two Team'}},
        {'eventId': 14809301, 'sportId': 2, 'matchName': 'Alexander Bublik·Tommy Paul',
         'eventUrl': '/kursy/tenis/other-people-99999999'},
    ]}
    assert direct.event_urls_from_payload(payload) == [URL]


def old_feed():
    return direct.build_selected_direct_feed([MATCH], [URL], fetcher=lambda _:
        _direct_event_payload('14809301', 'Alexander Bublik', 'Tommy Paul', MATCH['scheduled_time']))


def test_confirmed_identity_survives_listing_disappearance_but_quotes_are_refetched():
    old = old_feed()
    called = []
    def fetch(eid):
        called.append(eid)
        return _direct_event_payload(eid, 'Alexander Bublik', 'Tommy Paul', MATCH['scheduled_time'])
    fresh = direct.build_selected_direct_feed([MATCH], [], previous_feed=old, fetcher=fetch)
    assert called == ['14809301']
    assert fresh['resolved_app_matches'] == 1
    assert fresh['coverage']['remembered_event_matches'] == 1
    assert fresh['matches'][0]['observed_at']
    assert fresh['identity_bindings'][0]['event_id'] == '14809301'


def test_remembered_identity_cannot_reuse_price_or_match_different_participants():
    old = old_feed()
    def bad_fetch(_):
        raise TimeoutError('network down')
    fresh = direct.build_selected_direct_feed([MATCH], [], previous_feed=old, fetcher=bad_fetch)
    assert fresh['matches'] == []
    assert fresh['contains_prices'] is False
    assert fresh['match_diagnostics'][0]['reason'] == 'EVENT_FETCH_FAILED'
    assert len(fresh['identity_bindings']) == 1
    changed = {**MATCH, 'p1': 'Different Player'}
    fresh = direct.build_selected_direct_feed([changed], [], previous_feed=old,
        fetcher=lambda _: (_ for _ in ()).throw(AssertionError('foreign identity fetched')))
    assert fresh['matches'] == []
    assert fresh['identity_bindings'] == []


def test_every_input_has_diagnostic_including_missing_and_deferred():
    rows = [MATCH, {**MATCH, 'id': 'app-2'}, {'id': 'invalid'},
            {**MATCH, 'id': 'absent', 'p1': 'Someone Else'}]
    fresh = direct.build_selected_direct_feed(rows, [URL], max_matches=1,
        fetcher=lambda _: _direct_event_payload('14809301','Alexander Bublik','Tommy Paul',MATCH['scheduled_time']))
    assert len(fresh['match_diagnostics']) == len(rows)
    reasons = {x['match_id']:x['reason'] for x in fresh['match_diagnostics']}
    assert reasons == {'app-1':'OK','app-2':'DEFERRED_BATCH_LIMIT',
                       'invalid':'INVALID_SELECTED_MATCH','absent':'NOT_IN_DISCOVERED_CATALOGUE'}
    assert fresh['coverage']['reason_counts']['DEFERRED_BATCH_LIMIT'] == 1


def test_browser_refresh_revalidates_known_id_during_listing_outage(monkeypatch, tmp_path):
    data = tmp_path / 'frontend' / 'data'; data.mkdir(parents=True)
    (data / 'results.json').write_text(json.dumps([MATCH]))
    (data / 'superbet_direct_current.json').write_text(json.dumps(old_feed()))
    monkeypatch.setattr(direct, '__file__', str(tmp_path / 'backend' / 'superbet_direct.py'))
    monkeypatch.setattr(direct, 'browser_probe', lambda **_: {'status':'NO_MATCH_URLS','match_urls':[]})
    monkeypatch.setattr(direct, 'fetch_event_payload_public', lambda _:
        _direct_event_payload('14809301','Alexander Bublik','Tommy Paul',MATCH['scheduled_time']))
    fresh = direct.browser_selected_direct_feed()
    assert fresh['resolved_app_matches'] == 1
    assert fresh['listing_probe_status'] == 'NO_MATCH_URLS'
    assert fresh['coverage']['discovery_degraded'] is True


def test_failed_refresh_persists_diagnostics_without_stale_prices(tmp_path):
    old = old_feed()
    fresh = direct.build_selected_direct_feed([MATCH], [], previous_feed=old,
        fetcher=lambda _: (_ for _ in ()).throw(TimeoutError()))
    target = tmp_path / 'direct.json'
    direct.write_selected_direct_sidecar(fresh, target)
    saved = json.loads(target.read_text())
    assert saved['matches'] == []
    assert saved['identity_bindings']
    assert saved['match_diagnostics'][0]['reason'] == 'EVENT_FETCH_FAILED'


def test_remembered_identity_is_rejected_when_current_event_time_changes():
    old = old_feed()
    fresh = direct.build_selected_direct_feed([MATCH], [], previous_feed=old,
        fetcher=lambda _: _direct_event_payload('14809301','Alexander Bublik','Tommy Paul','2026-09-07T16:30:00Z'))
    assert fresh['matches'] == []
    assert fresh['match_diagnostics'][0]['reason'] == 'TIME_MISMATCH'


def test_catalogue_reader_consumes_only_public_tennis_prematch_responses():
    payload = {'events': [{'event_id': 15375776, 'fixture': {'sport_id': 2, 'event_name': 'Niels Lootsma·Aleksandar Mitev'}}]}
    class Driver:
        def get_log(self, _):
            return [{'message':json.dumps({'message':{'method':'Network.responseReceived','params': {
                'requestId':str(i),'response':{'url':url,'status':200,'mimeType':'application/json'}}}})}
                for i,url in enumerate([
                  'https://evil.example/v3/pl-PL/events?sports=2&index=active-prematch',
                  'https://'+direct.EVENT_API_HOST+'/v3/pl-PL/events?sports=1&index=active-prematch',
                  'https://'+direct.EVENT_API_HOST+'/v3/pl-PL/events?sports=2&index=active-live',
                  'https://'+direct.EVENT_API_HOST+'/v3/pl-PL/events?sports=2&index=active-prematch'])]
        def execute_cdp_cmd(self, _, params):
            assert params['requestId'] == '3'
            return {'body':json.dumps(payload),'base64Encoded':False}
    assert len(direct._drain_public_listing_json(Driver())) == 1


def test_transient_read_retries_once_but_rate_limit_does_not(monkeypatch):
    from urllib.error import HTTPError
    attempts = []
    def once(event_id, timeout=20):
        attempts.append(event_id)
        if len(attempts) == 1:
            raise TimeoutError()
        return {'data': []}
    monkeypatch.setattr(direct, '_fetch_event_payload_once', once)
    monkeypatch.setattr(direct.time, 'sleep', lambda _: None)
    assert direct.fetch_event_payload_public('14809301') == {'data': []}
    assert len(attempts) == 2
    attempts.clear()
    def limited(event_id, timeout=20):
        attempts.append(event_id)
        raise HTTPError('https://example.invalid', 429, 'rate limited', {}, None)
    monkeypatch.setattr(direct, '_fetch_event_payload_once', limited)
    import pytest
    with pytest.raises(HTTPError):
        direct.fetch_event_payload_public('14809301')
    assert len(attempts) == 1


def test_duplicate_input_rows_each_receive_a_completed_diagnostic():
    fresh = direct.build_selected_direct_feed([MATCH, dict(MATCH)], [URL],
        fetcher=lambda _: _direct_event_payload('14809301', 'Alexander Bublik',
                                                'Tommy Paul', MATCH['scheduled_time']))
    assert [row['reason'] for row in fresh['match_diagnostics']] == ['OK', 'OK']
    assert fresh['coverage']['unique_event_fetches'] == 1
