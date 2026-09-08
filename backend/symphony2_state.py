from __future__ import annotations

"""Symfonia 2.0 state facade with bounded exact market-family distributions.

The proven state engine lives in ``symphony2_state_core``.
New coverage is derived from exact bounded sufficient statistics instead of one
huge universal cross-product. Existing/base markets keep the original shared
state. New same-family joints stay exact; cross-family joints are deliberately
unsupported rather than approximated as independent.
"""

from collections import defaultdict
import json
import math
from pathlib import Path

try:
    from . import symphony2_state_core as _core
    from .player_dna_tennis_simulator import (
        inverse_hold_probability,
        shared_match_state_outcomes,
    )
except ImportError:
    import symphony2_state_core as _core
    from player_dna_tennis_simulator import (
        inverse_hold_probability,
        shared_match_state_outcomes,
    )

for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

VERSION = "symphony2-state-4"

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

PHASE9_SHARED_MARKETS = SET1_FAMILY | SET2_FAMILY | MATCH_FAMILY
ROOT = Path(__file__).resolve().parents[1]
PHASE8_REPORT = ROOT / "frontend" / "data" / "neuro_shadow_phase8_challenger_walk_forward.json"
PHASE9_OUT = ROOT / "frontend" / "data" / "symphony2_phase9_player_dna_shared_state.json"
PHASE9_VERSION = "symphony2-phase9-player-dna-shared-state-v1"
PHASE9_MODE = "SHADOW_PLAYER_DNA_SHARED_STATE_INTEGRATION_ONLY"


def build_outcomes(match: dict) -> list[dict]:
    """Preserve the bounded original shared state for all legacy markets."""
    return _core.build_outcomes(match)



def build_player_dna_shared_outcomes(match: dict) -> list[dict]:
    """Build one exact whole-match Player DNA state-space from current service holds.

    This is a Phase-9 SHADOW integration surface. The existing Symphony state
    remains the runtime/ranking source until a later promotion decision.
    """
    holds = _core._service_holds(match)
    if not holds:
        return []
    h1, h2 = holds
    try:
        p1s = inverse_hold_probability(float(h1))
        p2s = inverse_hold_probability(float(h2))
    except (TypeError, ValueError):
        return []
    return shared_match_state_outcomes(
        p1s,
        p2s,
        best_of=_best_of(match),
        start_server=None,
    )


def player_dna_marginal_probability(
    match: dict,
    selection: dict,
    outcomes: list[dict] | None = None,
):
    market = _core._market(selection.get("market"))
    if market not in PHASE9_SHARED_MARKETS:
        return None
    states = outcomes if outcomes is not None else build_player_dna_shared_outcomes(match)
    pred = predicate(match, selection)
    if pred is None or not states:
        return None
    try:
        return sum(float(row["prob"]) for row in states if pred(row))
    except (KeyError, TypeError):
        return None


def player_dna_joint_probability(
    match: dict,
    selections: list[dict],
    outcomes: list[dict] | None = None,
):
    if not selections:
        return None, 0
    markets = [_core._market(selection.get("market")) for selection in selections]
    supported_market_count = sum(market in PHASE9_SHARED_MARKETS for market in markets)
    if supported_market_count != len(selections):
        return None, supported_market_count

    states = outcomes if outcomes is not None else build_player_dna_shared_outcomes(match)
    preds = [predicate(match, selection) for selection in selections]
    supported = sum(pred is not None for pred in preds)
    if not states or supported != len(selections):
        return None, supported
    try:
        joint = sum(
            float(row["prob"])
            for row in states
            if all(pred(row) for pred in preds)
        )
    except (KeyError, TypeError):
        return None, supported
    return joint, len(preds)


def phase9_shared_state_contract() -> dict:
    return {
        "mode": PHASE9_MODE,
        "source": "CANONICAL_PLAYER_DNA_TENNIS_SIMULATOR",
        "source_state_builder": "shared_match_state_outcomes",
        "pre_match_start_server_policy": "NEUTRAL_50_50",
        "same_state_for_set1_set2_and_match_markets": True,
        "cross_family_joint_uses_single_state_mass": True,
        "independence_product_forbidden": True,
        "existing_symphony_runtime_state_replaced": False,
        "ranking_influence": False,
        "operator_model_probability_influence": False,
        "production_influence": False,
        "playable_influence": False,
        "auto_promote": False,
        "supported_markets": sorted(PHASE9_SHARED_MARKETS),
    }


def evaluate_phase9_gate(phase8_report: dict) -> dict:
    match = {
        "p1": "Phase9 A",
        "p2": "Phase9 B",
        "best_of": 3,
        "service_model": {"p1_hold": 0.78, "p2_hold": 0.74},
        "first_set_win": {"Phase9 A": 0.56, "Phase9 B": 0.44},
        "second_set_win": {"Phase9 A": 0.55, "Phase9 B": 0.45},
        "third_set_win": {"Phase9 A": 0.54, "Phase9 B": 0.46},
    }
    legs = [
        {"market": "set1_winner", "pick": "Phase9 A"},
        {"market": "set2_total", "pick": "over", "line": 8.5},
        {"market": "match_winner", "pick": "Phase9 A"},
    ]

    phase8_ready = bool(
        phase8_report.get("phase8_complete") is True
        and phase8_report.get("phase9_ready") is True
    )
    states = build_player_dna_shared_outcomes(match)
    mass = sum(float(row.get("prob") or 0.0) for row in states)
    marginals = [
        player_dna_marginal_probability(match, leg, states)
        for leg in legs
    ]
    joint, supported = player_dna_joint_probability(match, legs, states)
    legacy_joint, legacy_supported = joint_probability(match, legs)
    independent_product = (
        math.prod(float(value) for value in marginals)
        if all(value is not None for value in marginals)
        else None
    )
    exact_joint_valid = bool(
        joint is not None
        and supported == len(legs)
        and all(value is not None for value in marginals)
        and 0.0 <= float(joint) <= min(float(value) for value in marginals) + 1e-12
    )
    non_independence = bool(
        exact_joint_valid
        and independent_product is not None
        and abs(float(joint) - independent_product) > 1e-6
    )
    legacy_fail_closed = bool(
        legacy_joint is None and legacy_supported == len(legs)
    )
    normalized = bool(states and math.isclose(mass, 1.0, rel_tol=0.0, abs_tol=1e-9))
    contract = phase9_shared_state_contract()
    isolation = all(
        contract.get(key) is False
        for key in (
            "existing_symphony_runtime_state_replaced",
            "ranking_influence",
            "operator_model_probability_influence",
            "production_influence",
            "playable_influence",
            "auto_promote",
        )
    )
    complete = bool(
        phase8_ready
        and normalized
        and exact_joint_valid
        and non_independence
        and legacy_fail_closed
        and isolation
    )

    return {
        "version": PHASE9_VERSION,
        "mode": PHASE9_MODE,
        "status": (
            "PHASE9_SHARED_STATE_INTEGRATION_COMPLETE_NO_PROMOTION"
            if complete
            else "PHASE9_SHARED_STATE_INTEGRATION_INCOMPLETE_NO_PROMOTION"
        ),
        "phase": 9,
        "phase8_prerequisite_satisfied": phase8_ready,
        "phase9_complete": complete,
        "phase10_ready": complete,
        "shared_state_contract": contract,
        "evidence": {
            "shared_state_outcomes": len(states),
            "probability_mass": round(mass, 12),
            "cross_family_markets": [leg["market"] for leg in legs],
            "cross_family_supported": supported,
            "cross_family_joint_probability": (
                round(float(joint), 12) if joint is not None else None
            ),
            "cross_family_marginals": [
                round(float(value), 12) if value is not None else None
                for value in marginals
            ],
            "independence_product": (
                round(float(independent_product), 12)
                if independent_product is not None
                else None
            ),
            "joint_differs_from_independence": non_independence,
            "legacy_cross_family_joint": legacy_joint,
            "legacy_cross_family_supported": legacy_supported,
            "legacy_path_still_fails_closed": legacy_fail_closed,
        },
        "promotion_allowed_by_this_gate": False,
        "production_influence": False,
        "runtime_ranking_influence": False,
        "operator_model_probability_influence": False,
        "symphony2_current_ranking_replaced": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
    }


def build_phase9_gate() -> dict:
    try:
        phase8 = json.loads(PHASE8_REPORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        phase8 = {}
    report = evaluate_phase9_gate(phase8 if isinstance(phase8, dict) else {})
    PHASE9_OUT.parent.mkdir(parents=True, exist_ok=True)
    PHASE9_OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "version": report.get("version"),
        "status": report.get("status"),
        "phase9_complete": report.get("phase9_complete"),
        "phase10_ready": report.get("phase10_ready"),
        "evidence": report.get("evidence"),
    }, ensure_ascii=False))
    return report


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
