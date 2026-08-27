from __future__ import annotations

"""Tenis AI v9.0 — Tennis Symphony scenario engine.

This module is intentionally additive. It consumes existing PROD and SHADOW
signals without changing Ensemble, Adaptive final_score, or SHADOW promotion
rules. Its job is to turn existing evidence into coherent match stories and
multi-market candidates.
"""

from collections import defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
RESULTS = OUT / "results.json"
SHADOW = OUT / "shadow_signals_v894.json"
REPORT = OUT / "symphony_v90.json"

VERSION = "v9.0"
MODE = "ANALYSIS_ONLY"
CHECKPOINTS = (2, 4, 6)


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


def _norm_market(value: Any) -> str:
    x = str(value or "").strip().lower()
    return {
        "match_win": "match_winner",
        "set1_win": "set1_winner",
        "set2_win": "set2_winner",
        "set3_win": "set3_winner",
        "state": "game_state",
    }.get(x, x or "other")


def _match_key(match: dict) -> str:
    mid = match.get("match_id") if match.get("match_id") is not None else match.get("id")
    if mid is not None and str(mid) != "":
        return f"id:{mid}"
    return "|".join([
        str(match.get("p1") or "").casefold(),
        str(match.get("p2") or "").casefold(),
        str(match.get("scheduled_time") or "")[:10],
        str(match.get("tournament") or "").casefold(),
    ])


def _signal_key(signal: dict) -> str:
    return str(signal.get("key") or signal.get("id") or "")


def _line(signal: dict):
    x = _num(signal.get("line"), _num(signal.get("selected_line"), _num(signal.get("suggested_line"))))
    if x is not None:
        return x
    parts = _signal_key(signal).split("|")
    if len(parts) > 1:
        return _num(parts[1])
    return None


def _checkpoint(signal: dict):
    cp = _num(signal.get("checkpoint"))
    if cp in CHECKPOINTS:
        return int(cp)
    key = _signal_key(signal).lower()
    for c in CHECKPOINTS:
        if f"|{c}|" in key and ("state" in key or "game_state" in key):
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
            "evidence_score": round(self.evidence_score, 1),
            "agreement": round(self.agreement, 3),
            "conflict": round(self.conflict, 3),
        }


def _candidate(match: dict, signal: dict, shadow_scores: dict[str, float]) -> Candidate | None:
    prod = _prod_score(signal)
    if prod is None:
        return None
    vals = [float(v) for v in shadow_scores.values() if _num(v) is not None]
    if vals:
        shadow_mean = sum(vals) / len(vals)
        spread = max(vals + [prod]) - min(vals + [prod])
        agreement = max(0.0, 1.0 - spread / 50.0)
        # SHADOW is evidence only: capped to 25% of the blended evidence score.
        evidence = 0.75 * prod + 0.25 * shadow_mean
        conflict = max(0.0, min(1.0, spread / 35.0))
    else:
        agreement = 0.5
        evidence = prod
        conflict = 0.0
    market = _norm_market(signal.get("market"))
    pick = str(signal.get("pick") or "")
    cp = _checkpoint(signal)
    label = str(signal.get("label") or "").strip()
    if not label:
        if market == "game_state" and cp:
            label = f"Po {cp}: {pick}"
        elif market == "match_winner":
            label = f"Wygra mecz: {pick}"
        elif market == "set1_winner":
            label = f"Wygra 1. set: {pick}"
        else:
            label = _signal_key(signal) or market
    return Candidate(
        key=_signal_key(signal),
        label=label,
        market=market,
        pick=pick,
        line=_line(signal),
        checkpoint=cp,
        prod_score=prod,
        shadow_scores=shadow_scores,
        evidence_score=max(0.0, min(100.0, evidence)),
        agreement=agreement,
        conflict=conflict,
    )


def _compatible(a: Candidate, b: Candidate) -> bool:
    """Hard logical guard for combinations we can prove contradictory."""
    if a.key == b.key:
        return False

    # Same checkpoint cannot have two different exact states.
    if a.market == b.market == "game_state" and a.checkpoint == b.checkpoint:
        return a.pick.replace(" ", "") == b.pick.replace(" ", "")

    # Same winner market cannot pick opposite players.
    if a.market == b.market and a.market in {"match_winner", "set1_winner", "set2_winner", "set3_winner"}:
        return a.pick == b.pick

    # Same total market/line cannot be simultaneously over and under.
    if a.market == b.market and a.market in {"set1_total", "match_total"}:
        if a.line is not None and b.line is not None and abs(a.line - b.line) < 1e-9:
            pa, pb = a.pick.lower(), b.pick.lower()
            if {pa, pb} == {"over", "under"}:
                return False

    # Exact 3:3 after six games guarantees first-set total >= 9 games.
    state = a if a.market == "game_state" and a.checkpoint == 6 else b if b.market == "game_state" and b.checkpoint == 6 else None
    total = b if state is a else a if state is b else None
    if state and total and total.market == "set1_total" and state.pick.replace(" ", "") in {"3:3", "3-3"}:
        if total.pick.lower() == "under" and total.line is not None and total.line <= 8.5:
            return False

    return True


def _pair_affinity(a: Candidate, b: Candidate) -> float:
    if not _compatible(a, b):
        return -1e9
    score = 0.0
    if a.market != b.market:
        score += 5.0
    if a.checkpoint and b.checkpoint and a.checkpoint != b.checkpoint:
        score += 3.0
    if a.pick and b.pick and a.pick == b.pick:
        score += 2.5
    score += 3.0 * min(a.agreement, b.agreement)
    score -= 5.0 * max(a.conflict, b.conflict)
    return score


def _story_type(candidates: list[Candidate]) -> str:
    states = {c.checkpoint: c.pick.replace(" ", "") for c in candidates if c.market == "game_state" and c.checkpoint}
    total = next((c for c in candidates if c.market == "set1_total"), None)
    if states.get(2) in {"2:0", "0:2", "2-0", "0-2"} and states.get(4) in {"2:2", "2-2"}:
        return "BREAK_REBREAK"
    if states.get(2) in {"1:1", "1-1"} and states.get(4) in {"2:2", "2-2"} and states.get(6) in {"3:3", "3-3"}:
        return "SERVE_WAR"
    if total and total.pick.lower() == "under":
        return "FAST_CONTROL"
    if total and total.pick.lower() == "over":
        return "LONG_SET"
    return "BALANCED"


def _compose(candidates: list[Candidate], size: int = 4) -> list[Candidate]:
    pool = sorted(candidates, key=lambda c: (c.evidence_score, c.agreement, -c.conflict), reverse=True)
    if not pool:
        return []
    selected = [pool[0]]
    while len(selected) < size:
        best = None
        best_score = -1e18
        for c in pool:
            if c in selected:
                continue
            affinities = [_pair_affinity(c, s) for s in selected]
            if any(x < -1e8 for x in affinities):
                continue
            diversity = 4.0 if all(c.market != s.market for s in selected) else 0.0
            score = c.evidence_score + sum(affinities) + diversity
            if score > best_score:
                best, best_score = c, score
        if best is None:
            break
        selected.append(best)
    return selected


def _fragility(selected: list[Candidate]) -> list[dict]:
    if len(selected) < 2:
        return []
    base = sum(c.evidence_score for c in selected) / len(selected)
    rows = []
    for c in selected:
        rest = [x for x in selected if x is not c]
        rest_mean = sum(x.evidence_score for x in rest) / len(rest)
        lift = max(0.0, rest_mean - base)
        rows.append({
            "key": c.key,
            "label": c.label,
            "fragility": round((100.0 - c.evidence_score) + 20.0 * c.conflict + lift, 1),
            "evidence_score": round(c.evidence_score, 1),
        })
    rows.sort(key=lambda x: x["fragility"], reverse=True)
    return rows


def build_match_symphony(match: dict, shadow_for_match: dict[str, dict[str, float]], legs: int = 4) -> dict | None:
    signals = ((match.get("autolearn_v84") or {}).get("signals") or [])
    candidates = []
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        c = _candidate(match, signal, shadow_for_match.get(_signal_key(signal), {}))
        if c is not None:
            candidates.append(c)
    if not candidates:
        return None

    selected = _compose(candidates, max(2, min(6, int(legs))))
    if not selected:
        return None

    avg = sum(c.evidence_score for c in selected) / len(selected)
    agreement = sum(c.agreement for c in selected) / len(selected)
    conflict = max((c.conflict for c in selected), default=0.0)
    score = max(0.0, min(100.0, avg + 8.0 * agreement - 10.0 * conflict))

    return {
        "match_key": _match_key(match),
        "id": match.get("id") if match.get("id") is not None else match.get("match_id"),
        "p1": match.get("p1"),
        "p2": match.get("p2"),
        "scheduled_time": match.get("scheduled_time"),
        "tour": match.get("tour"),
        "tournament": match.get("tournament"),
        "surface": match.get("surface"),
        "story_type": _story_type(selected),
        "symphony_score": round(score, 1),
        "prod_shadow_agreement": round(agreement, 3),
        "model_conflict": round(conflict, 3),
        "legs_requested": legs,
        "legs_selected": len(selected),
        "selection": [c.as_dict() for c in selected],
        "fragility": _fragility(selected),
        "alternatives": [c.as_dict() for c in sorted(candidates, key=lambda x: x.evidence_score, reverse=True) if c not in selected][:8],
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
            "shadow_weight_cap": 0.25,
            "does_not_modify_final_score": True,
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
