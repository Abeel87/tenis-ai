"""Tenis AI v8.4E1 — exact game-state tracking helpers.

Po 2 / Po 4 / Po 6 are exact semantic states. No fuzzy matching and no
invented settlement: HIT/MISS requires real PBP checkpoints.
"""
from __future__ import annotations

import math
import re

VERSION = "v8.4E1"
CHECKPOINTS = (2, 4, 6)
NORMAL_TRACKING_FLOOR = 55.0


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def checkpoint_from_signal(signal: dict):
    try:
        cp = int(signal.get("checkpoint"))
        if cp in CHECKPOINTS:
            return cp
    except (TypeError, ValueError):
        pass

    key = str(signal.get("key") or signal.get("id") or "").strip().lower()
    for pattern in (
        r"^(?:state|game_state)\|([246])\|",
        r"^(?:state|game_state)_?([246])\|",
    ):
        m = re.match(pattern, key)
        if m:
            return int(m.group(1))

    market = str(signal.get("market") or "").strip().lower()
    if market.startswith("state"):
        tail = market.replace("state", "", 1).strip("_| ")
        if tail in {"2", "4", "6"}:
            return int(tail)
    return None


def is_game_state_signal(signal: dict) -> bool:
    return (
        str(signal.get("market") or "").strip().lower() == "game_state"
        or checkpoint_from_signal(signal) is not None
    )


def _states_for(match: dict, checkpoint: int):
    states = match.get("game_states") or {}
    obj = states.get(str(checkpoint))
    if obj is None:
        obj = states.get(checkpoint)
    return obj if isinstance(obj, dict) else {}


def top_state_signal(match: dict, checkpoint: int):
    if checkpoint not in CHECKPOINTS:
        return None
    rows = []
    for pick, value in _states_for(match, checkpoint).items():
        score = _num(value)
        if score is not None:
            rows.append((str(pick).replace(" ", ""), score))
    if not rows:
        return None
    pick, score = max(rows, key=lambda x: (x[1], x[0]))
    return {
        "key": f"state|{checkpoint}|{pick}",
        "id": f"game_state||{checkpoint}|{pick}",
        "label": f"Po {checkpoint}: {pick}",
        "market": "game_state",
        "pick": pick,
        "checkpoint": checkpoint,
        "score": round(score, 1),
        "result": "pending",
        "source_model": "adaptive",
        "learning_only": True,
        "resolvable": False,
        "tracker_version": VERSION,
    }


def current_signals(match: dict):
    out = []
    for checkpoint in CHECKPOINTS:
        signal = top_state_signal(match, checkpoint)
        if signal:
            out.append(signal)
    return out


def learning_signals(match: dict):
    return [dict(x) for x in current_signals(match)]


def select_tracking_signals(signals, limit: int, normal_floor: float = NORMAL_TRACKING_FLOOR):
    """Reserve one exact state for 2/4/6, then fill the remaining bounded slots."""
    rows = [dict(s) for s in (signals or []) if isinstance(s, dict)]
    if limit <= 0:
        return []

    reserved = []
    reserved_keys = set()
    for checkpoint in CHECKPOINTS:
        candidates = [
            s for s in rows
            if checkpoint_from_signal(s) == checkpoint and _num(s.get("ensemble")) is not None
        ]
        if not candidates:
            continue
        best = max(
            candidates,
            key=lambda s: (_num(s.get("ensemble"), -1.0), str(s.get("key") or "")),
        )
        key = str(best.get("key") or "")
        if key not in reserved_keys:
            reserved.append(best)
            reserved_keys.add(key)

    others = [
        s for s in rows
        if str(s.get("key") or "") not in reserved_keys
        and _num(s.get("ensemble"), 0.0) >= normal_floor
    ]
    others.sort(key=lambda s: (-_num(s.get("ensemble"), 0.0), str(s.get("key") or "")))

    selected = reserved[:limit]
    selected.extend(others[:max(0, limit - len(selected))])
    selected.sort(key=lambda s: (-_num(s.get("ensemble"), 0.0), str(s.get("key") or "")))
    return selected


def settle_from_states(signal: dict, states: dict):
    checkpoint = checkpoint_from_signal(signal)
    if checkpoint not in CHECKPOINTS:
        return None
    observed = (states or {}).get(str(checkpoint))
    if not observed:
        return None
    predicted = str(signal.get("pick") or "").replace(" ", "")
    observed = str(observed).replace(" ", "")
    return "hit" if predicted == observed else "miss"
