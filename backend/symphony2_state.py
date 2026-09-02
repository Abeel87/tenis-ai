from __future__ import annotations

"""Symfonia 2.0 state facade with bounded exact market-family distributions.

The proven v9.4.5 engine remains verbatim in ``symphony2_state_core_v945``.
New coverage is derived from exact bounded sufficient statistics instead of one
huge universal cross-product. Existing/base markets keep the original shared
state. New same-family joints stay exact; cross-family joints are deliberately
unsupported rather than approximated as independent.
"""

from collections import defaultdict

try:
    from . import symphony2_state_core_v945 as _core
except ImportError:
    import symphony2_state_core_v945 as _core

for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

VERSION = "symphony2-state-3"

SET1_FAMILY = {
    "set1_winner", "set1_total", "set1_exact_score", "set1_tiebreak",
    "set1_game_handicap", "set1_games_parity",
}
SET2_FAMILY = {
    "set2_winner", "set2_total", "set2_exact_score",
    "set2_game_handicap", "set2_games_parity",
}
MATCH_FAMILY = {
    "match_winner", "match_total", "total_sets", "exact_match_score",
    "match_game_handicap", "player_total_games", "exact_sets", "set_handicap",
    "match_games_parity", "any_set_to_nil",
    "p1_exactly_1_set", "p1_exactly_2_sets", "p2_exactly_1_set", "p2_exactly_2_sets",
    "p1_wins_a_set", "p2_wins_a_set",
}
NEW_MARKETS = {
    "set2_winner", "set2_total", "set2_exact_score",
    "match_game_handicap", "set1_game_handicap", "set2_game_handicap",
    "player_total_games", "exact_sets", "set_handicap",
    "match_games_parity", "set1_games_parity", "set2_games_parity",
    "any_set_to_nil",
    "p1_exactly_1_set", "p1_exactly_2_sets", "p2_exactly_1_set", "p2_exactly_2_sets",
    "p1_wins_a_set", "p2_wins_a_set",
}
SUPPORTED_MARKETS = set(_core.SUPPORTED_MARKETS) | NEW_MARKETS


def build_outcomes(match: dict) -> list[dict]:
    """Preserve the bounded original shared state for all legacy markets."""
    return _core.build_outcomes(match)


def _best_of(match: dict) -> int:
    value = _core._num(match.get("best_of"), None)
    if value is None:
        value = _core._num(match.get("bestOf"), 3)
    return 5 if int(value or 3) >= 5 else 3


def _normalise(mapping: dict) -> dict:
    total = sum(float(v) for v in mapping.values())
    if total <= 0:
        return {}
    return {k: float(v) / total for k, v in mapping.items() if float(v) > 0}


def _first_score_distribution(match: dict) -> dict[tuple[int, int], float]:
    holds = _core._service_holds(match)
    if not holds:
        return {}
    h1, h2 = holds
    paths = _core._reweight_winner(
        _core._first_set_paths(h1, h2),
        _core._set_target(match, 1),
    )
    out: dict[tuple[int, int], float] = defaultdict(float)
    for path, probability in paths.items():
        out[(int(path[6]), int(path[7]))] += probability
    return _normalise(out)


def _later_score_distribution(match: dict, set_no: int) -> dict[tuple[int, int], float]:
    holds = _core._service_holds(match)
    if not holds:
        return {}
    h1, h2 = holds
    dist = _core._reweight_winner(
        _core._terminal_set_distribution(h1, h2),
        _core._set_target(match, set_no),
        indexes=(0, 1),
    )
    return _normalise({(int(a), int(b)): p for (a, b), p in dist.items()})


def _set1_outcomes(match: dict) -> list[dict]:
    return [
        {
            "set1": score,
            "set1_winner": 1 if score[0] > score[1] else 2,
            "set1_tiebreak": set(score) == {6, 7},
            "prob": probability,
        }
        for score, probability in _first_score_distribution(match).items()
    ]


def _set2_outcomes(match: dict) -> list[dict]:
    return [
        {
            "set2": score,
            "set2_winner": 1 if score[0] > score[1] else 2,
            "prob": probability,
        }
        for score, probability in _later_score_distribution(match, 2).items()
    ]


def _match_game_outcomes(match: dict) -> list[dict]:
    """Exact full-match DP collapsed by sufficient aggregate statistics only."""
    first = _first_score_distribution(match)
    if not first:
        return []
    best_of = _best_of(match)
    need = best_of // 2 + 1
    later = {n: _later_score_distribution(match, n) for n in range(2, best_of + 1)}
    if any(not dist for dist in later.values()):
        return []

    # (p1 sets, p2 sets, p1 games, p2 games, any set-to-nil) -> probability
    frontier: dict[tuple[int, int, int, int, bool], float] = defaultdict(float)
    for (a, b), probability in first.items():
        frontier[(int(a > b), int(b > a), a, b, a == 0 or b == 0)] += probability

    for set_no in range(2, best_of + 1):
        nxt: dict[tuple[int, int, int, int, bool], float] = defaultdict(float)
        for (w1, w2, g1, g2, any_nil), probability in frontier.items():
            if w1 >= need or w2 >= need:
                nxt[(w1, w2, g1, g2, any_nil)] += probability
                continue
            for (a, b), set_probability in later[set_no].items():
                nxt[(
                    w1 + int(a > b),
                    w2 + int(b > a),
                    g1 + a,
                    g2 + b,
                    bool(any_nil or a == 0 or b == 0),
                )] += probability * set_probability
        frontier = nxt
        if all(w1 >= need or w2 >= need for w1, w2, _, _, _ in frontier):
            break

    terminal = {
        state: probability
        for state, probability in frontier.items()
        if state[0] >= need or state[1] >= need
    }
    terminal = _normalise(terminal)
    return [
        {
            "sets": (w1, w2),
            "set_count": w1 + w2,
            "winner": 1 if w1 > w2 else 2,
            "p1_games": g1,
            "p2_games": g2,
            "total_games": g1 + g2,
            "any_set_to_nil": any_nil,
            "prob": probability,
        }
        for (w1, w2, g1, g2, any_nil), probability in terminal.items()
    ]


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
        return (lambda o: sum(o["set2"]) > line) if ou == "over" else (lambda o: sum(o["set2"]) < line)

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
        return lambda o: sum(o["set2"]) % 2 == wanted

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


def _family(market: str) -> str | None:
    if market in SET1_FAMILY:
        return "set1"
    if market in SET2_FAMILY:
        return "set2"
    if market in MATCH_FAMILY:
        return "match"
    return None


def _family_outcomes(match: dict, family: str) -> list[dict]:
    if family == "set1":
        return _set1_outcomes(match)
    if family == "set2":
        return _set2_outcomes(match)
    if family == "match":
        return _match_game_outcomes(match)
    return []


def marginal_probability(match: dict, selection: dict, outcomes: list[dict] | None = None):
    market = _core._market(selection.get("market"))
    if market not in NEW_MARKETS:
        return _core.marginal_probability(match, selection, outcomes)
    family = _family(market)
    states = _family_outcomes(match, family) if family else []
    pred = predicate(match, selection)
    if pred is None or not states:
        return None
    return sum(o["prob"] for o in states if pred(o))


def joint_probability(match: dict, selections: list[dict], outcomes: list[dict] | None = None):
    markets = [_core._market(x.get("market")) for x in selections]
    if not markets:
        return None, 0
    if not any(m in NEW_MARKETS for m in markets):
        return _core.joint_probability(match, selections, outcomes)

    families = [_family(m) for m in markets]
    supported = sum(predicate(match, selection) is not None for selection in selections)
    if not families or any(f is None for f in families) or len(set(families)) != 1:
        # Honest unsupported cross-family joint; never multiply marginals as if independent.
        return None, supported

    states = _family_outcomes(match, families[0])
    preds = [predicate(match, selection) for selection in selections]
    if not states or any(p is None for p in preds):
        return None, supported
    return sum(o["prob"] for o in states if all(p(o) for p in preds)), len(preds)
