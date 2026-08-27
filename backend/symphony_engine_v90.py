from __future__ import annotations

"""Tenis AI v9.0 — Tennis Symphony scenario engine.

Symfonia is an additive analysis layer. It consumes existing PROD and SHADOW
outputs, builds an exact tennis state distribution when the service model is
available, and searches for coherent multi-market stories.

Hard contract:
- never edits RAW Ensemble;
- never edits Adaptive final_score;
- never auto-promotes SHADOW;
- SHADOW is supporting evidence only;
- a displayed joint probability is emitted only when every selected leg can be
  evaluated against the same exact state distribution.
"""

from collections import defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import unicodedata
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
RESULTS = OUT / "results.json"
SHADOW = OUT / "shadow_signals_v894.json"
REPORT = OUT / "symphony_v90.json"

VERSION = "v9.0B"
MODE = "ANALYSIS_ONLY"
CHECKPOINTS = (2, 4, 6)
EPS = 1e-12
SHADOW_WEIGHT_CAP = 0.20
BEAM_WIDTH = 120
POOL_LIMIT = 28


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


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


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", _ascii(value))


def _canonical_market(value: Any) -> str:
    x = _ascii(value).replace("-", "_").replace(" ", "_")
    aliases = {
        "match_win": "match_winner",
        "winner": "match_winner",
        "set1_win": "set1_winner",
        "first_set_win": "set1_winner",
        "set_1_winner": "set1_winner",
        "set2_win": "set2_winner",
        "second_set_win": "set2_winner",
        "set3_win": "set3_winner",
        "third_set_win": "set3_winner",
        "state": "game_state",
        "gamestate": "game_state",
        "sets_total": "total_sets",
        "set_total": "total_sets",
        "correct_score": "exact_match_score",
        "match_score": "exact_match_score",
        "exact_score": "exact_match_score",
        "set1_score": "set1_exact_score",
        "first_set_score": "set1_exact_score",
        "tie_break": "set1_tiebreak",
        "tiebreak": "set1_tiebreak",
        "tie_break_set1": "set1_tiebreak",
        "set1_tie_break": "set1_tiebreak",
    }
    return aliases.get(x, x or "other")


def _match_key(match: dict) -> str:
    mid = match.get("match_id") if match.get("match_id") is not None else match.get("id")
    if mid is not None and str(mid) != "":
        return f"id:{mid}"
    return "|".join([
        _ascii(match.get("p1")),
        _ascii(match.get("p2")),
        str(match.get("scheduled_time") or "")[:10],
        _ascii(match.get("tournament")),
    ])


def _signal_key(signal: dict) -> str:
    return str(signal.get("key") or signal.get("signal_key") or signal.get("id") or "")


def _line(signal: dict):
    x = _num(signal.get("line"), _num(signal.get("selected_line"), _num(signal.get("suggested_line"))))
    if x is not None:
        return x
    parts = _signal_key(signal).split("|")
    for part in parts[1:]:
        x = _num(part)
        if x is not None and ":" not in part:
            return x
    return None


def _checkpoint(signal: dict):
    cp = _num(signal.get("checkpoint"))
    if cp in CHECKPOINTS:
        return int(cp)
    key = _ascii(_signal_key(signal))
    market = _canonical_market(signal.get("market"))
    m = re.search(r"(?:state|game_state)[_|-]?([246])", key)
    if m:
        return int(m.group(1))
    if market == "game_state":
        for c in CHECKPOINTS:
            if f"|{c}|" in _signal_key(signal):
                return c
    return None


def _prod_score(signal: dict):
    prod = signal.get("adaptive_prod_v79") or {}
    for candidate in (
        prod.get("final_score"),
        signal.get("adaptive_prod"),
        signal.get("final_score"),
        signal.get("ensemble"),
        (signal.get("model_scores") or {}).get("ensemble"),
        signal.get("score"),
        signal.get("v"),
        signal.get("value"),
    ):
        x = _num(candidate)
        if x is not None:
            return max(0.0, min(100.0, x))
    return None


def _shadow_index(shadow_report: dict) -> dict[str, dict[str, dict[str, float]]]:
    out: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for match in shadow_report.get("matches") or []:
        if not isinstance(match, dict):
            continue
        mk = str(match.get("match_key") or _match_key(match))
        for signal in match.get("signals") or []:
            if not isinstance(signal, dict):
                continue
            sk = _signal_key(signal)
            scores = {
                str(model): float(score)
                for model, score in (signal.get("scores") or {}).items()
                if _num(score) is not None
            }
            if sk and scores:
                out[mk][sk] = scores
    return out


def _tb_p1(h1: float, h2: float) -> float:
    strength = (float(h1) + (1.0 - float(h2))) / 2.0
    x = 1.0 / (1.0 + math.exp(-(strength - 0.5) * 8.0))
    return max(0.20, min(0.80, x))


def _set_paths_one_order(h1: float, h2: float, p1_serves_first: bool) -> dict[tuple, float]:
    """Exact first-set path distribution retaining score after 2/4/6 games."""
    # state: games_a, games_b, cp2a,cp2b, cp4a,cp4b, cp6a,cp6b
    live = {(0, 0, -1, -1, -1, -1, -1, -1): 1.0}
    terminal: dict[tuple, float] = defaultdict(float)
    tb = _tb_p1(h1, h2)

    while live:
        nxt: dict[tuple, float] = defaultdict(float)
        for state, prob in live.items():
            a, b, c2a, c2b, c4a, c4b, c6a, c6b = state
            if a == 6 and b == 6:
                terminal[(c2a, c2b, c4a, c4b, c6a, c6b, 7, 6)] += prob * tb
                terminal[(c2a, c2b, c4a, c4b, c6a, c6b, 6, 7)] += prob * (1.0 - tb)
                continue
            if (a >= 6 or b >= 6) and abs(a - b) >= 2:
                terminal[(c2a, c2b, c4a, c4b, c6a, c6b, a, b)] += prob
                continue

            games_played = a + b
            p1_serves = p1_serves_first if games_played % 2 == 0 else not p1_serves_first
            p1_game = h1 if p1_serves else 1.0 - h2
            for p1_wins, branch in ((True, p1_game), (False, 1.0 - p1_game)):
                na = a + int(p1_wins)
                nb = b + int(not p1_wins)
                nc2a, nc2b, nc4a, nc4b, nc6a, nc6b = c2a, c2b, c4a, c4b, c6a, c6b
                played = na + nb
                if played == 2:
                    nc2a, nc2b = na, nb
                elif played == 4:
                    nc4a, nc4b = na, nb
                elif played == 6:
                    nc6a, nc6b = na, nb
                nxt[(na, nb, nc2a, nc2b, nc4a, nc4b, nc6a, nc6b)] += prob * branch
        live = nxt

    total = sum(terminal.values())
    return {k: v / total for k, v in terminal.items()} if total > 0 else {}


def _first_set_paths(h1: float, h2: float) -> dict[tuple, float]:
    a = _set_paths_one_order(h1, h2, True)
    b = _set_paths_one_order(h1, h2, False)
    out = {k: (a.get(k, 0.0) + b.get(k, 0.0)) / 2.0 for k in set(a) | set(b)}
    total = sum(out.values())
    return {k: v / total for k, v in out.items()} if total > 0 else {}


def _terminal_set_distribution(h1: float, h2: float) -> dict[tuple[int, int], float]:
    out: dict[tuple[int, int], float] = defaultdict(float)
    for path, prob in _first_set_paths(h1, h2).items():
        a, b = path[-2], path[-1]
        out[(a, b)] += prob
    total = sum(out.values())
    return {k: v / total for k, v in out.items()} if total > 0 else {}


def _winner_marginal(distribution: dict[tuple, float], score_indexes=(-2, -1)) -> float:
    ia, ib = score_indexes
    return sum(prob for key, prob in distribution.items() if key[ia] > key[ib])


def _reweight_winner(distribution: dict[tuple, float], target_p1: float | None, score_indexes=(-2, -1)) -> dict[tuple, float]:
    if target_p1 is None or not distribution:
        return dict(distribution)
    raw = _winner_marginal(distribution, score_indexes)
    if raw <= EPS or raw >= 1.0 - EPS:
        return dict(distribution)
    ia, ib = score_indexes
    out = {}
    for key, prob in distribution.items():
        if key[ia] > key[ib]:
            out[key] = prob * target_p1 / raw
        else:
            out[key] = prob * (1.0 - target_p1) / (1.0 - raw)
    total = sum(out.values())
    return {k: v / total for k, v in out.items()} if total > 0 else dict(distribution)


def _market_player_prob(obj: Any, player: str):
    if not isinstance(obj, dict):
        return None
    if player in obj:
        return _prob(obj.get(player))
    target = _ascii(player)
    for key, value in obj.items():
        if _ascii(key) == target:
            return _prob(value)
    return None


def _set_target(match: dict, set_no: int):
    p1 = str(match.get("p1") or "")
    keys = {
        1: ("first_set_win", "set1_win", "set1_winner"),
        2: ("second_set_win", "set2_win", "set2_winner"),
        3: ("third_set_win", "set3_win", "set3_winner"),
        4: ("fourth_set_win", "set4_win", "set4_winner"),
        5: ("fifth_set_win", "set5_win", "set5_winner"),
    }.get(set_no, ())
    for key in keys:
        p = _market_player_prob(match.get(key), p1)
        if p is not None:
            return p
    return _market_player_prob(match.get("first_set_win"), p1)


def _service_holds(match: dict):
    service = match.get("service_model") or {}
    h1 = _prob(service.get("p1_hold"))
    h2 = _prob(service.get("p2_hold"))
    if h1 is None or h2 is None:
        return None
    if not (0.01 < h1 < 0.99 and 0.01 < h2 < 0.99):
        return None
    return h1, h2


def _best_of(match: dict) -> int:
    x = int(_num(match.get("best_of"), 3) or 3)
    return 5 if x >= 5 else 3


def _build_outcomes(match: dict) -> list[dict]:
    holds = _service_holds(match)
    if not holds:
        return []
    h1, h2 = holds
    best_of = _best_of(match)
    need = best_of // 2 + 1

    first = _reweight_winner(_first_set_paths(h1, h2), _set_target(match, 1))
    later = {
        n: _reweight_winner(_terminal_set_distribution(h1, h2), _set_target(match, n), score_indexes=(0, 1))
        for n in range(2, best_of + 1)
    }

    agg: dict[tuple, float] = defaultdict(float)
    for path, p0 in first.items():
        c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b = path
        sa, sb = (1, 0) if s1a > s1b else (0, 1)
        tg = s1a + s1b
        if sa >= need or sb >= need:
            key = (c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b, sa, sb, tg)
            agg[key] += p0
            continue

        frontier = {(sa, sb, tg): p0}
        for set_no in range(2, best_of + 1):
            nxt: dict[tuple[int, int, int], float] = defaultdict(float)
            for (xa, xb, games), prob in frontier.items():
                if xa >= need or xb >= need:
                    nxt[(xa, xb, games)] += prob
                    continue
                for (ga, gb), sp in later[set_no].items():
                    na, nb = xa + int(ga > gb), xb + int(gb > ga)
                    nxt[(na, nb, games + ga + gb)] += prob * sp
            frontier = nxt
            if all(xa >= need or xb >= need for xa, xb, _ in frontier):
                break
        for (xa, xb, games), prob in frontier.items():
            if xa < need and xb < need:
                continue
            key = (c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b, xa, xb, games)
            agg[key] += prob

    total = sum(agg.values())
    outcomes = []
    if total <= 0:
        return outcomes
    for key, prob in agg.items():
        c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b, sa, sb, games = key
        outcomes.append({
            "cp2": (c2a, c2b),
            "cp4": (c4a, c4b),
            "cp6": (c6a, c6b),
            "set1": (s1a, s1b),
            "sets": (sa, sb),
            "total_games": int(games),
            "set_count": int(sa + sb),
            "winner": 1 if sa > sb else 2,
            "set1_winner": 1 if s1a > s1b else 2,
            "set1_tiebreak": {s1a, s1b} == {6, 7},
            "prob": prob / total,
        })
    return outcomes


def _score_pair(value: Any):
    m = re.search(r"(\d+)\s*[:\-]\s*(\d+)", str(value or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _side_for_pick(match: dict, pick: Any):
    p = _ascii(pick)
    if p in {_ascii(match.get("p1")), "1", "p1", "player1"}:
        return 1
    if p in {_ascii(match.get("p2")), "2", "p2", "player2"}:
        return 2
    return None


def _ou_side(pick: Any):
    p = _ascii(pick).replace(" ", "")
    if p in {"over", "o", "powyzej", "wiecej"}:
        return "over"
    if p in {"under", "u", "ponizej", "mniej"}:
        return "under"
    return None


def _yes_no(pick: Any):
    p = _ascii(pick).replace(" ", "")
    if p in {"yes", "tak", "1", "true"}:
        return True
    if p in {"no", "nie", "0", "false"}:
        return False
    return None


def _predicate(match: dict, candidate: "Candidate") -> Callable[[dict], bool] | None:
    market = candidate.market
    pick = candidate.pick
    line = candidate.line

    if market == "game_state":
        cp = candidate.checkpoint
        target = _score_pair(pick)
        if cp not in CHECKPOINTS or target is None:
            return None
        return lambda o: o.get(f"cp{cp}") == target

    if market == "set1_winner":
        side = _side_for_pick(match, pick)
        return (lambda o: o["set1_winner"] == side) if side else None

    if market == "match_winner":
        side = _side_for_pick(match, pick)
        return (lambda o: o["winner"] == side) if side else None

    if market in {"set1_total", "match_total", "total_sets"}:
        side = _ou_side(pick)
        if side is None or line is None:
            return None
        field = "set_count" if market == "total_sets" else "total_games" if market == "match_total" else None
        if market == "set1_total":
            if side == "over":
                return lambda o: sum(o["set1"]) > line
            return lambda o: sum(o["set1"]) < line
        if side == "over":
            return lambda o: o[field] > line
        return lambda o: o[field] < line

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


def _marginal(outcomes: list[dict], pred: Callable[[dict], bool] | None):
    if pred is None or not outcomes:
        return None
    return sum(o["prob"] for o in outcomes if pred(o))


def _joint(outcomes: list[dict], preds: list[Callable[[dict], bool] | None]):
    supported = [p for p in preds if p is not None]
    if not supported or not outcomes:
        return None, 0
    p = sum(o["prob"] for o in outcomes if all(pred(o) for pred in supported))
    return p, len(supported)


@dataclass(frozen=True)
class Candidate:
    key: str
    label: str
    market: str
    pick: str
    line: float | None
    checkpoint: int | None
    prod_score: float
    shadow_scores: dict[str, float]
    path_probability: float | None
    evidence_score: float
    agreement: float
    conflict: float

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "market": self.market,
            "pick": self.pick,
            "line": self.line,
            "checkpoint": self.checkpoint,
            "prod_score": round(self.prod_score, 1),
            "shadow_scores": {k: round(v, 1) for k, v in self.shadow_scores.items()},
            "path_probability": round(self.path_probability * 100.0, 1) if self.path_probability is not None else None,
            "evidence_score": round(self.evidence_score, 1),
            "agreement": round(self.agreement, 3),
            "conflict": round(self.conflict, 3),
        }


def _label(signal: dict, market: str, pick: str, cp: int | None):
    raw = str(signal.get("label") or "").strip()
    if raw:
        return raw
    if market == "game_state" and cp:
        return f"Po {cp}: {pick}"
    labels = {
        "match_winner": "Wygra mecz",
        "set1_winner": "Wygra 1. set",
        "match_total": "Gemy w meczu",
        "set1_total": "Gemy w 1. secie",
        "total_sets": "Liczba setów",
        "exact_match_score": "Dokładny wynik meczu",
        "set1_exact_score": "Dokładny wynik 1. seta",
        "set1_tiebreak": "Tie-break w 1. secie",
    }
    return f"{labels.get(market, market)} · {pick}" if pick else labels.get(market, market)


def _candidate(match: dict, signal: dict, shadow_scores: dict[str, float], outcomes: list[dict]) -> Candidate | None:
    prod = _prod_score(signal)
    if prod is None:
        return None
    market = _canonical_market(signal.get("market"))
    pick = str(signal.get("pick") or "")
    cp = _checkpoint(signal)
    base = Candidate(
        key=_signal_key(signal),
        label=_label(signal, market, pick, cp),
        market=market,
        pick=pick,
        line=_line(signal),
        checkpoint=cp,
        prod_score=prod,
        shadow_scores=shadow_scores,
        path_probability=None,
        evidence_score=prod,
        agreement=0.5,
        conflict=0.0,
    )
    path_p = _marginal(outcomes, _predicate(match, base))

    vals = [float(v) for v in shadow_scores.values() if _num(v) is not None]
    components = [prod]
    weights = [0.70 if path_p is not None else 0.80]
    if path_p is not None:
        components.append(path_p * 100.0)
        weights.append(0.30 if not vals else 0.20)
    if vals:
        shadow_mean = sum(vals) / len(vals)
        components.append(shadow_mean)
        weights.append(SHADOW_WEIGHT_CAP)
        # Keep total weight at 1.0 by taking shadow from PROD, never from path maths.
        weights[0] = max(0.0, 1.0 - sum(weights[1:]))
        spread = max(vals + [prod]) - min(vals + [prod])
        agreement = max(0.0, 1.0 - spread / 50.0)
        conflict = max(0.0, min(1.0, spread / 35.0))
    else:
        agreement, conflict = 0.5, 0.0
    evidence = sum(v * w for v, w in zip(components, weights)) / max(EPS, sum(weights))

    return Candidate(
        key=base.key,
        label=base.label,
        market=market,
        pick=pick,
        line=base.line,
        checkpoint=cp,
        prod_score=prod,
        shadow_scores=shadow_scores,
        path_probability=path_p,
        evidence_score=max(0.0, min(100.0, evidence)),
        agreement=agreement,
        conflict=conflict,
    )


def _compatible(a: Candidate, b: Candidate) -> bool:
    if a.key and a.key == b.key:
        return False
    if a.market == b.market == "game_state" and a.checkpoint == b.checkpoint:
        return _score_pair(a.pick) == _score_pair(b.pick)
    if a.market == b.market and a.market in {"match_winner", "set1_winner", "set2_winner", "set3_winner", "exact_match_score", "set1_exact_score"}:
        return _compact(a.pick) == _compact(b.pick)
    if a.market == b.market and a.market in {"set1_total", "match_total", "total_sets"}:
        if a.line is not None and b.line is not None and abs(a.line - b.line) < 1e-9:
            if {_ou_side(a.pick), _ou_side(b.pick)} == {"over", "under"}:
                return False
    # 3:3 after six guarantees at least nine games in set one.
    state = a if a.market == "game_state" and a.checkpoint == 6 else b if b.market == "game_state" and b.checkpoint == 6 else None
    total = b if state is a else a if state is b else None
    if state and total and total.market == "set1_total" and _score_pair(state.pick) == (3, 3):
        if _ou_side(total.pick) == "under" and total.line is not None and total.line <= 8.5:
            return False
    return True


def _pair_affinity(a: Candidate, b: Candidate) -> float:
    if not _compatible(a, b):
        return -1e9
    score = 0.0
    if a.market != b.market:
        score += 4.0
    if a.checkpoint and b.checkpoint and a.checkpoint != b.checkpoint:
        score += 2.0
    if a.pick and b.pick and _compact(a.pick) == _compact(b.pick):
        score += 1.5
    score += 2.0 * min(a.agreement, b.agreement)
    score -= 4.0 * max(a.conflict, b.conflict)
    return score


def _story_type(candidates: list[Candidate]) -> str:
    states = {c.checkpoint: _score_pair(c.pick) for c in candidates if c.market == "game_state" and c.checkpoint}
    totals = [c for c in candidates if c.market == "set1_total"]
    tb = next((c for c in candidates if c.market == "set1_tiebreak" and _yes_no(c.pick) is True), None)
    if states.get(2) in {(2, 0), (0, 2)} and states.get(4) == (2, 2):
        return "BREAK_REBREAK"
    if states.get(2) == (1, 1) and states.get(4) == (2, 2) and states.get(6) == (3, 3):
        return "SERVE_WAR"
    if tb:
        return "TIEBREAK_MAGNET"
    if any(_ou_side(c.pick) == "under" for c in totals):
        return "FAST_CONTROL"
    if any(_ou_side(c.pick) == "over" for c in totals):
        return "LONG_SET"
    exact = next((c for c in candidates if c.market == "exact_match_score"), None)
    if exact and _score_pair(exact.pick) in {(2, 0), (3, 0)}:
        return "ONE_SIDED"
    return "BALANCED"


def _combo_metrics(match: dict, combo: tuple[Candidate, ...], outcomes: list[dict]):
    preds = [_predicate(match, c) for c in combo]
    joint, supported = _joint(outcomes, preds)
    coverage = supported / len(combo) if combo else 0.0
    avg_evidence = sum(c.evidence_score for c in combo) / len(combo)
    avg_agreement = sum(c.agreement for c in combo) / len(combo)
    conflict = max((c.conflict for c in combo), default=0.0)

    if supported >= 2 and joint is not None:
        path_component = joint * 100.0
    else:
        path_component = avg_evidence
    # Score is a ranking score, not a claimed probability unless coverage == 1.
    score = 0.55 * path_component + 0.35 * avg_evidence + 10.0 * avg_agreement - 9.0 * conflict
    score += sum(_pair_affinity(combo[i], combo[j]) for i in range(len(combo)) for j in range(i + 1, len(combo))) / max(1, len(combo))
    return {
        "score": max(0.0, min(100.0, score)),
        "joint": joint if coverage == 1.0 else None,
        "joint_supported_only": joint,
        "path_coverage": coverage,
        "supported_legs": supported,
        "avg_evidence": avg_evidence,
        "agreement": avg_agreement,
        "conflict": conflict,
    }


def _beam_combinations(match: dict, candidates: list[Candidate], outcomes: list[dict], size: int):
    pool = sorted(candidates, key=lambda c: (c.evidence_score, c.agreement, -c.conflict), reverse=True)[:POOL_LIMIT]
    beam: list[tuple[tuple[Candidate, ...], dict]] = []
    for c in pool:
        metrics = _combo_metrics(match, (c,), outcomes)
        beam.append(((c,), metrics))
    beam.sort(key=lambda x: x[1]["score"], reverse=True)
    beam = beam[:BEAM_WIDTH]

    for _depth in range(2, size + 1):
        expanded = []
        seen = set()
        for combo, _ in beam:
            last_idx = max(pool.index(c) for c in combo)
            for idx in range(last_idx + 1, len(pool)):
                c = pool[idx]
                if any(not _compatible(c, old) for old in combo):
                    continue
                nxt = combo + (c,)
                key = tuple(sorted(x.key or f"{x.market}:{x.pick}:{x.line}" for x in nxt))
                if key in seen:
                    continue
                seen.add(key)
                metrics = _combo_metrics(match, nxt, outcomes)
                # Zero exact mass means a mathematically impossible combination.
                if metrics["supported_legs"] == len(nxt) and metrics["joint_supported_only"] is not None and metrics["joint_supported_only"] <= EPS:
                    continue
                expanded.append((nxt, metrics))
        expanded.sort(key=lambda x: (x[1]["score"], x[1]["path_coverage"], x[1]["avg_evidence"]), reverse=True)
        beam = expanded[:BEAM_WIDTH]
        if not beam:
            break
    return beam


def _path_text(o: dict) -> str:
    cp2 = f"{o['cp2'][0]}:{o['cp2'][1]}"
    cp4 = f"{o['cp4'][0]}:{o['cp4'][1]}"
    cp6 = f"{o['cp6'][0]}:{o['cp6'][1]}"
    s1 = f"{o['set1'][0]}:{o['set1'][1]}"
    ms = f"{o['sets'][0]}:{o['sets'][1]}"
    return f"{cp2} → {cp4} → {cp6} → set {s1} → mecz {ms}"


def _top_matching_paths(match: dict, combo: tuple[Candidate, ...], outcomes: list[dict], limit=5):
    preds = [_predicate(match, c) for c in combo]
    supported = [p for p in preds if p is not None]
    if not supported:
        return []
    rows = [o for o in outcomes if all(p(o) for p in supported)]
    rows.sort(key=lambda o: o["prob"], reverse=True)
    return [
        {
            "path": _path_text(o),
            "cp2": f"{o['cp2'][0]}:{o['cp2'][1]}",
            "cp4": f"{o['cp4'][0]}:{o['cp4'][1]}",
            "cp6": f"{o['cp6'][0]}:{o['cp6'][1]}",
            "set1": f"{o['set1'][0]}:{o['set1'][1]}",
            "match_score": f"{o['sets'][0]}:{o['sets'][1]}",
            "total_games": o["total_games"],
            "probability_mass": round(o["prob"] * 100.0, 3),
        }
        for o in rows[:limit]
    ]


def _fragility(match: dict, combo: tuple[Candidate, ...], outcomes: list[dict]):
    if len(combo) < 2:
        return []
    full_preds = [_predicate(match, c) for c in combo]
    full_joint, full_supported = _joint(outcomes, full_preds)
    rows = []
    for i, c in enumerate(combo):
        reduced = combo[:i] + combo[i + 1:]
        reduced_joint, reduced_supported = _joint(outcomes, [_predicate(match, x) for x in reduced])
        lift = 0.0
        if full_joint is not None and reduced_joint is not None and full_joint > EPS and full_supported == len(combo) and reduced_supported == len(reduced):
            lift = max(0.0, (reduced_joint / full_joint - 1.0) * 20.0)
        frag = (100.0 - c.evidence_score) + 18.0 * c.conflict + min(50.0, lift)
        rows.append({
            "key": c.key,
            "label": c.label,
            "fragility": round(frag, 1),
            "evidence_score": round(c.evidence_score, 1),
            "remove_joint_probability": round(reduced_joint * 100.0, 2) if reduced_joint is not None and reduced_supported == len(reduced) else None,
        })
    rows.sort(key=lambda x: x["fragility"], reverse=True)
    return rows


def _scenario_payload(match: dict, combo: tuple[Candidate, ...], metrics: dict, outcomes: list[dict]):
    return {
        "story_type": _story_type(list(combo)),
        "symphony_score": round(metrics["score"], 1),
        "joint_probability": round(metrics["joint"] * 100.0, 2) if metrics["joint"] is not None else None,
        "joint_probability_supported_legs": round(metrics["joint_supported_only"] * 100.0, 2) if metrics["joint_supported_only"] is not None else None,
        "path_coverage": round(metrics["path_coverage"], 3),
        "supported_legs": metrics["supported_legs"],
        "prod_shadow_agreement": round(metrics["agreement"], 3),
        "model_conflict": round(metrics["conflict"], 3),
        "selection": [c.as_dict() for c in combo],
        "fragility": _fragility(match, combo, outcomes),
        "top_paths": _top_matching_paths(match, combo, outcomes),
    }


def _compositions(match: dict, candidates: list[Candidate], outcomes: list[dict]):
    out = {}
    for size in range(2, 7):
        beam = _beam_combinations(match, candidates, outcomes, size)
        if not beam:
            continue
        best_combo, best_metrics = beam[0]
        out[str(size)] = {
            **_scenario_payload(match, best_combo, best_metrics, outcomes),
            "legs": size,
            "alternatives": [
                _scenario_payload(match, combo, metrics, outcomes)
                for combo, metrics in beam[1:4]
            ],
        }
    return out


def build_match_symphony(match: dict, shadow_for_match: dict[str, dict[str, float]], legs: int = 4) -> dict | None:
    outcomes = _build_outcomes(match)
    signals = ((match.get("autolearn_v84") or {}).get("signals") or [])
    candidates = []
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        c = _candidate(match, signal, shadow_for_match.get(_signal_key(signal), {}), outcomes)
        if c is not None:
            candidates.append(c)
    if not candidates:
        return None

    comps = _compositions(match, candidates, outcomes)
    requested = str(max(2, min(6, int(legs))))
    default = comps.get(requested) or next(iter(comps.values()), None)
    if default is None:
        return None

    return {
        "match_key": _match_key(match),
        "id": match.get("id") if match.get("id") is not None else match.get("match_id"),
        "p1": match.get("p1"),
        "p2": match.get("p2"),
        "scheduled_time": match.get("scheduled_time"),
        "tour": match.get("tour"),
        "tournament": match.get("tournament"),
        "surface": match.get("surface"),
        "best_of": _best_of(match),
        "path_engine": "EXACT" if outcomes else "EVIDENCE_ONLY",
        "outcome_states": len(outcomes),
        "compositions": comps,
        "story_type": default["story_type"],
        "symphony_score": default["symphony_score"],
        "joint_probability": default["joint_probability"],
        "path_coverage": default["path_coverage"],
        "prod_shadow_agreement": default["prod_shadow_agreement"],
        "model_conflict": default["model_conflict"],
        "legs_requested": int(requested),
        "legs_selected": len(default["selection"]),
        "selection": default["selection"],
        "fragility": default["fragility"],
        "top_paths": default["top_paths"],
        "candidate_pool": [c.as_dict() for c in sorted(candidates, key=lambda x: x.evidence_score, reverse=True)[:20]],
        "analysis_only": True,
    }


def build_report(legs: int = 4) -> dict:
    results = _read(RESULTS, [])
    shadow = _read(SHADOW, {})
    if not isinstance(results, list):
        results = []
    if not isinstance(shadow, dict):
        shadow = {}
    shadow_idx = _shadow_index(shadow)
    matches = []
    for match in results:
        if not isinstance(match, dict):
            continue
        mk = _match_key(match)
        row = build_match_symphony(match, shadow_idx.get(mk, {}), legs=legs)
        if row:
            matches.append(row)
    matches.sort(key=lambda x: (-float(x.get("symphony_score") or 0.0), str(x.get("scheduled_time") or "")))
    return {
        "version": VERSION,
        "mode": MODE,
        "production_influence": False,
        "shadow_auto_promotion": False,
        "matches_count": len(matches),
        "matches": matches,
        "contract": {
            "prod_is_source_of_truth": True,
            "shadow_is_supporting_evidence": True,
            "shadow_weight_cap": SHADOW_WEIGHT_CAP,
            "does_not_modify_final_score": True,
            "joint_probability_only_when_path_coverage_is_1": True,
        },
    }


def run(legs: int = 4) -> dict:
    report = build_report(legs=legs)
    _write(REPORT, report)
    return {
        "status": "OK",
        "version": VERSION,
        "matches": report.get("matches_count", 0),
        "production_influence": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
