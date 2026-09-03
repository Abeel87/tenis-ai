from __future__ import annotations

"""Shared-state tennis probability engine for Symfonia 2.0.

This is a clean 2.0 module. It does not import legacy Symphony code. The same
state distribution is used for every supported leg and for composition joint
probability, so no independence product is presented as a true joint P.
"""

from collections import defaultdict
import math
import re
import unicodedata
from typing import Any, Callable

VERSION = "symphony2-state-1"
CHECKPOINTS = (2, 4, 6)
EPS = 1e-12
SUPPORTED_MARKETS = {
    "game_state", "match_winner", "set1_winner", "match_total", "set1_total",
    "total_sets", "exact_match_score", "set1_exact_score", "set1_tiebreak",
}


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _prob(value):
    x = _num(value)
    if x is None:
        return None
    if x > 1.0:
        x /= 100.0
    return max(0.001, min(0.999, x))


def _ascii(value: Any) -> str:
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold().strip()


def _name_key(value: Any) -> str:
    return " ".join(sorted(re.sub(r"[^a-z0-9]+", " ", _ascii(value)).split()))


def _market(value: Any) -> str:
    x = _ascii(value).replace("-", "_").replace(" ", "_")
    aliases = {
        "match_win": "match_winner", "winner": "match_winner",
        "set1_win": "set1_winner", "first_set_win": "set1_winner", "set_1_winner": "set1_winner",
        "state": "game_state", "gamestate": "game_state",
        "sets_total": "total_sets", "set_total": "total_sets",
        "correct_score": "exact_match_score", "match_score": "exact_match_score", "exact_score": "exact_match_score",
        "set1_score": "set1_exact_score", "first_set_score": "set1_exact_score",
        "tie_break": "set1_tiebreak", "tiebreak": "set1_tiebreak", "tie_break_set1": "set1_tiebreak",
    }
    return aliases.get(x, x)


def _tb_p1(h1: float, h2: float) -> float:
    strength = (float(h1) + (1.0 - float(h2))) / 2.0
    x = 1.0 / (1.0 + math.exp(-(strength - 0.5) * 8.0))
    return max(0.20, min(0.80, x))


def _set_paths_one_order(h1: float, h2: float, p1_serves_first: bool) -> dict[tuple, float]:
    live = {(0, 0, -1, -1, -1, -1, -1, -1): 1.0}
    terminal: dict[tuple, float] = defaultdict(float)
    tb = _tb_p1(h1, h2)
    while live:
        nxt: dict[tuple, float] = defaultdict(float)
        for state, probability in live.items():
            a, b, c2a, c2b, c4a, c4b, c6a, c6b = state
            if a == 6 and b == 6:
                terminal[(c2a, c2b, c4a, c4b, c6a, c6b, 7, 6)] += probability * tb
                terminal[(c2a, c2b, c4a, c4b, c6a, c6b, 6, 7)] += probability * (1.0 - tb)
                continue
            if (a >= 6 or b >= 6) and abs(a - b) >= 2:
                terminal[(c2a, c2b, c4a, c4b, c6a, c6b, a, b)] += probability
                continue
            games_played = a + b
            p1_serves = p1_serves_first if games_played % 2 == 0 else not p1_serves_first
            p1_game = h1 if p1_serves else 1.0 - h2
            for p1_wins, branch in ((True, p1_game), (False, 1.0 - p1_game)):
                na, nb = a + int(p1_wins), b + int(not p1_wins)
                nc2a, nc2b, nc4a, nc4b, nc6a, nc6b = c2a, c2b, c4a, c4b, c6a, c6b
                played = na + nb
                if played == 2:
                    nc2a, nc2b = na, nb
                elif played == 4:
                    nc4a, nc4b = na, nb
                elif played == 6:
                    nc6a, nc6b = na, nb
                nxt[(na, nb, nc2a, nc2b, nc4a, nc4b, nc6a, nc6b)] += probability * branch
        live = nxt
    total = sum(terminal.values())
    return {k: v / total for k, v in terminal.items()} if total else {}


def _first_set_paths(h1: float, h2: float) -> dict[tuple, float]:
    a = _set_paths_one_order(h1, h2, True)
    b = _set_paths_one_order(h1, h2, False)
    out = {key: (a.get(key, 0.0) + b.get(key, 0.0)) / 2.0 for key in set(a) | set(b)}
    total = sum(out.values())
    return {k: v / total for k, v in out.items()} if total else {}


def _terminal_set_distribution(h1: float, h2: float) -> dict[tuple[int, int], float]:
    out: dict[tuple[int, int], float] = defaultdict(float)
    for path, probability in _first_set_paths(h1, h2).items():
        out[(path[-2], path[-1])] += probability
    total = sum(out.values())
    return {k: v / total for k, v in out.items()} if total else {}


def _winner_marginal(distribution: dict[tuple, float], indexes=(-2, -1)) -> float:
    ia, ib = indexes
    return sum(p for key, p in distribution.items() if key[ia] > key[ib])


def _reweight_winner(distribution: dict[tuple, float], target: float | None, indexes=(-2, -1)) -> dict[tuple, float]:
    if target is None or not distribution:
        return dict(distribution)
    raw = _winner_marginal(distribution, indexes)
    if raw <= EPS or raw >= 1.0 - EPS:
        return dict(distribution)
    ia, ib = indexes
    out = {}
    for key, p in distribution.items():
        out[key] = p * (target / raw if key[ia] > key[ib] else (1.0 - target) / (1.0 - raw))
    total = sum(out.values())
    return {k: v / total for k, v in out.items()} if total else dict(distribution)


def _market_player_prob(obj: Any, player: str):
    if not isinstance(obj, dict):
        return None
    target = _name_key(player)
    for key, value in obj.items():
        if target and _name_key(key) == target:
            return _prob(value)
    return None


def _set_target(match: dict, set_no: int):
    keys = {
        1: ("first_set_win", "set1_win", "set1_winner"),
        2: ("second_set_win", "set2_win", "set2_winner"),
        3: ("third_set_win", "set3_win", "set3_winner"),
        4: ("fourth_set_win", "set4_win", "set4_winner"),
        5: ("fifth_set_win", "set5_win", "set5_winner"),
    }.get(set_no, ())
    p1 = str(match.get("p1") or "")
    for key in keys:
        p = _market_player_prob(match.get(key), p1)
        if p is not None:
            return p
    return _market_player_prob(match.get("first_set_win"), p1)


def _service_holds(match: dict):
    service = match.get("service_model") or {}
    h1, h2 = _prob(service.get("p1_hold")), _prob(service.get("p2_hold"))
    if h1 is None or h2 is None or not (0.01 < h1 < 0.99 and 0.01 < h2 < 0.99):
        return None
    return h1, h2


def build_outcomes(match: dict) -> list[dict]:
    holds = _service_holds(match)
    if not holds:
        return []
    h1, h2 = holds
    best_of = 5 if int(_num(match.get("best_of"), 3) or 3) >= 5 else 3
    need = best_of // 2 + 1
    first = _reweight_winner(_first_set_paths(h1, h2), _set_target(match, 1))
    later = {
        n: _reweight_winner(_terminal_set_distribution(h1, h2), _set_target(match, n), indexes=(0, 1))
        for n in range(2, best_of + 1)
    }
    agg: dict[tuple, float] = defaultdict(float)
    for path, p0 in first.items():
        c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b = path
        sa, sb = ((1, 0) if s1a > s1b else (0, 1))
        tg = s1a + s1b
        if sa >= need or sb >= need:
            agg[(c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b, sa, sb, tg)] += p0
            continue
        frontier = {(sa, sb, tg): p0}
        for set_no in range(2, best_of + 1):
            nxt: dict[tuple[int, int, int], float] = defaultdict(float)
            for (xa, xb, games), probability in frontier.items():
                if xa >= need or xb >= need:
                    nxt[(xa, xb, games)] += probability
                    continue
                for (ga, gb), sp in later[set_no].items():
                    nxt[(xa + int(ga > gb), xb + int(gb > ga), games + ga + gb)] += probability * sp
            frontier = nxt
            if all(xa >= need or xb >= need for xa, xb, _ in frontier):
                break
        for (xa, xb, games), probability in frontier.items():
            if xa >= need or xb >= need:
                agg[(c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b, xa, xb, games)] += probability
    total = sum(agg.values())
    if not total:
        return []
    return [{
        "cp2": (key[0], key[1]), "cp4": (key[2], key[3]), "cp6": (key[4], key[5]),
        "set1": (key[6], key[7]), "sets": (key[8], key[9]), "total_games": int(key[10]),
        "set_count": int(key[8] + key[9]), "winner": 1 if key[8] > key[9] else 2,
        "set1_winner": 1 if key[6] > key[7] else 2,
        "set1_tiebreak": {key[6], key[7]} == {6, 7}, "prob": probability / total,
    } for key, probability in agg.items()]


def _score_pair(value: Any):
    m = re.search(r"(\d+)\s*[:\-]\s*(\d+)", str(value or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _side(match: dict, pick: Any):
    token = _ascii(pick).replace(" ", "")
    if token in {"1", "p1", "player1"}:
        return 1
    if token in {"2", "p2", "player2"}:
        return 2
    value = _name_key(pick)
    if value and value == _name_key(match.get("p1")):
        return 1
    if value and value == _name_key(match.get("p2")):
        return 2
    return None


def _ou(pick: Any):
    value = _ascii(pick).replace(" ", "")
    if value in {"over", "o", "powyzej", "wiecej"}:
        return "over"
    if value in {"under", "u", "ponizej", "mniej"}:
        return "under"
    return None


def _yes_no(pick: Any):
    value = _ascii(pick).replace(" ", "")
    if value in {"yes", "tak", "1", "true"}:
        return True
    if value in {"no", "nie", "0", "false"}:
        return False
    return None


def predicate(match: dict, selection: dict) -> Callable[[dict], bool] | None:
    market = _market(selection.get("market"))
    pick = selection.get("pick")
    line = _num(selection.get("line"))
    if market == "game_state":
        cp = int(_num(selection.get("checkpoint"), 0) or 0)
        target = _score_pair(pick)
        return (lambda o: o.get(f"cp{cp}") == target) if cp in CHECKPOINTS and target else None
    if market == "set1_winner":
        side = _side(match, pick)
        return (lambda o: o["set1_winner"] == side) if side else None
    if market == "match_winner":
        side = _side(match, pick)
        return (lambda o: o["winner"] == side) if side else None
    if market in {"set1_total", "match_total", "total_sets"}:
        ou = _ou(pick)
        if ou is None or line is None:
            return None
        if market == "set1_total":
            return (lambda o: sum(o["set1"]) > line) if ou == "over" else (lambda o: sum(o["set1"]) < line)
        field = "total_games" if market == "match_total" else "set_count"
        return (lambda o: o[field] > line) if ou == "over" else (lambda o: o[field] < line)
    if market == "exact_match_score":
        target = _score_pair(pick)
        return (lambda o: o["sets"] == target) if target else None
    if market == "set1_exact_score":
        target = _score_pair(pick)
        return (lambda o: o["set1"] == target) if target else None
    if market == "set1_tiebreak":
        yn = _yes_no(pick)
        return (lambda o: bool(o["set1_tiebreak"]) is yn) if yn is not None else None
    return None


def marginal_probability(match: dict, selection: dict, outcomes: list[dict] | None = None) -> float | None:
    outcomes = outcomes if outcomes is not None else build_outcomes(match)
    pred = predicate(match, selection)
    if pred is None or not outcomes:
        return None
    return sum(o["prob"] for o in outcomes if pred(o))


def joint_probability(match: dict, selections: list[dict], outcomes: list[dict] | None = None) -> tuple[float | None, int]:
    outcomes = outcomes if outcomes is not None else build_outcomes(match)
    preds = [predicate(match, x) for x in selections]
    if not outcomes or not preds or any(p is None for p in preds):
        return None, sum(p is not None for p in preds)
    return sum(o["prob"] for o in outcomes if all(pred(o) for pred in preds)), len(preds)
