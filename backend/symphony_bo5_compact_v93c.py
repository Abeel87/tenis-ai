from __future__ import annotations

"""Tenis AI v9.3C — compact exact BO5 state space for MODEL/RAW Symphony.

The BO3 deep lattice keeps game-by-game checkpoints. Repeating that full path
cartesian product for best-of-five can explode in memory, so BO5 is factorized
at set-score level instead:
- exact terminal scores for sets 1 and 2;
- exact final match score / set count / match games / game margin;
- set-1 and set-2 totals, winners, exact scores and parity;
- deterministic match-level v9.2.4 families (exact sets, set handicap,
  wins-a-set, set-to-nil, game parity).

Checkpoint markets and set-3-specific markets deliberately remain evidence-only
for BO5 in this compact step. No bookmaker prices or external requests are used.
"""

from collections import defaultdict

try:
    from . import symphony_engine_v90 as core
except ImportError:
    import symphony_engine_v90 as core

VERSION = "v9.3C"
SCOPE = "BO5_COMPACT_EXACT_SET1_SET2_MATCH"
BO5_EVIDENCE_ONLY_MARKETS = {
    "game_state",
    "set2_game_state",
    "set3_winner",
    "set3_total",
    "set3_game_handicap",
}


def _second_targets(match: dict, fallback: float | None):
    ctx = match.get("second_set_context") or {}
    win_target = core._market_player_prob(ctx, "p1_if_p1_wins_set1")
    loss_target = core._market_player_prob(ctx, "p1_if_p1_loses_set1")
    return (
        fallback if win_target is None else win_target,
        fallback if loss_target is None else loss_target,
    )


def _continuations(later: dict[int, dict[tuple[int, int], float]], sa: int, sb: int):
    """Exact later-set DP aggregated to only fields BO5 match predicates need."""
    need = 3
    frontier = {(sa, sb, 0, 0, False): 1.0}
    for set_no in (3, 4, 5):
        nxt: dict[tuple, float] = defaultdict(float)
        for (xa, xb, total_games, game_margin, any_nil), prob in frontier.items():
            if xa >= need or xb >= need:
                nxt[(xa, xb, total_games, game_margin, any_nil)] += prob
                continue
            for (ga, gb), set_prob in (later.get(set_no) or {}).items():
                nxt[(
                    xa + int(ga > gb),
                    xb + int(gb > ga),
                    total_games + int(ga) + int(gb),
                    game_margin + int(ga) - int(gb),
                    bool(any_nil or ga == 0 or gb == 0),
                )] += prob * set_prob
        frontier = nxt
        if frontier and all(xa >= need or xb >= need for xa, xb, *_ in frontier):
            break
    return frontier


def build_bo5_compact_outcomes(match: dict) -> list[dict]:
    if core._best_of(match) != 5:
        return []
    holds = core._service_holds(match)
    if not holds:
        return []
    h1, h2 = holds

    raw = core._terminal_set_distribution(h1, h2)
    first = core._reweight_winner(raw, core._set_target(match, 1), score_indexes=(0, 1))
    second_default = core._set_target(match, 2)
    if second_default is None:
        second_default = core._winner_marginal(first, score_indexes=(0, 1))
    target_if_win, target_if_loss = _second_targets(match, second_default)
    second_if_win = core._reweight_winner(raw, target_if_win, score_indexes=(0, 1))
    second_if_loss = core._reweight_winner(raw, target_if_loss, score_indexes=(0, 1))
    later = {
        n: core._reweight_winner(raw, core._set_target(match, n), score_indexes=(0, 1))
        for n in (3, 4, 5)
    }

    continuation_cache = {
        state: _continuations(later, *state)
        for state in ((2, 0), (1, 1), (0, 2))
    }
    agg: dict[tuple, float] = defaultdict(float)

    for (s1a, s1b), p1_score in first.items():
        first_win = int(s1a > s1b)
        second = second_if_win if first_win else second_if_loss
        for (s2a, s2b), p2_score in second.items():
            sa = first_win + int(s2a > s2b)
            sb = (1 - first_win) + int(s2b > s2a)
            initial_total = int(s1a + s1b + s2a + s2b)
            initial_margin = int((s1a - s1b) + (s2a - s2b))
            initial_nil = bool(0 in (s1a, s1b, s2a, s2b))
            base_prob = p1_score * p2_score

            for (fa, fb, add_total, add_margin, later_nil), cont_prob in continuation_cache[(sa, sb)].items():
                if fa < 3 and fb < 3:
                    continue
                total_games = initial_total + int(add_total)
                margin = initial_margin + int(add_margin)
                # total +/- margin are always even because they reconstruct the
                # two integer game totals exactly.
                p1_games = (total_games + margin) // 2
                p2_games = (total_games - margin) // 2
                key = (
                    int(s1a), int(s1b), int(s2a), int(s2b),
                    int(fa), int(fb), int(total_games), int(p1_games), int(p2_games),
                    bool(initial_nil or later_nil),
                )
                agg[key] += base_prob * cont_prob

    total = sum(agg.values())
    if total <= core.EPS:
        return []

    rows = []
    for key, probability in agg.items():
        s1a, s1b, s2a, s2b, sa, sb, total_games, p1_games, p2_games, any_nil = key
        rows.append({
            "set1": (s1a, s1b),
            "set2": (s2a, s2b),
            "set3": None,
            "sets": (sa, sb),
            "total_games": total_games,
            "p1_games": p1_games,
            "p2_games": p2_games,
            "set_count": sa + sb,
            "winner": 1 if sa > sb else 2,
            "set1_winner": 1 if s1a > s1b else 2,
            "set2_winner": 1 if s2a > s2b else 2,
            "set3_winner": None,
            "set1_tiebreak": {s1a, s1b} == {6, 7},
            "set2_tiebreak": {s2a, s2b} == {6, 7},
            "any_set_to_nil": any_nil,
            "_set_margin_p1": sa,
            "_set_margin_p2": sb,
            "bo5_compact_scope": SCOPE,
            "prob": probability / total,
        })
    return rows


def exact_market_supported(market: str) -> bool:
    return str(market or "") not in BO5_EVIDENCE_ONLY_MARKETS
