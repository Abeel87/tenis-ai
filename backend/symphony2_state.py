from __future__ import annotations

"""Symfonia 2.0 shared-state facade with expanded exact market coverage.

The proven v9.4.5 state engine is preserved verbatim in
``symphony2_state_core_v945``. This module keeps the same probability state and
adds only predicates that can be derived exactly from that state. Markets that
need unavailable point-by-point or serve-prop evidence remain unsupported.
"""

from collections import defaultdict

try:
    from . import symphony2_state_core_v945 as _core
except ImportError:
    import symphony2_state_core_v945 as _core

for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

VERSION = "symphony2-state-2"
SUPPORTED_MARKETS = set(_core.SUPPORTED_MARKETS) | {
    "set2_winner", "set2_total", "set2_exact_score",
    "match_game_handicap", "set1_game_handicap", "set2_game_handicap",
    "player_total_games", "exact_sets", "set_handicap",
    "match_games_parity", "set1_games_parity", "set2_games_parity",
    "any_set_to_nil",
    "p1_exactly_1_set", "p1_exactly_2_sets", "p2_exactly_1_set", "p2_exactly_2_sets",
    "p1_wins_a_set", "p2_wins_a_set",
}


def build_outcomes(match: dict) -> list[dict]:
    holds = _core._service_holds(match)
    if not holds:
        return []
    h1, h2 = holds
    best_of = 5 if int(_core._num(match.get("best_of"), 3) or 3) >= 5 else 3
    need = best_of // 2 + 1
    first = _core._reweight_winner(_core._first_set_paths(h1, h2), _core._set_target(match, 1))
    later = {
        n: _core._reweight_winner(
            _core._terminal_set_distribution(h1, h2),
            _core._set_target(match, n),
            indexes=(0, 1),
        )
        for n in range(2, best_of + 1)
    }

    agg: dict[tuple, float] = defaultdict(float)
    for path, p0 in first.items():
        c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b = path
        sa, sb = ((1, 0) if s1a > s1b else (0, 1))
        scores = ((int(s1a), int(s1b)),)
        p1_games, p2_games = int(s1a), int(s1b)
        frontier = {(sa, sb, p1_games, p2_games, scores): p0}

        for set_no in range(2, best_of + 1):
            nxt: dict[tuple, float] = defaultdict(float)
            for (xa, xb, ga_total, gb_total, set_scores), probability in frontier.items():
                if xa >= need or xb >= need:
                    nxt[(xa, xb, ga_total, gb_total, set_scores)] += probability
                    continue
                for (ga, gb), sp in later[set_no].items():
                    next_scores = set_scores + ((int(ga), int(gb)),)
                    nxt[(
                        xa + int(ga > gb),
                        xb + int(gb > ga),
                        ga_total + int(ga),
                        gb_total + int(gb),
                        next_scores,
                    )] += probability * sp
            frontier = nxt
            if all(xa >= need or xb >= need for xa, xb, _, _, _ in frontier):
                break

        for (xa, xb, ga_total, gb_total, set_scores), probability in frontier.items():
            if xa < need and xb < need:
                continue
            key = (
                c2a, c2b, c4a, c4b, c6a, c6b,
                int(s1a), int(s1b), int(xa), int(xb),
                int(ga_total), int(gb_total), set_scores,
            )
            agg[key] += probability

    total = sum(agg.values())
    if not total:
        return []

    out = []
    for key, probability in agg.items():
        set_scores = tuple(key[12])
        set2 = set_scores[1] if len(set_scores) >= 2 else None
        out.append({
            "cp2": (key[0], key[1]),
            "cp4": (key[2], key[3]),
            "cp6": (key[4], key[5]),
            "set1": (key[6], key[7]),
            "set2": set2,
            "set_scores": set_scores,
            "sets": (key[8], key[9]),
            "p1_games": int(key[10]),
            "p2_games": int(key[11]),
            "total_games": int(key[10] + key[11]),
            "set_count": int(key[8] + key[9]),
            "winner": 1 if key[8] > key[9] else 2,
            "set1_winner": 1 if key[6] > key[7] else 2,
            "set2_winner": (1 if set2 and set2[0] > set2[1] else 2) if set2 else None,
            "set1_tiebreak": {key[6], key[7]} == {6, 7},
            "any_set_to_nil": any(a == 0 or b == 0 for a, b in set_scores),
            "prob": probability / total,
        })
    return out


def _parity(value):
    token = _core._ascii(value).replace(" ", "")
    if token in {"odd", "nieparzyste", "nieparzysta"}:
        return 1
    if token in {"even", "parzyste", "parzysta"}:
        return 0
    return None


def _set_prop_actual(market: str, outcome: dict) -> bool:
    w1, w2 = outcome["sets"]
    return {
        "p1_exactly_1_set": w1 == 1,
        "p1_exactly_2_sets": w1 == 2,
        "p2_exactly_1_set": w2 == 1,
        "p2_exactly_2_sets": w2 == 2,
        "p1_wins_a_set": w1 >= 1,
        "p2_wins_a_set": w2 >= 1,
    }[market]


def predicate(match: dict, selection: dict):
    market = _core._market(selection.get("market"))
    base = _core.predicate(match, selection)
    if base is not None:
        return base

    pick = selection.get("pick")
    line = _core._num(selection.get("line"))

    if market == "set2_winner":
        side = _core._side(match, pick)
        return (lambda o: o.get("set2_winner") == side) if side else None

    if market == "set2_total":
        ou = _core._ou(pick)
        if ou is None or line is None:
            return None
        return (
            (lambda o: o.get("set2") is not None and sum(o["set2"]) > line)
            if ou == "over"
            else (lambda o: o.get("set2") is not None and sum(o["set2"]) < line)
        )

    if market == "set2_exact_score":
        target = _core._score_pair(pick)
        return (lambda o: o.get("set2") == target) if target else None

    if market in {"match_game_handicap", "set1_game_handicap", "set2_game_handicap"}:
        side = _core._side(match, pick)
        if side is None or line is None:
            return None

        def handicap(o):
            if market == "set1_game_handicap":
                a, b = o["set1"]
            elif market == "set2_game_handicap":
                if o.get("set2") is None:
                    return False
                a, b = o["set2"]
            else:
                a, b = o["p1_games"], o["p2_games"]
            margin = (a - b) if side == 1 else (b - a)
            return margin + line > 0

        return handicap

    if market == "player_total_games":
        side = _core._side(match, selection.get("player"))
        ou = _core._ou(pick)
        if side is None or ou is None or line is None:
            return None
        field = "p1_games" if side == 1 else "p2_games"
        return (lambda o: o[field] > line) if ou == "over" else (lambda o: o[field] < line)

    if market == "exact_sets":
        try:
            wanted = int(float(pick))
        except (TypeError, ValueError):
            return None
        return lambda o: o["set_count"] == wanted

    if market == "set_handicap":
        side = _core._side(match, pick)
        if side is None or line is None:
            return None
        return lambda o: (((o["sets"][0] - o["sets"][1]) if side == 1 else (o["sets"][1] - o["sets"][0])) + line) > 0

    if market in {"match_games_parity", "set1_games_parity", "set2_games_parity"}:
        wanted = _parity(pick)
        if wanted is None:
            return None
        if market == "match_games_parity":
            return lambda o: o["total_games"] % 2 == wanted
        if market == "set1_games_parity":
            return lambda o: sum(o["set1"]) % 2 == wanted
        return lambda o: o.get("set2") is not None and sum(o["set2"]) % 2 == wanted

    if market == "any_set_to_nil":
        yn = _core._yes_no(pick)
        return (lambda o: bool(o["any_set_to_nil"]) is yn) if yn is not None else None

    if market in {
        "p1_exactly_1_set", "p1_exactly_2_sets", "p2_exactly_1_set", "p2_exactly_2_sets",
        "p1_wins_a_set", "p2_wins_a_set",
    }:
        yn = _core._yes_no(pick)
        return (lambda o: bool(_set_prop_actual(market, o)) is yn) if yn is not None else None

    return None


def marginal_probability(match: dict, selection: dict, outcomes: list[dict] | None = None):
    outcomes = outcomes if outcomes is not None else build_outcomes(match)
    pred = predicate(match, selection)
    if pred is None or not outcomes:
        return None
    return sum(o["prob"] for o in outcomes if pred(o))


def joint_probability(match: dict, selections: list[dict], outcomes: list[dict] | None = None):
    outcomes = outcomes if outcomes is not None else build_outcomes(match)
    preds = [predicate(match, x) for x in selections]
    if not outcomes or not preds or any(p is None for p in preds):
        return None, sum(p is not None for p in preds)
    return sum(o["prob"] for o in outcomes if all(p(o) for p in preds)), len(preds)
