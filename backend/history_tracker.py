from __future__ import annotations

try:
    from .history_sampling import unique_signals
except ImportError:
    from history_sampling import unique_signals

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

try:
    from .signal_settlement import settle_signal, settle_layers, reconcile_settled
except ImportError:
    from signal_settlement import settle_signal, settle_layers, reconcile_settled

try:
    from .game_state_tracking_v84e1 import learning_signals as game_state_learning_signals
except ImportError:
    from game_state_tracking_v84e1 import learning_signals as game_state_learning_signals

GREEN_THRESHOLD = 72.0
MODEL_VERSION = 'v7.8D-calibration-guard'
HISTORY_MAX_ENTRIES = 2500
HISTORY_TARGET_BYTES = 48 * 1024 * 1024
TERMINAL_HISTORY_STATUSES = {'settled', 'void'}


def compact_history_size(entries: list[dict]) -> int:
    """UTF-8 byte size of the public compact JSON representation."""
    return len(json.dumps(entries, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def retain_history(
    entries: list[dict],
    max_entries: int = HISTORY_MAX_ENTRIES,
    max_compact_bytes: int = HISTORY_TARGET_BYTES,
) -> list[dict]:
    """Bound public history without discarding unresolved settlement work.

    The old policy capped history only by match count. As each match accumulated
    more SHADOW/learning layers, 2500 rows eventually exceeded the runtime's
    emergency 50 MiB payload ceiling. This policy keeps the same newest-first
    retention semantics but also enforces a byte budget on the *compact* JSON
    representation.

    Pending/upcoming/unknown statuses are protected. When either limit is
    exceeded we discard only the oldest terminal (settled/void) entries.
    """
    ordered = sorted(
        [entry for entry in entries if isinstance(entry, dict)],
        key=lambda entry: entry.get('scheduled_time') or '',
        reverse=True,
    )
    if not ordered:
        return []

    sizes = [
        len(json.dumps(entry, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        for entry in ordered
    ]
    keep = [True] * len(ordered)
    kept_count = len(ordered)

    # Preserve the legacy 2500-entry ceiling, but never sacrifice an unresolved
    # match merely to satisfy the count cap.
    if max_entries > 0 and kept_count > max_entries:
        for idx in range(len(ordered) - 1, -1, -1):
            if kept_count <= max_entries:
                break
            if str(ordered[idx].get('status') or '').casefold() in TERMINAL_HISTORY_STATUSES:
                keep[idx] = False
                kept_count -= 1

    def current_bytes() -> int:
        selected_sizes = [sizes[i] for i, flag in enumerate(keep) if flag]
        return 2 + sum(selected_sizes) + max(0, len(selected_sizes) - 1)

    total_bytes = current_bytes()
    if max_compact_bytes > 0 and total_bytes > max_compact_bytes:
        for idx in range(len(ordered) - 1, -1, -1):
            if total_bytes <= max_compact_bytes:
                break
            if not keep[idx]:
                continue
            if str(ordered[idx].get('status') or '').casefold() not in TERMINAL_HISTORY_STATUSES:
                continue
            # Removing one element removes its JSON bytes and one list comma
            # whenever at least one other element remains.
            keep[idx] = False
            total_bytes -= sizes[idx]
            if kept_count > 1:
                total_bytes -= 1
            kept_count -= 1

    return [entry for idx, entry in enumerate(ordered) if keep[idx]]
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

    def add_binary(field, market, label, source_model="adaptive", **extra):
        obj = match.get(field) or {}
        for pick, value in obj.items():
            if value is not None and float(value) >= threshold:
                out.append(_signal(market, label, pick, value, source_model=source_model, **extra))

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
                    source_model='early_hold_pbp' if (match.get('early_hold_v7') or {}).get('ready') else 'adaptive',
                ))

    for line, sides in (match.get('over_under') or {}).items():
        for side in ('over', 'under'):
            value = (sides or {}).get(side)
            if value is not None and float(value) >= threshold:
                out.append(_signal(
                    'set1_total', f'1. set · {side.upper()} {line}', side, value,
                    line=float(line), source_model='adaptive',
                ))

    for line, sides in (match.get('match_over_under') or {}).items():
        for side in ('over', 'under'):
            value = (sides or {}).get(side)
            if value is not None and float(value) >= threshold:
                out.append(_signal(
                    'match_total', f'Mecz · {side.upper()} {line}', side, value,
                    line=float(line), source_model='adaptive',
                ))

    for pick, value in (match.get('exact_first_set') or {}).items():
        if value is not None and float(value) >= threshold:
            out.append(_signal('exact_set1', 'Dokładny wynik 1. seta', pick, value, source_model='adaptive'))

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
            # Other models freeze their own snapshot once. Refreshing the base
            # forecast must not erase their scores or per-model capture times.
            **(current or {}),
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
            'game_state_learning_v84e1': game_state_learning_signals(match),
        }

    return list(by_key.values())


def is_current_match(match: dict, now: datetime | None = None, grace_minutes: int = 30) -> bool:
    """Client/backend safety net for feeds that keep a past fixture marked upcoming."""
    scheduled = _dt(match.get('scheduled_time'))
    if scheduled is None:
        return False
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


def _tournament_compatible(a, b) -> bool:
    ak, bk = _key(a), _key(b)
    if not ak or not bk:
        return False
    return ak == bk or (len(ak) >= 5 and len(bk) >= 5 and (ak in bk or bk in ak))


def _dedupe_final_candidates(candidates: pd.DataFrame) -> pd.DataFrame:
    cols = [
        c for c in (
            'winner_name', 'loser_name', 'tourney_date', 'tourney_name',
            'tournament', 'event_name', 'score',
        )
        if c in candidates.columns
    ]
    return candidates.drop_duplicates(subset=cols) if cols else candidates.drop_duplicates()


def find_final_result(hist: pd.DataFrame, entry: dict) -> dict | None:
    """Conservative TML fallback: names + closest date + tournament when possible.

    If two distinct rows are still equally plausible, leave the match pending so
    the Live Tennis API settlement step can resolve it instead of guessing.
    """
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

    # Tournament is a stronger disambiguator than a one-day archive-date drift.
    # Filter it before choosing the closest date when a compatible row exists.
    target_tournament = entry.get('tournament')
    if _key(target_tournament):
        for col in ('tourney_name', 'tournament', 'event_name'):
            if col not in candidates.columns:
                continue
            matched = candidates[candidates[col].map(
                lambda value: _tournament_compatible(target_tournament, value)
            )]
            if not matched.empty:
                candidates = matched.copy()
                break

    if '_delta' in candidates.columns:
        best_delta = candidates['_delta'].min()
        candidates = candidates[candidates['_delta'] == best_delta].copy()

    if 'score' in candidates.columns:
        scored = candidates[
            candidates['score'].notna()
            & (candidates['score'].astype(str).str.strip() != '')
        ]
        if not scored.empty:
            candidates = scored.copy()

    candidates = _dedupe_final_candidates(candidates)
    if len(candidates) != 1:
        return None
    return parse_final_row(candidates.iloc[0], entry)


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
        entry = settle_layers(entry, final, 'historical match result')
        out.append(entry)
    return reconcile_settled(out)


def _bucket(score: float) -> str:
    score = float(score)
    if score >= 90:
        return '90–100'
    if score >= 80:
        return '80–89'
    return '72–79'


def history_stats(entries: list[dict]) -> dict:
    """Headline accuracy = current model version only. Older versions are LEGACY."""
    all_settled = []
    current = []
    legacy = []

    for entry in entries:
        is_current = entry.get('model_version') == MODEL_VERSION
        for signal in unique_signals(entry):
            if signal.get('result') not in ('hit', 'miss'):
                continue
            pair = (entry, signal)
            all_settled.append(pair)
            (current if is_current else legacy).append(pair)

    def summarize(items):
        hits = sum(1 for _, sig in items if sig.get('result') == 'hit')
        total = len(items)
        return {
            'settled': total,
            'matches': len({e.get('match_key') or e.get('match_id') or (e.get('p1'), e.get('p2'), e.get('scheduled_time')) for e, _ in items}),
            'hits': hits,
            'misses': total - hits,
            'accuracy': round(hits * 100 / total, 1) if total else None,
        }

    def grouped(items, key_fn):
        groups = {}
        for pair in items:
            key = key_fn(*pair)
            groups.setdefault(key, []).append(pair)
        return {k: summarize(v) for k, v in sorted(groups.items())}

    current_entries = [e for e in entries if e.get('model_version') == MODEL_VERSION]
    legacy_entries = [e for e in entries if e.get('model_version') != MODEL_VERSION]

    pending = sum(
        1 for e in current_entries
        if e.get('status') in ('pending', 'upcoming') and (e.get('signals') or [])
    )
    unverifiable = sum(
        1 for e in current_entries for sig in (e.get('signals') or [])
        if sig.get('result') in ('unverifiable', 'void')
    )

    return {
        'overall': summarize(current),
        'sample_policy': 'unique events per model and match; standard set 10.5/11.5 merged; events within a match remain correlated',
        'raw_settled_signals': sum(s.get('result') in ('hit', 'miss') for e in current_entries for s in e.get('signals') or []),
        'current_model_version': MODEL_VERSION,
        'legacy_overall': summarize(legacy),
        'all_versions_overall': summarize(all_settled),
        'matches_tracked': sum(1 for e in current_entries if e.get('signals')),
        'matches_pending': pending,
        'legacy_matches_tracked': sum(1 for e in legacy_entries if e.get('signals')),
        'all_matches_tracked': sum(1 for e in entries if e.get('signals')),
        'excluded_signals': unverifiable,
        'by_market': grouped(current, lambda e, sig: sig.get('label') or sig.get('market') or 'Inne'),
        'by_tour': grouped(current, lambda e, sig: (e.get('tour') or 'inne').upper()),
        'by_score_band': grouped(current, lambda e, sig: _bucket(sig.get('score') or GREEN_THRESHOLD)),
        'by_version': grouped(all_settled, lambda e, sig: e.get('model_version') or 'N/D'),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'green_threshold': GREEN_THRESHOLD,
        'legacy_policy': 'reference_only',
    }
