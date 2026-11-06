"""Incomplete fixture reads must not replace the last complete publication."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import update
from backend import api_quota


def fixture_page(start, count, total):
    return {
        'data': [
            {'id': i, 'players': {'p1': {'name': f'A{i}'}, 'p2': {'name': f'B{i}'}}}
            for i in range(start, start + count)
        ],
        'meta': {} if total is None else {'total': total},
    }


def fixture_responses(monkeypatch, pages, budget):
    offsets, recorded = [], []

    class Response:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    def get(url, *, params, **kwargs):
        offsets.append(params['offset'])
        return Response(pages[len(offsets) - 1])

    monkeypatch.setenv('LIVE_TENNIS_API_KEY', 'isolated-test')
    monkeypatch.setattr(update, 'quota_budget', lambda *a: (budget, {'limits': {'per_minute': 300}}))
    monkeypatch.setattr(update, 'request_interval_seconds', lambda *a, **kw: 0)
    monkeypatch.setattr(update.requests, 'get', get)
    monkeypatch.setattr(update, 'record_calls', lambda role, count: recorded.append((role, count)))
    return offsets, recorded


@pytest.mark.parametrize('counts,total,budget', [
    ([200], 500, 1),
    ([200, 200], 500, 2),
    ([200], None, 1),
    ([100], 500, 1),
    ([0], 500, 1),
])
def test_partial_catalogue_is_not_published_as_complete(monkeypatch, counts, total, budget):
    start, pages = 0, []
    for count in counts:
        pages.append(fixture_page(start, count, total))
        start += count
    offsets, recorded = fixture_responses(monkeypatch, pages, budget)

    rows, mode = update.fetch_fixtures()

    assert rows is None
    assert mode == 'pagination-incomplete-safe-skip'
    assert len(offsets) == len(counts)
    assert recorded == [('fixtures', 1)] * len(counts)


@pytest.mark.parametrize('counts,total', [
    ([200], 200),
    ([200, 100], 300),
    ([200, 50], None),
    ([200, 0], None),
    ([0], 0),
])
def test_complete_catalogue_including_genuine_empty_is_publishable(monkeypatch, counts, total):
    start, pages = 0, []
    for count in counts:
        pages.append(fixture_page(start, count, total))
        start += count
    offsets, recorded = fixture_responses(monkeypatch, pages, len(pages))

    rows, mode = update.fetch_fixtures()

    assert mode == 'live-tennis-api-basic'
    assert [row['id'] for row in rows] == list(range(sum(counts)))
    assert offsets == [sum(counts[:i]) for i in range(len(counts))]
    assert recorded == [('fixtures', 1)] * len(counts)


@pytest.mark.parametrize('mode,reason', [
    ('quota-safe-skip', 'fixture_quota_safe_skip'),
    ('rate-limit-safe-skip', 'fixture_rate_limit_safe_skip'),
    ('pagination-incomplete-safe-skip', 'fixture_pagination_incomplete_safe_skip'),
])
@pytest.mark.parametrize('previous_timestamp', ['2026-11-01T09:52:48+00:00', None])
def test_skipped_refresh_preserves_data_and_source_time(monkeypatch, tmp_path, mode, reason, previous_timestamp):
    old_meta = {'visible_fixtures': 453, 'degraded_reason': None}
    if previous_timestamp is not None:
        old_meta['updated_at'] = previous_timestamp
    (tmp_path / 'meta.json').write_text(json.dumps(old_meta))
    preserved = {'results.json': b'[{"id":123}]', 'history.json': b'[{"frozen":true}]'}
    for name, content in preserved.items():
        (tmp_path / name).write_bytes(content)
    monkeypatch.setattr(update, 'OUT', tmp_path)
    history = pd.DataFrame([{'id': 1}])
    monkeypatch.setattr(update, 'load_history', lambda **kw: (history, [], {}))
    monkeypatch.setattr(update, 'clean_history', lambda h: (h, {}))
    monkeypatch.setattr(update, 'normalize_matches', lambda h: h)
    monkeypatch.setattr(update, 'save_sqlite', lambda h: None)
    monkeypatch.setattr(update, 'fetch_fixtures', lambda: (None, mode))
    started = datetime.now(timezone.utc)

    update.main()

    meta = json.loads((tmp_path / 'meta.json').read_text())
    assert meta.get('updated_at') == previous_timestamp
    assert meta['visible_fixtures'] == 453
    assert meta['fixtures_refresh_degraded_reason'] == reason
    assert meta['degraded_reason'] == reason
    assert datetime.fromisoformat(meta['fixtures_refresh_attempted_at']) >= started
    for name, content in preserved.items():
        assert (tmp_path / name).read_bytes() == content


def test_renewed_subscription_reopens_fixture_budget_without_resetting_spend(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    state_path = tmp_path / 'quota.json'
    state_path.write_text(json.dumps({
        'quota_day': now.date().isoformat(),
        'categories': {'fixtures': {'calls': 8}},
    }))
    monkeypatch.setattr(api_quota, 'CACHE', tmp_path)
    monkeypatch.setattr(api_quota, 'OUT', tmp_path)
    monkeypatch.setattr(api_quota, 'STATE_PATH', state_path)
    monkeypatch.setattr(api_quota, 'REPORT_PATH', tmp_path / 'report.json')
    monkeypatch.setattr(api_quota, 'META_PATH', tmp_path / 'meta.json')

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {'today': {'calls': 121, 'remaining_day': 9879},
                    'limits': {'per_day': 10000, 'per_minute': 300}}

    monkeypatch.setattr(api_quota.requests, 'get', lambda *a, **kw: Response())
    api_quota.begin_guard(key='isolated-test', now=now)
    budget, usage = api_quota.quota_budget('fixtures', 12)

    assert budget == 12
    assert usage['quota']['daily_cap'] == 800
    assert usage['quota']['role_spent_today'] == 8
