from __future__ import annotations

"""Tenis AI v9.2.6 — MODEL @ SUPERBET LINE projection adapter.

This module does not train or modify any model and never uses bookmaker prices.
It only reuses already-produced Tenis AI match state (hold probabilities and
set targets) to evaluate additional real Superbet lines that the base adapter
cannot map directly.
"""

import math
from collections import defaultdict

try:
    from . import model as core_model
    from . import superbet_market_context_v91 as base
except ImportError:
    import model as core_model
    import superbet_market_context_v91 as base

VERSION = "v9.2.6"
SUPPORTED_MARKETS = {
    "match_game_handicap",
    "set1_game_handicap",
    "set2_game_handicap",
    "player_total_games",
    "set2_total",
    "set3_total",
    "most_aces",
}


def _prob01(value):
    x = base._num(value)
    if x is None:
        return None
    if x > 1:
        x /= 100.0
    return max(0.0, min(1.0, x))


def _named_probability(block, player):
    if not isinstance(block, dict):
        return None
    target = base._name_key(player)
    for name, value in block.items():
        if base._name_key(name) == target:
            return _prob01(value)
    return None


def _normalize(dist):
    if not isinstance(dist, dict):
        return None
    z = sum(float(v) for v in dist.values() if base._num(v) is not None and float(v) >= 0)
    if z <= 0:
        return None
    return {k: float(v) / z for k, v in dist.items() if base._num(v) is not None and float(v) >= 0}


def _add(dist, key, probability):
    dist[key] += float(probability)


def _projection_distributions(match: dict):
    if not isinstance(match, dict) or not match.get("model_ready"):
        return None
    p1, p2 = str(match.get("p1") or ""), str(match.get("p2") or "")
    service = match.get("service_model") or {}
    h1 = _prob01(service.get("p1_hold"))
    h2 = _prob01(service.get("p2_hold"))
    first_target = _named_probability(match.get("first_set_win"), p1)
    third_target = _named_probability(match.get("third_set_win"), p1)
    second = match.get("second_set_context") or {}
    second_if_win = _prob01(second.get("p1_if_p1_wins_set1"))
    second_if_loss = _prob01(second.get("p1_if_p1_loses_set1"))
    if None in {h1, h2, first_target, second_if_win, second_if_loss, third_target}:
        return None

    raw = core_model._set_distribution(h1, h2)
    first_dist = core_model._reweight_set_distribution(raw, first_target)
    second_win_dist = core_model._reweight_set_distribution(raw, second_if_win)
    second_loss_dist = core_model._reweight_set_distribution(raw, second_if_loss)
    third_dist = core_model._reweight_set_distribution(raw, third_target)

    set1_margin = defaultdict(float)
    set2_margin = defaultdict(float)
    set2_total = defaultdict(float)
    set3_total = defaultdict(float)
    match_margin = defaultdict(float)
    p1_total = defaultdict(float)
    p2_total = defaultdict(float)

    for (a1, b1), pset1 in first_dist.items():
        _add(set1_margin, a1 - b1, pset1)
        p1won1 = a1 > b1
        second_dist = second_win_dist if p1won1 else second_loss_dist
        for (a2, b2), pset2 in second_dist.items():
            p12 = pset1 * pset2
            _add(set2_margin, a2 - b2, p12)
            _add(set2_total, a2 + b2, p12)
            p1won2 = a2 > b2
            if (p1won1 and p1won2) or ((not p1won1) and (not p1won2)):
                a = a1 + a2
                b = b1 + b2
                _add(match_margin, a - b, p12)
                _add(p1_total, a, p12)
                _add(p2_total, b, p12)
                continue
            for (a3, b3), pset3 in third_dist.items():
                pr = p12 * pset3
                a = a1 + a2 + a3
                b = b1 + b2 + b3
                _add(match_margin, a - b, pr)
                _add(p1_total, a, pr)
                _add(p2_total, b, pr)

    for (a3, b3), probability in third_dist.items():
        _add(set3_total, a3 + b3, probability)

    return {
        "set1_margin": _normalize(set1_margin),
        "set2_margin": _normalize(set2_margin),
        "set2_total": _normalize(set2_total),
        "set3_total": _normalize(set3_total),
        "match_margin": _normalize(match_margin),
        "p1_total": _normalize(p1_total),
        "p2_total": _normalize(p2_total),
    }


def _ou_probability(dist, line, pick):
    line = base._line(line)
    if not isinstance(dist, dict) or line is None or pick not in {"over", "under"}:
        return None
    z = sum(dist.values())
    if z <= 0:
        return None
    if pick == "over":
        selected = sum(p for value, p in dist.items() if float(value) > line)
    else:
        selected = sum(p for value, p in dist.items() if float(value) < line)
    return max(0.0, min(100.0, 100.0 * selected / z))


def _handicap_probability(dist, line, side):
    line = base._line(line)
    if not isinstance(dist, dict) or line is None or side not in {"p1", "p2"}:
        return None
    z = sum(dist.values())
    if z <= 0:
        return None
    selected = 0.0
    for margin, probability in dist.items():
        selected_margin = float(margin) if side == "p1" else -float(margin)
        if selected_margin + line > 1e-12:
            selected += probability
    return max(0.0, min(100.0, 100.0 * selected / z))


def _selection_side(match, pick):
    key = base._name_key(pick)
    if key and key == base._name_key(match.get("p1")):
        return "p1"
    if key and key == base._name_key(match.get("p2")):
        return "p2"
    return None


def _poisson_probs(mean):
    mean = base._num(mean)
    if mean is None or mean < 0:
        return None
    limit = max(25, int(math.ceil(mean + 10.0 * math.sqrt(mean + 1.0))))
    pmf = math.exp(-mean)
    out = [pmf]
    for k in range(1, limit + 1):
        pmf *= mean / k
        out.append(pmf)
    z = sum(out)
    return [p / z for p in out] if z > 0 else None


def _most_aces_probability(match, pick):
    props = match.get("serve_props_v72") or {}
    if not isinstance(props, dict) or not props.get("ready"):
        return None
    m1 = base._num((((props.get("p1") or {}).get("aces") or {}).get("mean")))
    m2 = base._num((((props.get("p2") or {}).get("aces") or {}).get("mean")))
    a, b = _poisson_probs(m1), _poisson_probs(m2)
    if a is None or b is None:
        return None
    p1 = p2 = draw = 0.0
    for i, pi in enumerate(a):
        for j, pj in enumerate(b):
            pr = pi * pj
            if i > j:
                p1 += pr
            elif j > i:
                p2 += pr
            else:
                draw += pr
    target = base._name_key(pick)
    if target == base._name_key(match.get("p1")):
        return 100.0 * p1
    if target == base._name_key(match.get("p2")):
        return 100.0 * p2
    if str(pick or "").casefold() in {"draw", "tie", "x"}:
        return 100.0 * draw
    return None


def projection_probability(match: dict, selection: dict, distributions=None):
    market = str(selection.get("market") or "")
    if market not in SUPPORTED_MARKETS:
        return None, None
    if market == "most_aces":
        probability = _most_aces_probability(match, selection.get("pick"))
        return probability, "serve_props_v72_independent_poisson"

    distributions = distributions or _projection_distributions(match)
    if not distributions:
        return None, None
    line = selection.get("line")
    pick = selection.get("pick")
    if market == "match_game_handicap":
        return _handicap_probability(distributions.get("match_margin"), line, _selection_side(match, pick)), "model_joint_games_distribution"
    if market == "set1_game_handicap":
        return _handicap_probability(distributions.get("set1_margin"), line, _selection_side(match, pick)), "model_set1_distribution"
    if market == "set2_game_handicap":
        return _handicap_probability(distributions.get("set2_margin"), line, _selection_side(match, pick)), "model_set2_distribution"
    if market == "set2_total":
        return _ou_probability(distributions.get("set2_total"), line, pick), "model_set2_distribution"
    if market == "set3_total":
        return _ou_probability(distributions.get("set3_total"), line, pick), "model_set3_distribution"
    if market == "player_total_games":
        side = "p1" if base._name_key(selection.get("player")) == base._name_key(match.get("p1")) else "p2" if base._name_key(selection.get("player")) == base._name_key(match.get("p2")) else None
        dist = distributions.get(f"{side}_total") if side else None
        return _ou_probability(dist, line, pick), "model_joint_player_games_distribution"
    return None, None


def _selection_signature(selection):
    return (
        str(selection.get("market") or ""),
        int(selection.get("checkpoint") or 0),
        base._name_key(selection.get("player")),
        base._line(selection.get("line")),
        base._name_key(selection.get("pick")),
    )


def _signal_row(selection, probability, source):
    row = dict(selection)
    row.update({
        "key": f"superbet|{selection.get('market')}|{selection.get('checkpoint') or ''}|{selection.get('player') or ''}|{selection.get('line') if selection.get('line') is not None else ''}|{selection.get('pick') or ''}",
        "label": base._signal_label(selection),
        "score": round(float(probability), 3),
        "symphony_raw_probability": round(float(probability), 4),
        "symphony_market_adapter": VERSION,
        "symphony_source": f"superbet_market_v91+{source}",
        "symphony_actionable": True,
        "operator": base.BOOKMAKER,
        "operator_available": True,
        "operator_line_verified": True,
        "operator_line_source": selection.get("operator_line_source") or "oddspapi_superbet_pl",
        "exact_path_supported": True,
        "model_at_operator_line": True,
        "projection_adapter_version": VERSION,
    })
    return row


def augment_match(match: dict):
    m = dict(match)
    ctx = dict(m.get("superbet_market_v91") or {})
    selections = [x for x in (ctx.get("canonical_selections") or []) if isinstance(x, dict)]
    signals = [dict(x) for x in (ctx.get("model_signals") or []) if isinstance(x, dict)]
    existing = {_selection_signature(row) for row in signals}
    distributions = _projection_distributions(m)
    added = []
    for selection in selections:
        if _selection_signature(selection) in existing:
            continue
        probability, source = projection_probability(m, selection, distributions)
        if probability is None:
            continue
        row = _signal_row(selection, probability, source)
        signals.append(row)
        added.append(row)
        existing.add(_selection_signature(selection))
    ctx["model_signals"] = signals
    ctx["model_signals_count"] = len(signals)
    ctx["available_selections_count"] = len(selections)
    ctx["model_coverage"] = round(len(signals) / len(selections), 4) if selections else 0.0
    ctx["projection_adapter_version"] = VERSION
    ctx["projection_signals_added"] = len(added)
    ctx["projection_markets"] = sorted({row.get("market") for row in added if row.get("market")})
    ctx["prices_used"] = False
    m["superbet_market_v91"] = ctx
    return m, len(added)


def augment_results(rows):
    out, added = [], 0
    for raw in rows if isinstance(rows, list) else []:
        if not isinstance(raw, dict):
            continue
        m, count = augment_match(raw)
        out.append(m)
        added += count
    return out, added


def augment_results_file():
    rows = base._read(base.RESULTS, [])
    rows = rows if isinstance(rows, list) else []
    projected, added = augment_results(rows)
    base._write(base.RESULTS, projected)
    matches = sum(1 for m in projected if (m.get("superbet_market_v91") or {}).get("projection_signals_added"))
    signals = sum(int((m.get("superbet_market_v91") or {}).get("model_signals_count") or 0) for m in projected)
    selections = sum(int((m.get("superbet_market_v91") or {}).get("available_selections_count") or 0) for m in projected)
    return {
        "version": VERSION,
        "matches_augmented": matches,
        "signals_added": added,
        "model_signals": signals,
        "available_selections": selections,
        "coverage": round(signals / selections, 4) if selections else 0.0,
        "prices_used": False,
    }
