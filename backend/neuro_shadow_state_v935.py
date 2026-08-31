from __future__ import annotations

"""Isolated SHADOW state expansion for future NEURO market coverage.

This module deliberately does not change symphony2_state or any production
PLAYABLE/Symphony path. It builds a richer outcome distribution for audit and
SHADOW evaluation only: later-set scores/winners plus per-player match games.
"""

from collections import defaultdict
from typing import Any

from backend import symphony2_state as s2

VERSION = "neuro-shadow-state-v9.3.5"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False


def build_shadow_outcomes(match: dict[str, Any]) -> list[dict[str, Any]]:
    holds = s2._service_holds(match)
    if not holds:
        return []
    h1, h2 = holds
    best_of = 5 if int(s2._num(match.get("best_of"), 3) or 3) >= 5 else 3
    need = best_of // 2 + 1
    first = s2._reweight_winner(s2._first_set_paths(h1, h2), s2._set_target(match, 1))
    later = {
        n: s2._reweight_winner(
            s2._terminal_set_distribution(h1, h2),
            s2._set_target(match, n),
            indexes=(0, 1),
        )
        for n in range(2, best_of + 1)
    }

    # Key: checkpoint scores, tuple(all set scores), final set score, P1/P2 games.
    agg: dict[tuple, float] = defaultdict(float)
    for path, p0 in first.items():
        c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b = path
        sa, sb = ((1, 0) if s1a > s1b else (0, 1))
        initial_scores = ((int(s1a), int(s1b)),)
        if sa >= need or sb >= need:
            agg[(c2a, c2b, c4a, c4b, c6a, c6b, initial_scores, sa, sb, s1a, s1b)] += p0
            continue

        frontier = {(sa, sb, int(s1a), int(s1b), initial_scores): p0}
        for set_no in range(2, best_of + 1):
            nxt: dict[tuple, float] = defaultdict(float)
            for (xa, xb, p1_games, p2_games, scores), probability in frontier.items():
                if xa >= need or xb >= need:
                    nxt[(xa, xb, p1_games, p2_games, scores)] += probability
                    continue
                for (ga, gb), sp in later[set_no].items():
                    next_scores = scores + ((int(ga), int(gb)),)
                    nxt[(
                        xa + int(ga > gb),
                        xb + int(gb > ga),
                        p1_games + int(ga),
                        p2_games + int(gb),
                        next_scores,
                    )] += probability * sp
            frontier = nxt
            if all(xa >= need or xb >= need for xa, xb, _, _, _ in frontier):
                break

        for (xa, xb, p1_games, p2_games, scores), probability in frontier.items():
            if xa >= need or xb >= need:
                agg[(c2a, c2b, c4a, c4b, c6a, c6b, scores, xa, xb, p1_games, p2_games)] += probability

    total = sum(agg.values())
    if not total:
        return []

    out = []
    for key, probability in agg.items():
        scores = tuple(key[6])
        row = {
            "cp2": (key[0], key[1]),
            "cp4": (key[2], key[3]),
            "cp6": (key[4], key[5]),
            "all_set_scores": scores,
            "set1": scores[0] if len(scores) >= 1 else None,
            "set2": scores[1] if len(scores) >= 2 else None,
            "set3": scores[2] if len(scores) >= 3 else None,
            "sets": (int(key[7]), int(key[8])),
            "p1_total_games": int(key[9]),
            "p2_total_games": int(key[10]),
            "total_games": int(key[9] + key[10]),
            "set_count": int(key[7] + key[8]),
            "winner": 1 if key[7] > key[8] else 2,
            "prob": probability / total,
        }
        for set_no in (1, 2, 3):
            score = row.get(f"set{set_no}")
            row[f"set{set_no}_winner"] = (1 if score[0] > score[1] else 2) if score else None
        out.append(row)
    return out


def shadow_probability(match: dict[str, Any], market: str, *, side: int | None = None, line: float | None = None, pick: str | None = None) -> float | None:
    """Small explicit SHADOW evaluator for newly retained fields only."""
    outcomes = build_shadow_outcomes(match)
    if not outcomes:
        return None

    market = str(market or "")
    predicates = []
    if market in {"set2_winner", "set3_winner"} and side in {1, 2}:
        predicates.append(lambda o: o.get(market) == side)
    elif market in {"set2_total", "set3_total"} and line is not None and pick in {"over", "under"}:
        set_no = 2 if market.startswith("set2") else 3
        if pick == "over":
            predicates.append(lambda o: o.get(f"set{set_no}") is not None and sum(o[f"set{set_no}"]) > float(line))
        else:
            predicates.append(lambda o: o.get(f"set{set_no}") is not None and sum(o[f"set{set_no}"]) < float(line))
    elif market == "player_total_games" and side in {1, 2} and line is not None and pick in {"over", "under"}:
        field = "p1_total_games" if side == 1 else "p2_total_games"
        if pick == "over":
            predicates.append(lambda o: o[field] > float(line))
        else:
            predicates.append(lambda o: o[field] < float(line))
    elif market == "match_game_handicap" and side in {1, 2} and line is not None:
        if side == 1:
            predicates.append(lambda o: o["p1_total_games"] + float(line) > o["p2_total_games"])
        else:
            predicates.append(lambda o: o["p2_total_games"] + float(line) > o["p1_total_games"])
    else:
        return None

    pred = predicates[0]
    return sum(o["prob"] for o in outcomes if pred(o))
