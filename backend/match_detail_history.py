"""Read-only UI export of existing H2H results; no model or settlement writes."""
from __future__ import annotations
import csv
import gzip
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

try:
    from .player_identity import player_identity_map
except ImportError:
    from player_identity import player_identity_map

ROOT = Path(__file__).resolve().parents[1]


def name_key(value):
    text = unicodedata.normalize('NFKD', str(value or '').casefold().replace('ł', 'l'))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(sorted(re.findall(r'[^\W_]+', text, re.UNICODE)))


def read(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def score_signature(row):
    """Comparable set scores for presentation-only cross-source deduplication."""
    result = row.get('result') or {}
    sets = result.get('sets')
    if isinstance(sets, list):
        out = []
        for pair in sets:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                return ()
            try:
                out.append((int(pair[0]), int(pair[1])))
            except (TypeError, ValueError):
                return ()
        if out:
            return tuple(out)
    score = str(result.get('score_text') or '')
    return tuple((int(a), int(b)) for a, b in re.findall(r'(?<!\d)(\d+)\s*[-:]\s*(\d+)', score))


def row_day(row):
    value = str(row.get('scheduled_time') or '')[:10]
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def same_meeting(a, b, max_day_gap=8):
    """Detect the same published meeting without comparing foreign provider IDs."""
    pair_a = tuple(sorted((name_key(a.get('p1')), name_key(a.get('p2')))))
    pair_b = tuple(sorted((name_key(b.get('p1')), name_key(b.get('p2')))))
    if not all(pair_a) or pair_a != pair_b:
        return False
    score_a, score_b = score_signature(a), score_signature(b)
    if not score_a or not score_b:
        return False
    reverse_b = tuple((right, left) for left, right in score_b)
    if score_a not in (score_b, reverse_b):
        return False
    day_a, day_b = row_day(a), row_day(b)
    return bool(day_a and day_b and abs((day_a - day_b).days) <= max_day_gap)


def merge_provider_identity(existing, provider):
    """Enrich a duplicate archive row with canonical live-provider identity only."""
    for existing_side in ('p1', 'p2'):
        for provider_side in ('p1', 'p2'):
            if name_key(existing.get(existing_side)) == name_key(provider.get(provider_side)):
                provider_id = provider.get(provider_side + '_id')
                if provider_id is not None:
                    existing[existing_side + '_id'] = provider_id
                break
    if provider.get('match_id') is not None:
        existing['match_id'] = provider['match_id']
    existing_sources = str(existing.get('source') or '').split('+')
    provider_source = str(provider.get('source') or '')
    if provider_source and provider_source not in existing_sources:
        existing['source'] = '+'.join([s for s in existing_sources + [provider_source] if s])


def build(root=ROOT):
    data = root / 'frontend/data'
    fixtures = read(data / 'results.json', [])
    if isinstance(fixtures, dict):
        fixtures = fixtures.get('matches', [])
    pairs = {tuple(sorted((name_key(m.get('p1')), name_key(m.get('p2'))))) for m in fixtures}
    rows, seen, sources = [], set(), []
    # IDs from TennisMyLife and the live provider are different namespaces.
    # Preserve external IDs; never compare them with fixture provider IDs.
    for path in sorted((root / 'data/cache').glob('*.csv.gz')):
        count = 0
        with gzip.open(path, 'rt', encoding='utf-8-sig', newline='') as stream:
            for r in csv.DictReader(stream):
                a, b = r.get('winner_name'), r.get('loser_name')
                if not a or not b or tuple(sorted((name_key(a), name_key(b)))) not in pairs:
                    continue
                try:
                    day = datetime.strptime(str(r.get('tourney_date', ''))[:8], '%Y%m%d').date().isoformat()
                except ValueError:
                    continue
                identity = (r.get('tourney_id'), r.get('match_num'), day, name_key(a), name_key(b), r.get('score'))
                if identity in seen:
                    continue
                seen.add(identity)
                rows.append({'p1': a, 'p2': b, 'scheduled_time': day,
                             'date_precision': 'tournament', 'surface': (r.get('surface') or '').lower(),
                             'tournament': r.get('tourney_name'), 'source': 'tennismylife',
                             'external_ids': {'namespace': 'tennismylife', 'p1': r.get('winner_id'), 'p2': r.get('loser_id')},
                             'result': {'winner': a, 'score_text': r.get('score') or None, 'status': 'completed'}})
                count += 1
        sources.append({'file': path.name, 'matched_rows': count})
    # Provider-backed DNA caches include stable IDs, unlike the betting history.
    provider_pairs = {frozenset((str(m.get('p1_id')), str(m.get('p2_id')))) for m in fixtures
                      if m.get('p1_id') is not None and m.get('p2_id') is not None}
    cache_files = sorted((root / 'data/cache/pbp_v7/matches').glob('*.json.gz'))
    provider_count = 0
    for path in cache_files:
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            payload = json.load(stream)
        identities = player_identity_map(payload)
        if not identities or frozenset(str(p['id']) for p in identities.values()) not in provider_pairs:
            continue
        match = payload.get('match') or {}
        status = str(match.get('event_status') or '').casefold()
        winner = match.get('winner')
        if status not in ('finished', 'completed', 'ended', 'retired', 'retirement'):
            continue
        if not all(p.get('name') for p in identities.values()) or not match.get('scheduled_time'):
            continue
        games = (match.get('score') or {}).get('games')
        sets = [list(pair) for pair in zip(*games)] if isinstance(games, list) and len(games) == 2 and all(isinstance(g, list) for g in games) else []
        candidate = {'match_id': match.get('id') or path.name.removesuffix('.json.gz'),
                     'p1': identities[1]['name'], 'p2': identities[2]['name'],
                     'p1_id': identities[1]['id'], 'p2_id': identities[2]['id'],
                     'scheduled_time': match['scheduled_time'], 'surface': match.get('surface'),
                     'source': 'livetennisapi',
                     'result': {'status': status, 'winner': identities[winner]['name'] if type(winner) is int and winner in (1, 2) else None, 'sets': sets}}
        duplicate = next((row for row in rows if same_meeting(row, candidate)), None)
        if duplicate is None:
            rows.append(candidate)
        else:
            merge_provider_identity(duplicate, candidate)
        provider_count += 1
    if cache_files:
        sources.append({'file': 'pbp_v7/matches', 'matched_rows': provider_count})
    # Only this presentation artifact is written. Historical results stay intact.
    payload = {'generated_at': datetime.now(timezone.utc).isoformat(), 'matches': rows,
               'sources': sources, 'archive_available': bool(sources),
               'scope': 'current_fixture_pairs; available cached archives; tournament dates labelled'}
    (data / 'match_detail_history.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return payload


if __name__ == '__main__':
    result = build()
    print(f"Match detail history: {len(result['matches'])} archived meetings, {len(result['sources'])} cached sources")
