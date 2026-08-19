from __future__ import annotations
import io, json, os, sqlite3
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
OUT.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)
HISTORY_PATH=OUT/'history.json'
HISTORY_STATS_PATH=OUT/'history_stats.json'

TML_URLS=[
    ('ATP','https://stats.tennismylife.org/data/ongoing_tourneys.csv'),
    ('CH','https://stats.tennismylife.org/data/challenger_ongoing_tourneys.csv'),
    ('WTA','https://stats.tennismylife.org/data/wta_ongoing_tourneys.csv'),
    ('ATP','https://stats.tennismylife.org/data/2026.csv'),
    ('ATP','https://stats.tennismylife.org/data/2025.csv'),
    ('CH','https://stats.tennismylife.org/data/2026_challenger.csv'),
    ('CH','https://stats.tennismylife.org/data/2025_challenger.csv'),
    ('WTA','https://stats.tennismylife.org/data/2026_wta.csv'),
    ('WTA','https://stats.tennismylife.org/data/2025_wta.csv'),
]

UA='TenisAI-EarlyHold/0.5.1 (personal non-commercial analytics)'


def download_csv(url):
    r=requests.get(url,headers={'User-Agent':UA},timeout=40)
    r.raise_for_status()
    return pd.read_csv(io.BytesIO(r.content), low_memory=False)


def load_history():
    frames=[]; errors=[]
    for tour,url in TML_URLS:
        try:
            d=download_csv(url); d['source_tour']=tour; frames.append(d)
        except Exception as e:
            errors.append(f'{url}: {e}')
    if not frames:
        raise RuntimeError('Nie udało się pobrać żadnego pliku historycznego. '+ '; '.join(errors))
    hist=pd.concat(frames, ignore_index=True, sort=False)
    return hist, errors


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
        r=requests.get('https://api.livetennisapi.com/api/public/v1/matches', params=params, headers=headers, timeout=30)
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
                'feed_status':m.get('status') or 'upcoming',
                'event_status':m.get('event_status'),
            })
        offset += len(page)
        total=meta.get('total')
        if not page or len(page) < 200:
            break
        if isinstance(total,(int,float)) and offset >= int(total):
            break
    return rows, 'live-tennis-api-free'


def manual_fixtures():
    p=DATA/'manual_matches.csv'
    if not p.exists(): return []
    d=pd.read_csv(p)
    rows=[]
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


def main():
    now=datetime.now(timezone.utc)
    hist, errors=load_history()
    long_df=normalize_matches(hist)
    save_sqlite(long_df)
    fixtures, mode=fetch_fixtures()
    analysed=[analyse_match(long_df,m) for m in fixtures]

    # Freeze green pre-match signals, then try to settle older entries from the result files
    # we already download for the model. This does not consume extra Live Tennis API quota.
    prediction_history=load_prediction_history(HISTORY_PATH)
    prediction_history=archive_predictions(prediction_history, analysed, now=now)
    prediction_history=settle_history(prediction_history, hist, now=now)
    # Keep the file bounded while preserving roughly a year of normal use.
    prediction_history=sorted(prediction_history, key=lambda e:e.get('scheduled_time') or '', reverse=True)[:2500]
    save_prediction_history(HISTORY_PATH, prediction_history)
    HISTORY_STATS_PATH.write_text(json.dumps(history_stats(prediction_history),ensure_ascii=False,indent=2),encoding='utf-8')

    # Feed occasionally leaves a past fixture marked upcoming. Hide it after a 30-minute grace window.
    results=[r for r in analysed if is_current_match(r, now=now, grace_minutes=30)]
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
    }
    (OUT/'meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
