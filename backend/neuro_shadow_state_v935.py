from __future__ import annotations

"""Isolated SHADOW state expansion for future NEURO market coverage.

This module deliberately does not change symphony2_state or any production
PLAYABLE/Symphony path. It builds a bounded richer outcome distribution for
audit and SHADOW evaluation only: set2/set3 scores/winners plus per-player
match games.
"""

from collections import defaultdict
from typing import Any, Callable

from backend import symphony2_state as s2

VERSION = "neuro-shadow-state-v9.3.5"
PRODUCTION_INFLUENCE = False
PLAYABLE_INFLUENCE = False
SYMPHONY_PROD_INFLUENCE = False

# These markets now have SHADOW state + exact shared settlement/capture semantics.
# This is evidence collection only; it never changes PLAYABLE or Symphony PROD.
CANDIDATE_CAPTURE_READY_MARKETS = frozenset({
    "set2_winner",
    "set3_winner",
    "set2_total",
    "set3_total",
    "player_total_games",
    "match_game_handicap",
})
CANDIDATE_CAPTURE_GAP_MARKETS = frozenset()


def build_shadow_outcomes(match: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a bounded SHADOW-only state distribution.

    Production state intentionally remains unchanged. For BO5 matches we do not
    retain complete set-score sequences for sets 4/5 because doing so destroys
    aggregation and creates a combinatorial state explosion. Current v9.3.5
    needs only set2/set3 terminal scores plus P1/P2 aggregate game totals.
    """
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

    # Key: checkpoints, set1, set2, set3, final set score and per-player games.
    # Later BO5 set scores are intentionally folded into aggregate game totals.
    agg: dict[tuple, float] = defaultdict(float)
    for path, p0 in first.items():
        c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b = path
        sa, sb = ((1, 0) if s1a > s1b else (0, 1))
        if sa >= need or sb >= need:
            agg[(c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b, None, None, None, None, sa, sb, s1a, s1b)] += p0
            continue

        # (set wins, P1/P2 games, set2 score, set3 score)
        frontier = {(sa, sb, int(s1a), int(s1b), None, None, None, None): p0}
        for set_no in range(2, best_of + 1):
            nxt: dict[tuple, float] = defaultdict(float)
            for (xa, xb, p1_games, p2_games, s2a, s2b, s3a, s3b), probability in frontier.items():
                if xa >= need or xb >= need:
                    nxt[(xa, xb, p1_games, p2_games, s2a, s2b, s3a, s3b)] += probability
                    continue
                for (ga, gb), sp in later[set_no].items():
                    ns2a, ns2b = (int(ga), int(gb)) if set_no == 2 else (s2a, s2b)
                    ns3a, ns3b = (int(ga), int(gb)) if set_no == 3 else (s3a, s3b)
                    nxt[(
                        xa + int(ga > gb),
                        xb + int(gb > ga),
                        p1_games + int(ga),
                        p2_games + int(gb),
                        ns2a,
                        ns2b,
                        ns3a,
                        ns3b,
                    )] += probability * sp
            frontier = nxt
            if all(xa >= need or xb >= need for xa, xb, *_ in frontier):
                break

        for (xa, xb, p1_games, p2_games, s2a, s2b, s3a, s3b), probability in frontier.items():
            if xa >= need or xb >= need:
                agg[(
                    c2a, c2b, c4a, c4b, c6a, c6b,
                    s1a, s1b, s2a, s2b, s3a, s3b,
                    xa, xb, p1_games, p2_games,
                )] += probability

    total = sum(agg.values())
    if not total:
        return []

    out = []
    for key, probability in agg.items():
        set1 = (int(key[6]), int(key[7]))
        set2 = (int(key[8]), int(key[9])) if key[8] is not None and key[9] is not None else None
        set3 = (int(key[10]), int(key[11])) if key[10] is not None and key[11] is not None else None
        row = {
            "cp2": (key[0], key[1]),
            "cp4": (key[2], key[3]),
            "cp6": (key[4], key[5]),
            "set1": set1,
            "set2": set2,
            "set3": set3,
            "sets": (int(key[12]), int(key[13])),
            "p1_total_games": int(key[14]),
            "p2_total_games": int(key[15]),
            "total_games": int(key[14] + key[15]),
            "set_count": int(key[12] + key[13]),
            "winner": 1 if key[12] > key[13] else 2,
            "prob": probability / total,
        }
        for set_no in (1, 2, 3):
            score = row.get(f"set{set_no}")
            row[f"set{set_no}_winner"] = (1 if score[0] > score[1] else 2) if score else None
        out.append(row)
    return out


def _conditional_probability(
    outcomes: list[dict[str, Any]],
    eligible: Callable[[dict[str, Any]], bool],
    hit: Callable[[dict[str, Any]], bool],
) -> float | None:
    denominator = sum(o["prob"] for o in outcomes if eligible(o))
    if denominator <= 0.0:
        return None
    numerator = sum(o["prob"] for o in outcomes if eligible(o) and hit(o))
    return numerator / denominator


def _settled_probability(
    outcomes: list[dict[str, Any]],
    voided: Callable[[dict[str, Any]], bool],
    hit: Callable[[dict[str, Any]], bool],
) -> float | None:
    """Return P(hit | selection settles), excluding VOID/push mass.

    Candidate Brier/accuracy is computed only from hit/miss rows, so integer
    operator lines that can push must not dilute the model probability with
    outcomes that settlement later removes as VOID.
    """
    return _conditional_probability(outcomes, lambda o: not voided(o), hit)


def set_reach_probability(match: dict[str, Any], set_no: int) -> float | None:
    """Return P(the requested set is played) in the SHADOW state."""
    if set_no not in {2, 3}:
        return None
    outcomes = build_shadow_outcomes(match)
    if not outcomes:
        return None
    return sum(o["prob"] for o in outcomes if o.get(f"set{set_no}") is not None)


def shadow_probability(
    match: dict[str, Any],
    market: str,
    *,
    side: int | None = None,
    line: float | None = None,
    pick: str | None = None,
) -> float | None:
    """Evaluate newly retained markets without fabricating unavailable outcomes.

    Later-set markets condition on that set being played. Any exact-line push is
    also excluded from the denominator because shared settlement records it as
    VOID and candidate calibration is measured only on hit/miss observations.
    """
    outcomes = build_shadow_outcomes(match)
    if not outcomes:
        return None

    market = str(market or "")
    if market in {"set2_winner", "set3_winner"} and side in {1, 2}:
        field = market.replace("_winner", "")
        return _conditional_probability(
            outcomes,
            lambda o: o.get(field) is not None,
            lambda o: o.get(market) == side,
        )

    if market in {"set2_total", "set3_total"} and line is not None and pick in {"over", "under"}:
        field = "set2" if market.startswith("set2") else "set3"
        target = float(line)
        eligible = [o for o in outcomes if o.get(field) is not None]
        if not eligible:
            return None
        return _settled_probability(
            eligible,
            lambda o: sum(o[field]) == target,
            (lambda o: sum(o[field]) > target) if pick == "over" else (lambda o: sum(o[field]) < target),
        )

    if market == "player_total_games" and side in {1, 2} and line is not None and pick in {"over", "under"}:
        field = "p1_total_games" if side == 1 else "p2_total_games"
        target = float(line)
        return _settled_probability(
            outcomes,
            lambda o: o[field] == target,
            (lambda o: o[field] > target) if pick == "over" else (lambda o: o[field] < target),
        )

    if market == "match_game_handicap" and side in {1, 2} and line is not None:
        handicap = float(line)
        adjusted = (
            (lambda o: o["p1_total_games"] + handicap - o["p2_total_games"])
            if side == 1
            else (lambda o: o["p2_total_games"] + handicap - o["p1_total_games"])
        )
        return _settled_probability(
            outcomes,
            lambda o: abs(adjusted(o)) <= 1e-12,
            lambda o: adjusted(o) > 0.0,
        )

    return None