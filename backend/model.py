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
        return _core._fixture_date(as_of)
    cut = _core.pd.to_datetime(as_of, errors="coerce", utc=True)
    if _core.pd.isna(cut):
        return _core._fixture_date(as_of)
    return _core.pd.Timestamp(cut.date())


def player_profile(long_df, player: str, surface: str = '', as_of=None, priors=None):
    history_df = _dated_history(long_df)
    cut = _naive_cutoff(as_of)
    safe_priors = priors if priors is not None else _core._surface_priors(history_df, surface, cut)
    return _core.player_profile(history_df, player, surface, cut, safe_priors)


def _match_distribution_conditional(
    base_dist: dict,
    first_target: float,
    second_if_win: float,
    second_if_loss: float,
    later_target: float,
    *,
    best_of: int = 3,
):
    best_of = best_of if best_of in {3, 5} else 3
    required = best_of // 2 + 1

    first_dist = _core._reweight_set_distribution(base_dist, first_target)
    second_win_dist = _core._reweight_set_distribution(base_dist, second_if_win)
    second_loss_dist = _core._reweight_set_distribution(base_dist, second_if_loss)
    later_dist = _core._reweight_set_distribution(base_dist, later_target)

    total_games: dict[int, float] = {}
    exact: dict[str, float] = {}
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
                w1 + (1 if p1_won else 0),
                w2 + (0 if p1_won else 1),
                games + int(a) + int(b),
                next_first,
                path_prob * set_prob,
            ))

    z = sum(exact.values()) or 1.0
    exact = {k: v / z for k, v in exact.items()}
    games_z = sum(total_games.values()) or 1.0
    total_games = {k: v / games_z for k, v in total_games.items()}

    p1_win = sum(v for k, v in exact.items() if int(k.split(":")[0]) == required)
    p2_win = sum(v for k, v in exact.items() if int(k.split(":")[1]) == required)
    winner = {1: p1_win, 2: p2_win}

    total_sets: dict[str, float] = {}
    for score, prob in exact.items():
        a, b = (int(x) for x in score.split(":"))
        n = a + b
        total_sets[f"{n} sety"] = total_sets.get(f"{n} sety", 0.0) + prob
    return total_games, winner, total_sets, exact


def _match_distribution_bo3_conditional(
    base_dist: dict,
    first_target: float,
    second_if_win: float,
    second_if_loss: float,
    third_target: float,
):
    return _match_distribution_conditional(
        base_dist,
        first_target,
        second_if_win,
        second_if_loss,
        third_target,
        best_of=3,
    )


def analyse_match(long_df, match: dict) -> dict:
    history_df = _dated_history(long_df)
    surface = (match.get('surface') or '').lower()
    as_of = match.get('scheduled_time') or None
    cut = _naive_cutoff(as_of)
    priors = _core._surface_priors(history_df, surface, cut)
    p1 = _core.player_profile(history_df, match['p1'], surface, cut, priors)
    p2 = _core.player_profile(history_df, match['p2'], surface, cut, priors)

    h1 = _core._service_hold_probability(p1, p2, priors.get('hold_rate', .72))
    h2 = _core._service_hold_probability(p2, p1, priors.get('hold_rate', .72))
    model_ready = (
        p1['matches'] >= 5 and p2['matches'] >= 5 and
        p1['quality'] != 'LOW' and p2['quality'] != 'LOW' and
        h1 is not None and h2 is not None
    )

    best_of = _best_of(match)
    game_states = first_set_win = second_set_win = third_set_win = None
    over_under = exact_first_set = match_over_under = None
    expected_match_games = match_win = total_sets = exact_match_score = None
    second_set_context = None
    pick = first_score = over85 = None
    model_confidence = round(min(float(p1.get('data_confidence') or 0), float(p2.get('data_confidence') or 0)), 0)

    if model_ready:
        game_states = {str(n): _core._state_probs(h1, h2, n) for n in (1, 2, 4, 6)}
        raw_dist = _core._set_distribution(h1, h2)
        raw_first = _core._p1_win(raw_dist)
        hist_first = _core._historical_set_probability(p1, p2, 1)
        first_target = _core._blend_set_target(raw_first, hist_first, model_confidence)
        first_dist = _core._reweight_set_distribution(raw_dist, first_target)

        markets = _core._markets_from_distribution(first_dist, match['p1'], match['p2'])
        first_set_win = markets['first_set_win']
        over_under = markets['over_under']
        exact_first_set = markets['exact_first_set']

        q_win, q_loss, q2 = _core._second_set_context(p1, p2, first_target, model_confidence)
        q3 = _core._third_set_target(p1, p2, first_target, model_confidence)
        second_set_context = {
            'p1_if_p1_wins_set1': round(q_win * 100, 1),
            'p1_if_p1_loses_set1': round(q_loss * 100, 1),
            'p1_unconditional': round(q2 * 100, 1),
        }
        second_set_win = {match['p1']: round(q2 * 100, 1), match['p2']: round((1 - q2) * 100, 1)}
        third_set_win = {match['p1']: round(q3 * 100, 1), match['p2']: round((1 - q3) * 100, 1)}

        total_dist, match_winner_raw, total_sets_raw, exact_raw = _match_distribution_conditional(
            raw_dist, first_target, q_win, q_loss, q3, best_of=best_of
        )
        total_lines = (
            (18.5, 19.5, 20.5, 21.5, 22.5, 23.5, 24.5, 25.5, 26.5)
            if best_of == 3
            else tuple(x + 0.5 for x in range(27, 51))
        )
        total_markets = _core._total_games_markets(total_dist, total_lines)
        if total_markets:
            match_over_under = total_markets['lines']
            expected_match_games = total_markets['expected']
        match_win = {
            match['p1']: round(match_winner_raw[1] * 100, 1),
            match['p2']: round(match_winner_raw[2] * 100, 1),
        }
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
        'best_of': best_of,
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
            'v0.6: recency + nawierzchnia + wygładzanie małej próbki + model punkt→hold + forma/ranking + zmęczenie + kontekst 2./3. seta. '
            f'Po gemach nadal jest estymacją bez historycznego point-by-point; pełny mecz liczony jako BO{best_of} z metadanych fixture.'
        ) if model_ready else None,
    }
