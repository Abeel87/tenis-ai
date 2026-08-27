"""Shared result settlement. Never derives checkpoints from final set scores."""
from __future__ import annotations
import re
import unicodedata

SIGNAL_LAYERS = ("signals", "shadow_signals", "learning_signals_v79b",
                 "autolearn_signals_v84", "game_state_learning_v84e1")

def market_name(value):
    return {"match_win": "match_winner", "set1_win": "set1_winner",
            "set2_win": "set2_winner", "set3_win": "set3_winner",
            "exact_match_score": "exact_match"}.get(value, value)

def _key(value):
    value = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().casefold()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', value).split())


def settle_signal(signal: dict, final: dict) -> str:
    if final.get('status') != 'completed':
        return 'void'

    market = market_name(signal.get('market'))
    pick = str(signal.get('pick') or '')
    sets = final.get('sets') or []

    if market == 'game_state':
        return 'unverifiable'
    if market == 'match_winner':
        return 'hit' if _key(pick) == _key(final.get('winner')) else 'miss'
    if market in ('set1_winner', 'set2_winner', 'set3_winner'):
        idx = {'set1_winner': 0, 'set2_winner': 1, 'set3_winner': 2}[market]
        if len(sets) <= idx:
            return 'void'
        a, b = sets[idx]
        # final sets are p1:p2; use the signal entry's player names supplied below.
        p1 = final.get('p1')
        p2 = final.get('p2')
        if not p1 or not p2:
            return 'void'
        actual = p1 if a > b else p2
        return 'hit' if _key(pick) == _key(actual) else 'miss'
    if market == 'total_sets':
        wanted = 2 if pick.startswith('2') else (3 if pick.startswith('3') else None)
        return 'hit' if wanted == final.get('number_of_sets') else 'miss' if wanted else 'void'
    if market == 'exact_match':
        return 'hit' if pick == final.get('match_score') else 'miss'
    if market == 'set1_total':
        if not sets:
            return 'void'
        total = sum(sets[0])
        try:
            line = float(signal.get('line'))
        except (TypeError, ValueError):
            return 'unverifiable'
        if pick not in ('over', 'under'):
            return 'unverifiable'
        if total == line:
            return 'void'
        ok = total > line if pick == 'over' else total < line
        return 'hit' if ok else 'miss'
    if market == 'match_total':
        total = final.get('total_games')
        if total is None:
            return 'void'
        try:
            line = float(signal.get('line'))
        except (TypeError, ValueError):
            return 'unverifiable'
        if pick not in ('over', 'under'):
            return 'unverifiable'
        if total == line:
            return 'void'
        ok = total > line if pick == 'over' else total < line
        return 'hit' if ok else 'miss'
    if market == 'exact_set1':
        return 'hit' if pick == final.get('first_set_score') else 'miss'
    return 'unverifiable'


def settle_signal_live(signal: dict, final: dict) -> str:
    status = final.get("status")
    if status == "completed":
        return settle_signal(signal, final)
    if status == "void":
        return "void"
    if status != "retired":
        return "unverifiable"

    market = market_name(signal.get("market"))
    pick = str(signal.get("pick") or "")
    sets = final.get("sets") or []
    complete = final.get("completed_sets") or []
    p1, p2 = final.get("p1"), final.get("p2")

    if market == "game_state":
        return "unverifiable"
    if market in ("match_winner", "total_sets", "exact_match", "match_total"):
        return "void"

    if market in ("set1_winner", "set2_winner", "set3_winner"):
        idx = {"set1_winner": 0, "set2_winner": 1, "set3_winner": 2}[market]
        if len(sets) <= idx or len(complete) <= idx or not complete[idx] or not p1 or not p2:
            return "void"
        a, b = sets[idx]
        if a == b:
            return "void"
        actual = p1 if a > b else p2
        return "hit" if _key(pick) == _key(actual) else "miss"

    if market == "set1_total":
        if not sets or not complete or not complete[0]:
            return "void"
        total = sum(sets[0])
        try:
            line = float(signal.get("line"))
        except (TypeError, ValueError):
            return "void"
        ok = total > line if pick == "over" else total < line
        return "hit" if ok else "miss"

    if market == "exact_set1":
        if not sets or not complete or not complete[0]:
            return "void"
        actual = f"{sets[0][0]}:{sets[0][1]}"
        return "hit" if pick == actual else "miss"

    return "unverifiable"



def settle_layers(entry, final, source, pending_only=False):
    out = dict(entry)
    final = {**final, "p1": entry.get("p1"), "p2": entry.get("p2")}
    for layer in SIGNAL_LAYERS:
        if layer not in entry:
            continue
        rows = []
        for signal in entry.get(layer) or []:
            # PBP-resolved checkpoints carry evidence a final score cannot replace.
            resolved = signal.get("result") in ("hit", "miss", "void")
            if (pending_only and signal.get("result") != "pending") or (
                signal.get("market") == "game_state" and resolved
            ):
                rows.append(signal)
                continue
            rows.append({**signal, "result": settle_signal_live(signal, final),
                         "settlement_source": source})
        out[layer] = rows
    return out


def reconcile_settled(entries):
    """Repair pending layers using only the final result already in the archive.

    Frozen scores, capture times and existing resolved evidence stay unchanged.
    This is idempotent and deliberately performs no network access.
    """
    return [settle_layers(e, e["result"], "archived final result", pending_only=True)
            if e.get("status") in ("settled", "void") and
               (e.get("result") or {}).get("status") in ("completed", "retired", "void")
            else e for e in entries]
