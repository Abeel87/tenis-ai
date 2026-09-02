from __future__ import annotations
import math
import re
import unicodedata
from datetime import datetime
from typing import Optional

import pandas as pd

SET_RE = re.compile(r"(\d+)\s*[-:]\s*(\d+)")


def _key(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().casefold()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float('nan')


def _safe_div(a, b):
    a, b = _num(a), _num(b)
    if pd.isna(a) or pd.isna(b) or b <= 0:
        return float('nan')
    return a / b


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _sigmoid(x):
    return 1 / (1 + math.exp(-x))


def _logit(p):
    p = _clamp(float(p), 1e-6, 1 - 1e-6)
    return math.log(p / (1 - p))


def parse_sets(score) -> list[tuple[int, int]]:
    if not isinstance(score, str):
        return []
    return [(int(a), int(b)) for a, b in SET_RE.findall(score)]


def parse_first_set(score) -> tuple[Optional[int], Optional[int]]:
    sets = parse_sets(score)
    return sets[0] if sets else (None, None)


def parse_second_set(score) -> tuple[Optional[int], Optional[int]]:
    sets = parse_sets(score)
    return sets[1] if len(sets) > 1 else (None, None)


def _dedupe_history(df: pd.DataFrame) -> pd.DataFrame:
    """Ongoing + roczny CSV potrafią zawierać ten sam mecz. Nie liczmy go dwa razy."""
    if df is None or df.empty:
        return df
    cols = [c for c in ('tourney_date', 'tourney_name', 'winner_name', 'loser_name', 'score') if c in df.columns]
    return df.drop_duplicates(subset=cols, keep='last') if cols else df.drop_duplicates()


def normalize_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Convert winner/loser rows into one row per player-match."""
    out = []
    if df is None or df.empty:
        return pd.DataFrame()
    df = _dedupe_history(df)
    for _, r in df.iterrows():
        sets = parse_sets(r.get('score'))
        a, b = sets[0] if sets else (None, None)
        a2, b2 = sets[1] if len(sets) > 1 else (None, None)
        a3, b3 = sets[2] if len(sets) > 2 else (None, None)
        date = pd.to_datetime(str(r.get('tourney_date', '')), format='%Y%m%d', errors='coerce')
        surface = str(r.get('surface') or '').strip().lower()
        source_tour = str(r.get('source_tour') or '').strip().lower()
        first_set_games = (a + b) if a is not None and b is not None else None

        for side in ('w', 'l'):
            opp = 'l' if side == 'w' else 'w'
            name = r.get('winner_name') if side == 'w' else r.get('loser_name')
            opp_name = r.get('loser_name') if side == 'w' else r.get('winner_name')
            if not isinstance(name, str) or not name.strip():
                continue

            svpt = _num(r.get(f'{side}_svpt'))
            first_in = _num(r.get(f'{side}_1stIn'))
            first_won = _num(r.get(f'{side}_1stWon'))
            second_won = _num(r.get(f'{side}_2ndWon'))
            sv_gms = _num(r.get(f'{side}_SvGms'))
            bp_saved = _num(r.get(f'{side}_bpSaved'))
            bp_faced = _num(r.get(f'{side}_bpFaced'))

            opp_svpt = _num(r.get(f'{opp}_svpt'))
            opp_first_won = _num(r.get(f'{opp}_1stWon'))
            opp_second_won = _num(r.get(f'{opp}_2ndWon'))
            opp_sv_gms = _num(r.get(f'{opp}_SvGms'))
            opp_bp_saved = _num(r.get(f'{opp}_bpSaved'))
            opp_bp_faced = _num(r.get(f'{opp}_bpFaced'))

            breaks_conceded = bp_faced - bp_saved if not pd.isna(bp_faced) and not pd.isna(bp_saved) else float('nan')
            breaks_made = opp_bp_faced - opp_bp_saved if not pd.isna(opp_bp_faced) and not pd.isna(opp_bp_saved) else float('nan')
            second_total = svpt - first_in if not pd.isna(svpt) and not pd.isna(first_in) else float('nan')
            opp_spw = _safe_div(opp_first_won + opp_second_won, opp_svpt) if not pd.isna(opp_first_won) and not pd.isna(opp_second_won) else float('nan')

            def set_won(x, y):
                if x is None or y is None:
                    return float('nan')
                if side == 'w':
                    return 1.0 if x > y else 0.0
                return 1.0 if y > x else 0.0

            fsw = set_won(a, b)
            ssw = set_won(a2, b2)
            tsw = set_won(a3, b3)
            after_first_win = ssw if not pd.isna(fsw) and fsw == 1.0 else float('nan')
            after_first_loss = ssw if not pd.isna(fsw) and fsw == 0.0 else float('nan')

            rank = _num(r.get('winner_rank') if side == 'w' else r.get('loser_rank'))
            opp_rank = _num(r.get('loser_rank') if side == 'w' else r.get('winner_rank'))

            row = {
                'date': date,
                'surface': surface,
                'source_tour': source_tour,
                'player': name.strip(),
                'player_key': _key(name),
                'opponent': str(opp_name or '').strip(),
                'opponent_key': _key(opp_name),
                'rank': rank,
                'opponent_rank': opp_rank,
                'won': 1.0 if side == 'w' else 0.0,
                'hold_rate': 1 - _safe_div(breaks_conceded, sv_gms) if not pd.isna(breaks_conceded) else float('nan'),
                'break_rate': _safe_div(breaks_made, opp_sv_gms) if not pd.isna(breaks_made) else float('nan'),
                'serve_points_won': _safe_div(first_won + second_won, svpt) if not pd.isna(first_won) and not pd.isna(second_won) else float('nan'),
                'return_points_won': 1.0 - opp_spw if not pd.isna(opp_spw) else float('nan'),
                'first_serve_won': _safe_div(first_won, first_in),
                'second_serve_won': _safe_div(second_won, second_total),
                'first_set_won': fsw,
                'second_set_won': ssw,
                'second_after_first_win': after_first_win,
                'second_after_first_loss': after_first_loss,
                'third_set_won': tsw,
                'sets_played': float(len(sets)) if sets else float('nan'),
                'first_set_games': float(first_set_games) if first_set_games is not None else float('nan'),
            }
            for line in (8.5, 9.5, 10.5, 11.5, 12.5):
                key = str(line).replace('.', '')
                row[f'first_set_over{key}'] = (1.0 if first_set_games > line else 0.0) if first_set_games is not None else float('nan')
            out.append(row)
    return pd.DataFrame(out)


def _weighted_mean(values, weights):
    s = [(float(v), float(w)) for v, w in zip(values, weights) if not pd.isna(v) and w > 0]
    if not s:
        return None
    den = sum(w for _, w in s)
    return sum(v * w for v, w in s) / den if den else None


def _surface_priors(long_df: pd.DataFrame, surface: str = '', as_of=None) -> dict:
    if long_df is None or long_df.empty:
        return {}
    x = long_df
    if as_of is not None and 'date' in x.columns:
        cut = pd.to_datetime(as_of, errors='coerce')
        if not pd.isna(cut):
            x = x[x['date'] <= cut]
    if surface and 'surface' in x.columns:
        sx = x[x['surface'] == surface.lower()]
        if len(sx) >= 100:
            x = sx
    defaults = {
        'won': .50, 'hold_rate': .72, 'break_rate': .28, 'serve_points_won': .60,
        'return_points_won': .40, 'first_set_won': .50, 'second_set_won': .50,
        'second_after_first_win': .55, 'second_after_first_loss': .45, 'third_set_won': .50,
        'first_set_over85': .75, 'first_set_over95': .55, 'first_set_over105': .30,
        'first_set_over115': .25, 'first_set_over125': .15,
    }
    out = {}
    for col, default in defaults.items():
        if col in x.columns:
            v = pd.to_numeric(x[col], errors='coerce').mean()
            out[col] = float(v) if not pd.isna(v) else default
        else:
            out[col] = default
    return out


def _shrink(raw, prior, effective_n, prior_strength=3.0):
    if raw is None:
        return prior
    if prior is None:
        return raw
    n = max(0.0, float(effective_n or 0.0))
    return (float(raw) * n + float(prior) * prior_strength) / (n + prior_strength) if n + prior_strength > 0 else float(prior)


def _fixture_date(as_of):
    if as_of is None or as_of == '':
        return pd.Timestamp(datetime.utcnow().date())
    d = pd.to_datetime(as_of, errors='coerce', utc=True)
    if pd.isna(d):
        return pd.Timestamp(datetime.utcnow().date())
    return pd.Timestamp(d.date())


def player_profile(long_df: pd.DataFrame, player: str, surface: str = '', as_of=None, priors=None) -> dict:
    if long_df.empty:
        return {'player': player, 'matches': 0, 'quality': 'LOW'}
    key = _key(player)
    if 'player_key' in long_df.columns:
        x = long_df[long_df['player_key'] == key].copy()
    else:
        x = long_df[long_df['player'].map(_key) == key].copy()

    cut = _fixture_date(as_of)
    if 'date' in x.columns:
        x = x[x['date'].isna() | (x['date'] <= cut)]
    x = x.sort_values('date', ascending=False).head(20)
    if x.empty:
        return {'player': player, 'matches': 0, 'quality': 'LOW'}

    priors = priors or _surface_priors(long_df, surface, cut)
    weights = []
    for i, row in x.reset_index(drop=True).iterrows():
        # Płynny spadek zamiast sztywnego 5 + 5. Najnowsze mecze liczą się wyraźnie mocniej.
        w = 0.90 ** i
        if surface and row.get('surface') == surface.lower():
            w *= 1.55
        elif surface:
            w *= 0.72
        weights.append(w)

    cols = [
        'won', 'hold_rate', 'break_rate', 'serve_points_won', 'return_points_won',
        'first_serve_won', 'second_serve_won', 'first_set_won', 'second_set_won',
        'second_after_first_win', 'second_after_first_loss', 'third_set_won', 'first_set_games',
        'first_set_over85', 'first_set_over95', 'first_set_over105', 'first_set_over115', 'first_set_over125',
    ]
    effective_n = sum(weights) / max(weights) if weights and max(weights) > 0 else 0.0
    metrics = {}
    shrink_cols = {
        'won', 'hold_rate', 'break_rate', 'serve_points_won', 'return_points_won',
        'first_set_won', 'second_set_won', 'second_after_first_win', 'second_after_first_loss', 'third_set_won',
        'first_set_over85', 'first_set_over95', 'first_set_over105', 'first_set_over115', 'first_set_over125',
    }
    for col in cols:
        raw = _weighted_mean(x[col].tolist(), weights) if col in x.columns else None
        if col in shrink_cols:
            metrics[col] = _shrink(raw, priors.get(col), effective_n, 3.0)
        else:
            metrics[col] = raw

    stat_cols = ['hold_rate', 'break_rate', 'serve_points_won', 'return_points_won', 'first_set_won']
    coverage = sum(x[c].notna().mean() for c in stat_cols if c in x.columns) / len(stat_cols)
    n = len(x)
    surface_matches = int((x['surface'] == surface.lower()).sum()) if surface and 'surface' in x.columns else n

    recent = x[x['date'].notna()].copy() if 'date' in x.columns else pd.DataFrame()
    days_since_last = None
    matches_7d = 0
    sets_7d = 0.0
    if not recent.empty:
        recent['days_ago'] = (cut - recent['date'].dt.normalize()).dt.days
        past = recent[recent['days_ago'] >= 0]
        if not past.empty:
            days_since_last = int(past['days_ago'].min())
            r7 = past[past['days_ago'] <= 7]
            matches_7d = int(len(r7))
            if 'sets_played' in r7.columns:
                sets_7d = float(pd.to_numeric(r7['sets_played'], errors='coerce').fillna(0).sum())

    latest_rank = None
    if 'rank' in x.columns:
        ranks = pd.to_numeric(x['rank'], errors='coerce').dropna()
        if not ranks.empty and ranks.iloc[0] > 0:
            latest_rank = int(round(float(ranks.iloc[0])))

    fatigue = 0.0
    if days_since_last is not None and days_since_last <= 1:
        fatigue += 0.04
    fatigue += 0.025 * max(0, matches_7d - 2)
    fatigue += 0.008 * max(0.0, sets_7d - 6.0)
    fatigue = _clamp(fatigue, 0.0, 0.18)

    quality = 'HIGH' if n >= 10 and coverage >= 0.82 else ('MEDIUM' if n >= 5 and coverage >= 0.62 else 'LOW')
    confidence = round(100 * _clamp(
        0.42 * min(1.0, n / 10.0) +
        0.28 * min(1.0, surface_matches / 5.0) +
        0.30 * coverage
    ), 0)

    return {
        'player': player, 'matches': n, 'surface_matches': surface_matches, 'quality': quality,
        'coverage': round(float(coverage), 3), 'effective_n': round(float(effective_n), 2),
        'rank': latest_rank, 'days_since_last': days_since_last, 'matches_7d': matches_7d,
        'sets_7d': round(sets_7d, 1), 'fatigue_load': round(fatigue, 3), 'data_confidence': confidence,
        **metrics,
    }


def _hold_from_point_probability(p: float) -> float:
    """Prawdopodobieństwo utrzymania gema z prawdopodobieństwa wygrania punktu przy serwisie."""
    p = _clamp(float(p), 0.35, 0.85)
    q = 1.0 - p
    win_before_deuce = p**4 * (1 + 4*q + 10*q*q)
    reach_deuce = 20 * p**3 * q**3
    win_from_deuce = p*p / (p*p + q*q)
    return _clamp(win_before_deuce + reach_deuce * win_from_deuce, 0.30, 0.98)


def _service_hold_probability(server: dict, receiver: dict, prior_hold=.72):
    parts = []
    spw = server.get('serve_points_won')
    rpw = receiver.get('return_points_won')
    if spw is not None or rpw is not None:
        point_parts = []
        if spw is not None:
            point_parts.append((float(spw), .58))
        if rpw is not None:
            point_parts.append((1.0 - float(rpw), .42))
        den = sum(w for _, w in point_parts)
        p_point = sum(v*w for v, w in point_parts) / den
        parts.append((_hold_from_point_probability(p_point), .50))
    if server.get('hold_rate') is not None:
        parts.append((float(server['hold_rate']), .30))
    if receiver.get('break_rate') is not None:
        parts.append((1.0 - float(receiver['break_rate']), .20))
    if not parts:
        return None
    den = sum(w for _, w in parts)
    model = sum(v*w for v, w in parts) / den
    # Lekki prior chroni przed skrajnymi wartościami przy małych próbkach.
    model = .90 * model + .10 * float(prior_hold)
    return _clamp(model, 0.42, 0.95)


def _states_one_order(h1: float, h2: float, games: int, p1_serves_first: bool):
    states = {(0, 0): 1.0}
    for g in range(games):
        p1_serves = p1_serves_first if g % 2 == 0 else not p1_serves_first
        p1_game = h1 if p1_serves else 1.0 - h2
        nxt = {}
        for (a, b), prob in states.items():
            nxt[(a + 1, b)] = nxt.get((a + 1, b), 0.0) + prob * p1_game
            nxt[(a, b + 1)] = nxt.get((a, b + 1), 0.0) + prob * (1.0 - p1_game)
        states = nxt
    return states


def _state_probs(h1: float, h2: float, games: int):
    a = _states_one_order(h1, h2, games, True)
    b = _states_one_order(h1, h2, games, False)
    keys = set(a) | set(b)
    return {f'{x}:{y}': round(100.0 * (a.get((x, y), 0.0) + b.get((x, y), 0.0)) / 2.0, 1)
            for x, y in sorted(keys, key=lambda z: (-z[0], z[1]))}


def _set_distribution_one_order(h1: float, h2: float, tb_p1: float, p1_serves_first: bool):
    live = {(0, 0): 1.0}
    terminal = {}
    while live:
        nxt = {}
        for (a, b), prob in live.items():
            if a == 6 and b == 6:
                terminal[(7, 6)] = terminal.get((7, 6), 0.0) + prob * tb_p1
                terminal[(6, 7)] = terminal.get((6, 7), 0.0) + prob * (1.0 - tb_p1)
                continue
            if (a >= 6 or b >= 6) and abs(a - b) >= 2:
                terminal[(a, b)] = terminal.get((a, b), 0.0) + prob
                continue
            g = a + b
            p1_serves = p1_serves_first if g % 2 == 0 else not p1_serves_first
            p1_game = h1 if p1_serves else 1.0 - h2
            nxt[(a + 1, b)] = nxt.get((a + 1, b), 0.0) + prob * p1_game
            nxt[(a, b + 1)] = nxt.get((a, b + 1), 0.0) + prob * (1.0 - p1_game)
        live = nxt
    return terminal


def _set_distribution(h1: float, h2: float):
    p1_game_strength = (h1 + (1.0 - h2)) / 2.0
    tb_p1 = _clamp(_sigmoid((p1_game_strength - 0.5) * 8.0), 0.20, 0.80)
    a = _set_distribution_one_order(h1, h2, tb_p1, True)
    b = _set_distribution_one_order(h1, h2, tb_p1, False)
    keys = set(a) | set(b)
    return {k: (a.get(k, 0.0) + b.get(k, 0.0)) / 2.0 for k in keys}


def _p1_win(dist):
    return sum(prob for (a, b), prob in dist.items() if a > b)


def _reweight_set_distribution(dist: dict, target_p1: float):
    raw = _p1_win(dist)
    target = _clamp(float(target_p1), .03, .97)
    if raw <= 0 or raw >= 1:
        return dist.copy()
    out = {}
    for score, prob in dist.items():
        a, b = score
        if a > b:
            out[score] = prob * target / raw
        else:
            out[score] = prob * (1 - target) / (1 - raw)
    z = sum(out.values())
    return {k: v / z for k, v in out.items()} if z else dist.copy()


def _pairwise_rate(a, b, fallback=.5):
    if a is None or b is None:
        return float(fallback)
    return _sigmoid(_logit(_clamp(float(a), .08, .92)) - _logit(_clamp(float(b), .08, .92)))


def _historical_set_probability(p1: dict, p2: dict, set_no=1):
    metric = 'first_set_won' if set_no == 1 else 'second_set_won'
    a = p1.get(metric)
    b = p2.get(metric)
    hist = _pairwise_rate(a, b, .5)
    win = _pairwise_rate(p1.get('won'), p2.get('won'), .5)
    serve1 = None
    serve2 = None
    if p1.get('serve_points_won') is not None and p1.get('return_points_won') is not None:
        serve1 = (float(p1['serve_points_won']) + float(p1['return_points_won'])) / 2
    if p2.get('serve_points_won') is not None and p2.get('return_points_won') is not None:
        serve2 = (float(p2['serve_points_won']) + float(p2['return_points_won'])) / 2
    sr = _pairwise_rate(serve1, serve2, .5) if serve1 is not None and serve2 is not None else .5
    p = .55 * hist + .25 * win + .20 * sr

    r1, r2 = p1.get('rank'), p2.get('rank')
    if r1 and r2 and r1 > 0 and r2 > 0:
        rank_term = _clamp(_sigmoid(math.log((r2 + 30) / (r1 + 30)) * .75), .30, .70)
        p = .90 * p + .10 * rank_term

    fatigue_delta = float(p1.get('fatigue_load') or 0) - float(p2.get('fatigue_load') or 0)
    p = _sigmoid(_logit(_clamp(p, .08, .92)) - fatigue_delta * 1.3)
    return _clamp(p, .08, .92)


def _blend_set_target(raw_p: float, hist_p: float, confidence: float):
    # Historia/form/ranking ma być korektą, a nie kasować model serwisowy.
    w = .16 + .14 * _clamp(confidence / 100.0, 0, 1)
    return _clamp((1 - w) * raw_p + w * hist_p, .04, .96)


def _second_set_context(p1: dict, p2: dict, first_target: float, confidence: float):
    general = _historical_set_probability(p1, p2, 2)
    base = .62 * first_target + .38 * general
    ifwin = _pairwise_rate(p1.get('second_after_first_win'), p2.get('second_after_first_loss'), base)
    ifloss = _pairwise_rate(p1.get('second_after_first_loss'), p2.get('second_after_first_win'), base)
    w = .22 + .18 * _clamp(confidence / 100.0, 0, 1)
    q_win = _clamp((1 - w) * base + w * ifwin, .06, .94)
    q_loss = _clamp((1 - w) * base + w * ifloss, .06, .94)
    unconditional = first_target * q_win + (1 - first_target) * q_loss
    return q_win, q_loss, _clamp(unconditional, .06, .94)


def _third_set_target(p1: dict, p2: dict, fallback: float, confidence: float):
    hist = _pairwise_rate(p1.get('third_set_won'), p2.get('third_set_won'), fallback)
    w = .15 + .15 * _clamp(confidence / 100.0, 0, 1)
    return _clamp((1 - w) * fallback + w * hist, .07, .93)


def _markets_from_distribution(dist: dict, p1: str, p2: str):
    p1win = _p1_win(dist)
    over_under = {}
    for line in (8.5, 9.5, 10.5, 11.5, 12.5):
        over = sum(prob for (a, b), prob in dist.items() if (a + b) > line)
        over_under[f'{line:.1f}'] = {'over': round(over * 100, 1), 'under': round((1.0 - over) * 100, 1)}
    exact = {f'{a}:{b}': round(prob * 100, 1) for (a, b), prob in sorted(dist.items(), key=lambda kv: kv[1], reverse=True)}
    return {
        'first_set_win': {p1: round(p1win * 100, 1), p2: round((1 - p1win) * 100, 1)},
        'over_under': over_under,
        'exact_first_set': exact,
    }


def _match_distribution_bo3_conditional(base_dist: dict, first_target: float, second_if_win: float,
                                        second_if_loss: float, third_target: float):
    first_dist = _reweight_set_distribution(base_dist, first_target)
    second_win_dist = _reweight_set_distribution(base_dist, second_if_win)
    second_loss_dist = _reweight_set_distribution(base_dist, second_if_loss)
    third_dist = _reweight_set_distribution(base_dist, third_target)

    total_games = {}
    exact = {'2:0': 0.0, '2:1': 0.0, '1:2': 0.0, '0:2': 0.0}

    for (a1, b1), pset1 in first_dist.items():
        p1won1 = a1 > b1
        second_dist = second_win_dist if p1won1 else second_loss_dist
        for (a2, b2), pset2 in second_dist.items():
            p1won2 = a2 > b2
            g12 = a1 + b1 + a2 + b2
            p12 = pset1 * pset2
            if p1won1 and p1won2:
                total_games[g12] = total_games.get(g12, 0.0) + p12
                exact['2:0'] += p12
                continue
            if (not p1won1) and (not p1won2):
                total_games[g12] = total_games.get(g12, 0.0) + p12
                exact['0:2'] += p12
                continue
            for (a3, b3), pset3 in third_dist.items():
                g = g12 + a3 + b3
                pr = p12 * pset3
                total_games[g] = total_games.get(g, 0.0) + pr
                if a3 > b3:
                    exact['2:1'] += pr
                else:
                    exact['1:2'] += pr

    z = sum(exact.values()) or 1.0
    exact = {k: v / z for k, v in exact.items()}
    winner = {1: exact['2:0'] + exact['2:1'], 2: exact['0:2'] + exact['1:2']}
    total_sets = {'2 sety': exact['2:0'] + exact['0:2'], '3 sety': exact['2:1'] + exact['1:2']}
    return total_games, winner, total_sets, exact


def _total_games_markets(total_dist: dict, lines=(18.5, 19.5, 20.5, 21.5, 22.5, 23.5, 24.5, 25.5, 26.5)):
    if not total_dist:
        return None
    z = sum(total_dist.values())
    if z <= 0:
        return None
    out = {}
    for line in lines:
        over = sum(p for games, p in total_dist.items() if games > line) / z
        out[f'{line:.1f}'] = {'over': round(over * 100, 1), 'under': round((1.0 - over) * 100, 1)}
    expected = sum(games * p for games, p in total_dist.items()) / z
    return {'lines': out, 'expected': round(expected, 1)}


def analyse_match(long_df: pd.DataFrame, match: dict) -> dict:
    surface = (match.get('surface') or '').lower()
    as_of = match.get('scheduled_time') or None
    cut = _fixture_date(as_of)
    priors = _surface_priors(long_df, surface, cut)
    p1 = player_profile(long_df, match['p1'], surface, cut, priors)
    p2 = player_profile(long_df, match['p2'], surface, cut, priors)

    h1 = _service_hold_probability(p1, p2, priors.get('hold_rate', .72))
    h2 = _service_hold_probability(p2, p1, priors.get('hold_rate', .72))
    model_ready = (
        p1['matches'] >= 5 and p2['matches'] >= 5 and
        p1['quality'] != 'LOW' and p2['quality'] != 'LOW' and
        h1 is not None and h2 is not None
    )

    game_states = first_set_win = second_set_win = third_set_win = None
    over_under = exact_first_set = match_over_under = None
    expected_match_games = match_win = total_sets = exact_match_score = None
    second_set_context = None
    pick = first_score = over85 = None
    model_confidence = round(min(float(p1.get('data_confidence') or 0), float(p2.get('data_confidence') or 0)), 0)

    if model_ready:
        game_states = {str(n): _state_probs(h1, h2, n) for n in (1, 2, 4, 6)}
        raw_dist = _set_distribution(h1, h2)
        raw_first = _p1_win(raw_dist)
        hist_first = _historical_set_probability(p1, p2, 1)
        first_target = _blend_set_target(raw_first, hist_first, model_confidence)
        first_dist = _reweight_set_distribution(raw_dist, first_target)

        markets = _markets_from_distribution(first_dist, match['p1'], match['p2'])
        first_set_win = markets['first_set_win']
        over_under = markets['over_under']
        exact_first_set = markets['exact_first_set']

        q_win, q_loss, q2 = _second_set_context(p1, p2, first_target, model_confidence)
        q3 = _third_set_target(p1, p2, first_target, model_confidence)
        second_set_context = {'p1_if_p1_wins_set1': round(q_win*100,1), 'p1_if_p1_loses_set1': round(q_loss*100,1), 'p1_unconditional': round(q2*100,1)}
        second_set_win = {match['p1']: round(q2 * 100, 1), match['p2']: round((1 - q2) * 100, 1)}
        third_set_win = {match['p1']: round(q3 * 100, 1), match['p2']: round((1 - q3) * 100, 1)}

        total_dist, match_winner_raw, total_sets_raw, exact_raw = _match_distribution_bo3_conditional(
            raw_dist, first_target, q_win, q_loss, q3
        )
        total_markets = _total_games_markets(total_dist)
        if total_markets:
            match_over_under = total_markets['lines']
            expected_match_games = total_markets['expected']
        match_win = {match['p1']: round(match_winner_raw[1] * 100, 1), match['p2']: round(match_winner_raw[2] * 100, 1)}
        total_sets = {k: round(v * 100, 1) for k, v in total_sets_raw.items()}
        exact_match_score = {k: round(v * 100, 1) for k, v in exact_raw.items()}

        pick = max(first_set_win, key=first_set_win.get)
        first_score = first_set_win[pick]
        over85 = over_under['8.5']['over']

    quality = 'HIGH' if p1['quality'] == 'HIGH' and p2['quality'] == 'HIGH' else (
        'MEDIUM' if p1['quality'] != 'LOW' and p2['quality'] != 'LOW' else 'LOW'
    )

    return {
        **match,
        'pick_first_set': pick,
        'score_first_set': first_score,
        'score_over85': over85,
        'score_lead_after6': None,
        'score_joint_builder': None,
        'quality': quality,
        'model_confidence': model_confidence if model_ready else None,
        'p1_stats': p1,
        'p2_stats': p2,
        'model_ready': model_ready,
        'service_model': {'p1_hold': round(h1 * 100, 1), 'p2_hold': round(h2 * 100, 1)} if model_ready else None,
        'game_states': game_states,
        'first_set_win': first_set_win,
        'second_set_win': second_set_win,
        'second_set_context': second_set_context,
        'third_set_win': third_set_win,
        'over_under': over_under,
        'exact_first_set': exact_first_set,
        'match_over_under': match_over_under,
        'expected_match_games': expected_match_games,
        'match_win': match_win,
        'total_sets': total_sets,
        'exact_match_score': exact_match_score,
        'note': (
            'v0.5: recency + nawierzchnia + wygładzanie małej próbki + model punkt→hold + forma/ranking + zmęczenie + kontekst 2./3. seta. '
            'Po gemach nadal jest estymacją bez historycznego point-by-point; pełny mecz liczony jako BO3.'
        ) if model_ready else None,
    }
