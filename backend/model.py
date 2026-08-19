from __future__ import annotations
import math
import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import Optional
import pandas as pd

SET_RE = re.compile(r"(\d+)\s*[-:]\s*(\d+)")

def _key(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii','ignore').decode().casefold()
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())


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
        for side in ('w','l'):
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
            over85 = None
            if a is not None and b is not None:
                over85 = 1.0 if (a+b) >= 9 else 0.0
                if side == 'w': first_set_won = 1.0 if a > b else 0.0
                else: first_set_won = 1.0 if b > a else 0.0
            out.append({
                'date': date, 'surface': surface, 'player': name.strip(), 'opponent': str(opp_name or '').strip(),
                'won': 1.0 if side == 'w' else 0.0,
                'hold_rate': 1 - _safe_div(breaks_conceded, sv_gms) if not pd.isna(breaks_conceded) else float('nan'),
                'break_rate': _safe_div(breaks_made, opp_sv_gms) if not pd.isna(breaks_made) else float('nan'),
                'serve_points_won': _safe_div(first_won + second_won, svpt) if not pd.isna(first_won) and not pd.isna(second_won) else float('nan'),
                'first_serve_won': _safe_div(first_won, first_in),
                'second_serve_won': _safe_div(second_won, second_total),
                'first_set_won': first_set_won, 'first_set_over85': over85,
            })
    return pd.DataFrame(out)


def _weighted_mean(values, weights):
    s = [(float(v), float(w)) for v,w in zip(values,weights) if not pd.isna(v) and w > 0]
    if not s: return None
    den = sum(w for _,w in s)
    return sum(v*w for v,w in s)/den if den else None


def player_profile(long_df: pd.DataFrame, player: str, surface: str='') -> dict:
    if long_df.empty:
        return {'player': player, 'matches': 0, 'quality': 'LOW'}
    x = long_df[long_df['player'].map(_key) == _key(player)].copy()
    x = x.sort_values('date', ascending=False).head(10)
    if x.empty:
        return {'player': player, 'matches': 0, 'quality': 'LOW'}
    weights=[]
    for i, row in x.reset_index(drop=True).iterrows():
        w = 1.0 if i < 5 else 0.5
        if surface and row.get('surface') == surface.lower(): w *= 1.25
        elif surface: w *= 0.85
        weights.append(w)
    metrics={}
    for col in ['won','hold_rate','break_rate','serve_points_won','first_serve_won','second_serve_won','first_set_won','first_set_over85']:
        metrics[col] = _weighted_mean(x[col].tolist(), weights)
    stat_cols=['hold_rate','break_rate','serve_points_won','first_set_won','first_set_over85']
    coverage=sum(x[c].notna().mean() for c in stat_cols)/len(stat_cols)
    n=len(x)
    quality='HIGH' if n>=8 and coverage>=0.8 else ('MEDIUM' if n>=5 and coverage>=0.6 else 'LOW')
    return {'player':player,'matches':n,'quality':quality, **metrics}


def _clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def _sigmoid(x): return 1/(1+math.exp(-x))

def _strength(p):
    vals=[p.get('first_set_won'),p.get('won'),p.get('hold_rate'),p.get('break_rate'),p.get('serve_points_won')]
    if any(v is None for v in vals): return None
    fsw, win, hold, brk, spw = vals
    return .32*fsw + .20*win + .23*hold + .12*brk + .13*spw


def analyse_match(long_df: pd.DataFrame, match: dict) -> dict:
    surface=(match.get('surface') or '').lower()
    p1=player_profile(long_df, match['p1'], surface)
    p2=player_profile(long_df, match['p2'], surface)
    s1,s2=_strength(p1),_strength(p2)
    enough = p1['matches']>=5 and p2['matches']>=5 and s1 is not None and s2 is not None
    first_score=over_score=None
    pick=None
    if enough:
        p1_index=_sigmoid((s1-s2)*7.0)
        first_score=round(100*p1_index,1)
        pick=match['p1'] if first_score>=50 else match['p2']
        pick_score=first_score if first_score>=50 else round(100-first_score,1)
        o1=p1.get('first_set_over85'); o2=p2.get('first_set_over85')
        if o1 is not None and o2 is not None:
            closeness=1-abs(p1_index-.5)*2
            hold_avg=((p1.get('hold_rate') or .5)+(p2.get('hold_rate') or .5))/2
            over_score=round(100*_clamp(.55*((o1+o2)/2)+.25*hold_avg+.20*closeness),1)
        first_score=pick_score
    quality = 'HIGH' if p1['quality']=='HIGH' and p2['quality']=='HIGH' else ('MEDIUM' if p1['quality']!='LOW' and p2['quality']!='LOW' else 'LOW')
    return {
        **match,
        'pick_first_set': pick,
        'score_first_set': first_score,
        'score_over85': over_score,
        # Darmowe historyczne CSV nie zawiera kolejności gemów: nie udajemy, że znamy ten rynek.
        'score_lead_after6': None,
        'score_joint_builder': None,
        'quality': quality,
        'p1_stats': p1,
        'p2_stats': p2,
        'note': 'Prowadzenie po 6 gemach = N/D bez wiarygodnego game-by-game.'
    }
