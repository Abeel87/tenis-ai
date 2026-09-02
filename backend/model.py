from __future__ import annotations

"""Current Engine facade with best-of aware match distribution (v9.4.6).

The proven player/set model is preserved verbatim in ``model_core``. This
facade re-exports its public/private helpers and only replaces full-match
aggregation so BO5 fixtures are never evaluated as BO3.
No Superbet/PLAYABLE logic lives here.
"""

try:  # package import in tests
    from . import model_core as _core
except ImportError:  # top-level import used by backend/update.py
    import model_core as _core

# Preserve the complete existing module API, including private helpers used by
# tests and specialist code. The overrides below intentionally replace only the
# full-match distribution and analyse_match.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

VERSION = "current-engine-bestof-v9.4.6"


def _best_of(match: dict) -> int:
    value = match.get("best_of")
    if value is None:
        value = match.get("bestOf")
    try:
        best_of = int(value)
    except (TypeError, ValueError):
        best_of = 3
    return best_of if best_of in {3, 5} else 3


def _dated_history(long_df):
    """Fail closed for temporal features: undated rows are not pre-match history."""
    if long_df is None or getattr(long_df, "empty", False) or "date" not in long_df.columns:
        return long_df
    return long_df[long_df["date"].notna()].copy()


def _naive_cutoff(as_of):
    """Normalize fixture timestamps to the tz-naive date domain used by normalized history."""
    if as_of is None or as_of == "":
        return as_of
    cut = _core.pd.to_datetime(as_of, errors="coerce", utc=True)
    if _core.pd.isna(cut):
        return as_of
    return _core.pd.Timestamp(cut.date())


def player_profile(long_df, player: str, surface: str = '', as_of=None, priors=None):
    """Public Current Engine profile with the same fail-closed temporal guard as analyse_match."""
    history_df = _dated_history(long_df)
    cutoff = _naive_cutoff(as_of)
    safe_priors = priors if priors is not None else _core._surface_priors(history_df, surface, cutoff)
    return _core.player_profile(history_df, player, surface, cutoff, safe_priors)


def _match_distribution_conditional(
    base_dist: dict,
    first_target: float,
    second_if_win: float,
    second_if_loss: float,
    later_target: float,
    *,
    best_of: int = 3,
):
    """Aggregate set-score distributions for BO3 or BO5 without truncation.

    Set 1 keeps the calibrated first-set target. Set 2 keeps the existing
    conditional response to the first-set result. Set 3+ use the existing
    deciding/later-set target; we do not invent unsupported fourth/fifth-set
    features. The match stops immediately when either player reaches the
    required number of sets.
    """
    best_of = best_of if best_of in {3, 5} else 3
    required = best_of // 2 + 1

    first_dist = _core._reweight_set_distribution(base_dist, first_target)
    second_win_dist = _core._reweight_set_distribution(base_dist, second_if_win)
    second_loss_dist = _core._reweight_set_distribution(base_dist, second_if_loss)
    later_dist = _core._reweight_set_distribution(base_dist, later_target)

    total_games: dict[int, float] = {}
    exact: dict[str, float] = {}

    # state = (sets_played, p1_sets, p2_sets, games_so_far, p1_won_first)
    live = [(0, 0, 0, 0, None, 1.0)]
    while live:
        set_no, w1, w2, games, p1_won_first, path_prob = live.pop()
        if w1 >= required or w2 >= required:
            key = f"{w1}:{w2}"
            exact[key] = exact.get(key, 0.0) + path_prob
            total_games[games] = total_games.get(games, 0.0) + path_prob
            continue

        if set_no == 0:
            dist = first_dist
        elif set_no == 1:
            dist = second_win_dist if p1_won_first else second_loss_dist
        else:
            dist = later_dist

        for (a, b), set_prob in dist.items():
            if set_prob <= 0:
                continue
            p1_won = a > b
            next_first = p1_won if set_no == 0 else p1_won_first
            live.append((
                set_no + 1,
                w1 + int(p1_won),
                w2 + int(not p1_won),
                games + int(a) + int(b),
                next_first,
                path_prob * float(set_prob),
            ))

    mass = sum(exact.values())
    if mass > 0:
        exact = {k: v / mass for k, v in exact.items()}
        total_games = {k: v / mass for k, v in total_games.items()}

    winner = {"p1": 0.0, "p2": 0.0}
    total_sets: dict[int, float] = {}
    for score, prob in exact.items():
        a, b = (int(x) for x in score.split(":"))
        winner["p1" if a > b else "p2"] += prob
        total_sets[a + b] = total_sets.get(a + b, 0.0) + prob
    return total_games, winner, total_sets, exact


def analyse_match(long_df, match: dict) -> dict:
    history_df = _dated_history(long_df)
    p1, p2 = match['p1'], match['p2']
    surface = str(match.get('surface') or '').lower()
    as_of = match.get('scheduled_time') or match.get('date')
    priors = _core._surface_priors(history_df, surface, as_of)
    s1 = _core.player_profile(history_df, p1, surface, as_of, priors)
    s2 = _core.player_profile(history_df, p2, surface, as_of, priors)

    quality = 'HIGH' if s1.get('quality') == 'HIGH' and s2.get('quality') == 'HIGH' else 'MEDIUM' if s1.get('quality') != 'LOW' and s2.get('quality') != 'LOW' else 'LOW'
    note = None if quality == 'HIGH' else 'Część estymacji ma mniejszą próbę i używa shrinkage do średniej touru/nawierzchni.'

    p1_first = _core._logistic_probability(s1, s2, 'first_set_won', 1.9)
    p1_second_base = _core._logistic_probability(s1, s2, 'second_set_won', 1.7)
    p1_third = _core._logistic_probability(s1, s2, 'third_set_won', 1.6)
    p1_second_if_win = _core._conditional_second_probability(s1, s2, True, p1_second_base)
    p1_second_if_loss = _core._conditional_second_probability(s1, s2, False, p1_second_base)

    total_probs = _core._first_set_total_probabilities(s1, s2)
    avg_games = _core._clamp(_core._avg([s1.get('first_set_games'), s2.get('first_set_games')], 9.5), 6.0, 13.0)
    tie_prob = _core._clamp(0.03 + max(0.0, avg_games - 9.0) * 0.035 + max(0.0, total_probs.get(10.5, 0.0) - 0.25) * 0.12, 0.03, 0.24)
    base_dist = _core._set_score_distribution(p1_first, avg_games, tie_prob)
    total_games_dist, match_winner_dist, total_sets_dist, exact_match_dist = _match_distribution_conditional(
        base_dist, p1_first, p1_second_if_win, p1_second_if_loss, p1_third, best_of=_best_of(match)
    )

    best_of = _best_of(match)
    total_lines = _core.MATCH_TOTAL_LINES if best_of == 3 else [x + 0.5 for x in range(27, 51)]
    match_over_under = {}
    for line in total_lines:
        over = sum(prob for games, prob in total_games_dist.items() if games > line)
        match_over_under[str(line)] = {'over': _core._pct(over), 'under': _core._pct(1.0 - over)}

    exact_match_score = {score: _core._pct(prob) for score, prob in exact_match_dist.items()}
    match_win = {p1: _core._pct(match_winner_dist.get('p1', 0.0)), p2: _core._pct(match_winner_dist.get('p2', 0.0))}
    total_sets = {str(k): _core._pct(v) for k, v in sorted(total_sets_dist.items())}

    return {
        'version': VERSION,
        'p1': p1,
        'p2': p2,
        'surface': surface,
        'best_of': best_of,
        'quality': quality,
        'note': note,
        'p1_stats': s1,
        'p2_stats': s2,
        'first_set_win': {p1: _core._pct(p1_first), p2: _core._pct(1.0 - p1_first)},
        'match_win': match_win,
        'over_under': {str(line): {'over': _core._pct(prob), 'under': _core._pct(1.0 - prob)} for line, prob in total_probs.items()},
        'match_over_under': match_over_under,
        'exact_match_score': exact_match_score,
        'total_sets': total_sets,
        'game_states': _core._game_state_probabilities(p1_first, s1, s2),
        'first_set_exact_score': {f'{a}:{b}': _core._pct(prob) for (a, b), prob in base_dist.items()},
        'conditional_sets': {
            'p1_second_if_first_win': _core._pct(p1_second_if_win),
            'p1_second_if_first_loss': _core._pct(p1_second_if_loss),
            'p1_later_set': _core._pct(p1_third),
        },
    }
