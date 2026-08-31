from __future__ import annotations

"""Tenis AI v9.2.4 — zero-request coverage for audited Superbet families.

This adapter enriches real Superbet selections with probabilities derived from
existing model distributions. It is intentionally operator/display focused and
has no dependency on the retired Symphony v9.x stack.
"""

import json
import re
from collections import defaultdict

try:
    from . import market_lab_v741 as lab
    from . import superbet_line_coverage_v922 as base
    from . import symphony2_state as state
except ImportError:
    import market_lab_v741 as lab
    import superbet_line_coverage_v922 as base
    import symphony2_state as state

VERSION = "v9.2.4"
RESULTS = base.RESULTS
META = base.META
DISPLAY_DERIVED_MARKETS = {
    "any_set_to_nil", "set2_exact_score", "set2_game_state", "exact_sets",
    "match_games_parity", "set1_games_parity", "set2_games_parity",
    "p1_exactly_1_set", "p1_exactly_2_sets", "p2_exactly_1_set",
    "p2_exactly_2_sets", "p1_wins_a_set", "p2_wins_a_set", "set_handicap",
}


def _score_pair(value):
    m = re.search(r"(\d+)\s*[:\-]\s*(\d+)", str(value or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _yes_no(value):
    token = str(value or "").strip().casefold()
    if token in {"yes", "tak", "true", "1"}:
        return True
    if token in {"no", "nie", "false", "0"}:
        return False
    return None


def _parity(value):
    token = str(value or "").strip().casefold()
    if token in {"odd", "nieparzyste", "nieparzysta"}:
        return 1
    if token in {"even", "parzyste", "parzysta"}:
        return 0
    return None


def _extended_bundle(match: dict) -> dict:
    first = lab.parse_exact(match.get("exact_first_set"))
    out = {
        "set1": first or None,
        "set2": None,
        "match_games": None,
        "match_sets": None,
        "set2_paths": None,
        "any_set_nil": None,
    }
    if not first or base._best_of(match) == 5:
        return out

    service = match.get("service_model") or {}
    h1 = base._num(service.get("p1_hold"))
    h2 = base._num(service.get("p2_hold"))
    if h1 is None or h2 is None:
        return out
    if h1 > 1:
        h1 /= 100.0
    if h2 > 1:
        h2 /= 100.0
    h1, h2 = lab.clamp(h1, .01, .99), lab.clamp(h2, .01, .99)

    raw = lab.base_set(h1, h2)
    p1 = match.get("p1")
    first_p1 = lab.p1win(first)
    second_default = base._target(match.get("second_set_win"), p1, first_p1)
    ctx = match.get("second_set_context") or {}
    target_if_win = base._target(ctx, "p1_if_p1_wins_set1", second_default)
    target_if_loss = base._target(ctx, "p1_if_p1_loses_set1", second_default)
    second_if_win = lab.reweight(raw, target_if_win)
    second_if_loss = lab.reweight(raw, target_if_loss)
    second = lab.mix_dist(second_if_win, second_if_loss, first_p1)
    third = lab.reweight(raw, base._target(match.get("third_set_win"), p1, first_p1))
    joint, _, exact = lab.build_match(first, second_if_win, second_if_loss, third)

    raw_paths = state._first_set_paths(h1, h2)
    path_if_win = state._reweight_winner(raw_paths, target_if_win)
    path_if_loss = state._reweight_winner(raw_paths, target_if_loss)
    keys = set(path_if_win) | set(path_if_loss)
    second_paths = {
        key: first_p1 * path_if_win.get(key, 0.0) + (1.0 - first_p1) * path_if_loss.get(key, 0.0)
        for key in keys
    }
    z = sum(second_paths.values())
    if z > 0:
        second_paths = {key: value / z for key, value in second_paths.items()}

    any_nil = 0.0
    for s1, p_s1 in first.items():
        first_nil = 0 in s1
        w1 = s1[0] > s1[1]
        second_cond = second_if_win if w1 else second_if_loss
        for s2, p_s2 in second_cond.items():
            pr12 = p_s1 * p_s2
            second_nil = 0 in s2
            w2 = s2[0] > s2[1]
            if w1 == w2:
                if first_nil or second_nil:
                    any_nil += pr12
                continue
            for s3, p_s3 in third.items():
                if first_nil or second_nil or 0 in s3:
                    any_nil += pr12 * p_s3

    out.update({
        "set2": second,
        "match_games": joint,
        "match_sets": exact,
        "set2_paths": second_paths or None,
        "any_set_nil": max(0.0, min(1.0, any_nil)),
    })
    return out


def _score_probability(dist, target):
    if not isinstance(dist, dict) or not target:
        return None
    return 100.0 * float(dist.get(tuple(target), 0.0))


def _parity_probability(dist, parity):
    if not isinstance(dist, dict) or parity not in {0, 1}:
        return None
    return 100.0 * sum(float(p) for (a, b), p in dist.items() if (int(a) + int(b)) % 2 == parity)


def _set2_checkpoint_probability(paths, checkpoint, target):
    if not isinstance(paths, dict) or checkpoint not in {2, 4, 6} or target is None:
        return None
    ia, ib = {2: (0, 1), 4: (2, 3), 6: (4, 5)}[checkpoint]
    return 100.0 * sum(float(p) for path, p in paths.items() if (path[ia], path[ib]) == tuple(target))


def _set_score_probs(exact):
    if not isinstance(exact, dict):
        return {}
    return {str(k): float(v) for k, v in exact.items()}


def _sets_event_probability(exact, market: str, selection: dict):
    probs = _set_score_probs(exact)
    if not probs:
        return None
    pick = str(selection.get("pick") or "").strip().casefold()
    yn = _yes_no(pick)

    if market == "exact_sets":
        try:
            n = int(float(pick))
        except (TypeError, ValueError):
            return None
        yes = sum(v for score, v in probs.items() if sum(map(int, score.split(":"))) == n)
    elif market == "p1_exactly_1_set":
        yes = probs.get("1:2", 0.0)
    elif market == "p1_exactly_2_sets":
        yes = probs.get("2:0", 0.0) + probs.get("2:1", 0.0)
    elif market == "p2_exactly_1_set":
        yes = probs.get("2:1", 0.0)
    elif market == "p2_exactly_2_sets":
        yes = probs.get("0:2", 0.0) + probs.get("1:2", 0.0)
    elif market == "p1_wins_a_set":
        yes = 1.0 - probs.get("0:2", 0.0)
    elif market == "p2_wins_a_set":
        yes = 1.0 - probs.get("2:0", 0.0)
    elif market == "set_handicap":
        line = base._num(selection.get("line"))
        side = base._name_key(selection.get("pick"))
        p1 = base._name_key(selection.get("_p1"))
        p2 = base._name_key(selection.get("_p2"))
        if line is None or side not in {p1, p2}:
            return None
        yes = push = 0.0
        for score, probability in probs.items():
            a, b = map(int, score.split(":"))
            margin = (a - b) if side == p1 else (b - a)
            adjusted = margin + line
            if adjusted > 1e-9:
                yes += probability
            elif abs(adjusted) <= 1e-9:
                push += probability
        return {
            "score": 100.0 * yes,
            "push_probability": 100.0 * push,
            "probability_semantics": "exact_match_set_score_distribution; display_only_until_settlement",
        }
    else:
        return None

    if market == "exact_sets":
        return {"score": 100.0 * yes, "probability_semantics": "exact_match_set_score_distribution"}
    if yn is None:
        return None
    return {
        "score": 100.0 * (yes if yn else 1.0 - yes),
        "probability_semantics": "exact_match_set_score_distribution",
    }


def _derived(match: dict, selection: dict, bundle: dict):
    market = str(selection.get("market") or "")
    pick = selection.get("pick")
    if market == "set2_exact_score":
        score = _score_probability(bundle.get("set2"), _score_pair(pick))
        return ({"score": score, "probability_semantics": "market_lab_v741_set2_distribution"} if score is not None else None), "market_lab_v741_set2_distribution"
    if market == "set2_game_state":
        score = _set2_checkpoint_probability(bundle.get("set2_paths"), int(selection.get("checkpoint") or 0), _score_pair(pick))
        return ({"score": score, "probability_semantics": "market_lab_reweighted_set2_game_paths"} if score is not None else None), "symphony2_state+market_lab_targets"
    if market == "set1_games_parity":
        score = _parity_probability(bundle.get("set1"), _parity(pick))
        return ({"score": score, "probability_semantics": "exact_set_score_parity"} if score is not None else None), "market_lab_v741_set1_distribution"
    if market == "set2_games_parity":
        score = _parity_probability(bundle.get("set2"), _parity(pick))
        return ({"score": score, "probability_semantics": "exact_set_score_parity"} if score is not None else None), "market_lab_v741_set2_distribution"
    if market == "match_games_parity":
        score = _parity_probability(bundle.get("match_games"), _parity(pick))
        return ({"score": score, "probability_semantics": "joint_match_games_parity"} if score is not None else None), "market_lab_v741_joint_games_distribution"
    if market == "any_set_to_nil":
        yn = _yes_no(pick)
        p = bundle.get("any_set_nil")
        if yn is None or p is None:
            return None, None
        return {"score": 100.0 * (p if yn else 1.0 - p), "probability_semantics": "joint_set_score_paths"}, "market_lab_v741_joint_set_paths"
    if market in {
        "exact_sets", "p1_exactly_1_set", "p1_exactly_2_sets", "p2_exactly_1_set",
        "p2_exactly_2_sets", "p1_wins_a_set", "p2_wins_a_set", "set_handicap",
    }:
        enriched = dict(selection)
        enriched["_p1"], enriched["_p2"] = match.get("p1"), match.get("p2")
        return _sets_event_probability(bundle.get("match_sets"), market, enriched), "market_lab_v741_exact_match_sets"
    return None, None


def _label(selection: dict) -> str:
    market = str(selection.get("market") or "")
    names = {
        "any_set_to_nil": "Set do zera w meczu", "set2_exact_score": "2. set · dokładny wynik",
        "set2_game_state": "2. set · stan po gemach", "exact_sets": "Dokładna liczba setów",
        "match_games_parity": "Mecz · parzystość gemów", "set1_games_parity": "1. set · parzystość gemów",
        "set2_games_parity": "2. set · parzystość gemów", "p1_exactly_1_set": "Zawodnik 1 · dokładnie 1 set",
        "p1_exactly_2_sets": "Zawodnik 1 · dokładnie 2 sety", "p2_exactly_1_set": "Zawodnik 2 · dokładnie 1 set",
        "p2_exactly_2_sets": "Zawodnik 2 · dokładnie 2 sety", "p1_wins_a_set": "Zawodnik 1 · wygra co najmniej set",
        "p2_wins_a_set": "Zawodnik 2 · wygra co najmniej set", "set_handicap": "Handicap setów",
    }
    bits = [names.get(market, market.replace("_", " "))]
    if selection.get("player"):
        bits.append(str(selection.get("player")))
    if selection.get("pick") is not None:
        bits.append(str(selection.get("pick")))
    if selection.get("line") is not None:
        bits.append(f"{float(selection['line']):+g}")
    if selection.get("checkpoint"):
        bits.append(f"po {int(selection['checkpoint'])} gemach")
    return " · ".join(bits)


def _recompute(ctx: dict, new_shadow_added: int) -> dict:
    selections = [x for x in (ctx.get("canonical_selections") or []) if isinstance(x, dict)]
    signals = [x for x in (ctx.get("model_signals") or []) if isinstance(x, dict)]
    shadow = [x for x in (ctx.get("coverage_shadow_signals") or []) if isinstance(x, dict)]
    signal_keys = {base._selection_key(x) for x in signals}
    shadow_keys = {base._selection_key(x) for x in shadow}
    selection_keys = {base._selection_key(x) for x in selections}
    playable = len(selection_keys & signal_keys)
    shadow_n = len(selection_keys & shadow_keys)
    display = len(selection_keys & (signal_keys | shadow_keys))
    coverage = defaultdict(lambda: {"available": 0, "playable_model": 0, "shadow_model": 0})
    for selection in selections:
        market = str(selection.get("market") or "unknown")
        key = base._selection_key(selection)
        coverage[market]["available"] += 1
        if key in signal_keys:
            coverage[market]["playable_model"] += 1
        elif key in shadow_keys:
            coverage[market]["shadow_model"] += 1
    by_market = {}
    for market, row in sorted(coverage.items()):
        available = int(row["available"])
        pm = int(row["playable_model"])
        sm = int(row["shadow_model"])
        by_market[market] = {
            "available": available, "model": pm + sm, "playable_model": pm, "shadow_model": sm,
            "coverage": round((pm + sm) / available, 4) if available else 0.0,
            "playable_coverage": round(pm / available, 4) if available else 0.0,
        }
    ctx["coverage_shadow_signals"] = shadow
    ctx["coverage_shadow_signals_count"] = len(shadow)
    ctx["available_selections_count"] = len(selections)
    ctx["model_coverage"] = round(playable / len(selections), 4) if selections else 0.0
    ctx["display_model_coverage"] = round(display / len(selections), 4) if selections else 0.0
    ctx["playable_covered_count"] = playable
    ctx["shadow_covered_count"] = shadow_n
    ctx["display_covered_count"] = display
    ctx["coverage_by_market"] = by_market
    ctx["operator_only_count"] = max(0, len(selections) - display)
    ctx["coverage_adapter_version"] = VERSION
    ctx["coverage_adapter_shadow_added"] = int(ctx.get("coverage_adapter_shadow_added") or 0) + new_shadow_added
    ctx["coverage_adapter_external_requests"] = 0
    ctx["prices_used"] = False
    return ctx


def enrich_match(raw: dict) -> dict:
    match = base.enrich_match(raw)
    ctx = dict(match.get("superbet_market_v91") or {})
    selections = [x for x in (ctx.get("canonical_selections") or []) if isinstance(x, dict)]
    shadow = [dict(x) for x in (ctx.get("coverage_shadow_signals") or []) if isinstance(x, dict)]
    existing = {base._selection_key(x) for x in (ctx.get("model_signals") or []) if isinstance(x, dict)}
    existing |= {base._selection_key(x) for x in shadow}
    wanted = [s for s in selections if str(s.get("market") or "") in DISPLAY_DERIVED_MARKETS and base._selection_key(s) not in existing]
    bundle = _extended_bundle(match) if wanted else {}
    added = 0
    for selection in wanted:
        result, source = _derived(match, selection, bundle)
        if not result or result.get("score") is None:
            continue
        row = base._signal(selection, result, source or "existing_distribution", False)
        row["label"] = _label(selection)
        row["coverage_adapter_version"] = VERSION
        row["coverage_status"] = "MODEL_DERIVED_DISPLAY_ONLY_PENDING_SETTLEMENT"
        row["exact_path_supported"] = False
        row["symphony_actionable"] = False
        shadow.append(row)
        existing.add(base._selection_key(selection))
        added += 1
    ctx["coverage_shadow_signals"] = shadow
    match["superbet_market_v91"] = _recompute(ctx, added)
    return match


def enrich_results(rows: list[dict]):
    out = []
    available = playable = shadow = displayed = operator_only = matches = 0
    added = shadow_added = 0
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        match = enrich_match(raw)
        ctx = match.get("superbet_market_v91") or {}
        n = int(ctx.get("available_selections_count") or 0)
        matches += int(n > 0)
        available += n
        playable += int(ctx.get("playable_covered_count") or 0)
        shadow += int(ctx.get("shadow_covered_count") or 0)
        displayed += int(ctx.get("display_covered_count") or 0)
        operator_only += int(ctx.get("operator_only_count") or 0)
        added += int(ctx.get("coverage_adapter_added") or 0)
        shadow_added += int(ctx.get("coverage_adapter_shadow_added") or 0)
        out.append(match)
    return out, {
        "version": VERSION,
        "matches_with_operator_selections": matches,
        "available_selections": available,
        "playable_model_covered_selections": playable,
        "shadow_model_covered_selections": shadow,
        "display_model_covered_selections": displayed,
        "operator_only_selections": operator_only,
        "signals_added": added,
        "shadow_signals_added": shadow_added,
        "new_family_policy": "display_only_pending_settlement",
        "external_requests": 0,
        "prices_used": False,
    }


def main():
    rows = base._read(RESULTS, [])
    rows = rows if isinstance(rows, list) else []
    out, report = enrich_results(rows)
    base._write(RESULTS, out)
    meta = base._read(META, {})
    if not isinstance(meta, dict):
        meta = {}
    meta["superbet_line_coverage_v922"] = report
    meta["superbet_line_coverage_v924"] = report
    base._write(META, meta)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
