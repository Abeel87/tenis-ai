from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

GREEN_THRESHOLD = 72.0
MODEL_VERSION = 'v5-adaptive'
VOID_RE = re.compile(r'\b(RET|W/O|WO|DEF|ABD|ABN)\b', re.I)
SET_RE = re.compile(r'(\d+)\s*[-:]\s*(\d+)')


def _key(value):
    value = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().casefold()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', value).split())


def _dt(value):
    if not value:
        return None
    try:
        d = pd.to_datetime(value, utc=True, errors='coerce')
    except Exception:
        return None
    if pd.isna(d):
        return None
    return d.to_pydatetime()


def match_key(match: dict) -> str:
    mid = match.get('id')
    if mid is not None and str(mid) != '':
        return f'id:{mid}'
    return '|'.join([
        _key(match.get('p1')),
        _key(match.get('p2')),
        str(match.get('scheduled_time') or '')[:10],
        _key(match.get('tournament')),
    ])


def load_history(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def save_history(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = sorted(entries, key=lambda e: e.get('scheduled_time') or '', reverse=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')


def _signal(market, label, pick, score, **extra):
    return {
        'id': '|'.join([market, str(extra.get('line', '')), str(extra.get('checkpoint', '')), str(pick)]),
        'market': market,
        'label': label,
        'pick': str(pick),
        'score': round(float(score), 1),
        'result': 'pending',
        **extra,
    }


def extract_green_signals(match: dict, threshold: float = GREEN_THRESHOLD) -> list[dict]:
    """Freeze every market that is visually green in the app (score >= threshold)."""
    out = []

    def add_binary(field, market, label, **extra):
        obj = match.get(field) or {}
        for pick, value in obj.items():
            if value is not None and float(value) >= threshold:
                out.append(_signal(market, label, pick, value, **extra))

    add_binary('match_win', 'match_winner', 'Zwycięzca meczu')
    add_binary('first_set_win', 'set1_winner', 'Zwycięzca 1. seta')
    add_binary('second_set_win', 'set2_winner', 'Zwycięzca 2. seta')
    add_binary('third_set_win', 'set3_winner', 'Zwycięzca 3. seta · jeśli będzie')
    add_binary('total_sets', 'total_sets', 'Liczba setów')
    add_binary('exact_match_score', 'exact_match', 'Dokładny wynik meczu')

    for checkpoint, states in (match.get('game_states') or {}).items():
        for pick, value in (states or {}).items():
            if value is not None and float(value) >= threshold:
                out.append(_signal(
                    'game_state', f'Wynik po {checkpoint} gemach', pick, value,
                    checkpoint=int(checkpoint), resolvable=False,
                ))

    for line, sides in (match.get('over_under') or {}).items():
        for side in ('over', 'under'):
            value = (sides or {}).get(side)
            if value is not None and float(value) >= threshold:
                out.append(_signal(
                    'set1_total', f'1. set · {side.upper()} {line}', side, value,
                    line=float(line),
                ))

    for line, sides in (match.get('match_over_under') or {}).items():
        for side in ('over', 'under'):
            value = (sides or {}).get(side)
            if value is not None and float(value) >= threshold:
                out.append(_signal(
                    'match_total', f'Mecz · {side.upper()} {line}', side, value,
                    line=float(line),
                ))

    for pick, value in (match.get('exact_first_set') or {}).items():
        if value is not None and float(value) >= threshold:
            out.append(_signal('exact_set1', 'Dokładny wynik 1. seta', pick, value))

    return sorted(out, key=lambda s: (-s['score'], s['label'], s['pick']))


def archive_predictions(entries: list[dict], matches: list[dict], now: datetime | None = None,
                        cutoff_minutes: int = 5) -> list[dict]:
    """Keep the latest pre-match snapshot. Once kickoff is within cutoff, the snapshot is frozen."""
    now = now or datetime.now(timezone.utc)
    by_key = {e.get('match_key'): e for e in entries if e.get('match_key')}

    for match in matches:
        if not match.get('model_ready'):
            continue
        scheduled = _dt(match.get('scheduled_time'))
        if scheduled is None or scheduled <= now + timedelta(minutes=cutoff_minutes):
            continue
        key = match_key(match)
        current = by_key.get(key)
        if current and current.get('status') not in ('pending', 'upcoming'):
            continue

        signals = extract_green_signals(match)
        first_captured = (current or {}).get('first_captured_at') or now.isoformat()
        by_key[key] = {
            'match_key': key,
            'match_id': match.get('id'),
            'scheduled_time': match.get('scheduled_time'),
            'tour': match.get('tour') or '',
            'tournament': match.get('tournament') or '',
            'surface': match.get('surface') or '',
            'p1': match.get('p1') or '',
            'p2': match.get('p2') or '',
            'quality': match.get('quality'),
            'model_confidence': match.get('model_confidence'),
            'model_version': MODEL_VERSION,
            'first_captured_at': first_captured,
            'captured_at': now.isoformat(),
            'status': 'pending',
            'result': None,
            'signals': signals,
        }

    return list(by_key.values())


def is_current_match(match: dict, now: datetime | None = None, grace_minutes: int = 30) -> bool:
    """Client/backend safety net for feeds that keep a past fixture marked upcoming."""
    scheduled = _dt(match.get('scheduled_time'))
    if scheduled is None:
        return True
    now = now or datetime.now(timezone.utc)
    return scheduled >= now - timedelta(minutes=grace_minutes)


def _date_from_row(row) -> datetime | None:
    value = row.get('tourney_date')
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        text = str(int(float(value)))
    except (TypeError, ValueError):
        text = str(value)
    d = pd.to_datetime(text, format='%Y%m%d', errors='coerce', utc=True)
    if pd.isna(d):
        return None
    return d.to_pydatetime()


def find_final_result(hist: pd.DataFrame, entry: dict) -> dict | None:
    """Resolve ATP/WTA/Challenger entries from the already-downloaded TennisMyLife result files."""
    if hist is None or hist.empty:
        return None
    p1k, p2k = _key(entry.get('p1')), _key(entry.get('p2'))
    if not p1k or not p2k or 'winner_name' not in hist.columns or 'loser_name' not in hist.columns:
        return None

    wk = hist['winner_name'].map(_key)
    lk = hist['loser_name'].map(_key)
    mask = ((wk == p1k) & (lk == p2k)) | ((wk == p2k) & (lk == p1k))
    candidates = hist[mask].copy()
    if candidates.empty:
        return None

    scheduled = _dt(entry.get('scheduled_time'))
    if scheduled is not None and 'tourney_date' in candidates.columns:
        candidates['_result_date'] = candidates.apply(_date_from_row, axis=1)
        candidates['_delta'] = candidates['_result_date'].map(
            lambda d: abs((d.date() - scheduled.date()).days) if d else 999
        )
        candidates = candidates[candidates['_delta'] <= 2]
        if candidates.empty:
            return None
        candidates = candidates.sort_values('_delta')

    # Prefer a row that actually contains a score.
    if 'score' in candidates.columns:
        scored = candidates[candidates['score'].notna() & (candidates['score'].astype(str).str.strip() != '')]
        if not scored.empty:
            candidates = scored
    row = candidates.iloc[0]
    return parse_final_row(row, entry)


def parse_final_row(row, entry: dict) -> dict | None:
    winner = str(row.get('winner_name') or '').strip()
    loser = str(row.get('loser_name') or '').strip()
    score_text = str(row.get('score') or '').strip()
    if not winner or not loser:
        return None

    if VOID_RE.search(score_text):
        return {
            'status': 'void', 'winner': winner, 'score_text': score_text,
            'reason': 'retirement/walkover/unfinished',
        }

    raw_sets = [(int(a), int(b)) for a, b in SET_RE.findall(score_text)]
    if len(raw_sets) < 2:
        return None

    p1k = _key(entry.get('p1'))
    winner_is_p1 = _key(winner) == p1k
    sets = raw_sets if winner_is_p1 else [(b, a) for a, b in raw_sets]
    set_wins_p1 = sum(1 for a, b in sets if a > b)
    set_wins_p2 = sum(1 for a, b in sets if b > a)
    if set_wins_p1 == set_wins_p2:
        return None

    return {
        'status': 'completed',
        'winner': entry.get('p1') if set_wins_p1 > set_wins_p2 else entry.get('p2'),
        'score_text': score_text,
        'sets': [[a, b] for a, b in sets],
        'match_score': f'{set_wins_p1}:{set_wins_p2}',
        'number_of_sets': len(sets),
        'total_games': sum(a + b for a, b in sets),
        'first_set_score': f'{sets[0][0]}:{sets[0][1]}',
    }


def settle_signal(signal: dict, final: dict) -> str:
    if final.get('status') != 'completed':
        return 'void'

    market = signal.get('market')
    pick = str(signal.get('pick') or '')
    sets = final.get('sets') or []

    if market == 'game_state':
        return 'unverifiable'
    if market == 'match_winner':
        return 'hit' if _key(pick) == _key(final.get('winner')) else 'miss'
    if market in ('set1_winner', 'set2_winner', 'set3_winner'):
        idx = {'set1_winner': 0, 'set2_winner': 1, 'set3_winner': 2}[market]
        if len(sets) <= idx:
            return 'void'
        a, b = sets[idx]
        actual = final.get('p1') if False else None
        # final sets are p1:p2; use the signal entry's player names supplied below.
        p1 = final.get('p1')
        p2 = final.get('p2')
        if not p1 or not p2:
            return 'void'
        actual = p1 if a > b else p2
        return 'hit' if _key(pick) == _key(actual) else 'miss'
    if market == 'total_sets':
        wanted = 2 if pick.startswith('2') else (3 if pick.startswith('3') else None)
        return 'hit' if wanted == final.get('number_of_sets') else 'miss' if wanted else 'void'
    if market == 'exact_match':
        return 'hit' if pick == final.get('match_score') else 'miss'
    if market == 'set1_total':
        if not sets:
            return 'void'
        total = sum(sets[0])
        line = float(signal.get('line'))
        ok = total > line if pick == 'over' else total < line
        return 'hit' if ok else 'miss'
    if market == 'match_total':
        total = final.get('total_games')
        if total is None:
            return 'void'
        line = float(signal.get('line'))
        ok = total > line if pick == 'over' else total < line
        return 'hit' if ok else 'miss'
    if market == 'exact_set1':
        return 'hit' if pick == final.get('first_set_score') else 'miss'
    return 'unverifiable'


def settle_history(entries: list[dict], hist: pd.DataFrame, now: datetime | None = None,
                   min_age_minutes: int = 75) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    out = []
    for entry in entries:
        if entry.get('status') not in ('pending', 'upcoming'):
            out.append(entry)
            continue
        scheduled = _dt(entry.get('scheduled_time'))
        if scheduled is None or scheduled > now - timedelta(minutes=min_age_minutes):
            out.append(entry)
            continue
        final = find_final_result(hist, entry)
        if final is None:
            out.append(entry)
            continue

        final = {**final, 'p1': entry.get('p1'), 'p2': entry.get('p2')}
        entry = dict(entry)
        entry['result'] = final
        entry['settled_at'] = now.isoformat()
        entry['status'] = 'void' if final.get('status') == 'void' else 'settled'
        signals = []
        for signal in entry.get('signals') or []:
            signal = dict(signal)
            signal['result'] = settle_signal(signal, final)
            signals.append(signal)
        entry['signals'] = signals
        out.append(entry)
    return out


def _bucket(score: float) -> str:
    score = float(score)
    if score >= 90:
        return '90–100'
    if score >= 80:
        return '80–89'
    return '72–79'


def history_stats(entries: list[dict]) -> dict:
    settled = []
    for entry in entries:
        for signal in entry.get('signals') or []:
            if signal.get('result') in ('hit', 'miss'):
                settled.append((entry, signal))

    def summarize(items):
        hits = sum(1 for _, s in items if s.get('result') == 'hit')
        total = len(items)
        return {
            'settled': total,
            'hits': hits,
            'misses': total - hits,
            'accuracy': round(hits * 100 / total, 1) if total else None,
        }

    def grouped(key_fn):
        groups = {}
        for pair in settled:
            key = key_fn(*pair)
            groups.setdefault(key, []).append(pair)
        return {k: summarize(v) for k, v in sorted(groups.items())}

    pending = sum(1 for e in entries if e.get('status') in ('pending', 'upcoming') and (e.get('signals') or []))
    unverifiable = sum(
        1 for e in entries for s in (e.get('signals') or [])
        if s.get('result') in ('unverifiable', 'void')
    )
    return {
        'overall': summarize(settled),
        'matches_tracked': sum(1 for e in entries if e.get('signals')),
        'matches_pending': pending,
        'excluded_signals': unverifiable,
        'by_market': grouped(lambda e, s: s.get('label') or s.get('market') or 'Inne'),
        'by_tour': grouped(lambda e, s: (e.get('tour') or 'inne').upper()),
        'by_score_band': grouped(lambda e, s: _bucket(s.get('score') or GREEN_THRESHOLD)),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'green_threshold': GREEN_THRESHOLD,
    }
