from __future__ import annotations
import io, json, os, sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from model import normalize_matches, analyse_match
from history_tracker import (
    archive_predictions, history_stats, is_current_match, load_history as load_prediction_history,
    save_history as save_prediction_history, settle_history,
)

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'frontend'/'data'
DATA=ROOT/'data'
CACHE_DIR=DATA/'cache'
OUT.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_PATH=OUT/'history.json'
HISTORY_STATS_PATH=OUT/'history_stats.json'
CACHE_MANIFEST='manifest.json'

# refresh_hours:
#   0    -> try every run (ongoing tournaments)
#   12   -> refresh current-year archive twice a day
#   None -> immutable/old archive: download only if cache is missing
TML_SOURCES=[
    {'key':'atp_ongoing','tour':'ATP','url':'https://stats.tennismylife.org/data/ongoing_tourneys.csv','refresh_hours':0},
    {'key':'ch_ongoing','tour':'CH','url':'https://stats.tennismylife.org/data/challenger_ongoing_tourneys.csv','refresh_hours':0},
    {'key':'wta_ongoing','tour':'WTA','url':'https://stats.tennismylife.org/data/wta_ongoing_tourneys.csv','refresh_hours':0},
    {'key':'atp_2026','tour':'ATP','url':'https://stats.tennismylife.org/data/2026.csv','refresh_hours':12},
    {'key':'ch_2026','tour':'CH','url':'https://stats.tennismylife.org/data/2026_challenger.csv','refresh_hours':12},
    {'key':'wta_2026','tour':'WTA','url':'https://stats.tennismylife.org/data/2026_wta.csv','refresh_hours':12},
    {'key':'atp_2025','tour':'ATP','url':'https://stats.tennismylife.org/data/2025.csv','refresh_hours':None},
    {'key':'ch_2025','tour':'CH','url':'https://stats.tennismylife.org/data/2025_challenger.csv','refresh_hours':None},
    {'key':'wta_2025','tour':'WTA','url':'https://stats.tennismylife.org/data/2025_wta.csv','refresh_hours':None},
]

UA='TenisAI-EarlyHold/0.5.2 (personal non-commercial analytics)'


def download_csv(url):
    """Short network timeout: cache is the retry/fallback, not a 6-minute blocked workflow."""
    r=requests.get(url,headers={'User-Agent':UA},timeout=(7,18))
    r.raise_for_status()
    return pd.read_csv(io.BytesIO(r.content), low_memory=False)


def _manifest_path(cache_dir: Path):
    return cache_dir/CACHE_MANIFEST


def _load_manifest(cache_dir: Path):
    p=_manifest_path(cache_dir)
    try:
        data=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        return data if isinstance(data,dict) else {}
    except Exception:
        return {}


def _save_manifest(cache_dir: Path, manifest: dict):
    cache_dir.mkdir(parents=True,exist_ok=True)
    p=_manifest_path(cache_dir); tmp=p.with_suffix('.tmp')
    tmp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(p)


def _cache_path(cache_dir: Path, source: dict):
    return cache_dir/f"{source['key']}.csv.gz"


def _read_cached(cache_dir: Path, source: dict):
    p=_cache_path(cache_dir,source)
    if not p.exists():
        return None
    try:
        return pd.read_csv(p,compression='gzip',low_memory=False)
    except Exception:
        return None


def _write_cached(cache_dir: Path, source: dict, df: pd.DataFrame):
    cache_dir.mkdir(parents=True,exist_ok=True)
    p=_cache_path(cache_dir,source); tmp=p.with_suffix('.tmp.gz')
    df.to_csv(tmp,index=False,compression={'method':'gzip','compresslevel':6,'mtime':0})
    tmp.replace(p)


def _parse_dt(value):
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _source_due(source: dict, manifest: dict, cache_dir: Path, now: datetime):
    p=_cache_path(cache_dir,source)
    if not p.exists() or p.stat().st_size<=0:
        return True
    hours=source.get('refresh_hours')
    if hours is None:
        return False
    if float(hours)<=0:
        return True
    stamp=((manifest.get('sources') or {}).get(source['key']) or {}).get('fetched_at')
    d=_parse_dt(stamp)
    if d is None:
        return True
    return now-d >= timedelta(hours=float(hours))


def load_history(cache_dir=CACHE_DIR, sources=None, now=None, downloader=download_csv):
    """Load history from a persistent cache and only refresh sources that are due.

    Returns (history_or_none, warnings, info). A total source outage never raises here;
    the caller can keep/deploy the previous analysis instead of breaking GitHub Pages.
    """
    sources=list(sources or TML_SOURCES)
    cache_dir=Path(cache_dir); cache_dir.mkdir(parents=True,exist_ok=True)
    now=now or datetime.now(timezone.utc)
    manifest=_load_manifest(cache_dir); manifest.setdefault('sources',{})
    due=[]; resolved={}; warnings=[]; fresh=[]; cached=[]; missing=[]

    for source in sources:
        if _source_due(source,manifest,cache_dir,now):
            due.append(source)
        else:
            d=_read_cached(cache_dir,source)
            if d is not None:
                resolved[source['key']]=d; cached.append(source['key'])
            else:
                due.append(source)

    # Fetch due sources in parallel. If the provider is down, total wait is roughly one
    # timeout window instead of timeout * number_of_files.
    if due:
        workers=min(6,len(due))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures={pool.submit(downloader,s['url']):s for s in due}
            for fut in as_completed(futures):
                source=futures[fut]
                try:
                    d=fut.result()
                    if d is None or d.empty:
                        raise RuntimeError('pusty plik CSV')
                    _write_cached(cache_dir,source,d)
                    manifest['sources'][source['key']]={
                        'fetched_at':now.isoformat(),'rows':int(len(d)),'url':source['url']
                    }
                    resolved[source['key']]=d; fresh.append(source['key'])
                except Exception as e:
                    fallback=_read_cached(cache_dir,source)
                    if fallback is not None and not fallback.empty:
                        resolved[source['key']]=fallback; cached.append(source['key'])
                        warnings.append(f"{source['key']}: świeże dane niedostępne, użyto cache ({type(e).__name__})")
                    else:
                        missing.append(source['key'])
                        warnings.append(f"{source['key']}: brak świeżych danych i cache ({type(e).__name__})")

    _save_manifest(cache_dir,manifest)
    frames=[]
    for source in sources:
        d=resolved.get(source['key'])
        if d is None or d.empty:
            continue
        d=d.copy(); d['source_tour']=source['tour']; frames.append(d)

    info={
        'fresh_sources':len(set(fresh)),
        'cached_sources':len(set(cached)),
        'missing_sources':len(set(missing)),
        'cache_files':sum(1 for s in sources if _cache_path(cache_dir,s).exists()),
    }
    if fresh and cached: info['mode']='fresh+cache'
    elif fresh: info['mode']='fresh'
    elif cached: info['mode']='cache'
    else: info['mode']='unavailable'

    if not frames:
        return None,warnings,info
    return pd.concat(frames,ignore_index=True,sort=False),warnings,info


def fetch_fixtures():
    key=os.getenv('LIVE_TENNIS_API_KEY','').strip()
    if not key:
        return manual_fixtures(), 'manual'
    days=max(1,int(os.getenv('FIXTURE_DAYS','1')))
    today=datetime.now(timezone.utc).date()
    headers={'Authorization':f'Bearer {key}','User-Agent':UA}
    base={'status':'upcoming','from':str(today),'to':str(today+timedelta(days=days-1)),'limit':200}

    rows=[]; seen=set(); offset=0
    for _ in range(10):
        params={**base,'offset':offset}
        r=requests.get('https://api.livetennisapi.com/api/public/v1/matches',params=params,headers=headers,timeout=(7,18))
        r.raise_for_status()
        payload=r.json(); page=payload.get('data',[]) or []; meta=payload.get('meta',{}) or {}
        for m in page:
            if m.get('is_doubles'):
                continue
            players=m.get('players') or {}
            p1=(players.get('p1') or {}).get('name'); p2=(players.get('p2') or {}).get('name')
            if not p1 or not p2:
                continue
            mid=m.get('id')
            uniq=mid if mid is not None else (m.get('scheduled_time'),p1,p2,m.get('tournament'))
            if uniq in seen:
                continue
            seen.add(uniq)
            rows.append({
                'id':mid,'tour':m.get('tour') or '', 'tournament':m.get('tournament') or '',
                'surface':m.get('surface') or '', 'p1':p1, 'p2':p2,
                'scheduled_time':m.get('scheduled_time') or '',
                'feed_status':m.get('status') or 'upcoming','event_status':m.get('event_status'),
            })
        offset += len(page)
        total=meta.get('total')
        if not page or len(page)<200:
            break
        if isinstance(total,(int,float)) and offset>=int(total):
            break
    return rows,'live-tennis-api-free'


def manual_fixtures():
    p=DATA/'manual_matches.csv'
    if not p.exists(): return []
    d=pd.read_csv(p); rows=[]
    for _,r in d.iterrows():
        if not str(r.get('p1','')).strip() or not str(r.get('p2','')).strip(): continue
        rows.append({k:(str(r.get(k,'')) if not pd.isna(r.get(k,'')) else '') for k in ['tour','tournament','surface','p1','p2','scheduled_time']})
    return rows


def save_sqlite(long_df):
    db=DATA/'tennis.db'
    with sqlite3.connect(db) as con:
        long_df.to_sql('player_matches',con,if_exists='replace',index=False)
        con.execute('CREATE INDEX IF NOT EXISTS ix_player_date ON player_matches(player,date)')
        if 'player_key' in long_df.columns:
            con.execute('CREATE INDEX IF NOT EXISTS ix_player_key_date ON player_matches(player_key,date)')
    return db


def _load_existing_meta():
    p=OUT/'meta.json'
    try:
        x=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        return x if isinstance(x,dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    now=datetime.now(timezone.utc)
    hist,errors,history_info=load_history(now=now)

    # First cache bootstrap + provider outage: keep the last committed analysis instead
    # of failing Pages. Client-side stale filtering still removes already-started matches.
    if hist is None or hist.empty:
        meta=_load_existing_meta()
        meta.update({
            'history_mode':'degraded-previous','degraded_reason':'history_source_unavailable',
            'history_cache_sources':history_info.get('cached_sources',0),
            'history_missing_sources':history_info.get('missing_sources',0),
        })
        _write_json(OUT/'meta.json',meta)
        print(json.dumps({'degraded':True,'history_info':history_info,'warnings':errors},ensure_ascii=False,indent=2))
        return

    long_df=normalize_matches(hist)
    save_sqlite(long_df)
    fixtures,mode=fetch_fixtures()
    analysed=[analyse_match(long_df,m) for m in fixtures]

    prediction_history=load_prediction_history(HISTORY_PATH)
    prediction_history=archive_predictions(prediction_history,analysed,now=now)
    prediction_history=settle_history(prediction_history,hist,now=now)
    prediction_history=sorted(prediction_history,key=lambda e:e.get('scheduled_time') or '',reverse=True)[:2500]
    save_prediction_history(HISTORY_PATH,prediction_history)
    _write_json(HISTORY_STATS_PATH,history_stats(prediction_history))

    results=[r for r in analysed if is_current_match(r,now=now,grace_minutes=30)]
    hidden_stale=len(analysed)-len(results)
    ready=sum(1 for r in results if r.get('model_ready'))

    def default(o):
        if pd.isna(o): return None
        if hasattr(o,'isoformat'): return o.isoformat()
        raise TypeError(type(o))

    (OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,default=default),encoding='utf-8')
    meta={
        'updated_at':now.isoformat(),'fixtures_mode':mode,
        'fixtures':len(fixtures),'visible_fixtures':len(results),'hidden_stale':hidden_stale,'model_ready':ready,
        'history_rows_raw':len(hist),'player_rows':len(long_df),'download_warnings':errors,
        'history_matches':sum(1 for e in prediction_history if e.get('signals')),
        'history_mode':history_info.get('mode'),'history_fresh_sources':history_info.get('fresh_sources',0),
        'history_cache_sources':history_info.get('cached_sources',0),'history_missing_sources':history_info.get('missing_sources',0),
        'degraded_reason':None,
    }
    _write_json(OUT/'meta.json',meta)
    print(json.dumps(meta,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
