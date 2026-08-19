from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from update import load_history


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
