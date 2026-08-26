from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
HISTORY_PATH = OUT / "history.json"
PBP_HISTORY_PATH = OUT / "pbp_history.json"
RESULTS_PATH = OUT / "results.json"
REPORT_PATH = OUT / "adaptive_learning_v79.json"
META_PATH = OUT / "meta.json"

VERSION = "v7.9B-bayesian-meta"
MODE = "PROD"
CURRENT_MODEL_VERSION = "v7.8D-calibration-guard"
OFFICIAL_WEIGHT = 1.0
SHADOW_WEIGHT = 0.60
PBP_WEIGHT = 0.90
SPECIALIST_WEIGHT = 0.85
MIN_CELL_SAMPLE = 6.0
STRONG_CELL_SAMPLE = 20.0
PROMOTION_SAMPLE = 300
PRIOR_STRENGTH = 12.0
MAX_LOGIT_SHIFT = 0.80
PRODUCTION_CAP_PP = {
    "COLLECTING": 0.0,
    "EARLY": 4.0,
    "STRONG": 8.0,
}


def _read(path: Path, fallback):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _num(value, default=None):
    try:
        x = float(value)
        if math.isfinite(x):
            return x
    except (TypeError, ValueError):
        pass
    return default


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(value)))


def _logit(p):
    p = _clamp(p, 1e-5, 1 - 1e-5)
    return math.log(p / (1 - p))


def _sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)


def _norm(value):
    return str(value or "").strip().lower()


def _score_band(score):
    v = _num(score, 0.0)
    if v >= 90:
        return "90-100"
    if v >= 80:
        return "80-89"
    if v >= 72:
        return "72-79"
    if v >= 65:
        return "65-71"
    if v >= 55:
        return "55-64"
    return "<55"


def _line(value):
    v = _num(value)
    return "?" if v is None else f"{v:.1f}"


def canonical_market(signal: dict) -> str:
    market = _norm(signal.get("market"))
    if market == "game_state":
        checkpoint = signal.get("checkpoint")
        return f"state{checkpoint}" if checkpoint is not None else "game_state"
    aliases = {
        "set1_win": "set1_winner",
        "match_win": "match_winner",
        "first_set": "set1_winner",
    }
    return aliases.get(market, market or "other")


def signal_key(signal: dict) -> str:
    market = canonical_market(signal)
    pick = _norm(signal.get("pick"))
    if market in ("set1_total", "match_total"):
        return f"{market}|{_line(signal.get('line'))}|{pick}"
    if market.startswith("state"):
        return f"{market}|{pick}"
    if market in ("lead_after6", "joint_builder", "balanced_after6"):
        return f"{market}|{pick or 'event'}"
    return f"{market}|{pick}" if pick else market


def _training_row(entry: dict, signal: dict, weight: float, source_model: str | None = None) -> dict | None:
    result = signal.get("result")
    if result not in ("hit", "miss"):
        return None
    raw = _num(signal.get("score"))
    if raw is None:
        prob = _num(signal.get("prob"))
        if prob is not None:
            raw = prob * 100.0 if prob <= 1.0 else prob
    if raw is None:
        conf = _num(signal.get("confidence"))
        if conf is not None:
            raw = conf * 100.0 if conf <= 1.0 else conf
    if raw is None:
        return None
    raw = _clamp(raw / 100.0, 0.01, 0.99)
    return {
        "source_model": source_model or str(signal.get("source_model") or "adaptive"),
        "market": canonical_market(signal),
        "key": signal_key(signal),
        "tour": str(entry.get("tour") or "N/D").upper(),
        "surface": str(entry.get("surface") or "N/D").lower(),
        "band": _score_band(raw * 100.0),
        "raw": raw,
        "hit": 1.0 if result == "hit" else 0.0,
        "weight": float(weight),
    }


def collect_training_rows(history: list[dict], pbp_history: list[dict]) -> list[dict]:
    rows = []
    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("model_version") == CURRENT_MODEL_VERSION:
            for signal in entry.get("signals") or []:
                row = _training_row(entry, signal, OFFICIAL_WEIGHT)
                if row:
                    rows.append(row)
            for signal in entry.get("shadow_signals") or []:
                row = _training_row(entry, signal, SHADOW_WEIGHT)
                if row:
                    rows.append(row)
            # v7.9B: client specialist models are captured pre-match by
            # specialist_learning_v79b.py and settled separately so they do not
            # contaminate the official production accuracy.
            for signal in entry.get("learning_signals_v79b") or []:
                row = _training_row(
                    entry, signal, SPECIALIST_WEIGHT,
                    str(signal.get("source_model") or "specialist"),
                )
                if row:
                    rows.append(row)
            # Ensemble is frozen before the match by AutoLearn and settled through
            # the same result pipeline. Learn its residual independently so the
            # production correction remains a post-adjustment and never changes
            # Current/CatBoost/TabPFN weights or their raw scores.
            for signal in entry.get("autolearn_signals_v84") or []:
                row = _training_row(entry, signal, OFFICIAL_WEIGHT, "ensemble_v84")
                if row:
                    rows.append(row)

    for entry in pbp_history or []:
        if not isinstance(entry, dict) or entry.get("status") != "settled":
            continue
        for signal in entry.get("signals") or []:
            # PBP tracker scores correctness of the predicted direction; confidence is
            # therefore the comparable "how sure was the model?" quantity.
            copy = dict(signal)
            conf = _num(signal.get("confidence"))
            if conf is not None:
                copy["score"] = conf * 100.0 if conf <= 1.0 else conf
            row = _training_row(entry, copy, PBP_WEIGHT, "early_hold_pbp")
            if row:
                rows.append(row)
    return rows


def _cell_key(level: str, row: dict) -> str:
    if level == "source":
        return row["source_model"]
    if level == "market":
        return f'{row["source_model"]}|{row["market"]}'
    if level == "signal":
        return f'{row["source_model"]}|{row["key"]}'
    if level == "context":
        return "|".join([
            row["source_model"], row["market"], row["tour"], row["surface"]
        ])
    if level == "band":
        return f'{row["source_model"]}|{row["market"]}|{row["band"]}'
    return "global"


def _summarize(items: list[dict]) -> dict:
    n = sum(float(x["weight"]) for x in items)
    hits = sum(float(x["hit"]) * float(x["weight"]) for x in items)
    raw_sum = sum(float(x["raw"]) * float(x["weight"]) for x in items)
    raw_mean = raw_sum / n if n else 0.5
    empirical = hits / n if n else 0.5

    # Beta/Bayesian shrinkage centered on the model's own mean confidence.
    posterior = (hits + PRIOR_STRENGTH * raw_mean) / (n + PRIOR_STRENGTH) if n else raw_mean
    residual = _logit(posterior) - _logit(raw_mean)
    reliability = n / (n + PRIOR_STRENGTH)
    effective_residual = residual * reliability

    gap_pp = (empirical - raw_mean) * 100.0
    if n < MIN_CELL_SAMPLE:
        evidence = "COLLECTING"
    elif n < STRONG_CELL_SAMPLE:
        evidence = "EARLY"
    else:
        evidence = "STRONG"

    return {
        "effective_n": round(n, 1),
        "weighted_hits": round(hits, 1),
        "raw_mean": round(raw_mean * 100.0, 1),
        "accuracy": round(empirical * 100.0, 1),
        "posterior": round(posterior * 100.0, 1),
        "gap_pp": round(gap_pp, 1),
        "residual_logit": round(effective_residual, 5),
        "evidence": evidence,
    }


def build_cells(rows: list[dict]) -> dict:
    levels = ("global", "source", "market", "signal", "context", "band")
    out = {}
    for level in levels:
        grouped = defaultdict(list)
        for row in rows:
            grouped[_cell_key(level, row)].append(row)
        out[level] = {k: _summarize(v) for k, v in sorted(grouped.items())}
    return out


def _query_context(source_model: str, signal: dict, tour="", surface="") -> dict:
    raw = _num(signal.get("score"))
    if raw is None:
        raw = 50.0
    return {
        "source_model": source_model or str(signal.get("source_model") or "adaptive"),
        "market": canonical_market(signal),
        "key": signal_key(signal),
        "tour": str(tour or "N/D").upper(),
        "surface": str(surface or "N/D").lower(),
        "band": _score_band(raw),
        "raw": _clamp(raw / 100.0, 0.01, 0.99),
    }


def adjust_score(score: float, source_model: str, signal: dict, cells: dict, tour="", surface="") -> dict:
    raw_score = _clamp(_num(score, 50.0), 1.0, 99.0)
    q = _query_context(source_model, {**signal, "score": raw_score}, tour, surface)

    candidates = []
    specs = [
        ("signal", _cell_key("signal", q), 1.00),
        ("context", _cell_key("context", q), 0.80),
        ("band", _cell_key("band", q), 0.55),
        ("market", _cell_key("market", q), 0.45),
        ("source", _cell_key("source", q), 0.30),
    ]
    for level, key, importance in specs:
        cell = (cells.get(level) or {}).get(key)
        if not cell:
            continue
        n = float(cell.get("effective_n") or 0)
        if n < MIN_CELL_SAMPLE:
            continue
        strength = min(1.0, n / STRONG_CELL_SAMPLE) * importance
        candidates.append((float(cell.get("residual_logit") or 0), strength, level, cell))

    if candidates:
        den = sum(w for _, w, _, _ in candidates) or 1.0
        shift = sum(resid * w for resid, w, _, _ in candidates) / den
        # More evidence may move the score more, but never beyond the guardrail.
        evidence_scale = min(1.0, sum(w for _, w, _, _ in candidates) / 1.8)
        shift *= evidence_scale
    else:
        shift = 0.0
    shift = _clamp(shift, -MAX_LOGIT_SHIFT, MAX_LOGIT_SHIFT)

    proposed = _sigmoid(_logit(raw_score / 100.0) + shift) * 100.0
    best = max(candidates, key=lambda x: x[1]) if candidates else None
    best_cell = best[3] if best else None
    n = best_cell.get("effective_n") if best_cell else 0
    hist_acc = best_cell.get("accuracy") if best_cell else None
    evidence = best_cell.get("evidence") if best_cell else "COLLECTING"
    cap_pp = PRODUCTION_CAP_PP.get(evidence, 0.0)
    applied_delta = _clamp(proposed - raw_score, -cap_pp, cap_pp)
    learned = _clamp(raw_score + applied_delta, 1.0, 99.0)

    if not candidates:
        action = "collect"
        lesson = "Za mało podobnych, rozliczonych przypadków — wynik pozostaje bez korekty."
    elif learned <= raw_score - 2.0:
        action = "downgrade"
        lesson = "W podobnych przypadkach model był zbyt pewny siebie — Adaptive Learning obniża ocenę."
    elif learned >= raw_score + 2.0:
        action = "upgrade"
        lesson = "W podobnych przypadkach model radził sobie lepiej niż sugerował score — ocena rośnie ostrożnie."
    else:
        action = "keep"
        lesson = "Historia podobnych przypadków nie uzasadnia istotnej zmiany oceny."

    return {
        "raw_score": round(raw_score, 1),
        "uncapped_score": round(proposed, 1),
        "learned_score": round(learned, 1),
        "final_score": round(learned, 1),
        "delta": round(learned - raw_score, 1),
        "cap_pp": cap_pp,
        "applied": evidence != "COLLECTING" and abs(learned - raw_score) >= 0.05,
        "action": action,
        "lesson": lesson,
        "similar_n": n,
        "historical_accuracy": hist_acc,
        "evidence": evidence,
        "components": [
            {
                "level": level,
                "effective_n": cell.get("effective_n"),
                "accuracy": cell.get("accuracy"),
                "gap_pp": cell.get("gap_pp"),
            }
            for _, _, level, cell in sorted(candidates, key=lambda x: x[1], reverse=True)[:3]
        ],
    }


def _decorate_ensemble_signal(signal: dict, cells: dict, tour="", surface="") -> dict:
    """Add bounded Adaptive PROD output without mutating any model score."""
    item = dict(signal)
    raw = _num(item.get("ensemble"))
    if raw is None:
        # Frozen AutoLearn history stores the Ensemble value in score and keeps
        # the individual RAW model values under model_scores.
        raw = _num(item.get("score"))
    if raw is None:
        return item
    review = adjust_score(raw, "ensemble_v84", item, cells, tour, surface)
    # Preserve the exact published Ensemble number as the official RAW value.
    # adjust_score uses its own safe 1..99 math clamp, but must not rewrite RAW.
    raw_score = raw
    final_score = review["final_score"]
    item.update({
        **review,
        "ensemble_raw": raw_score,
        "raw_score": raw_score,
        "final_score": final_score,
        "adaptive_delta_pp": review["delta"],
        "adaptive_prod_v79": {
            "version": VERSION,
            "mode": MODE,
            "status": review["evidence"],
            "evidence": review["evidence"],
            "applied": review["applied"],
            "cap_pp": review["cap_pp"],
            "raw_score": raw_score,
            "final_score": final_score,
            "delta_pp": review["delta"],
            "similar_n": review["similar_n"],
            "historical_accuracy": review["historical_accuracy"],
            "action": review["action"],
            "lesson": review["lesson"],
        },
    })
    return item


def decorate_frozen_history(history: list[dict], cells: dict) -> list[dict]:
    """Freeze Adaptive PROD beside RAW Ensemble for newly captured predictions."""
    out = []
    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        e = dict(entry)
        frozen = []
        for signal in e.get("autolearn_signals_v84") or []:
            if not isinstance(signal, dict):
                continue
            # Never recompute a prediction after it has been frozen. This keeps
            # later learning data from leaking into an earlier official score.
            if signal.get("adaptive_prod_v79"):
                frozen.append(signal)
            elif signal.get("result") == "pending":
                frozen.append(_decorate_ensemble_signal(
                    signal, cells, e.get("tour"), e.get("surface")
                ))
            else:
                # Legacy settled rows predate PROD and must not be backfilled
                # using future evidence.
                frozen.append(signal)
        if "autolearn_signals_v84" in e:
            e["autolearn_signals_v84"] = frozen
        out.append(e)
    return out


def _core_signals(match: dict) -> list[dict]:
    out = []

    def binary(field, market, label, source_model="adaptive"):
        for pick, value in (match.get(field) or {}).items():
            v = _num(value)
            if v is not None and v >= 55.0:
                out.append({
                    "market": market, "label": label, "pick": str(pick),
                    "score": v, "source_model": source_model,
                })

    binary("match_win", "match_winner", "Zwycięzca meczu")
    binary("first_set_win", "set1_winner", "Zwycięzca 1. seta")
    binary("second_set_win", "set2_winner", "Zwycięzca 2. seta")
    binary("third_set_win", "set3_winner", "Zwycięzca 3. seta")
    binary("total_sets", "total_sets", "Liczba setów")

    for line, sides in (match.get("over_under") or {}).items():
        for pick in ("over", "under"):
            v = _num((sides or {}).get(pick))
            if v is not None and v >= 55.0:
                out.append({
                    "market": "set1_total", "label": f"1. set · {pick.upper()} {line}",
                    "pick": pick, "line": _num(line), "score": v, "source_model": "adaptive",
                })

    for line, sides in (match.get("match_over_under") or {}).items():
        for pick in ("over", "under"):
            v = _num((sides or {}).get(pick))
            if v is not None and v >= 55.0:
                out.append({
                    "market": "match_total", "label": f"Mecz · {pick.upper()} {line}",
                    "pick": pick, "line": _num(line), "score": v, "source_model": "adaptive",
                })

    # Specialist Early Hold / PBP outputs are learned independently.
    early = match.get("early_hold_v7") or {}
    if early.get("ready"):
        pick = match.get("pick_first_set_early")
        pairs = [
            ("set1_winner", "Early Hold · zwycięzca 1. seta", pick, match.get("score_first_set_early"), {}),
            ("lead_after6", "Early Hold · prowadzenie po 6 gemach", pick, match.get("score_lead_after6"), {}),
            ("joint_builder", "Early Hold · Joint Builder", pick, match.get("score_joint_builder"), {}),
            ("balanced_after6", "Early Hold · 3:3 po 6 gemach", "3:3", early.get("balanced_after6"), {}),
        ]
        for market, label, chosen, value, extra in pairs:
            v = _num(value)
            if chosen and v is not None and v >= 55.0:
                out.append({
                    "market": market, "label": label, "pick": str(chosen),
                    "score": v, "source_model": "early_hold_pbp", **extra,
                })
        over85 = _num((((match.get("early_over_under") or {}).get("8.5") or {}).get("over")))
        if over85 is not None and over85 >= 55.0:
            out.append({
                "market": "over85", "label": "Early Hold · OVER 8.5 1S", "pick": "over",
                "score": over85, "source_model": "early_hold_pbp",
            })
        for checkpoint in ("2", "4", "6"):
            states = (match.get("game_states") or {}).get(checkpoint) or {}
            if not states:
                continue
            pick, value = max(
                ((str(k), _num(v)) for k, v in states.items() if _num(v) is not None),
                key=lambda x: x[1],
                default=(None, None),
            )
            if pick and value is not None and value >= 55.0:
                out.append({
                    "market": f"state{checkpoint}", "label": f"Early Hold · wynik po {checkpoint} gemach",
                    "pick": pick, "score": value, "source_model": "early_hold_pbp",
                })
    return out


def decorate_results(results: list[dict], cells: dict) -> list[dict]:
    out = []
    for match in results or []:
        if not isinstance(match, dict):
            continue
        m = dict(match)
        auto = m.get("autolearn_v84")
        learned = []
        if isinstance(auto, dict) and isinstance(auto.get("signals"), list):
            decorated_signals = [
                _decorate_ensemble_signal(signal, cells, m.get("tour"), m.get("surface"))
                for signal in auto.get("signals") or []
                if isinstance(signal, dict)
            ]
            decorated_signals.sort(
                key=lambda x: (-float(x.get("final_score") or x.get("ensemble") or 0), x.get("key") or "")
            )
            auto_out = dict(auto)
            auto_out["signals"] = decorated_signals
            auto_out["by_key"] = {
                signal["key"]: signal for signal in decorated_signals if signal.get("key")
            }
            m["autolearn_v84"] = auto_out
            learned = decorated_signals

        # Current Engine is a safe fallback when AutoLearn has not produced an
        # Ensemble signal. Once Ensemble exists, it is the sole production base.
        if not learned:
            for signal in _core_signals(m):
                review = adjust_score(
                    signal["score"], signal.get("source_model") or "adaptive", signal, cells,
                    m.get("tour"), m.get("surface"),
                )
                learned.append({**signal, **review})
            learned.sort(key=lambda x: (-float(x.get("final_score") or 0), x.get("label") or ""))

        trained = [x for x in learned if x.get("evidence") != "COLLECTING"]
        applied = [x for x in learned if x.get("applied")]
        m["adaptive_learning_v79"] = {
            "version": VERSION,
            "mode": MODE,
            "status": "ACTIVE" if trained else "COLLECTING",
            "signals": learned[:18],
            "applied_signals": len(applied),
            "policy": {
                "COLLECTING": {"cap_pp": PRODUCTION_CAP_PP["COLLECTING"], "influence": False},
                "EARLY": {"cap_pp": PRODUCTION_CAP_PP["EARLY"], "influence": True},
                "STRONG": {"cap_pp": PRODUCTION_CAP_PP["STRONG"], "influence": True},
            },
            "note": (
                "Kontrolowany PROD: final_score jest ograniczoną korektą po Ensemble; "
                "current/catboost/tabpfn/ensemble oraz ensemble_raw pozostają bez zmian."
            ),
        }
        out.append(m)
    return out


def _actual_first_set(entry: dict):
    sets = (entry.get("result") or {}).get("sets") or []
    if not sets:
        return None
    try:
        return int(sets[0][0]), int(sets[0][1])
    except (TypeError, ValueError, IndexError):
        return None


def explain_signal(entry: dict, signal: dict) -> str:
    market = canonical_market(signal)
    pick = str(signal.get("pick") or "")
    final = entry.get("result") or {}
    first = _actual_first_set(entry)
    p1, p2 = entry.get("p1"), entry.get("p2")

    if signal.get("result") == "hit":
        return "Typ wszedł — zapisujemy ten przypadek jako pozytywny przykład dla podobnych sytuacji."

    if market == "match_winner":
        winner = final.get("winner") or "przeciwnik"
        return f"Typ na {pick} nie wszedł, bo mecz wygrał {winner} ({final.get('score_text') or 'wynik końcowy'})."
    if market in ("set1_winner", "set2_winner", "set3_winner"):
        idx = {"set1_winner": 0, "set2_winner": 1, "set3_winner": 2}[market]
        sets = final.get("sets") or []
        if len(sets) > idx:
            a, b = sets[idx]
            actual = p1 if a > b else p2
            return f"Typ na {pick} nie wszedł: set {idx + 1} wygrał {actual} {a}:{b}."
        return f"Typ na {pick} nie wszedł; brak pełnego wyniku seta do dokładniejszej diagnozy."
    if market == "set1_total" and first:
        total = first[0] + first[1]
        side = str(signal.get("pick") or "").upper()
        return f"{side} {_line(signal.get('line'))} nie wszedł: 1. set skończył się {first[0]}:{first[1]} ({total} gemów)."
    if market == "match_total":
        total = final.get("total_games")
        return f"{str(signal.get('pick') or '').upper()} {_line(signal.get('line'))} nie wszedł: mecz miał {total if total is not None else 'N/D'} gemów."
    if market == "exact_set1" and first:
        return f"Dokładny wynik {pick} nie wszedł: 1. set skończył się {first[0]}:{first[1]}."
    if market == "exact_match":
        return f"Dokładny wynik {pick} nie wszedł: rzeczywisty wynik setów to {final.get('match_score') or 'N/D'}."
    if market == "total_sets":
        return f"Typ {pick} nie wszedł: rozegrano {final.get('number_of_sets') or 'N/D'} sety/setów."
    return "Typ nie wszedł. Wynik zapisano do uczenia, ale obecne dane nie pozwalają uczciwie wskazać bardziej szczegółowej przyczyny."


def _pbp_review_by_match(pbp_history: list[dict], cells: dict) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for entry in pbp_history or []:
        if not isinstance(entry, dict) or entry.get("status") != "settled":
            continue
        mid = entry.get("match_id")
        if mid is None:
            continue
        actual = entry.get("actual") or {}
        for signal in entry.get("signals") or []:
            if signal.get("result") != "miss":
                continue
            conf = _num(signal.get("confidence"))
            score = (conf * 100.0 if conf is not None and conf <= 1 else conf)
            if score is None:
                continue
            s = {
                "market": signal.get("market"), "pick": signal.get("pick"),
                "score": score, "source_model": "early_hold_pbp",
            }
            adj = adjust_score(score, "early_hold_pbp", s, cells, entry.get("tour"), entry.get("surface"))
            market = canonical_market(s)
            why = "Sygnał Early Hold/PBP nie wszedł."
            if market == "lead_after6":
                st = (actual.get("states") or {}).get("6")
                why = f"Prowadzenie po 6 gemach nie weszło: rzeczywisty stan po 6 gemach to {st or 'N/D'}."
            elif market in ("state2", "state4", "state6"):
                cp = market.replace("state", "")
                st = (actual.get("states") or {}).get(cp)
                why = f"Przewidywany stan {signal.get('pick')} po {cp} gemach nie wszedł; było {st or 'N/D'}."
            elif market == "first_set":
                why = f"Early Hold źle wskazał 1. set; wygrał {actual.get('first_set_winner') or 'N/D'} ({actual.get('first_set_score') or 'N/D'})."
            elif market == "over85":
                why = f"OVER 8.5 nie wszedł; 1. set miał {actual.get('first_set_games') or 'N/D'} gemów."
            elif market == "joint_builder":
                why = "Joint Builder nie wszedł, bo co najmniej jeden z warunków (prowadzenie po 6 / O8.5 / wygrana 1S) nie został spełniony."
            out[str(mid)].append({
                "label": f"Early Hold · {market}",
                "result": "miss",
                "why": why,
                **adj,
            })
    return out


def decorate_history(history: list[dict], pbp_history: list[dict], cells: dict) -> list[dict]:
    pbp_by_match = _pbp_review_by_match(pbp_history, cells)
    out = []
    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        e = dict(entry)
        lessons = []
        hits = 0
        misses = 0
        all_review_signals = (
            list(e.get("signals") or [])
            + list(e.get("shadow_signals") or [])
            + list(e.get("learning_signals_v79b") or [])
            + list(e.get("autolearn_signals_v84") or [])
        )
        for signal in all_review_signals:
            if signal.get("result") not in ("hit", "miss"):
                continue
            source = signal.get("source_model") or "adaptive"
            adj = adjust_score(signal.get("score") or 50.0, source, signal, cells, e.get("tour"), e.get("surface"))
            if signal.get("result") == "hit":
                hits += 1
            else:
                misses += 1
                source_label = str(source).replace("_", " ").title()
                lessons.append({
                    "label": f"{source_label} · {signal.get('label') or canonical_market(signal)}",
                    "source_model": source,
                    "pick": signal.get("pick"),
                    "result": "miss",
                    "why": explain_signal(e, signal),
                    **adj,
                })

        linked = pbp_by_match.get(str(e.get("match_id")), [])
        if linked:
            misses += len(linked)
            lessons.extend(linked)

        if e.get("status") in ("settled", "void") and (hits or misses or linked):
            lessons.sort(key=lambda x: (x.get("evidence") == "COLLECTING", abs(float(x.get("delta") or 0)) * -1))
            e["adaptive_review_v79"] = {
                "version": VERSION,
                "mode": MODE,
                "status": "ANALYZED",
                "hits": hits,
                "misses": misses,
                "lessons": lessons[:8],
                "summary": (
                    "Model zapisuje błędy jako dane uczące. W PROD wpływ zależy od próbki: "
                    "COLLECTING 0 pp, EARLY maks. 4 pp, STRONG maks. 8 pp."
                ),
            }
        out.append(e)
    return out


def _repeated_errors(cells: dict) -> list[dict]:
    rows = []
    for key, cell in (cells.get("signal") or {}).items():
        n = float(cell.get("effective_n") or 0)
        gap = float(cell.get("gap_pp") or 0)
        if n < 10 or gap > -7.5:
            continue
        rows.append({
            "key": key,
            "effective_n": cell.get("effective_n"),
            "raw_mean": cell.get("raw_mean"),
            "accuracy": cell.get("accuracy"),
            "gap_pp": cell.get("gap_pp"),
            "evidence": cell.get("evidence"),
            "action": "downgrade",
        })
    rows.sort(key=lambda x: (x["gap_pp"], -float(x["effective_n"] or 0)))
    return rows[:20]


def build_report(rows: list[dict], cells: dict) -> dict:
    base_official_rows = [
        r for r in rows
        if r["weight"] == OFFICIAL_WEIGHT
        and r["source_model"] not in ("early_hold_pbp", "ensemble_v84")
    ]
    ensemble_rows = [r for r in rows if r["source_model"] == "ensemble_v84"]
    source_counts = defaultdict(float)
    for row in rows:
        source_counts[row["source_model"]] += row["weight"]
    base_official_n = sum(r["weight"] for r in base_official_rows)
    ensemble_n = sum(r["weight"] for r in ensemble_rows)
    production_n = ensemble_n if ensemble_n else base_official_n
    production_source = "ensemble_v84" if ensemble_n else "adaptive_base_fallback"
    repeated = _repeated_errors(cells)
    return {
        "version": VERSION,
        "mode": MODE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "learner": {
            "name": "Bayesian Online Meta-Learner",
            "type": "hierarchical_bayesian_residual_calibration",
            "prior_strength": PRIOR_STRENGTH,
            "max_logit_shift": MAX_LOGIT_SHIFT,
            "official_weight": OFFICIAL_WEIGHT,
            "shadow_weight": SHADOW_WEIGHT,
            "pbp_weight": PBP_WEIGHT,
            "specialist_weight": SPECIALIST_WEIGHT,
            "production_source": production_source,
            "production_caps_pp": PRODUCTION_CAP_PP,
        },
        "training": {
            "rows": len(rows),
            "effective_rows": round(sum(r["weight"] for r in rows), 1),
            # Keep the historical base-official counter stable; Ensemble is a
            # separate production tracking stream and must not double-count it.
            "official_effective_rows": round(base_official_n, 1),
            "ensemble_effective_rows": round(ensemble_n, 1),
            "production_effective_rows": round(production_n, 1),
            "by_source": {k: round(v, 1) for k, v in sorted(source_counts.items())},
        },
        "repeated_errors": repeated,
        "promotion_gate": {
            # Production activation is per cell, not an unrestricted global
            # override: insufficient evidence always has exactly zero influence.
            "ready": production_n >= MIN_CELL_SAMPLE,
            "sample_ready": production_n >= PROMOTION_SAMPLE,
            "manual_validation_required": False,
            "required_official_settled": PROMOTION_SAMPLE,
            "current_official_effective": round(base_official_n, 1),
            "current_ensemble_effective": round(ensemble_n, 1),
            "production_source": production_source,
            "blocking_error_patterns": len(repeated),
            "policy": "per_cell_evidence_bounded_post_ensemble_adjustment",
        },
        "notes": [
            "Uczenie koryguje pewność istniejących modeli; nie zastępuje ich logiki tenisowej.",
            "Każdy source_model/rynek uczy się osobno z hierarchicznym shrinkage.",
            "Serve/Return, Form, Surface, Early i Consensus są śledzone jako learning-only i nie mieszają się z oficjalną skutecznością.",
            "Player Intelligence i Accuracy Lab pozostają SHADOW i nie uczestniczą w korekcie PROD.",
            "COLLECTING nie ma wpływu; EARLY ma limit 4 pp; STRONG ma limit 8 pp.",
            "Current/CatBoost/TabPFN/Ensemble są zachowane jako RAW; korekta działa wyłącznie po Ensemble.",
        ],
    }


def run() -> dict:
    history = _read(HISTORY_PATH, [])
    pbp_history = _read(PBP_HISTORY_PATH, [])
    results = _read(RESULTS_PATH, [])
    meta = _read(META_PATH, {})
    if not isinstance(history, list):
        history = []
    if not isinstance(pbp_history, list):
        pbp_history = []
    if not isinstance(results, list):
        results = []
    if not isinstance(meta, dict):
        meta = {}

    rows = collect_training_rows(history, pbp_history)
    cells = build_cells(rows)
    report = build_report(rows, cells)
    report["cells"] = cells

    history = decorate_history(history, pbp_history, cells)
    history = decorate_frozen_history(history, cells)
    results = decorate_results(results, cells)

    _write(HISTORY_PATH, history)
    _write(RESULTS_PATH, results)
    _write(REPORT_PATH, report)

    meta.update({
        "adaptive_learning_version": VERSION,
        "adaptive_learning_mode": MODE,
        "adaptive_learning_rows": report["training"]["rows"],
        "adaptive_learning_effective_rows": report["training"]["effective_rows"],
        "adaptive_learning_repeated_errors": len(report["repeated_errors"]),
        "adaptive_learning_promotion_ready": report["promotion_gate"]["ready"],
        "adaptive_learning_updated_at": report["generated_at"],
    })
    _write(META_PATH, meta)
    return {
        "version": VERSION,
        "mode": MODE,
        "training_rows": report["training"]["rows"],
        "effective_rows": report["training"]["effective_rows"],
        "repeated_errors": len(report["repeated_errors"]),
        "promotion_ready": report["promotion_gate"]["ready"],
    }


def main():
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
