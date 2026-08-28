from __future__ import annotations

"""Tenis AI v9.3A — deep MODEL/RAW scenario lattice for Tennis Symphony.

This is a separate analysis surface, not a Superbet PLAYABLE projection.

It keeps the existing v9.1 PLAYABLE Symphony untouched and builds a second,
model-first scenario search with a richer exact tennis state:
- first-set checkpoints after 2/4/6 games;
- second-set checkpoints after 2/4/6 games;
- exact scores of sets 1/2 and (when played) set 3;
- player game totals, set totals, match total, final set score and set count;
- deterministic v9.2.4 mapped market families as analysis-only candidates.

Bookmaker prices are never inputs. v9.2.4 DISPLAY/SHADOW markets may help describe
MODEL/RAW scenarios, but they remain non-actionable until their own v9.2.5
settlement/promotion gate says otherwise.
"""

from collections import defaultdict
from copy import deepcopy
import json
import re

try:
    from . import symphony_engine_v90 as core
    from . import symphony_engine_v90c as full
    from . import symphony_engine_v91 as fast
    from .symphony_c4 import leg_count_intelligence
except ImportError:
    import symphony_engine_v90 as core
    import symphony_engine_v90c as full
    import symphony_engine_v91 as fast
    from symphony_c4 import leg_count_intelligence

VERSION = "v9.3A"
MODE = "MODEL_RAW_ANALYSIS_ONLY"
REPORT = core.OUT / "symphony_model_v93.json"

V924_CANDIDATE_MARKETS = {
    "any_set_to_nil",
    "set2_exact_score",
    "set2_game_state",
    "exact_sets",
    "match_games_parity",
    "set1_games_parity",
    "set2_games_parity",
    "p1_exactly_1_set",
    "p1_exactly_2_sets",
    "p2_exactly_1_set",
    "p2_exactly_2_sets",
    "p1_wins_a_set",
    "p2_wins_a_set",
    "set_handicap",
}

DEEP_EXACT_MARKETS = V924_CANDIDATE_MARKETS | {
    "game_state",
    "match_winner",
    "set1_winner",
    "set2_winner",
    "set3_winner",
    "match_total",
    "set1_total",
    "set2_total",
    "set3_total",
    "total_sets",
    "exact_match_score",
    "set1_exact_score",
    "set1_tiebreak",
    "match_game_handicap",
    "set1_game_handicap",
    "set2_game_handicap",
}


def _block_target(block, key, default):
    p = core._market_player_prob(block, str(key))
    return p if p is not None else default


def _set2_path_distributions(match: dict, h1: float, h2: float, fallback: float):
    raw = core._first_set_paths(h1, h2)
    ctx = match.get("second_set_context") or {}
    win_target = _block_target(ctx, "p1_if_p1_wins_set1", fallback)
    loss_target = _block_target(ctx, "p1_if_p1_loses_set1", fallback)
    return (
        core._reweight_winner(raw, win_target),
        core._reweight_winner(raw, loss_target),
        win_target,
        loss_target,
    )


def _build_deep_outcomes(match: dict) -> list[dict]:
    """Exact multi-set state retaining set-2 checkpoints without changing model math."""
    holds = core._service_holds(match)
    if not holds:
        return []
    h1, h2 = holds
    best_of = core._best_of(match)
    need = best_of // 2 + 1

    first = core._reweight_winner(
        core._first_set_paths(h1, h2),
        core._set_target(match, 1),
    )
    second_default = core._set_target(match, 2)
    if second_default is None:
        second_default = core._winner_marginal(first)
    second_if_first_win, second_if_first_loss, _, _ = _set2_path_distributions(
        match, h1, h2, second_default
    )
    later = {
        n: core._reweight_winner(
            core._terminal_set_distribution(h1, h2),
            core._set_target(match, n),
            score_indexes=(0, 1),
        )
        for n in range(3, best_of + 1)
    }

    # Keep every field needed by exact predicates while aggregating away
    # irrelevant later-set path details.
    agg: dict[tuple, float] = defaultdict(float)

    for path1, p1_path in first.items():
        c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b = map(int, path1)
        first_win = s1a > s1b
        second_dist = second_if_first_win if first_win else second_if_first_loss
        for path2, p2_path in second_dist.items():
            d2a, d2b, d4a, d4b, d6a, d6b, s2a, s2b = map(int, path2)
            sa = int(first_win) + int(s2a > s2b)
            sb = int(not first_win) + int(s2b > s2a)
            games_a = s1a + s2a
            games_b = s1b + s2b
            any_nil = int(0 in (s1a, s1b) or 0 in (s2a, s2b))
            base_prob = p1_path * p2_path

            # Set 3 is retained because the current Symphony already models its
            # winner/total. Sets 4/5 are aggregated after they affect final state.
            if sa >= need or sb >= need:
                key = (
                    c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b,
                    d2a, d2b, d4a, d4b, d6a, d6b, s2a, s2b,
                    -1, -1, 0, sa, sb, games_a, games_b, any_nil,
                )
                agg[key] += base_prob
                continue

            frontier = {(sa, sb, games_a, games_b, any_nil, -1, -1, 0): base_prob}
            for set_no in range(3, best_of + 1):
                nxt: dict[tuple, float] = defaultdict(float)
                dist = later.get(set_no) or {}
                for (xa, xb, ga_total, gb_total, nil_flag, s3a, s3b, s3winner), prob in frontier.items():
                    if xa >= need or xb >= need:
                        nxt[(xa, xb, ga_total, gb_total, nil_flag, s3a, s3b, s3winner)] += prob
                        continue
                    for score, sp in dist.items():
                        ga, gb = map(int, score)
                        na = xa + int(ga > gb)
                        nb = xb + int(gb > ga)
                        n_s3a, n_s3b, n_s3winner = s3a, s3b, s3winner
                        if set_no == 3:
                            n_s3a, n_s3b = ga, gb
                            n_s3winner = 1 if ga > gb else 2
                        nxt[(
                            na, nb, ga_total + ga, gb_total + gb,
                            int(bool(nil_flag) or ga == 0 or gb == 0),
                            n_s3a, n_s3b, n_s3winner,
                        )] += prob * sp
                frontier = nxt
                if frontier and all(xa >= need or xb >= need for xa, xb, *_ in frontier):
                    break

            for (xa, xb, ga_total, gb_total, nil_flag, s3a, s3b, s3winner), prob in frontier.items():
                if xa < need and xb < need:
                    continue
                key = (
                    c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b,
                    d2a, d2b, d4a, d4b, d6a, d6b, s2a, s2b,
                    s3a, s3b, s3winner, xa, xb, ga_total, gb_total, nil_flag,
                )
                agg[key] += prob

    total = sum(agg.values())
    if total <= core.EPS:
        return []

    rows = []
    for key, prob in agg.items():
        (
            c2a, c2b, c4a, c4b, c6a, c6b, s1a, s1b,
            d2a, d2b, d4a, d4b, d6a, d6b, s2a, s2b,
            s3a, s3b, s3winner, sa, sb, games_a, games_b, any_nil,
        ) = key
        set3 = (s3a, s3b) if s3a >= 0 and s3b >= 0 else None
        rows.append({
            "cp2": (c2a, c2b),
            "cp4": (c4a, c4b),
            "cp6": (c6a, c6b),
            "set1": (s1a, s1b),
            "set2_cp2": (d2a, d2b),
            "set2_cp4": (d4a, d4b),
            "set2_cp6": (d6a, d6b),
            "set2": (s2a, s2b),
            "set3": set3,
            "sets": (sa, sb),
            "total_games": int(games_a + games_b),
            "p1_games": int(games_a),
            "p2_games": int(games_b),
            "set_count": int(sa + sb),
            "winner": 1 if sa > sb else 2,
            "set1_winner": 1 if s1a > s1b else 2,
            "set2_winner": 1 if s2a > s2b else 2,
            "set3_winner": s3winner or None,
            "set1_tiebreak": {s1a, s1b} == {6, 7},
            "set2_tiebreak": {s2a, s2b} == {6, 7},
            "any_set_to_nil": bool(any_nil),
            "prob": prob / total,
        })
    return rows


def _parity_pick(value):
    p = core._ascii(value).replace(" ", "")
    if p in {"odd", "nieparzyste", "nieparzysta", "nieparzysty"}:
        return 1
    if p in {"even", "parzyste", "parzysta", "parzysty"}:
        return 0
    return None


def _exact_sets_pick(value):
    m = re.search(r"\b([2-5])\b", str(value or ""))
    return int(m.group(1)) if m else None


def _handicap_predicate(match: dict, candidate, field_a: str, field_b: str):
    side = core._side_for_pick(match, candidate.pick)
    line = candidate.line
    if side not in {1, 2} or line is None:
        return None

    def pred(outcome):
        a = outcome.get(field_a)
        b = outcome.get(field_b)
        if a is None or b is None:
            return False
        margin = (float(a) - float(b)) if side == 1 else (float(b) - float(a))
        return margin + float(line) > 1e-9

    return pred


def _deep_predicate(base_predicate):
    def predicate(match: dict, candidate):
        existing = base_predicate(match, candidate)
        if existing is not None:
            return existing

        market = candidate.market
        pick = candidate.pick

        if market == "set2_winner":
            side = core._side_for_pick(match, pick)
            return (lambda o: o.get("set2_winner") == side) if side else None

        if market == "set3_winner":
            side = core._side_for_pick(match, pick)
            return (lambda o: o.get("set3_winner") == side) if side else None

        if market == "set2_exact_score":
            target = core._score_pair(pick)
            return (lambda o: o.get("set2") == target) if target else None

        if market == "set2_game_state":
            cp = candidate.checkpoint
            target = core._score_pair(pick)
            if cp not in core.CHECKPOINTS or target is None:
                return None
            return lambda o: o.get(f"set2_cp{cp}") == target

        if market in {"set2_total", "set3_total"}:
            side = core._ou_side(pick)
            line = candidate.line
            field = "set2" if market == "set2_total" else "set3"
            if side is None or line is None:
                return None
            if side == "over":
                return lambda o: o.get(field) is not None and sum(o[field]) > line
            return lambda o: o.get(field) is not None and sum(o[field]) < line

        if market == "exact_sets":
            wanted = _exact_sets_pick(pick)
            return (lambda o: o.get("set_count") == wanted) if wanted else None

        if market in {"match_games_parity", "set1_games_parity", "set2_games_parity"}:
            parity = _parity_pick(pick)
            if parity is None:
                return None
            if market == "match_games_parity":
                return lambda o: int(o.get("total_games", -1)) % 2 == parity
            field = "set1" if market == "set1_games_parity" else "set2"
            return lambda o: o.get(field) is not None and sum(o[field]) % 2 == parity

        if market == "any_set_to_nil":
            yn = core._yes_no(pick)
            return (lambda o: bool(o.get("any_set_to_nil")) is yn) if yn is not None else None

        if market in {
            "p1_exactly_1_set", "p1_exactly_2_sets",
            "p2_exactly_1_set", "p2_exactly_2_sets",
            "p1_wins_a_set", "p2_wins_a_set",
        }:
            yn = core._yes_no(pick)
            if yn is None:
                return None
            if market == "p1_exactly_1_set":
                event = lambda o: o["sets"][0] == 1
            elif market == "p1_exactly_2_sets":
                event = lambda o: o["sets"][0] == 2
            elif market == "p2_exactly_1_set":
                event = lambda o: o["sets"][1] == 1
            elif market == "p2_exactly_2_sets":
                event = lambda o: o["sets"][1] == 2
            elif market == "p1_wins_a_set":
                event = lambda o: o["sets"][0] >= 1
            else:
                event = lambda o: o["sets"][1] >= 1
            return lambda o: bool(event(o)) is yn

        if market == "set_handicap":
            return _handicap_predicate(match, candidate, "_set_margin_p1", "_set_margin_p2")

        if market == "match_game_handicap":
            return _handicap_predicate(match, candidate, "p1_games", "p2_games")

        if market == "set1_game_handicap":
            side = core._side_for_pick(match, pick)
            line = candidate.line
            if side not in {1, 2} or line is None:
                return None
            return lambda o: (
                ((o["set1"][0] - o["set1"][1]) if side == 1 else (o["set1"][1] - o["set1"][0]))
                + float(line) > 1e-9
            )

        if market == "set2_game_handicap":
            side = core._side_for_pick(match, pick)
            line = candidate.line
            if side not in {1, 2} or line is None:
                return None
            return lambda o: (
                ((o["set2"][0] - o["set2"][1]) if side == 1 else (o["set2"][1] - o["set2"][0]))
                + float(line) > 1e-9
            )

        return None

    return predicate


def _deep_outcome_finalize(outcomes: list[dict]) -> list[dict]:
    for row in outcomes:
        sets = row.get("sets") or (0, 0)
        row["_set_margin_p1"] = int(sets[0])
        row["_set_margin_p2"] = int(sets[1])
    return outcomes


def _deep_compatible(base_compatible):
    exclusive = {
        "set2_exact_score", "exact_sets",
        "match_games_parity", "set1_games_parity", "set2_games_parity",
        "any_set_to_nil",
        "p1_exactly_1_set", "p1_exactly_2_sets",
        "p2_exactly_1_set", "p2_exactly_2_sets",
        "p1_wins_a_set", "p2_wins_a_set",
    }

    def compatible(a, b):
        if not base_compatible(a, b):
            return False
        if a.market == b.market == "set2_game_state" and a.checkpoint == b.checkpoint:
            return core._score_pair(a.pick) == core._score_pair(b.pick)
        if a.market == b.market and a.market in exclusive:
            return core._compact(a.pick) == core._compact(b.pick)
        if a.market == b.market == "set_handicap":
            return False
        return True

    return compatible


def _candidate_only_rows(match: dict) -> list[dict]:
    ctx = match.get("superbet_market_v91") or {}
    rows = []
    for raw in ctx.get("coverage_shadow_signals") or []:
        if not isinstance(raw, dict):
            continue
        market = str(raw.get("market") or "")
        if market not in V924_CANDIDATE_MARKETS:
            continue
        row = dict(raw)
        row["symphony_source"] = "superbet_v924_model_derived_candidate"
        row["symphony_raw_probability"] = row.get("score")
        row["symphony_scenario_layer"] = "MODEL_DERIVED_SHADOW"
        row["symphony_actionable"] = False
        row["operator_playable"] = False
        row["scenario_candidate_only"] = True
        rows.append(row)
    return rows


def _augment_model_raw(match: dict):
    augmented, meta = full.augment_match_c4(deepcopy(match))
    auto = dict(augmented.get("autolearn_v84") or {})
    signals = [dict(x) for x in (auto.get("signals") or []) if isinstance(x, dict)]
    existing = {full._semantic_signature(x) for x in signals}
    by_key = dict(meta.get("by_key") or {})

    added = 0
    for row in _candidate_only_rows(match):
        sig = full._semantic_signature(row)
        if sig in existing:
            continue
        signals.append(row)
        existing.add(sig)
        key = core._signal_key(row)
        if key:
            by_key[key] = row
        added += 1

    auto["signals"] = signals
    augmented["autolearn_v84"] = auto
    meta["by_key"] = by_key
    meta["deep_candidate_added"] = added
    augmented, meta = full._dedupe_augmented(augmented, meta)
    return augmented, meta


def _path_text_v93(o: dict) -> str:
    first = (
        f"1S {o['cp2'][0]}:{o['cp2'][1]} → "
        f"{o['cp4'][0]}:{o['cp4'][1]} → {o['cp6'][0]}:{o['cp6'][1]} "
        f"→ {o['set1'][0]}:{o['set1'][1]}"
    )
    second = (
        f"2S {o['set2_cp2'][0]}:{o['set2_cp2'][1]} → "
        f"{o['set2_cp4'][0]}:{o['set2_cp4'][1]} → "
        f"{o['set2_cp6'][0]}:{o['set2_cp6'][1]} "
        f"→ {o['set2'][0]}:{o['set2'][1]}"
    )
    third = f" → 3S {o['set3'][0]}:{o['set3'][1]}" if o.get("set3") else ""
    score = f" → mecz {o['sets'][0]}:{o['sets'][1]}"
    return first + " · " + second + third + score


def _top_paths_v93(match: dict, combo, outcomes: list[dict], limit=5):
    preds = [core._predicate(match, c) for c in combo]
    supported = [p for p in preds if p is not None]
    if not supported:
        return []
    rows = [o for o in outcomes if all(p(o) for p in supported)]
    rows.sort(key=lambda x: x["prob"], reverse=True)
    out = []
    for row in rows[:limit]:
        out.append({
            "path": _path_text_v93(row),
            "set1": f"{row['set1'][0]}:{row['set1'][1]}",
            "set2": f"{row['set2'][0]}:{row['set2'][1]}",
            "set3": f"{row['set3'][0]}:{row['set3'][1]}" if row.get("set3") else None,
            "match_score": f"{row['sets'][0]}:{row['sets'][1]}",
            "total_games": row["total_games"],
            "probability_mass": round(row["prob"] * 100.0, 3),
        })
    return out


def _story_v93(match: dict, combo) -> tuple[str, str]:
    by_market = defaultdict(list)
    for c in combo:
        by_market[c.market].append(c)

    def side(market):
        c = next(iter(by_market.get(market) or []), None)
        return core._side_for_pick(match, c.pick) if c else None

    exact_sets = next(iter(by_market.get("exact_sets") or []), None)
    exact_sets_n = _exact_sets_pick(exact_sets.pick) if exact_sets else None
    match_side = side("match_winner")
    set1_side = side("set1_winner")
    set2_side = side("set2_winner")

    if match_side and set1_side and match_side != set1_side:
        return "COMEBACK_AFTER_SET1", "Przegrany 1. set, potem odwrócenie meczu."
    if match_side and set1_side == match_side and set2_side == match_side:
        return "STRAIGHT_SETS_CONTROL", "Ten sam zawodnik kontroluje oba pierwsze sety."
    if exact_sets_n and exact_sets_n >= 3:
        return "SPLIT_SETS_DECIDER", "Scenariusz zakłada podział setów i dalszą walkę."
    if any(c.market == "any_set_to_nil" and core._yes_no(c.pick) is True for c in combo):
        return "ROUT_OR_COLLAPSE", "Co najmniej jeden set ma profil bardzo jednostronny."
    if any(c.market == "set1_tiebreak" and core._yes_no(c.pick) is True for c in combo):
        return "TIEBREAK_PRESSURE", "Scenariusz prowadzi do seta rozstrzyganego przy 6:6."

    set1_states = {
        c.checkpoint: core._score_pair(c.pick)
        for c in by_market.get("game_state") or []
        if c.checkpoint
    }
    set2_states = {
        c.checkpoint: core._score_pair(c.pick)
        for c in by_market.get("set2_game_state") or []
        if c.checkpoint
    }
    if set1_states.get(2) in {(2, 0), (0, 2)} and set1_states.get(4) == (2, 2):
        return "BREAK_REBREAK_SET1", "Wczesny break w 1. secie i szybki rebreak."
    if set2_states.get(2) in {(2, 0), (0, 2)} and set2_states.get(4) == (2, 2):
        return "BREAK_REBREAK_SET2", "Wczesny break w 2. secie i szybki rebreak."
    if (
        set1_states.get(2) == (1, 1) and set1_states.get(4) == (2, 2)
        and set1_states.get(6) == (3, 3)
    ):
        return "SERVE_WAR_SET1", "Pierwszy set długo idzie gem za gem."
    if (
        set2_states.get(2) == (1, 1) and set2_states.get(4) == (2, 2)
        and set2_states.get(6) == (3, 3)
    ):
        return "SERVE_WAR_SET2", "Drugi set długo idzie gem za gem."

    return "MULTI_MARKET_CONSENSUS", "Najmocniejsze rynki opisują wspólny przebieg meczu."


def _decorate_leg_v93(leg: dict, evidence_by_key: dict):
    out = dict(leg)
    raw = evidence_by_key.get(str(out.get("key") or "")) or {}
    out["market_source"] = raw.get("symphony_source") or raw.get("operator_line_source")
    out["raw_market_probability"] = raw.get("symphony_raw_probability", raw.get("score"))
    out["scenario_layer"] = raw.get("symphony_scenario_layer") or (
        "MODEL_DERIVED_SHADOW" if raw.get("scenario_candidate_only") else "MODEL_RAW"
    )
    out["scenario_candidate_only"] = bool(raw.get("scenario_candidate_only"))
    out["operator_playable"] = bool(raw.get("operator_playable") is True)
    return out


def _decorate_comp_v93(match: dict, comp: dict, candidates_by_key: dict, evidence_by_key: dict, outcomes: list[dict]):
    if not isinstance(comp, dict):
        return comp
    out = dict(comp)
    selection = [_decorate_leg_v93(x, evidence_by_key) for x in out.get("selection") or []]
    out["selection"] = selection
    combo = tuple(
        candidates_by_key[str(x.get("key") or "")]
        for x in selection
        if str(x.get("key") or "") in candidates_by_key
    )
    if combo:
        story, narrative = _story_v93(match, combo)
        out["story_type"] = story
        out["scenario_narrative"] = narrative
        out["top_paths"] = _top_paths_v93(match, combo, outcomes)
        out["exact_path_scope"] = "SET1+SET2+MATCH"
    out["analysis_only"] = True
    out["operator_playable"] = False
    out["alternatives"] = [
        _decorate_comp_v93(match, alt, candidates_by_key, evidence_by_key, outcomes)
        for alt in out.get("alternatives") or []
    ]
    return out


def build_match_model_scenario(match: dict, shadow_for_match: dict[str, dict[str, float]], legs: int = 4):
    augmented, meta = _augment_model_raw(match)
    outcomes = _deep_outcome_finalize(_build_deep_outcomes(augmented))
    signals = [x for x in ((augmented.get("autolearn_v84") or {}).get("signals") or []) if isinstance(x, dict)]

    original_predicate = core._predicate
    original_compatible = core._compatible
    core._predicate = _deep_predicate(original_predicate)
    core._compatible = _deep_compatible(full.comparison_compatible(original_compatible))
    try:
        candidates = []
        seen = set()
        for signal in signals:
            key = core._signal_key(signal)
            c = core._candidate(augmented, signal, shadow_for_match.get(key, {}), outcomes)
            if c is None:
                continue
            sig = full._semantic_signature(signal)
            if sig in seen:
                continue
            seen.add(sig)
            candidates.append(c)

        if len(candidates) < 2:
            return None

        old_pool = core.POOL_LIMIT
        old_beam = core.BEAM_WIDTH
        core.POOL_LIMIT = max(old_pool, 48)
        core.BEAM_WIDTH = max(old_beam, 112)
        try:
            comps = fast._fast_one_pass_compositions(augmented, candidates, outcomes)
        finally:
            core.POOL_LIMIT = old_pool
            core.BEAM_WIDTH = old_beam

        if not comps:
            return None

        candidates_by_key = {c.key: c for c in candidates if c.key}
        evidence_by_key = dict(meta.get("by_key") or {})
        comps = {
            str(n): _decorate_comp_v93(
                augmented, comp, candidates_by_key, evidence_by_key, outcomes
            )
            for n, comp in comps.items()
        }
    finally:
        core._predicate = original_predicate
        core._compatible = original_compatible

    requested = str(max(2, min(6, int(legs))))
    default = comps.get(requested) or next(iter(comps.values()), None)
    if not default:
        return None

    row = {
        "match_key": core._match_key(match),
        "id": match.get("id") if match.get("id") is not None else match.get("match_id"),
        "p1": match.get("p1"),
        "p2": match.get("p2"),
        "scheduled_time": match.get("scheduled_time"),
        "tour": match.get("tour"),
        "tournament": match.get("tournament"),
        "surface": match.get("surface"),
        "best_of": core._best_of(match),
        "path_engine": "DEEP_EXACT_SET1_SET2" if outcomes else "EVIDENCE_ONLY",
        "outcome_states": len(outcomes),
        "compositions": comps,
        "story_type": default.get("story_type"),
        "scenario_narrative": default.get("scenario_narrative"),
        "symphony_score": default.get("symphony_score"),
        "joint_probability": default.get("joint_probability"),
        "path_coverage": default.get("path_coverage"),
        "prod_shadow_agreement": default.get("prod_shadow_agreement"),
        "model_conflict": default.get("model_conflict"),
        "selection": default.get("selection") or [],
        "top_paths": default.get("top_paths") or [],
        "candidate_pool": [
            _decorate_leg_v93(c.as_dict(), evidence_by_key)
            for c in sorted(candidates, key=lambda x: x.evidence_score, reverse=True)[:28]
        ],
        "market_adapter": {
            "version": VERSION,
            "catalog_size": len(candidates),
            "deep_candidate_added": int(meta.get("deep_candidate_added") or 0),
            "exact_market_families": sorted(DEEP_EXACT_MARKETS),
        },
        "analysis_only": True,
        "operator_playable": False,
    }
    intelligence = leg_count_intelligence(row)
    row["leg_count_intelligence"] = intelligence
    row["recommended_leg_count"] = intelligence.get("recommended")
    return row


def build_report(legs: int = 4) -> dict:
    results = core._read(core.RESULTS, [])
    shadow = core._read(core.SHADOW, {})
    results = results if isinstance(results, list) else []
    shadow = shadow if isinstance(shadow, dict) else {}
    shadow_idx = core._shadow_index(shadow)

    rows = []
    for match in results:
        if not isinstance(match, dict) or not match.get("model_ready"):
            continue
        key = core._match_key(match)
        row = build_match_model_scenario(match, shadow_idx.get(key, {}), legs=legs)
        if row:
            rows.append(row)

    rows.sort(key=lambda x: (
        -float(x.get("symphony_score") or 0.0),
        str(x.get("scheduled_time") or ""),
    ))
    return {
        "version": VERSION,
        "mode": MODE,
        "matches_count": len(rows),
        "matches": rows,
        "contract": {
            "separate_from_superbet_playable": True,
            "core_prod_adaptive_shadow_scores_unchanged": True,
            "v924_candidate_markets_analysis_only": True,
            "v925_promotion_gate_not_bypassed": True,
            "bookmaker_prices_used": False,
            "external_requests": 0,
            "set2_checkpoints_exact_from_tennis_paths": True,
            "joint_probability_only_when_all_legs_share_exact_state_space": True,
        },
    }


def run(legs: int = 4) -> dict:
    report = build_report(legs=legs)
    core._write(REPORT, report)
    return {
        "status": "OK",
        "version": VERSION,
        "mode": MODE,
        "matches": report.get("matches_count", 0),
        "output": str(REPORT.relative_to(core.ROOT)),
        "production_influence": False,
        "playable_influence": False,
        "external_requests": 0,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
