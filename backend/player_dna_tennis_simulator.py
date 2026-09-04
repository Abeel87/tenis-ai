from __future__ import annotations

"""Deterministic SHADOW tennis simulator driven by Player DNA point probabilities.

This layer converts pre-match serve-point probabilities into game/set/match
distributions. Match-level outputs are deliberately marked UNVALIDATED until a
separate historical backtest proves calibration. Nothing here may influence
PROD, Symfonia 2.0 or Superbet PLAYABLE.
"""

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

    target = games // 2
    return sum(mass for (g1, g2, _server), mass in states.items() if g1 == target and g2 == target)


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
