from __future__ import annotations

"""Deterministic SHADOW tennis simulator driven by Player DNA point probabilities.

This layer converts pre-match serve-point probabilities into game/set/match
distributions. Match-level outputs are deliberately marked UNVALIDATED until a
separate historical backtest proves calibration. Nothing here may influence
PROD, Symfonia 2.0 or Superbet PLAYABLE.
"""

import heapq
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "frontend" / "data" / "player_dna_current_shadow.json"
CALIBRATION = ROOT / "frontend" / "data" / "player_dna_hold_calibration_audit.json"
OUT = ROOT / "frontend" / "data" / "player_dna_current_simulation.json"

VERSION = "player-dna-tennis-simulator-v1"
MODE = "SHADOW_SIMULATION_ONLY"


def _clamp_probability(value: Any) -> float:
    p = float(value)
    if not math.isfinite(p):
        raise ValueError("probability must be finite")
    if p <= 0.0 or p >= 1.0:
        raise ValueError("probability must be strictly between 0 and 1")
    return p


def hold_probability(point_win_probability: float) -> float:
    """Exact probability of holding a standard advantage game."""
    p = _clamp_probability(point_win_probability)
    q = 1.0 - p
    win_before_deuce = p**4 * (1.0 + 4.0 * q + 10.0 * q * q)
    reach_deuce = 20.0 * (p**3) * (q**3)
    win_from_deuce = (p * p) / ((p * p) + (q * q))
    return win_before_deuce + reach_deuce * win_from_deuce


def calibrated_hold_probability(iid_hold_probability: float, calibrator: dict[str, Any]) -> float:
    p = _clamp_probability(iid_hold_probability)
    intercept = float(calibrator.get("intercept"))
    slope = float(calibrator.get("slope"))
    if not math.isfinite(intercept) or not math.isfinite(slope):
        raise ValueError("hold calibrator parameters must be finite")
    logit = math.log(p / (1.0 - p))
    z = max(-30.0, min(30.0, intercept + slope * logit))
    return 1.0 / (1.0 + math.exp(-z))


def inverse_hold_probability(target_hold: float) -> float:
    target = _clamp_probability(target_hold)
    lo, hi = 1e-6, 1.0 - 1e-6
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        current = hold_probability(mid)
        if current < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def simulate_match_with_hold_calibration(
    p1_serve_point: float,
    p2_serve_point: float,
    calibrator: dict[str, Any],
    best_of: int = 3,
) -> dict[str, Any]:
    p1s = _clamp_probability(p1_serve_point)
    p2s = _clamp_probability(p2_serve_point)
    p1_iid_hold = hold_probability(p1s)
    p2_iid_hold = hold_probability(p2s)
    p1_cal_hold = calibrated_hold_probability(p1_iid_hold, calibrator)
    p2_cal_hold = calibrated_hold_probability(p2_iid_hold, calibrator)
    p1_equiv = inverse_hold_probability(p1_cal_hold)
    p2_equiv = inverse_hold_probability(p2_cal_hold)

    simulation = simulate_match(p1_equiv, p2_equiv, best_of=best_of)
    simulation["mode"] = "SHADOW_HOLD_CALIBRATED_CANDIDATE"
    simulation["validation_status"] = "BACKTESTED_HOLD_CALIBRATION_CANDIDATE"
    simulation["production_influence"] = False
    simulation["symphony2_influence"] = False
    simulation["superbet_playable_influence"] = False
    simulation["auto_promote"] = False
    simulation["source_point_probabilities"] = {
        "p1_serve_point_win": p1s,
        "p2_serve_point_win": p2s,
    }
    simulation["raw_iid_hold_probabilities"] = {
        "p1_hold": p1_iid_hold,
        "p2_hold": p2_iid_hold,
    }
    simulation["calibrated_hold_probabilities"] = {
        "p1_hold": p1_cal_hold,
        "p2_hold": p2_cal_hold,
    }
    simulation["equivalent_point_probabilities_for_tennis_dp"] = {
        "p1_serve_point_win": p1_equiv,
        "p2_serve_point_win": p2_equiv,
    }
    simulation["hold_calibrator"] = {
        "intercept": float(calibrator.get("intercept")),
        "slope": float(calibrator.get("slope")),
        "l2": calibrator.get("l2"),
    }
    return simulation


def _promising_calibration(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(report, dict):
        return None
    if report.get("mode") != "SHADOW_CALIBRATION_AUDIT_ONLY":
        return None
    if report.get("status") != "CALIBRATION_EXPERIMENT_COMPLETE_NO_INTEGRATION":
        return None
    if report.get("signal") != "HOLD_CALIBRATION_PROMISING_SHADOW":
        return None
    if (
        report.get("production_influence") is not False
        or report.get("symphony2_influence") is not False
        or report.get("superbet_playable_influence") is not False
        or report.get("auto_integrate") is not False
    ):
        return None
    calibrator = report.get("hold_calibrator")
    if not isinstance(calibrator, dict) or calibrator.get("converged") is not True:
        return None
    try:
        intercept = float(calibrator.get("intercept"))
        slope = float(calibrator.get("slope"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(intercept) or not math.isfinite(slope):
        return None
    return calibrator


def neutral_tiebreak_win_probability(p1_serve_point: float, p2_serve_point: float) -> float:
    """Serve-order-neutral tiebreak approximation.

    We average P1's point-win probability across own serve and return, then solve
    an exact i.i.d. first-to-7-by-2 race. The approximation is intentionally
    explicit and remains SHADOW-only until match-level validation.
    """
    p1s = _clamp_probability(p1_serve_point)
    p2s = _clamp_probability(p2_serve_point)
    p = 0.5 * (p1s + (1.0 - p2s))
    q = 1.0 - p

    win_before_6_all = 0.0
    for losses in range(0, 6):
        win_before_6_all += math.comb(6 + losses, losses) * (p**7) * (q**losses)

    reach_6_all = math.comb(12, 6) * (p**6) * (q**6)
    win_from_6_all = (p * p) / ((p * p) + (q * q))
    return win_before_6_all + reach_6_all * win_from_6_all


def _other(server: int) -> int:
    return 2 if server == 1 else 1


def _game_win_probability_for_p1(p1_hold: float, p2_hold: float, server: int) -> float:
    return p1_hold if server == 1 else (1.0 - p2_hold)


def score_distribution_after_games(
    p1_serve_point: float,
    p2_serve_point: float,
    games: int,
    start_server: int,
) -> dict[str, float]:
    """Exact game-score distribution after a fixed number of opening games."""
    if games <= 0 or games > 6:
        raise ValueError("games must be between 1 and 6")
    if start_server not in (1, 2):
        raise ValueError("start_server must be 1 or 2")

    p1_hold = hold_probability(p1_serve_point)
    p2_hold = hold_probability(p2_serve_point)
    states: dict[tuple[int, int, int], float] = {(0, 0, start_server): 1.0}
    for _ in range(games):
        nxt: dict[tuple[int, int, int], float] = defaultdict(float)
        for (g1, g2, server), mass in states.items():
            p1_game = _game_win_probability_for_p1(p1_hold, p2_hold, server)
            next_server = _other(server)
            nxt[(g1 + 1, g2, next_server)] += mass * p1_game
            nxt[(g1, g2 + 1, next_server)] += mass * (1.0 - p1_game)
        states = nxt

    out: dict[str, float] = defaultdict(float)
    for (g1, g2, _server), mass in states.items():
        out[f"{g1}:{g2}"] += mass
    total = sum(out.values())
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise AssertionError(f"checkpoint probability mass drift: {total}")
    return dict(sorted(out.items()))


def _top_first_set_game_paths(
    p1_serve_point: float,
    p2_serve_point: float,
    start_server: int,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Exact top-K complete first-set game paths for one known starting server.

    Best-first search is exact for top-K because every transition probability is
    <= its parent path probability.
    """
    if start_server not in (1, 2):
        raise ValueError("start_server must be 1 or 2")
    if limit <= 0:
        return []

    p1_hold = hold_probability(p1_serve_point)
    p2_hold = hold_probability(p2_serve_point)
    p1_tb = neutral_tiebreak_win_probability(p1_serve_point, p2_serve_point)

    heap: list[tuple[float, int, int, int, int, tuple[str, ...]]] = []
    serial = 0
    heapq.heappush(heap, (-1.0, serial, 0, 0, start_server, ()))
    out: list[dict[str, Any]] = []

    while heap and len(out) < limit:
        neg_mass, _serial, g1, g2, server, path = heapq.heappop(heap)
        mass = -neg_mass

        if g1 == 6 and g2 == 6:
            for winner, probability in ((1, p1_tb), (2, 1.0 - p1_tb)):
                score = "7:6" if winner == 1 else "6:7"
                out.append({
                    "final_score": score,
                    "winner": winner,
                    "games": 13,
                    "tiebreak": True,
                    "progression": [*path, score],
                    "probability": mass * probability,
                })
            out.sort(key=lambda row: float(row["probability"]), reverse=True)
            out = out[:limit]
            continue

        if (g1 >= 6 or g2 >= 6) and abs(g1 - g2) >= 2:
            out.append({
                "final_score": f"{g1}:{g2}",
                "winner": 1 if g1 > g2 else 2,
                "games": g1 + g2,
                "tiebreak": False,
                "progression": list(path),
                "probability": mass,
            })
            continue

        p1_game = _game_win_probability_for_p1(p1_hold, p2_hold, server)
        next_server = _other(server)
        for ng1, ng2, probability in (
            (g1 + 1, g2, p1_game),
            (g1, g2 + 1, 1.0 - p1_game),
        ):
            serial += 1
            score = f"{ng1}:{ng2}"
            heapq.heappush(
                heap,
                (-(mass * probability), serial, ng1, ng2, next_server, (*path, score)),
            )

    return sorted(out, key=lambda row: float(row["probability"]), reverse=True)[:limit]


def _representative_set_progression(
    p1_serve_point: float,
    p2_serve_point: float,
    start_server: int,
    final_score: str,
) -> dict[str, Any] | None:
    """Most likely exact game progression for one already-selected set score.

    The returned progression is representative only. Its probability is the
    exact path mass for that one game-by-game realization and must never be
    presented as the probability of the whole set-score family.
    """
    if start_server not in (1, 2):
        raise ValueError("start_server must be 1 or 2")
    try:
        target_g1, target_g2 = (int(x) for x in str(final_score).split(":"))
    except (TypeError, ValueError):
        return None

    p1_hold = hold_probability(p1_serve_point)
    p2_hold = hold_probability(p2_serve_point)
    p1_tb = neutral_tiebreak_win_probability(p1_serve_point, p2_serve_point)

    states: dict[
        tuple[int, int, int],
        tuple[float, tuple[str, ...]],
    ] = {(0, 0, start_server): (1.0, ())}
    best: dict[str, Any] | None = None

    while states:
        nxt: dict[
            tuple[int, int, int],
            tuple[float, tuple[str, ...]],
        ] = {}
        for (g1, g2, server), (mass, progression) in states.items():
            if g1 == 6 and g2 == 6:
                next_set_server = _other(server)
                for winner, probability in ((1, p1_tb), (2, 1.0 - p1_tb)):
                    score = "7:6" if winner == 1 else "6:7"
                    if score != final_score:
                        continue
                    candidate_mass = mass * probability
                    candidate = {
                        "score": score,
                        "winner": winner,
                        "games": 13,
                        "tiebreak": True,
                        "start_server": start_server,
                        "next_set_server": next_set_server,
                        "progression": [*progression, score],
                        "representative_path_probability": candidate_mass,
                        "representative_only": True,
                    }
                    if best is None or candidate_mass > float(best["representative_path_probability"]):
                        best = candidate
                continue

            if (g1 >= 6 or g2 >= 6) and abs(g1 - g2) >= 2:
                score = f"{g1}:{g2}"
                if score == final_score:
                    candidate = {
                        "score": score,
                        "winner": 1 if g1 > g2 else 2,
                        "games": g1 + g2,
                        "tiebreak": False,
                        "start_server": start_server,
                        "next_set_server": server,
                        "progression": list(progression),
                        "representative_path_probability": mass,
                        "representative_only": True,
                    }
                    if best is None or mass > float(best["representative_path_probability"]):
                        best = candidate
                continue

            p1_game = _game_win_probability_for_p1(p1_hold, p2_hold, server)
            next_server = _other(server)
            for ng1, ng2, probability in (
                (g1 + 1, g2, p1_game),
                (g1, g2 + 1, 1.0 - p1_game),
            ):
                if ng1 > target_g1 or ng2 > target_g2:
                    continue
                child_mass = mass * probability
                child_state = (ng1, ng2, next_server)
                child = (child_mass, (*progression, f"{ng1}:{ng2}"))
                previous = nxt.get(child_state)
                if previous is None or child_mass > previous[0]:
                    nxt[child_state] = child
        states = nxt

    return best


def _ranked_match_storylines(
    p1_serve_point: float,
    p2_serve_point: float,
    best_of: int,
    start_server: int,
) -> list[dict[str, Any]]:
    """Rank coarse match-score families and attach one representative full path.

    Probability belongs to the exact match-score family (for example 2:0 or
    2:1). The game-by-game sequence is only the most likely representative
    realization inside the most likely set-score sequence for that family.
    """
    if best_of not in (3, 5):
        raise ValueError("best_of must be 3 or 5")
    if start_server not in (1, 2):
        raise ValueError("start_server must be 1 or 2")

    needed = best_of // 2 + 1
    set_cache = {
        1: set_outcomes(p1_serve_point, p2_serve_point, 1),
        2: set_outcomes(p1_serve_point, p2_serve_point, 2),
    }
    states: dict[
        tuple[int, int, int],
        tuple[float, tuple[tuple[str, int, int, bool], ...]],
    ] = {(0, 0, start_server): (1.0, ())}
    representatives: dict[
        str,
        tuple[float, tuple[tuple[str, int, int, bool], ...]],
    ] = {}

    while states:
        nxt: dict[
            tuple[int, int, int],
            tuple[float, tuple[tuple[str, int, int, bool], ...]],
        ] = {}
        for (s1, s2, server), (mass, path) in states.items():
            if s1 >= needed or s2 >= needed:
                match_score = f"{s1}:{s2}"
                previous = representatives.get(match_score)
                if previous is None or mass > previous[0]:
                    representatives[match_score] = (mass, path)
                continue

            for row in set_cache[server]:
                winner = int(row["winner"])
                ns1 = s1 + (1 if winner == 1 else 0)
                ns2 = s2 + (1 if winner == 2 else 0)
                next_server = int(row["next_set_server"])
                child_mass = mass * float(row["probability"])
                child_path = (
                    *path,
                    (
                        str(row["score"]),
                        server,
                        next_server,
                        bool(row["tiebreak"]),
                    ),
                )
                child_state = (ns1, ns2, next_server)
                previous = nxt.get(child_state)
                if previous is None or child_mass > previous[0]:
                    nxt[child_state] = (child_mass, child_path)
        states = nxt

    family_probabilities = match_outcomes(
        p1_serve_point,
        p2_serve_point,
        best_of,
        start_server,
    )
    storylines: list[dict[str, Any]] = []
    for match_score, family_probability in sorted(
        family_probabilities.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        representative = representatives.get(match_score)
        if representative is None:
            continue
        set_sequence_probability, set_path = representative
        representative_sets = []
        representative_exact_path_probability = 1.0
        for score, set_start_server, next_set_server, tiebreak in set_path:
            set_row = _representative_set_progression(
                p1_serve_point,
                p2_serve_point,
                set_start_server,
                score,
            )
            if set_row is None:
                representative_sets = []
                break
            if int(set_row["next_set_server"]) != next_set_server:
                raise AssertionError("representative set serve-order drift")
            if bool(set_row["tiebreak"]) != tiebreak:
                raise AssertionError("representative set tiebreak drift")
            representative_exact_path_probability *= float(
                set_row["representative_path_probability"]
            )
            representative_sets.append(set_row)

        if not representative_sets:
            continue
        s1, s2 = (int(x) for x in match_score.split(":"))
        storylines.append({
            "winner": 1 if s1 > s2 else 2,
            "match_score": match_score,
            "probability": float(family_probability),
            "probability_scope": "MATCH_SCORE_FAMILY",
            "representative_only": True,
            "representative_set_sequence_probability": float(set_sequence_probability),
            "representative_exact_game_path_probability": representative_exact_path_probability,
            "set_scores": [str(row["score"]) for row in representative_sets],
            "sets": representative_sets,
            "sets_played": len(representative_sets),
            "total_games": sum(int(row["games"]) for row in representative_sets),
        })

    total = sum(float(row["probability"]) for row in storylines)
    if storylines and not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise AssertionError(f"storyline family probability mass drift: {total}")
    return storylines



SET_SHAPE_FAMILIES = (
    "DOMINANT",
    "NORMAL",
    "CLOSE",
    "EXTENDED_7_5",
    "TIEBREAK",
)


def set_shape_family(score: str) -> str | None:
    """Map one completed tennis set score to a coarse structural family."""
    try:
        a, b = (int(x) for x in str(score).split(":"))
    except (TypeError, ValueError):
        return None
    hi, lo = max(a, b), min(a, b)
    if hi == 6 and 0 <= lo <= 2:
        return "DOMINANT"
    if hi == 6 and lo == 3:
        return "NORMAL"
    if hi == 6 and lo == 4:
        return "CLOSE"
    if hi == 7 and lo == 5:
        return "EXTENDED_7_5"
    if hi == 7 and lo == 6:
        return "TIEBREAK"
    return None


def _ranked_first_set_shapes(
    p1_serve_point: float,
    p2_serve_point: float,
    start_server: int,
) -> list[dict[str, Any]]:
    """Exact first-set probability aggregated into five shape families."""
    if start_server not in (1, 2):
        raise ValueError("start_server must be 1 or 2")
    mass: dict[str, float] = defaultdict(float)
    representative: dict[str, dict[str, Any]] = {}
    for row in set_outcomes(p1_serve_point, p2_serve_point, start_server):
        shape = set_shape_family(str(row["score"]))
        if shape is None:
            continue
        probability = float(row["probability"])
        mass[shape] += probability
        previous = representative.get(shape)
        if previous is None or probability > float(previous["probability"]):
            representative[shape] = row

    rows = [
        {
            "shape": shape,
            "probability": float(probability),
            "probability_scope": "FIRST_SET_SHAPE_FAMILY",
            "representative_score": str(representative[shape]["score"]),
        }
        for shape, probability in mass.items()
    ]
    rows.sort(key=lambda row: float(row["probability"]), reverse=True)
    total = sum(float(row["probability"]) for row in rows)
    if rows and not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise AssertionError(f"first-set shape probability mass drift: {total}")
    return rows


def _ranked_set_shape_trajectories(
    p1_serve_point: float,
    p2_serve_point: float,
    best_of: int,
    start_server: int,
) -> list[dict[str, Any]]:
    """Exact match distribution aggregated by match score + set-shape sequence.

    Winner order is used internally only to terminate the match correctly.
    The reported probability belongs to the coarse shape sequence, not to the
    representative exact set scores.
    """
    if best_of not in (3, 5):
        raise ValueError("best_of must be 3 or 5")
    if start_server not in (1, 2):
        raise ValueError("start_server must be 1 or 2")

    needed = best_of // 2 + 1
    grouped: dict[int, dict[tuple[int, int, str], dict[str, Any]]] = {1: {}, 2: {}}
    for server in (1, 2):
        for row in set_outcomes(p1_serve_point, p2_serve_point, server):
            shape = set_shape_family(str(row["score"]))
            if shape is None:
                continue
            key = (int(row["winner"]), int(row["next_set_server"]), shape)
            bucket = grouped[server].setdefault(
                key,
                {"probability": 0.0, "representative": None},
            )
            bucket["probability"] += float(row["probability"])
            rep = bucket["representative"]
            if rep is None or float(row["probability"]) > float(rep["probability"]):
                bucket["representative"] = row

    states: dict[
        tuple[int, int, int, tuple[str, ...]],
        tuple[float, float, tuple[str, ...]],
    ] = {(0, 0, start_server, ()): (1.0, 1.0, ())}
    terminal: dict[
        tuple[str, tuple[str, ...]],
        tuple[float, float, tuple[str, ...]],
    ] = {}

    while states:
        nxt: dict[
            tuple[int, int, int, tuple[str, ...]],
            tuple[float, float, tuple[str, ...]],
        ] = {}
        for (s1, s2, server, shapes), (mass, rep_mass, rep_scores) in states.items():
            if s1 >= needed or s2 >= needed:
                key = (f"{s1}:{s2}", shapes)
                previous = terminal.get(key)
                if previous is None:
                    terminal[key] = (mass, rep_mass, rep_scores)
                else:
                    total_mass = previous[0] + mass
                    if rep_mass > previous[1]:
                        terminal[key] = (total_mass, rep_mass, rep_scores)
                    else:
                        terminal[key] = (total_mass, previous[1], previous[2])
                continue

            for (winner, next_server, shape), transition in grouped[server].items():
                probability = float(transition["probability"])
                representative = transition["representative"]
                if probability <= 0.0 or not isinstance(representative, dict):
                    continue
                ns1 = s1 + (1 if winner == 1 else 0)
                ns2 = s2 + (1 if winner == 2 else 0)
                child_shapes = (*shapes, shape)
                child_mass = mass * probability
                child_rep_mass = rep_mass * float(representative["probability"])
                child_rep_scores = (*rep_scores, str(representative["score"]))
                state_key = (ns1, ns2, next_server, child_shapes)
                previous = nxt.get(state_key)
                if previous is None:
                    nxt[state_key] = (child_mass, child_rep_mass, child_rep_scores)
                else:
                    total_mass = previous[0] + child_mass
                    if child_rep_mass > previous[1]:
                        nxt[state_key] = (total_mass, child_rep_mass, child_rep_scores)
                    else:
                        nxt[state_key] = (total_mass, previous[1], previous[2])
        states = nxt

    rows = []
    for (match_score, shapes), (probability, rep_mass, rep_scores) in terminal.items():
        rows.append({
            "match_score": match_score,
            "set_shapes": list(shapes),
            "probability": float(probability),
            "probability_scope": "MATCH_SCORE_SET_SHAPE_SEQUENCE",
            "representative_only": True,
            "representative_set_score_sequence_probability": float(rep_mass),
            "representative_set_scores": list(rep_scores),
            "sets_played": len(shapes),
        })

    rows.sort(key=lambda row: float(row["probability"]), reverse=True)
    match_score_mass: dict[str, float] = defaultdict(float)
    for row in rows:
        match_score_mass[str(row["match_score"])] += float(row["probability"])
    for row in rows:
        family_mass = match_score_mass.get(str(row["match_score"]), 0.0)
        row["conditional_probability_within_match_score"] = (
            float(row["probability"]) / family_mass if family_mass > 0.0 else 0.0
        )

    total = sum(float(row["probability"]) for row in rows)
    if rows and not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise AssertionError(f"set-shape trajectory probability mass drift: {total}")
    return rows


def _ranked_set_winner_trajectories(
    p1_serve_point: float,
    p2_serve_point: float,
    best_of: int,
    start_server: int,
) -> list[dict[str, Any]]:
    """Exact distribution of set-winner order with one representative full path.

    This is deliberately coarser than exact set scores. Probability belongs to
    the complete winner order, for example P1 -> P2 -> P1. Set scores and game
    progressions are representative realizations only.
    """
    if best_of not in (3, 5):
        raise ValueError("best_of must be 3 or 5")
    if start_server not in (1, 2):
        raise ValueError("start_server must be 1 or 2")

    needed = best_of // 2 + 1
    grouped: dict[int, dict[tuple[int, int], dict[str, Any]]] = {1: {}, 2: {}}
    for server in (1, 2):
        for row in set_outcomes(p1_serve_point, p2_serve_point, server):
            key = (int(row["winner"]), int(row["next_set_server"]))
            bucket = grouped[server].setdefault(
                key,
                {"probability": 0.0, "representative": None},
            )
            bucket["probability"] += float(row["probability"])
            rep = bucket["representative"]
            if rep is None or float(row["probability"]) > float(rep["probability"]):
                bucket["representative"] = row

    # key -> (total probability mass, representative exact-set-score mass, path)
    states: dict[
        tuple[int, int, int, tuple[int, ...]],
        tuple[float, float, tuple[tuple[str, int, int, bool], ...]],
    ] = {(0, 0, start_server, ()): (1.0, 1.0, ())}
    terminal: dict[
        tuple[int, ...],
        tuple[float, float, tuple[tuple[str, int, int, bool], ...]],
    ] = {}

    while states:
        nxt: dict[
            tuple[int, int, int, tuple[int, ...]],
            tuple[float, float, tuple[tuple[str, int, int, bool], ...]],
        ] = {}
        for (s1, s2, server, sequence), (mass, rep_mass, rep_path) in states.items():
            if s1 >= needed or s2 >= needed:
                previous = terminal.get(sequence)
                if previous is None:
                    terminal[sequence] = (mass, rep_mass, rep_path)
                else:
                    total_mass = previous[0] + mass
                    if rep_mass > previous[1]:
                        terminal[sequence] = (total_mass, rep_mass, rep_path)
                    else:
                        terminal[sequence] = (total_mass, previous[1], previous[2])
                continue

            for (winner, next_server), transition in grouped[server].items():
                transition_probability = float(transition["probability"])
                representative = transition["representative"]
                if transition_probability <= 0.0 or not isinstance(representative, dict):
                    continue
                ns1 = s1 + (1 if winner == 1 else 0)
                ns2 = s2 + (1 if winner == 2 else 0)
                child_sequence = (*sequence, winner)
                child_mass = mass * transition_probability
                child_rep_mass = rep_mass * float(representative["probability"])
                child_path = (
                    *rep_path,
                    (
                        str(representative["score"]),
                        server,
                        next_server,
                        bool(representative["tiebreak"]),
                    ),
                )
                state_key = (ns1, ns2, next_server, child_sequence)
                previous = nxt.get(state_key)
                if previous is None:
                    nxt[state_key] = (child_mass, child_rep_mass, child_path)
                else:
                    total_mass = previous[0] + child_mass
                    if child_rep_mass > previous[1]:
                        nxt[state_key] = (total_mass, child_rep_mass, child_path)
                    else:
                        nxt[state_key] = (total_mass, previous[1], previous[2])
        states = nxt

    rows: list[dict[str, Any]] = []
    for sequence, (probability, set_score_path_probability, set_path) in terminal.items():
        representative_sets = []
        representative_exact_path_probability = 1.0
        for score, set_start_server, next_set_server, tiebreak in set_path:
            set_row = _representative_set_progression(
                p1_serve_point,
                p2_serve_point,
                set_start_server,
                score,
            )
            if set_row is None:
                representative_sets = []
                break
            if int(set_row["next_set_server"]) != next_set_server:
                raise AssertionError("set-winner trajectory serve-order drift")
            if bool(set_row["tiebreak"]) != tiebreak:
                raise AssertionError("set-winner trajectory tiebreak drift")
            representative_exact_path_probability *= float(
                set_row["representative_path_probability"]
            )
            representative_sets.append(set_row)

        if not representative_sets:
            continue
        p1_sets = sum(1 for winner in sequence if winner == 1)
        p2_sets = len(sequence) - p1_sets
        rows.append({
            "winner": 1 if p1_sets > p2_sets else 2,
            "match_score": f"{p1_sets}:{p2_sets}",
            "set_winners": list(sequence),
            "probability": float(probability),
            "probability_scope": "SET_WINNER_SEQUENCE",
            "representative_only": True,
            "representative_set_score_sequence_probability": float(set_score_path_probability),
            "representative_exact_game_path_probability": representative_exact_path_probability,
            "set_scores": [str(row["score"]) for row in representative_sets],
            "sets": representative_sets,
            "sets_played": len(representative_sets),
            "total_games": sum(int(row["games"]) for row in representative_sets),
        })

    rows.sort(key=lambda row: float(row["probability"]), reverse=True)

    match_score_mass: dict[str, float] = defaultdict(float)
    for row in rows:
        match_score_mass[str(row["match_score"])] += float(row["probability"])
    for row in rows:
        family_mass = match_score_mass.get(str(row["match_score"]), 0.0)
        row["conditional_probability_within_match_score"] = (
            float(row["probability"]) / family_mass if family_mass > 0.0 else 0.0
        )

    total = sum(float(row["probability"]) for row in rows)
    if rows and not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise AssertionError(f"set-winner trajectory probability mass drift: {total}")
    return rows


def _top_match_set_paths(
    p1_serve_point: float,
    p2_serve_point: float,
    best_of: int,
    start_server: int,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Exact top-K set-score sequences for one known starting server."""
    if best_of not in (3, 5):
        raise ValueError("best_of must be 3 or 5")
    if start_server not in (1, 2):
        raise ValueError("start_server must be 1 or 2")
    if limit <= 0:
        return []

    needed = best_of // 2 + 1
    set_cache = {
        1: set_outcomes(p1_serve_point, p2_serve_point, 1),
        2: set_outcomes(p1_serve_point, p2_serve_point, 2),
    }
    heap: list[tuple[float, int, int, int, int, tuple[str, ...], int, int]] = []
    serial = 0
    heapq.heappush(heap, (-1.0, serial, 0, 0, start_server, (), 0, 0))
    out: list[dict[str, Any]] = []

    while heap and len(out) < limit:
        neg_mass, _serial, s1, s2, server, path, total_games, tiebreak_sets = heapq.heappop(heap)
        mass = -neg_mass

        if s1 >= needed or s2 >= needed:
            out.append({
                "winner": 1 if s1 > s2 else 2,
                "match_score": f"{s1}:{s2}",
                "set_scores": list(path),
                "sets_played": s1 + s2,
                "total_games": total_games,
                "tiebreak_sets": tiebreak_sets,
                "probability": mass,
            })
            continue

        for row in set_cache[server]:
            ns1 = s1 + (1 if row["winner"] == 1 else 0)
            ns2 = s2 + (1 if row["winner"] == 2 else 0)
            child_mass = mass * float(row["probability"])
            serial += 1
            heapq.heappush(
                heap,
                (
                    -child_mass,
                    serial,
                    ns1,
                    ns2,
                    int(row["next_set_server"]),
                    (*path, str(row["score"])),
                    total_games + int(row["games"]),
                    tiebreak_sets + (1 if row["tiebreak"] else 0),
                ),
            )

    return sorted(out, key=lambda row: float(row["probability"]), reverse=True)


def _top_full_match_game_paths(
    p1_serve_point: float,
    p2_serve_point: float,
    best_of: int,
    start_server: int,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """Exact top-K complete match paths at game resolution.

    Each path preserves every game score inside every set. The search is
    best-first over exact game transitions, so completed paths are emitted in
    descending probability for a known first server.
    """
    if best_of not in (3, 5):
        raise ValueError("best_of must be 3 or 5")
    if start_server not in (1, 2):
        raise ValueError("start_server must be 1 or 2")
    if limit <= 0:
        return []

    p1_hold = hold_probability(p1_serve_point)
    p2_hold = hold_probability(p2_serve_point)
    p1_tb = neutral_tiebreak_win_probability(p1_serve_point, p2_serve_point)
    needed = best_of // 2 + 1

    # Heap tuple order keeps the unique serial before path payloads so Python
    # never needs to compare nested tuples when probabilities tie.
    heap: list[tuple[
        float, int, int, int, int, int, int,
        tuple[str, ...], tuple[tuple[str, tuple[str, ...], bool], ...]
    ]] = []
    serial = 0
    heapq.heappush(
        heap,
        (-1.0, serial, 0, 0, 0, 0, start_server, (), ()),
    )
    out: list[dict[str, Any]] = []

    while heap and len(out) < limit:
        (
            neg_mass,
            _serial,
            s1,
            s2,
            g1,
            g2,
            server,
            current_set_path,
            completed_sets,
        ) = heapq.heappop(heap)
        mass = -neg_mass

        if s1 >= needed or s2 >= needed:
            sets = [
                {
                    "score": score,
                    "progression": list(progression),
                    "tiebreak": tiebreak,
                }
                for score, progression, tiebreak in completed_sets
            ]
            out.append({
                "winner": 1 if s1 > s2 else 2,
                "match_score": f"{s1}:{s2}",
                "sets": sets,
                "sets_played": len(sets),
                "total_games": sum(len(row["progression"]) for row in sets),
                "probability": mass,
            })
            continue

        if g1 == 6 and g2 == 6:
            next_set_server = _other(server)
            for winner, probability in ((1, p1_tb), (2, 1.0 - p1_tb)):
                final_score = "7:6" if winner == 1 else "6:7"
                ns1 = s1 + (1 if winner == 1 else 0)
                ns2 = s2 + (1 if winner == 2 else 0)
                final_path = (*current_set_path, final_score)
                new_completed = (*completed_sets, (final_score, final_path, True))
                serial += 1
                heapq.heappush(
                    heap,
                    (
                        -(mass * probability),
                        serial,
                        ns1,
                        ns2,
                        0,
                        0,
                        next_set_server,
                        (),
                        new_completed,
                    ),
                )
            continue

        if (g1 >= 6 or g2 >= 6) and abs(g1 - g2) >= 2:
            set_winner = 1 if g1 > g2 else 2
            final_score = f"{g1}:{g2}"
            ns1 = s1 + (1 if set_winner == 1 else 0)
            ns2 = s2 + (1 if set_winner == 2 else 0)
            new_completed = (*completed_sets, (final_score, current_set_path, False))
            serial += 1
            heapq.heappush(
                heap,
                (
                    -mass,
                    serial,
                    ns1,
                    ns2,
                    0,
                    0,
                    server,
                    (),
                    new_completed,
                ),
            )
            continue

        p1_game = _game_win_probability_for_p1(p1_hold, p2_hold, server)
        next_server = _other(server)
        for ng1, ng2, probability in (
            (g1 + 1, g2, p1_game),
            (g1, g2 + 1, 1.0 - p1_game),
        ):
            serial += 1
            score = f"{ng1}:{ng2}"
            heapq.heappush(
                heap,
                (
                    -(mass * probability),
                    serial,
                    s1,
                    s2,
                    ng1,
                    ng2,
                    next_server,
                    (*current_set_path, score),
                    completed_sets,
                ),
            )

    return sorted(out, key=lambda row: float(row["probability"]), reverse=True)


def trajectory_summary(
    p1_serve_point: float,
    p2_serve_point: float,
    best_of: int,
) -> dict[str, Any]:
    checkpoints = {}
    for games in (2, 4, 6):
        neutral: dict[str, float] = defaultdict(float)
        for start_server in (1, 2):
            for score, probability in score_distribution_after_games(
                p1_serve_point,
                p2_serve_point,
                games,
                start_server,
            ).items():
                neutral[score] += 0.5 * probability
        ranked = sorted(neutral.items(), key=lambda item: item[1], reverse=True)
        checkpoints[f"after_{games}_games"] = [
            {"score": score, "probability": probability}
            for score, probability in ranked
        ]

    conditioned = {}
    for start_server, label in ((1, "p1_serves_first"), (2, "p2_serves_first")):
        conditioned[label] = {
            "start_server": start_server,
            "first_set_top_game_paths": _top_first_set_game_paths(
                p1_serve_point,
                p2_serve_point,
                start_server,
                limit=8,
            ),
            "match_top_set_paths": _top_match_set_paths(
                p1_serve_point,
                p2_serve_point,
                best_of,
                start_server,
                limit=12,
            ),
            "match_storylines": _ranked_match_storylines(
                p1_serve_point,
                p2_serve_point,
                best_of,
                start_server,
            ),
            "first_set_shape_families": _ranked_first_set_shapes(
                p1_serve_point,
                p2_serve_point,
                start_server,
            ),
            "set_shape_trajectories": _ranked_set_shape_trajectories(
                p1_serve_point,
                p2_serve_point,
                best_of,
                start_server,
            ),
            "set_winner_trajectories": _ranked_set_winner_trajectories(
                p1_serve_point,
                p2_serve_point,
                best_of,
                start_server,
            ),
            "full_match_top_game_paths": _top_full_match_game_paths(
                p1_serve_point,
                p2_serve_point,
                best_of,
                start_server,
                limit=4,
            ),
        }

    return {
        "status": "SHADOW_TRAJECTORY_FOUNDATION",
        "validation_status": "UNVALIDATED_MATCH_LEVEL",
        "checkpoints_neutral_start_server": checkpoints,
        "serve_order_conditioned": conditioned,
        "contract": {
            "not_a_single_certain_script": True,
            "ranked_paths_are_exact_within_known_start_server_condition": True,
            "pre_match_start_server_unknown": True,
            "checkpoint_distributions_average_both_start_servers": True,
            "full_match_set_sequence_is_ranked_not_guaranteed": True,
            "first_set_game_progression_is_ranked_not_guaranteed": True,
            "full_match_game_progression_is_ranked_not_guaranteed": True,
            "full_match_game_paths_are_exact_for_known_start_server": True,
            "primary_storyline_probability_scope": "MATCH_SCORE_FAMILY",
            "set_shape_taxonomy": list(SET_SHAPE_FAMILIES),
            "set_shape_probability_scope": "MATCH_SCORE_SET_SHAPE_SEQUENCE",
            "set_shape_conditional_scope": "WITHIN_MATCH_SCORE_FAMILY",
            "set_winner_trajectory_probability_scope": "SET_WINNER_SEQUENCE",
            "set_winner_trajectory_conditional_scope": "WITHIN_MATCH_SCORE_FAMILY",
            "set_winner_trajectory_game_progressions_are_representative": True,
            "storyline_game_progressions_are_representative": True,
            "storyline_probability_never_claims_exact_game_path": True,
            "exact_full_match_game_paths_are_diagnostic_only": True,
            "production_influence": False,
            "symphony2_influence": False,
            "superbet_playable_influence": False,
        },
    }


def set_outcomes(
    p1_serve_point: float,
    p2_serve_point: float,
    start_server: int,
) -> list[dict[str, Any]]:
    """Exact game-level set distribution with a serve-order-neutral tiebreak."""
    if start_server not in (1, 2):
        raise ValueError("start_server must be 1 or 2")

    p1_hold = hold_probability(p1_serve_point)
    p2_hold = hold_probability(p2_serve_point)
    p1_tb = neutral_tiebreak_win_probability(p1_serve_point, p2_serve_point)

    live: dict[tuple[int, int, int], float] = {(0, 0, start_server): 1.0}
    outcomes: list[dict[str, Any]] = []

    while live:
        nxt: dict[tuple[int, int, int], float] = defaultdict(float)
        for (g1, g2, server), mass in live.items():
            if mass <= 0.0:
                continue

            if g1 == 6 and g2 == 6:
                next_set_server = _other(server)
                outcomes.append({
                    "winner": 1,
                    "score": "7:6",
                    "games": 13,
                    "tiebreak": True,
                    "next_set_server": next_set_server,
                    "probability": mass * p1_tb,
                })
                outcomes.append({
                    "winner": 2,
                    "score": "6:7",
                    "games": 13,
                    "tiebreak": True,
                    "next_set_server": next_set_server,
                    "probability": mass * (1.0 - p1_tb),
                })
                continue

            if (g1 >= 6 or g2 >= 6) and abs(g1 - g2) >= 2:
                outcomes.append({
                    "winner": 1 if g1 > g2 else 2,
                    "score": f"{g1}:{g2}",
                    "games": g1 + g2,
                    "tiebreak": False,
                    "next_set_server": server,
                    "probability": mass,
                })
                continue

            p1_game = _game_win_probability_for_p1(p1_hold, p2_hold, server)
            next_server = _other(server)
            nxt[(g1 + 1, g2, next_server)] += mass * p1_game
            nxt[(g1, g2 + 1, next_server)] += mass * (1.0 - p1_game)

        live = nxt

    total = sum(row["probability"] for row in outcomes)
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-10):
        raise AssertionError(f"set probability mass drift: {total}")
    return outcomes


def early_equal_score_probability(
    p1_serve_point: float,
    p2_serve_point: float,
    games: int,
    start_server: int,
) -> float:
    if games not in (2, 4, 6):
        raise ValueError("games must be 2, 4 or 6")
    target = f"{games // 2}:{games // 2}"
    return float(
        score_distribution_after_games(
            p1_serve_point,
            p2_serve_point,
            games,
            start_server,
        ).get(target, 0.0)
    )


def _neutral_set_distribution(p1_serve_point: float, p2_serve_point: float) -> list[dict[str, Any]]:
    combined: dict[tuple[int, str, int, bool, int], float] = defaultdict(float)
    for start_server in (1, 2):
        for row in set_outcomes(p1_serve_point, p2_serve_point, start_server):
            key = (
                int(row["winner"]),
                str(row["score"]),
                int(row["games"]),
                bool(row["tiebreak"]),
                int(row["next_set_server"]),
            )
            combined[key] += 0.5 * float(row["probability"])

    rows = [
        {
            "winner": winner,
            "score": score,
            "games": games,
            "tiebreak": tiebreak,
            "next_set_server": next_server,
            "probability": probability,
        }
        for (winner, score, games, tiebreak, next_server), probability in combined.items()
    ]
    total = sum(row["probability"] for row in rows)
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-10):
        raise AssertionError(f"neutral set probability mass drift: {total}")
    return rows


def match_outcomes(
    p1_serve_point: float,
    p2_serve_point: float,
    best_of: int,
    start_server: int,
) -> dict[str, float]:
    if best_of not in (3, 5):
        raise ValueError("best_of must be 3 or 5")
    if start_server not in (1, 2):
        raise ValueError("start_server must be 1 or 2")

    needed = best_of // 2 + 1
    states: dict[tuple[int, int, int], float] = {(0, 0, start_server): 1.0}
    exact: dict[str, float] = defaultdict(float)

    while states:
        nxt: dict[tuple[int, int, int], float] = defaultdict(float)
        for (s1, s2, server), mass in states.items():
            if s1 >= needed or s2 >= needed:
                exact[f"{s1}:{s2}"] += mass
                continue

            for set_row in set_outcomes(p1_serve_point, p2_serve_point, server):
                if set_row["winner"] == 1:
                    ns1, ns2 = s1 + 1, s2
                else:
                    ns1, ns2 = s1, s2 + 1
                nxt[(ns1, ns2, int(set_row["next_set_server"]))] += mass * float(set_row["probability"])
        states = nxt

    total = sum(exact.values())
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise AssertionError(f"match probability mass drift: {total}")
    return dict(exact)


def simulate_match(
    p1_serve_point: float,
    p2_serve_point: float,
    best_of: int = 3,
) -> dict[str, Any]:
    p1s = _clamp_probability(p1_serve_point)
    p2s = _clamp_probability(p2_serve_point)

    p1_hold = hold_probability(p1s)
    p2_hold = hold_probability(p2s)
    first_set_rows = _neutral_set_distribution(p1s, p2s)

    first_set_exact: dict[str, float] = defaultdict(float)
    first_set_games: dict[int, float] = defaultdict(float)
    p1_set = 0.0
    tiebreak = 0.0
    for row in first_set_rows:
        probability = float(row["probability"])
        first_set_exact[str(row["score"])] += probability
        first_set_games[int(row["games"])] += probability
        if row["winner"] == 1:
            p1_set += probability
        if row["tiebreak"]:
            tiebreak += probability

    early = {}
    for games, label in ((2, "1:1"), (4, "2:2"), (6, "3:3")):
        early[label] = 0.5 * (
            early_equal_score_probability(p1s, p2s, games, 1)
            + early_equal_score_probability(p1s, p2s, games, 2)
        )

    exact_match: dict[str, float] = defaultdict(float)
    for start_server in (1, 2):
        for score, probability in match_outcomes(p1s, p2s, best_of, start_server).items():
            exact_match[score] += 0.5 * probability

    needed = best_of // 2 + 1
    p1_match = sum(
        probability
        for score, probability in exact_match.items()
        if int(score.split(":")[0]) == needed
    )

    total_sets: dict[str, float] = defaultdict(float)
    for score, probability in exact_match.items():
        a, b = (int(x) for x in score.split(":"))
        total_sets[str(a + b)] += probability

    over_lines = {}
    for line in (8.5, 9.5, 10.5, 11.5, 12.5):
        over_lines[str(line)] = sum(
            probability for games, probability in first_set_games.items() if games > line
        )

    return {
        "mode": MODE,
        "validation_status": "UNVALIDATED_MATCH_LEVEL",
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "assumptions": {
            "point_independence_within_server": True,
            "serve_order_neutral_pre_match": True,
            "tiebreak_method": "neutral_average_point_probability_exact_first_to_7_by_2",
        },
        "point_probabilities": {
            "p1_serve_point_win": p1s,
            "p2_serve_point_win": p2s,
        },
        "hold_probabilities": {
            "p1_hold": p1_hold,
            "p2_hold": p2_hold,
        },
        "trajectory": trajectory_summary(p1s, p2s, best_of),
        "early_equal_score": early,
        "first_set": {
            "p1_win": p1_set,
            "p2_win": 1.0 - p1_set,
            "tiebreak": tiebreak,
            "exact_score": dict(sorted(first_set_exact.items())),
            "games_distribution": {str(k): v for k, v in sorted(first_set_games.items())},
            "over": over_lines,
        },
        "match": {
            "best_of": best_of,
            "p1_win": p1_match,
            "p2_win": 1.0 - p1_match,
            "exact_score": dict(sorted(exact_match.items())),
            "total_sets": dict(sorted(total_sets.items())),
        },
    }


def simulate_current_report(
    current: dict[str, Any],
    calibration_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    matches = current.get("matches") if isinstance(current, dict) else None
    matches = matches if isinstance(matches, list) else []

    calibrator = _promising_calibration(calibration_report)
    out_rows = []
    calibrated_count = 0
    for row in matches:
        if not isinstance(row, dict) or row.get("status") != "SHADOW_SCORED":
            continue
        p1s = row.get("p1_serve_point_win_probability")
        p2s = row.get("p2_serve_point_win_probability")
        if p1s is None or p2s is None:
            continue

        best_of = row.get("best_of")
        if not isinstance(best_of, int) or isinstance(best_of, bool):
            best_of = 3

        simulation = simulate_match(float(p1s), float(p2s), best_of=best_of)
        calibrated_candidate = None
        if calibrator is not None:
            calibrated_candidate = simulate_match_with_hold_calibration(
                float(p1s),
                float(p2s),
                calibrator,
                best_of=best_of,
            )
            calibrated_count += 1

        out_rows.append({
            "match_id": row.get("match_id"),
            "scheduled_time": row.get("scheduled_time"),
            "tour": row.get("tour"),
            "surface": row.get("surface"),
            "p1": row.get("p1"),
            "p2": row.get("p2"),
            "p1_id": row.get("p1_id"),
            "p2_id": row.get("p2_id"),
            "support": row.get("support"),
            "source_model_fingerprint_sha256": row.get("model_fingerprint_sha256"),
            "production_influence": False,
            "validation_status": "UNVALIDATED_MATCH_LEVEL",
            "simulation": simulation,
            "hold_calibrated_candidate": calibrated_candidate,
        })

    return {
        "version": VERSION,
        "mode": MODE,
        "source_current_version": current.get("version") if isinstance(current, dict) else None,
        "production_influence": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "match_level_validation_required": True,
        "auto_promote": False,
        "hold_calibration_candidate_enabled": calibrator is not None,
        "calibrated_candidate_matches": calibrated_count,
        "hold_calibration_source": {
            "version": calibration_report.get("version") if isinstance(calibration_report, dict) else None,
            "signal": calibration_report.get("signal") if isinstance(calibration_report, dict) else None,
            "status": calibration_report.get("status") if isinstance(calibration_report, dict) else None,
        },
        "market_policy": {
            "raw_iid_remains_reference": True,
            "hold_calibrated_is_candidate_only": True,
            "duration_markets": "COMPARE_RAW_VS_HOLD_CALIBRATED",
            "winner_markets": "NO_AUTOMATIC_SWITCH",
            "exact_score_markets": "NO_AUTOMATIC_SWITCH",
        },
        "source_scored_matches": sum(
            1 for row in matches if isinstance(row, dict) and row.get("status") == "SHADOW_SCORED"
        ),
        "simulated_matches": len(out_rows),
        "matches": out_rows,
    }


def build() -> dict[str, Any]:
    try:
        current = json.loads(CURRENT.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        current = {}

    try:
        calibration_report = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        calibration_report = {}

    report = simulate_current_report(current, calibration_report=calibration_report)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": report["version"],
        "mode": report["mode"],
        "source_scored_matches": report["source_scored_matches"],
        "simulated_matches": report["simulated_matches"],
        "match_level_validation_required": report["match_level_validation_required"],
        "hold_calibration_candidate_enabled": report["hold_calibration_candidate_enabled"],
        "calibrated_candidate_matches": report["calibrated_candidate_matches"],
        "production_influence": report["production_influence"],
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
