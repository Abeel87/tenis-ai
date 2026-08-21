from __future__ import annotations

import math


VERSION = "v7.8B"
EPS = 1e-9


def _clamp(value, lo=0.0, hi=1.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, value))


def _pct(value):
    return round(float(value) * 100.0, 1)


def _tb_p1(h1: float, h2: float) -> float:
    p1_game_strength = (float(h1) + (1.0 - float(h2))) / 2.0
    x = 1.0 / (1.0 + math.exp(-(p1_game_strength - 0.5) * 8.0))
    return max(0.20, min(0.80, x))


def _paths_one_order(h1: float, h2: float, p1_serves_first: bool) -> dict:
    """Exact game-path distribution for one set, retaining the score after 6 games."""
    live = {(0, 0, -1, -1): 1.0}
    terminal = {}
    tb = _tb_p1(h1, h2)

    while live:
        nxt = {}
        for (a, b, cp_a, cp_b), prob in live.items():
            if a == 6 and b == 6:
                terminal[(cp_a, cp_b, 7, 6)] = terminal.get((cp_a, cp_b, 7, 6), 0.0) + prob * tb
                terminal[(cp_a, cp_b, 6, 7)] = terminal.get((cp_a, cp_b, 6, 7), 0.0) + prob * (1.0 - tb)
                continue

            if (a >= 6 or b >= 6) and abs(a - b) >= 2:
                terminal[(cp_a, cp_b, a, b)] = terminal.get((cp_a, cp_b, a, b), 0.0) + prob
                continue

            games_played = a + b
            p1_serves = p1_serves_first if games_played % 2 == 0 else not p1_serves_first
            p1_game = h1 if p1_serves else 1.0 - h2

            for p1_wins_game, branch_prob in ((True, p1_game), (False, 1.0 - p1_game)):
                na = a + (1 if p1_wins_game else 0)
                nb = b + (0 if p1_wins_game else 1)
                ncp_a, ncp_b = cp_a, cp_b
                if na + nb == 6:
                    ncp_a, ncp_b = na, nb
                key = (na, nb, ncp_a, ncp_b)
                nxt[key] = nxt.get(key, 0.0) + prob * branch_prob

        live = nxt

    return terminal


def _path_distribution(h1: float, h2: float) -> dict:
    """Average over unknown first server, matching the existing model convention."""
    a = _paths_one_order(h1, h2, True)
    b = _paths_one_order(h1, h2, False)
    keys = set(a) | set(b)
    out = {k: (a.get(k, 0.0) + b.get(k, 0.0)) / 2.0 for k in keys}
    total = sum(out.values())
    if total > 0:
        out = {k: v / total for k, v in out.items()}
    return out


def _target_p1(match: dict):
    p1 = match.get("p1")
    market = match.get("first_set_win") or {}
    value = market.get(p1)
    try:
        value = float(value) / 100.0
    except (TypeError, ValueError):
        return None
    return _clamp(value, 0.01, 0.99)


def _reweight_winner(paths: dict, target_p1: float) -> dict:
    """Reweight full paths so their terminal winner marginal equals the model's set-1 target."""
    raw_p1 = sum(prob for (_, _, a, b), prob in paths.items() if a > b)
    if raw_p1 <= EPS or raw_p1 >= 1.0 - EPS:
        return dict(paths)

    out = {}
    for key, prob in paths.items():
        _, _, a, b = key
        if a > b:
            out[key] = prob * target_p1 / raw_p1
        else:
            out[key] = prob * (1.0 - target_p1) / (1.0 - raw_p1)

    total = sum(out.values())
    return {k: v / total for k, v in out.items()} if total > 0 else dict(paths)


def _selection(paths: dict, side: int, player: str) -> dict:
    lead = over = win = joint = 0.0
    lead_and_over = lead_and_win = over_and_win = 0.0
    lead_states = {}

    for (cp_a, cp_b, a, b), prob in paths.items():
        is_lead = cp_a > cp_b if side == 1 else cp_b > cp_a
        is_over = (a + b) > 8.5
        is_win = a > b if side == 1 else b > a

        if is_lead:
            lead += prob
            state = f"{cp_a}:{cp_b}"
            lead_states[state] = lead_states.get(state, 0.0) + prob
        if is_over:
            over += prob
        if is_win:
            win += prob
        if is_lead and is_over:
            lead_and_over += prob
        if is_lead and is_win:
            lead_and_win += prob
        if is_over and is_win:
            over_and_win += prob
        if is_lead and is_over and is_win:
            joint += prob

    naive = lead * over * win
    dep = (joint / naive) if naive > EPS else None

    return {
        "player": player,
        "lead_after_6": _pct(lead),
        "over_8_5_set1": _pct(over),
        "win_set1": _pct(win),
        "joint_all_3": _pct(joint),
        "naive_independent": _pct(naive),
        "dependency_ratio": round(dep, 3) if dep is not None else None,
        "lead_and_over": _pct(lead_and_over),
        "lead_and_win": _pct(lead_and_win),
        "over_and_win": _pct(over_and_win),
        "lead_states_after_6": {
            state: _pct(prob)
            for state, prob in sorted(lead_states.items(), key=lambda kv: kv[1], reverse=True)
        },
    }


def validate_joint_builder(payload: dict) -> list[str]:
    errors = []
    if not isinstance(payload, dict) or payload.get("status") != "READY":
        return errors

    for key in ("p1", "p2"):
        row = payload.get(key) or {}
        vals = {
            "lead": row.get("lead_after_6"),
            "over": row.get("over_8_5_set1"),
            "win": row.get("win_set1"),
            "joint": row.get("joint_all_3"),
        }
        for name, value in vals.items():
            try:
                value = float(value)
            except (TypeError, ValueError):
                errors.append(f"{key}.{name}: brak liczby")
                continue
            if value < -0.05 or value > 100.05:
                errors.append(f"{key}.{name}: poza 0..100")

        try:
            joint = float(vals["joint"])
            marginals = [float(vals["lead"]), float(vals["over"]), float(vals["win"])]
            if joint > min(marginals) + 0.11:
                errors.append(f"{key}: joint > marginal")
        except (TypeError, ValueError):
            pass

    return errors


def build_joint_builder(match: dict) -> dict:
    if not isinstance(match, dict):
        return {"version": VERSION, "status": "N/D", "reason": "invalid_match"}

    service = match.get("service_model") or {}
    try:
        h1 = float(service.get("p1_hold")) / 100.0
        h2 = float(service.get("p2_hold")) / 100.0
    except (TypeError, ValueError):
        return {"version": VERSION, "status": "N/D", "reason": "service_model_missing"}

    if not (0.0 < h1 < 1.0 and 0.0 < h2 < 1.0):
        return {"version": VERSION, "status": "N/D", "reason": "service_model_invalid"}

    target_p1 = _target_p1(match)
    if target_p1 is None:
        return {"version": VERSION, "status": "N/D", "reason": "first_set_target_missing"}

    raw_paths = _path_distribution(h1, h2)
    paths = _reweight_winner(raw_paths, target_p1)

    p1 = _selection(paths, 1, str(match.get("p1") or "P1"))
    p2 = _selection(paths, 2, str(match.get("p2") or "P2"))
    best = p1 if p1["joint_all_3"] >= p2["joint_all_3"] else p2

    payload = {
        "version": VERSION,
        "status": "READY",
        "method": "joint-game-path-distribution",
        "description": "Prowadzenie po 6 gemach + OVER 8.5 w 1. secie + wygrana 1. seta liczone wspólnie z tych samych ścieżek seta.",
        "model_confidence": match.get("model_confidence"),
        "p1": p1,
        "p2": p2,
        "best": {
            "player": best["player"],
            "joint_all_3": best["joint_all_3"],
            "naive_independent": best["naive_independent"],
            "dependency_ratio": best["dependency_ratio"],
        },
        "mass": _pct(sum(paths.values())),
    }
    payload["validation_errors"] = validate_joint_builder(payload)
    if payload["validation_errors"]:
        payload["status"] = "FAIL"
    return payload


def add_joint_builder(match: dict) -> dict:
    out = dict(match or {})
    out["joint_builder_v78b"] = build_joint_builder(out)
    return out
