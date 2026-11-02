from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from update import fetch_fixtures, load_history
import update


def source(refresh_hours=None):
    return {'key':'x','tour':'ATP','url':'https://example.test/x.csv','refresh_hours':refresh_hours}


def frame():
    return pd.DataFrame([{'tourney_date':20260819,'winner_name':'A','loser_name':'B','score':'6-4 6-4'}])


def test_static_cache_is_downloaded_once(tmp_path):
    calls=[]
    def downloader(url):
        calls.append(url); return frame()
    now=datetime(2026,8,19,12,0,tzinfo=timezone.utc)
    h1,w1,i1=load_history(cache_dir=tmp_path,sources=[source(None)],now=now,downloader=downloader)
    h2,w2,i2=load_history(cache_dir=tmp_path,sources=[source(None)],now=now+timedelta(hours=1),downloader=downloader)
    assert len(calls)==1
    assert len(h1)==1 and len(h2)==1
    assert i2['cached_sources']==1
    assert not w2


def test_due_source_uses_cache_when_network_fails(tmp_path):
    now=datetime(2026,8,19,12,0,tzinfo=timezone.utc)
    load_history(cache_dir=tmp_path,sources=[source(0)],now=now,downloader=lambda url: frame())
    def fail(url):
        raise TimeoutError('offline')
    hist,warnings,info=load_history(cache_dir=tmp_path,sources=[source(0)],now=now+timedelta(hours=1),downloader=fail)
    assert hist is not None and len(hist)==1
    assert info['mode']=='cache'
    assert info['cached_sources']==1
    assert warnings and 'użyto cache' in warnings[0]


def test_total_outage_without_cache_returns_none_not_exception(tmp_path):
    def fail(url):
        raise TimeoutError('offline')
    hist,warnings,info=load_history(cache_dir=tmp_path,sources=[source(0)],now=datetime.now(timezone.utc),downloader=fail)
    assert hist is None
    assert info['mode']=='unavailable'
    assert info['missing_sources']==1
    assert warnings


def empty_ongoing_frame():
    # A real HTTP 200 ongoing feed may contain only this documented match schema.
    return pd.DataFrame(columns=[
        'tourney_id', 'tourney_name', 'surface', 'tourney_date', 'match_num',
        'winner_id', 'winner_name', 'loser_id', 'loser_name', 'score',
    ])


@pytest.mark.parametrize('source_key', ['atp_ongoing', 'ch_ongoing', 'wta_ongoing'])
def test_valid_empty_ongoing_refresh_replaces_previous_snapshot(tmp_path, source_key):
    declared = next(s for s in update.TML_SOURCES if s['key'] == source_key)
    now = datetime(2026, 11, 2, 8, tzinfo=timezone.utc)
    load_history(tmp_path, [declared], now, lambda url: frame())
    history, warnings, info = load_history(
        tmp_path, [declared], now + timedelta(hours=1), lambda url: empty_ongoing_frame(),
    )
    assert history is None  # No synthetic rows or stale ongoing results.
    assert warnings == []
    assert info['fresh_sources'] == 1
    assert info['cached_sources'] == info['missing_sources'] == 0
    assert info['empty_source_keys'] == [source_key]
    cached = update._read_cached(tmp_path, declared)
    assert cached is not None and cached.empty
    assert update._load_manifest(tmp_path)['sources'][source_key]['rows'] == 0


def test_valid_empty_ongoing_cache_survives_outage_without_renewing_timestamp(tmp_path):
    declared = next(s for s in update.TML_SOURCES if s['key'] == 'ch_ongoing')
    now = datetime(2026, 11, 2, 8, tzinfo=timezone.utc)
    load_history(tmp_path, [declared], now, lambda url: empty_ongoing_frame())
    before = update._load_manifest(tmp_path)

    def unavailable(url):
        raise TimeoutError('offline')

    history, warnings, info = load_history(tmp_path, [declared], now + timedelta(hours=1), unavailable)
    assert history is None
    assert info['fresh_sources'] == info['missing_sources'] == 0
    assert info['cached_sources'] == 1
    assert info['empty_source_keys'] == ['ch_ongoing']
    assert warnings and 'użyto cache' in warnings[0]
    assert update._load_manifest(tmp_path) == before


@pytest.mark.parametrize('source_key,empty', [
    ('ch_2026', empty_ongoing_frame()),
    ('ch_2025', empty_ongoing_frame()),
    ('ch_ongoing', pd.DataFrame()),
    ('ch_ongoing', empty_ongoing_frame().drop(columns=['winner_id'])),
    ('ch_ongoing', pd.DataFrame({'error': ['temporary outage']})),
])
def test_empty_archive_or_invalid_ongoing_preserves_last_good_cache(tmp_path, source_key, empty):
    declared = dict(next(s for s in update.TML_SOURCES if s['key'] == source_key))
    now = datetime(2026, 11, 2, 8, tzinfo=timezone.utc)
    load_history(tmp_path, [declared], now, lambda url: frame())
    before = update._load_manifest(tmp_path)
    # Force revalidation here; immutable archives otherwise intentionally stay cached.
    declared['refresh_hours'] = 0
    history, warnings, info = load_history(tmp_path, [declared], now + timedelta(hours=1), lambda url: empty)
    assert len(history) == 1
    assert info['fresh_sources'] == 0 and info['cached_sources'] == 1
    assert warnings
    assert update._load_manifest(tmp_path) == before


def test_fetch_fixtures_preserves_provider_rank_context(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                'data': [{
                    'id': 123,
                    'tour': 'ATP',
                    'tournament': 'Test',
                    'surface': 'hard',
                    'scheduled_time': '2026-09-06T12:00:00Z',
                    'status': 'upcoming',
                    'is_doubles': False,
                    'players': {
                        'p1': {'id': 1, 'name': 'A', 'ranking': 12},
                        'p2': {'id': 2, 'name': 'B', 'ranking': 34},
                    },
                }],
                'meta': {'total': 1},
            }

    monkeypatch.setenv('LIVE_TENNIS_API_KEY', 'test-key')
    # This unit test verifies provider ranking context only. Isolate it from the
    # canonical persistent quota manager so pytest cannot mutate frontend/data.
    monkeypatch.setattr('update.quota_budget', lambda *args, **kwargs: (1, {'limits': {'per_minute': 300}}))
    monkeypatch.setattr('update.request_interval_seconds', lambda *args, **kwargs: 0.0)
    monkeypatch.setattr('update.requests.get', lambda *args, **kwargs: Response())
    monkeypatch.setattr('update.record_calls', lambda *args, **kwargs: None)

    rows, mode = fetch_fixtures()
    assert mode == 'live-tennis-api-basic'
    assert len(rows) == 1
    assert rows[0]['p1_rank'] == 12
    assert rows[0]['p2_rank'] == 34



def test_fetch_fixtures_fails_closed_without_erasing_current_analysis_on_quota_exhaustion(monkeypatch):
    monkeypatch.setenv('LIVE_TENNIS_API_KEY', 'test-key')
    monkeypatch.setattr('update.quota_budget', lambda *args, **kwargs: (0, {'limits': {'per_minute': 300}}))

    def must_not_call(*args, **kwargs):
        raise AssertionError('fixture endpoint must not be called with zero quota budget')

    monkeypatch.setattr('update.requests.get', must_not_call)

    rows, mode = fetch_fixtures()
    assert rows is None
    assert mode == 'quota-safe-skip'


def test_fetch_fixtures_terminal_429_is_safe_skip(monkeypatch):
    class RateLimited:
        status_code = 429
        headers = {}

        def raise_for_status(self):
            raise AssertionError('terminal 429 must be handled before raise_for_status')

    monkeypatch.setenv('LIVE_TENNIS_API_KEY', 'test-key')
    monkeypatch.setattr('update.quota_budget', lambda *args, **kwargs: (1, {'limits': {'per_minute': 300}}))
    monkeypatch.setattr('update.request_interval_seconds', lambda *args, **kwargs: 0.0)
    monkeypatch.setattr('update.requests.get', lambda *args, **kwargs: RateLimited())
    monkeypatch.setattr('update.record_calls', lambda *args, **kwargs: None)

    rows, mode = fetch_fixtures()
    assert rows is None
    assert mode == 'rate-limit-safe-skip'
