from __future__ import annotations

"""Tenis AI v9.2.2 — zero-request model coverage for real Superbet lines.

Runs after Superbet FINALIZE. It never calls an external API and never changes
core model/training math. It only reuses distributions already present in
results.json (or deterministically reconstructs Market Lab's existing BO3
probability distributions) to cover additional real operator selections.

Actionable derived coverage:
- match game handicap on any real operator line;
- set 1 game handicap on any real operator line;
- set 2 game handicap on any real operator line.

Display-only SHADOW coverage:
- "most aces" from existing Serve Props ace means using an independent Poisson
  comparison. It is deliberately NOT injected into PLAYABLE until settlement /
  backtest evidence exists for that target.

Bookmaker prices are not inputs. Missing evidence stays uncovered instead of
being fabricated.
"""

import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import market_lab_v741 as lab

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "frontend" / "data" / "results.json"
META = ROOT / "frontend" / "data" / "meta.json"
VERSION = "v9.2.2"
ACTIONABLE_DERIVED_MARKETS = {
    "match_game_handicap",
    "set1_game_handicap",
    "set2_game_handicap",
}
SHADOW_DERIVED_MARKETS = {"most_aces"}
DERIVED_MARKETS = ACTIONABLE_DERIVED_MARKETS | SHADOW_DERIVED_MARKETS


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _num(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _name_key(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).casefold()
    return " ".join(sorted(text.split()))


def _best_of(match: dict) -> int:
    try:
        return 5 if int(match.get("best_of") or 3) == 5 else 3
    except (TypeError, ValueError):
        return 3


def _target(block, player, default):
    if not isinstance(block, dict):
        return default
    target = _name_key(player)
    for name, value in block.items():
        if _name_key(name) != target:
            continue
        p = _num(value)
        if p is None:
            return default
        return lab.clamp(p / 100.0 if p > 1 else p, .03, .97)
    return default


def _selection_key(selection: dict) -> str:
    return (
        f"superbet|{selection.get('market') or ''}|{selection.get('checkpoint') or ''}|"
        f"{selection.get('player') or ''}|"
        f"{selection.get('line') if selection.get('line') is not None else ''}|"
        f"{selection.get('pick') or ''}"
    )


def _distribution_bundle(match: dict) -> dict:
    """Rebuild Market Lab distributions locally; zero network and no new math."""
    first = lab.parse_exact(match.get("exact_first_set"))
    bundle = {"set1": first or None, "set2": None, "match": None}
    if not first or _best_of(match) == 5:
        return bundle

    service = match.get("service_model") or {}
    h1 = _num(service.get("p1_hold"))
    h2 = _num(service.get("p2_hold"))
    if h1 is None or h2 is None:
        return bundle
    if h1 > 1:
        h1 /= 100.0
    if h2 > 1:
        h2 /= 100.0

    raw = lab.base_set(h1, h2)
    p1 = match.get("p1")
    first_p1 = lab.p1win(first)
    second_default = _target(match.get("second_set_win"), p1, first_p1)
    ctx = match.get("second_set_context") or {}
    second_if_win = lab.reweight(raw, _target(ctx, "p1_if_p1_wins_set1", second_default))
    second_if_loss = lab.reweight(raw, _target(ctx, "p1_if_p1_loses_set1", second_default))
    second = lab.mix_dist(second_if_win, second_if_loss, first_p1)
    third = lab.reweight(raw, _target(match.get("third_set_win"), p1, first_p1))
    joint, _, _ = lab.build_match(first, second_if_win, second_if_loss, third)
    bundle["set2"] = second or None
    bundle["match"] = joint or None
    return bundle


def _handicap_probability(dist: dict | None, match: dict, selection: dict):
    if not isinstance(dist, dict) or not dist:
        return None
    line = _num(selection.get("line"))
    if line is None:
        return None
    pick = _name_key(selection.get("pick"))
    p1 = _name_key(match.get("p1"))
    p2 = _name_key(match.get("p2"))
    if not pick or pick not in {p1, p2}:
        return None

    win = push = loss = 0.0
    for score, probability in dist.items():
        try:
            a, b = score
            pr = float(probability)
        except Exception:
            continue
        margin = (float(a) - float(b)) if pick == p1 else (float(b) - float(a))
        adjusted = margin + line
        if adjusted > 1e-9:
            win += pr
        elif adjusted < -1e-9:
            loss += pr
        else:
            push += pr

    total = win + push + loss
    if total <= 0:
        return None
    return {
        "score": 100.0 * win / total,
        "push_probability": 100.0 * push / total,
        "loss_probability": 100.0 * loss / total,
        "probability_semantics": "unconditional_win_probability; push_is_neutral",
    }


def _poisson_pmf(mean: float) -> list[float]:
    mean = max(0.0, float(mean))
    # Serve Props caps ace means at 20. This leaves negligible tail mass and the
    # final normalization only removes floating-point truncation.
    max_k = max(24, int(math.ceil(mean + 12.0 * math.sqrt(mean + 1.0) + 20.0)))
    values = [math.exp(-mean)]
    for k in range(1, max_k + 1):
        values.append(values[-1] * mean / k)
    z = sum(values)
    return [x / z for x in values] if z > 0 else []


def _most_aces_distribution(match: dict):
    props = match.get("serve_props_v72") or {}
    if not isinstance(props, dict) or not props.get("ready"):
        return None
    means = []
    for side in ("p1", "p2"):
        aces = ((props.get(side) or {}).get("aces") or {})
        if not isinstance(aces, dict) or not aces.get("ready"):
            return None
        mean = _num(aces.get("mean"))
        if mean is None or mean < 0:
            return None
        means.append(mean)

    a, b = _poisson_pmf(means[0]), _poisson_pmf(means[1])
    if not a or not b:
        return None
    p1 = p2 = draw = 0.0
    for i, pa in enumerate(a):
        for j, pb in enumerate(b):
            pr = pa * pb
            if i > j:
                p1 += pr
            elif j > i:
                p2 += pr
            else:
                draw += pr
    z = p1 + p2 + draw
    if z <= 0:
        return None
    return {
        "p1": 100.0 * p1 / z,
        "p2": 100.0 * p2 / z,
        "draw": 100.0 * draw / z,
        "p1_mean": means[0],
        "p2_mean": means[1],
    }


def _most_aces_probability(match: dict, selection: dict, dist=None):
    dist = dist or _most_aces_distribution(match)
    if not dist:
        return None
    pick = _name_key(selection.get("pick"))
    if pick == _name_key(match.get("p1")):
        score = dist["p1"]
    elif pick == _name_key(match.get("p2")):
        score = dist["p2"]
    elif str(selection.get("pick") or "").strip().casefold() in {"draw", "tie", "remis"}:
        score = dist["draw"]
    else:
        return None
    return {
        "score": score,
        "draw_probability": dist["draw"],
        "p1_ace_mean": dist["p1_mean"],
        "p2_ace_mean": dist["p2_mean"],
        "probability_semantics": "independent_poisson_comparison_approximation",
    }


def _label(selection: dict) -> str:
    market = str(selection.get("market") or "")
    pick = str(selection.get("pick") or "")
    line = _num(selection.get("line"))
    titles = {
        "match_game_handicap": "Mecz · handicap gemów",
        "set1_game_handicap": "1. set · handicap gemów",
        "set2_game_handicap": "2. set · handicap gemów",
        "most_aces": "Najwięcej asów",
    }
    title = titles.get(market, market.replace("_", " "))
    if line is not None:
        return f"{title} · {pick} {line:+g}"
    return f"{title} · {pick}".strip(" ·")


def _derived_for_selection(match: dict, selection: dict, bundle=None, ace_dist=None):
    market = str(selection.get("market") or "")
    if market == "set1_game_handicap":
        return _handicap_probability((bundle or {}).get("set1"), match, selection), "market_lab_v741_set1_distribution"
    if market == "set2_game_handicap":
        return _handicap_probability((bundle or {}).get("set2"), match, selection), "market_lab_v741_set2_distribution"
    if market == "match_game_handicap":
        return _handicap_probability((bundle or {}).get("match"), match, selection), "market_lab_v741_joint_games_distribution"
    if market == "most_aces":
        return _most_aces_probability(match, selection, ace_dist), "serve_props_v72_poisson_compare"
    return None, None


def _signal(selection: dict, result: dict, source: str, actionable: bool) -> dict:
    score = max(0.0, min(100.0, float(result["score"])))
    row = dict(selection)
    row.update(
        {
            "key": _selection_key(selection),
            "label": _label(selection),
            "score": round(score, 3),
            "symphony_raw_probability": round(score, 4),
            "symphony_market_adapter": VERSION,
            "symphony_source": f"superbet_market_v91+{source}",
            "symphony_actionable": bool(actionable),
            "operator": "superbet.pl",
            "operator_available": True,
            "operator_line_verified": True,
            "operator_line_source": "oddspapi_superbet_pl",
            "exact_path_supported": bool(actionable),
            "coverage_adapter_version": VERSION,
            "coverage_status": "MODEL_DERIVED" if actionable else "SHADOW_DERIVED_NOT_PLAYABLE",
        }
    )
    for key, value in result.items():
        if key != "score":
            row[key] = round(float(value), 4) if isinstance(value, (int, float)) else value
    return row


def enrich_match(raw: dict) -> dict:
    match = dict(raw)
    ctx = dict(match.get("superbet_market_v91") or {})
    selections = [x for x in (ctx.get("canonical_selections") or []) if isinstance(x, dict)]
    signals = [dict(x) for x in (ctx.get("model_signals") or []) if isinstance(x, dict)]
    shadow = [dict(x) for x in (ctx.get("coverage_shadow_signals") or []) if isinstance(x, dict)]
    existing = {_selection_key(x) for x in signals} | {_selection_key(x) for x in shadow}
    wanted = [
        s for s in selections
        if str(s.get("market") or "") in DERIVED_MARKETS and _selection_key(s) not in existing
    ]

    bundle = None
    ace_dist = None
    if any(str(s.get("market") or "") in ACTIONABLE_DERIVED_MARKETS for s in wanted):
        bundle = _distribution_bundle(match)
    if any(str(s.get("market") or "") in SHADOW_DERIVED_MARKETS for s in wanted):
        ace_dist = _most_aces_distribution(match)

    added = shadow_added = 0
    for selection in wanted:
        result, source = _derived_for_selection(match, selection, bundle, ace_dist)
        if not result or result.get("score") is None:
            continue
        market = str(selection.get("market") or "")
        actionable = market in ACTIONABLE_DERIVED_MARKETS
        row = _signal(selection, result, source, actionable)
        if actionable:
            signals.append(row)
            added += 1
        else:
            shadow.append(row)
            shadow_added += 1
        existing.add(_selection_key(selection))

    signal_keys = {_selection_key(x) for x in signals}
    shadow_keys = {_selection_key(x) for x in shadow}
    display_keys = signal_keys | shadow_keys
    selection_keys = {_selection_key(x) for x in selections}
    playable_covered = len(selection_keys & signal_keys)
    shadow_covered = len(selection_keys & shadow_keys)
    display_covered = len(selection_keys & display_keys)

    coverage = defaultdict(lambda: {"available": 0, "playable_model": 0, "shadow_model": 0})
    for selection in selections:
        market = str(selection.get("market") or "unknown")
        skey = _selection_key(selection)
        coverage[market]["available"] += 1
        if skey in signal_keys:
            coverage[market]["playable_model"] += 1
        elif skey in shadow_keys:
            coverage[market]["shadow_model"] += 1
    coverage_by_market = {}
    for market, row in sorted(coverage.items()):
        available = int(row["available"])
        playable = int(row["playable_model"])
        shadow_n = int(row["shadow_model"])
        model = playable + shadow_n
        coverage_by_market[market] = {
            "available": available,
            "model": model,
            "playable_model": playable,
            "shadow_model": shadow_n,
            "coverage": round(model / available, 4) if available else 0.0,
            "playable_coverage": round(playable / available, 4) if available else 0.0,
        }

    ctx["model_signals"] = signals
    ctx["coverage_shadow_signals"] = shadow
    ctx["model_signals_count"] = len(signals)
    ctx["coverage_shadow_signals_count"] = len(shadow)
    ctx["available_selections_count"] = len(selections)
    # Preserve the old meaning: model_coverage is strictly eligible for the
    # current model-signal/PLAYABLE path. Display-only SHADOW has its own metric.
    ctx["model_coverage"] = round(playable_covered / len(selections), 4) if selections else 0.0
    ctx["display_model_coverage"] = round(display_covered / len(selections), 4) if selections else 0.0
    ctx["playable_covered_count"] = playable_covered
    ctx["shadow_covered_count"] = shadow_covered
    ctx["display_covered_count"] = display_covered
    ctx["coverage_by_market"] = coverage_by_market
    ctx["operator_only_count"] = max(0, len(selections) - display_covered)
    ctx["coverage_adapter_version"] = VERSION
    ctx["coverage_adapter_added"] = added
    ctx["coverage_adapter_shadow_added"] = shadow_added
    ctx["coverage_adapter_external_requests"] = 0
    ctx["prices_used"] = False
    match["superbet_market_v91"] = ctx
    return match


def enrich_results(rows: list[dict]):
    out = []
    added = shadow_added = available = playable = shadow = displayed = operator_only = matches = 0
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        match = enrich_match(raw)
        ctx = match.get("superbet_market_v91") or {}
        n = int(ctx.get("available_selections_count") or 0)
        if n:
            matches += 1
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
        "external_requests": 0,
        "prices_used": False,
    }


def main():
    rows = _read(RESULTS, [])
    rows = rows if isinstance(rows, list) else []
    out, report = enrich_results(rows)
    _write(RESULTS, out)
    meta = _read(META, {})
    if not isinstance(meta, dict):
        meta = {}
    meta["superbet_line_coverage_v922"] = report
    _write(META, meta)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
