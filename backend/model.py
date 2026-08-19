from __future__ import annotations
import math
import re
import unicodedata
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


def parse_first_set(score) -> tuple[Optional[int], Optional[int]]:
    if not isinstance(score, str):
        return None, None
    m = SET_RE.search(score)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def normalize_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Convert winner/loser rows into one row per player-match."""
    out = []
    if df is None or df.empty:
        return pd.DataFrame()
    for _, r in df.iterrows():
        a, b = parse_first_set(r.get('score'))
        date = pd.to_datetime(str(r.get('tourney_date', '')), format='%Y%m%d', errors='coerce')
        surface = str(r.get('surface') or '').strip().lower()
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
            opp_sv_gms = _num(r.get(f'{opp}_SvGms'))
            opp_bp_saved = _num(r.get(f'{opp}_bpSaved'))
            opp_bp_faced = _num(r.get(f'{opp}_bpFaced'))

            breaks_conceded = bp_faced - bp_saved if not pd.isna(bp_faced) and not pd.isna(bp_saved) else float('nan')
            breaks_made = opp_bp_faced - opp_bp_saved if not pd.isna(opp_bp_faced) and not pd.isna(opp_bp_saved) else float('nan')
            second_total = svpt - first_in if not pd.isna(svpt) and not pd.isna(first_in) else float('nan')

            first_set_won = None
            if a is not None and b is not None:
                if side == 'w':
                    first_set_won = 1.0 if a > b else 0.0
                else:
                    first_set_won = 1.0 if b > a else 0.0

            row = {
                'date': date,
                'surface': surface,
                'player': name.strip(),
                'opponent': str(opp_name or '').strip(),
                'won': 1.0 if side == 'w' else 0.0,
                'hold_rate': 1 - _safe_div(breaks_conceded, sv_gms) if not pd.isna(breaks_conceded) else float('nan'),
                'break_rate': _safe_div(breaks_made, opp_sv_gms) if not pd.isna(breaks_made) else float('nan'),
                'serve_points_won': _safe_div(first_won + second_won, svpt) if not pd.isna(first_won) and not pd.isna(second_won) else float('nan'),
                'first_serve_won': _safe_div(first_won, first_in),
                'second_serve_won': _safe_div(second_won, second_total),
                'first_set_won': first_set_won,
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


def player_profile(long_df: pd.DataFrame, player: str, surface: str = '') -> dict:
    if long_df.empty:
        return {'player': player, 'matches': 0, 'quality': 'LOW'}
    x = long_df[long_df['player'].map(_key) == _key(player)].copy()
    x = x.sort_values('date', ascending=False).head(10)
    if x.empty:
        return {'player': player, 'matches': 0, 'quality': 'LOW'}

    weights = []
    for i, row in x.reset_index(drop=True).iterrows():
        w = 1.0 if i < 5 else 0.5
        if surface and row.get('surface') == surface.lower():
            w *= 1.25
        elif surface:
            w *= 0.85
        weights.append(w)

    cols = [
        'won', 'hold_rate', 'break_rate', 'serve_points_won', 'first_serve_won', 'second_serve_won',
        'first_set_won', 'first_set_games',
        'first_set_over85', 'first_set_over95', 'first_set_over105', 'first_set_over115', 'first_set_over125',
    ]
    metrics = {col: _weighted_mean(x[col].tolist(), weights) if col in x.columns else None for col in cols}
    stat_cols = ['hold_rate', 'break_rate', 'serve_points_won', 'first_set_won', 'first_set_over85']
    coverage = sum(x[c].notna().mean() for c in stat_cols if c in x.columns) / len(stat_cols)
    n = len(x)
    quality = 'HIGH' if n >= 8 and coverage >= 0.8 else ('MEDIUM' if n >= 5 and coverage >= 0.6 else 'LOW')
    return {'player': player, 'matches': n, 'quality': quality, **metrics}


def _strength(p):
    vals = [p.get('first_set_won'), p.get('won'), p.get('hold_rate'), p.get('break_rate'), p.get('serve_points_won')]
    if any(v is None for v in vals):
        return None
    fsw, win, hold, brk, spw = vals
    return .32 * fsw + .20 * win + .23 * hold + .12 * brk + .13 * spw


def _service_hold_probability(server: dict, receiver: dict):
    hold = server.get('hold_rate')
    opp_break = receiver.get('break_rate')
    parts = []
    if hold is not None:
        parts.append((float(hold), 0.60))
    if opp_break is not None:
        parts.append((1.0 - float(opp_break), 0.40))
    if not parts:
        return None
    den = sum(w for _, w in parts)
    return _clamp(sum(v * w for v, w in parts) / den, 0.35, 0.95)


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
    # Brak informacji, kto serwuje pierwszy przed meczem: uśredniamy oba warianty.
    p1_game_strength = (h1 + (1.0 - h2)) / 2.0
    tb_p1 = _clamp(_sigmoid((p1_game_strength - 0.5) * 8.0), 0.20, 0.80)
    a = _set_distribution_one_order(h1, h2, tb_p1, True)
    b = _set_distribution_one_order(h1, h2, tb_p1, False)
    keys = set(a) | set(b)
    return {k: (a.get(k, 0.0) + b.get(k, 0.0)) / 2.0 for k in keys}


def _markets_from_distribution(dist: dict, p1: str, p2: str):
    p1win = sum(prob for (a, b), prob in dist.items() if a > b)
    p2win = 1.0 - p1win
    over_under = {}
    for line in (8.5, 9.5, 10.5, 11.5, 12.5):
        over = sum(prob for (a, b), prob in dist.items() if (a + b) > line)
        over_under[f'{line:.1f}'] = {'over': round(over * 100, 1), 'under': round((1.0 - over) * 100, 1)}
    exact = {f'{a}:{b}': round(prob * 100, 1) for (a, b), prob in sorted(dist.items(), key=lambda kv: kv[1], reverse=True)}
    return {
        'first_set_win': {p1: round(p1win * 100, 1), p2: round(p2win * 100, 1)},
        'over_under': over_under,
        'exact_first_set': exact,
    }



def _match_distribution_bo3(set_dist: dict):
    """Model pełnego meczu best-of-3 z rozkładu wyniku pojedynczego seta."""
    live = {(0, 0, 0): 1.0}  # sety p1, sety p2, suma gemów
    total_games = {}
    winner = {1: 0.0, 2: 0.0}
    while live:
        nxt = {}
        for (s1, s2, games), prob0 in live.items():
            if s1 >= 2 or s2 >= 2:
                total_games[games] = total_games.get(games, 0.0) + prob0
                winner[1 if s1 > s2 else 2] += prob0
                continue
            for (a, b), pset in set_dist.items():
                if pset <= 0:
                    continue
                ns1 = s1 + (1 if a > b else 0)
                ns2 = s2 + (1 if b > a else 0)
                ng = games + a + b
                pr = prob0 * pset
                if ns1 >= 2 or ns2 >= 2:
                    total_games[ng] = total_games.get(ng, 0.0) + pr
                    winner[1 if ns1 > ns2 else 2] += pr
                else:
                    key = (ns1, ns2, ng)
                    nxt[key] = nxt.get(key, 0.0) + pr
        live = nxt
    return total_games, winner


def _total_games_markets(total_dist: dict, lines=(18.5, 19.5, 20.5, 21.5, 22.5, 23.5, 24.5, 25.5, 26.5)):
    if not total_dist:
        return None
    z = sum(total_dist.values())
    if z <= 0:
        return None
    out = {}
    for line in lines:
        over = sum(p for games, p in total_dist.items() if games > line) / z
        out[f'{line:.1f}'] = {
            'over': round(over * 100, 1),
            'under': round((1.0 - over) * 100, 1),
        }
    expected = sum(games * p for games, p in total_dist.items()) / z
    return {'lines': out, 'expected': round(expected, 1)}

def analyse_match(long_df: pd.DataFrame, match: dict) -> dict:
    surface = (match.get('surface') or '').lower()
    p1 = player_profile(long_df, match['p1'], surface)
    p2 = player_profile(long_df, match['p2'], surface)

    h1 = _service_hold_probability(p1, p2)
    h2 = _service_hold_probability(p2, p1)
    model_ready = (
        p1['matches'] >= 5 and p2['matches'] >= 5 and
        p1['quality'] != 'LOW' and p2['quality'] != 'LOW' and
        h1 is not None and h2 is not None
    )

    game_states = None
    first_set_win = None
    over_under = None
    exact_first_set = None
    match_over_under = None
    expected_match_games = None
    match_win = None
    pick = None
    first_score = None
    over85 = None

    if model_ready:
        game_states = {str(n): _state_probs(h1, h2, n) for n in (1, 2, 4, 6)}
        dist = _set_distribution(h1, h2)
        markets = _markets_from_distribution(dist, match['p1'], match['p2'])
        first_set_win = markets['first_set_win']
        over_under = markets['over_under']
        exact_first_set = markets['exact_first_set']
        total_dist, match_winner_raw = _match_distribution_bo3(dist)
        total_markets = _total_games_markets(total_dist)
        if total_markets:
            match_over_under = total_markets['lines']
            expected_match_games = total_markets['expected']
        match_win = {
            match['p1']: round(match_winner_raw[1] * 100, 1),
            match['p2']: round(match_winner_raw[2] * 100, 1),
        }
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
        # Zachowujemy kompatybilność: historycznego EHS po 6 nie udajemy.
        'score_lead_after6': None,
        'score_joint_builder': None,
        'quality': quality,
        'p1_stats': p1,
        'p2_stats': p2,
        'model_ready': model_ready,
        'service_model': {'p1_hold': round(h1 * 100, 1), 'p2_hold': round(h2 * 100, 1)} if model_ready else None,
        'game_states': game_states,
        'first_set_win': first_set_win,
        'over_under': over_under,
        'exact_first_set': exact_first_set,
        'match_over_under': match_over_under,
        'expected_match_games': expected_match_games,
        'match_win': match_win,
        'note': 'Rynki po gemach i linie meczu są estymacją modelu z hold/break; nie są historycznym game-by-game.' if model_ready else None,
    }
