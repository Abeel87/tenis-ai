"""Shared result settlement. Never derives checkpoints from final set scores."""
from __future__ import annotations
import re
import unicodedata
from datetime import datetime, timezone

SIGNAL_LAYERS = (
    "signals", "shadow_signals", "learning_signals_v79b",
    "autolearn_signals_v84", "game_state_learning_v84e1",
    "playable_signals_v912", "playable_shadow_lab_v912",
    "playable_autolearn_signals_v912", "playable_shadow_models_v912",
    "superbet_candidate_signals_v925",
)


def market_name(value):
    return {
        "match_win": "match_winner",
        "set1_win": "set1_winner",
        "set2_win": "set2_winner",
        "set3_win": "set3_winner",
        "exact_match_score": "exact_match",
        "set1_exact_score": "exact_set1",
        "exact_first_set": "exact_set1",
    }.get(value, value)


def _key(value):
    value = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().casefold()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', value).split())


def resolve_player_side(value, final: dict):
    """Resolve a full name against this fixture only; never fuzzy-match names.

    Operator names may reverse given/family name order. All normalized tokens
    must match exactly and identify one of two distinct participants.
    """
    wanted = tuple(sorted(_key(value).split()))
    participants = [tuple(sorted(_key(final.get(p)).split())) for p in ('p1', 'p2')]
    if not wanted or not all(participants) or participants[0] == participants[1]:
        return None
    hits = [i + 1 for i, tokens in enumerate(participants) if tokens == wanted]
    return hits[0] if len(hits) == 1 else None


def _settle_named_winner(pick, actual, final):
    selected = resolve_player_side(pick, final)
    winner = resolve_player_side(actual, final)
    if selected is None or winner is None:
        return 'unverifiable'
    return 'hit' if selected == winner else 'miss'


def _yes_no(value):
    token = _key(value)
    if token in {"yes", "tak", "true", "1"}:
        return True
    if token in {"no", "nie", "false", "0"}:
        return False
    return None


def _parity(value):
    token = _key(value)
    if token in {"odd", "nieparzyste", "nieparzysta"}:
        return 1
    if token in {"even", "parzyste", "parzysta"}:
        return 0
    return None


def _set_wins(sets):
    return (
        sum(1 for a, b in sets if a > b),
        sum(1 for a, b in sets if b > a),
    )


def _settle_yes_no(actual: bool, pick) -> str:
    wanted = _yes_no(pick)
    if wanted is None:
        return "unverifiable"
    return "hit" if wanted == actual else "miss"


def _settle_parity(total: int, pick) -> str:
    wanted = _parity(pick)
    if wanted is None:
        return "unverifiable"
    return "hit" if total % 2 == wanted else "miss"


def _settle_over_under(total, signal: dict) -> str:
    try:
        line = float(signal.get('line'))
    except (TypeError, ValueError):
        return 'unverifiable'
    pick = str(signal.get('pick') or '').strip().casefold()
    if pick not in ('over', 'under'):
        return 'unverifiable'
    if total == line:
        return 'void'
    return 'hit' if (total > line if pick == 'over' else total < line) else 'miss'


def _settle_game_handicap(signal: dict, final: dict, sets, market: str) -> str:
    if market == 'set1_game_handicap':
        if len(sets) < 1:
            return 'void'
        relevant = [sets[0]]
    elif market == 'set2_game_handicap':
        if len(sets) < 2:
            return 'void'
        relevant = [sets[1]]
    else:
        if not sets:
            return 'void'
        relevant = sets

    p1, p2 = final.get('p1'), final.get('p2')
    side = resolve_player_side(signal.get('pick'), final)
    if side is None:
        return 'unverifiable'
    try:
        line = float(signal.get('line'))
    except (TypeError, ValueError):
        return 'unverifiable'

    p1_games = sum(int(a) for a, _ in relevant)
    p2_games = sum(int(b) for _, b in relevant)
    margin = (p1_games - p2_games) if side == 1 else (p2_games - p1_games)
    adjusted = margin + line
    if abs(adjusted) <= 1e-9:
        return 'void'
    return 'hit' if adjusted > 0 else 'miss'


def _settle_player_total_games(signal: dict, final: dict, sets) -> str:
    if not sets:
        return 'void'
    p1, p2 = final.get('p1'), final.get('p2')
    player = resolve_player_side(signal.get('player'), final)
    if player is None:
        return 'unverifiable'
    total = sum(int(a) for a, _ in sets) if player == 1 else sum(int(b) for _, b in sets)
    return _settle_over_under(total, signal)


def _settle_set1_tiebreak(pick, sets) -> str:
    if not sets:
        return 'void'
    a, b = sets[0]
    return _settle_yes_no({int(a), int(b)} == {6, 7}, pick)


def settle_signal(signal: dict, final: dict) -> str:
    if final.get('status') != 'completed':
        return 'void'

    market = market_name(signal.get('market'))
    pick = str(signal.get('pick') or '')
    sets = final.get('sets') or []

    if market in ('game_state', 'set2_game_state'):
        return 'unverifiable'
    if market == 'match_winner':
        return _settle_named_winner(pick, final.get('winner'), final)
    if market in ('set1_winner', 'set2_winner', 'set3_winner'):
        idx = {'set1_winner': 0, 'set2_winner': 1, 'set3_winner': 2}[market]
        if len(sets) <= idx:
            return 'void'
        a, b = sets[idx]
        p1 = final.get('p1')
        p2 = final.get('p2')
        if not p1 or not p2:
            return 'void'
        actual = p1 if a > b else p2
        return _settle_named_winner(pick, actual, final)
    if market == 'total_sets':
        direction = pick.strip().casefold()
        if direction in ('over', 'under'):
            total = final.get('number_of_sets')
            if total is None:
                return 'void'
            return _settle_over_under(total, signal)
        wanted = 2 if pick.startswith('2') else (3 if pick.startswith('3') else None)
        return 'hit' if wanted == final.get('number_of_sets') else 'miss' if wanted else 'void'
    if market == 'exact_match':
        return 'hit' if pick.replace('-', ':') == str(final.get('match_score') or '').replace('-', ':') else 'miss'
    if market == 'set1_total':
        return _settle_over_under(sum(sets[0]), signal) if sets else 'void'
    if market == 'set2_total':
        return _settle_over_under(sum(sets[1]), signal) if len(sets) >= 2 else 'void'
    if market == 'set3_total':
        return _settle_over_under(sum(sets[2]), signal) if len(sets) >= 3 else 'void'
    if market == 'match_total':
        total = final.get('total_games')
        if total is None and sets:
            total = sum(a + b for a, b in sets)
        return _settle_over_under(total, signal) if total is not None else 'void'
    if market == 'player_total_games':
        return _settle_player_total_games(signal, final, sets)
    if market == 'exact_set1':
        return 'hit' if pick.replace('-', ':') == str(final.get('first_set_score') or '').replace('-', ':') else 'miss'
    if market in {'match_game_handicap', 'set1_game_handicap', 'set2_game_handicap'}:
        return _settle_game_handicap(signal, final, sets, market)
    if market == 'set1_tiebreak':
        return _settle_set1_tiebreak(pick, sets)
    if market == 'set2_exact_score':
        if len(sets) < 2:
            return 'void'
        actual = f"{sets[1][0]}:{sets[1][1]}"
        return 'hit' if pick.replace('-', ':') == actual else 'miss'
    if market == 'exact_sets':
        try:
            wanted = int(float(pick))
        except (TypeError, ValueError):
            return 'unverifiable'
        total = final.get('number_of_sets')
        if total is None:
            total = len(sets) if sets else None
        return 'hit' if total == wanted else 'miss' if total is not None else 'void'
    if market == 'set1_games_parity':
        return _settle_parity(sum(sets[0]), pick) if sets else 'void'
    if market == 'set2_games_parity':
        return _settle_parity(sum(sets[1]), pick) if len(sets) >= 2 else 'void'
    if market == 'match_games_parity':
        total = final.get('total_games')
        if total is None and sets:
            total = sum(a + b for a, b in sets)
        return _settle_parity(int(total), pick) if total is not None else 'void'
    if market == 'any_set_to_nil':
        if not sets:
            return 'void'
        return _settle_yes_no(any(a == 0 or b == 0 for a, b in sets), pick)
    if market in {
        'p1_exactly_1_set', 'p1_exactly_2_sets',
        'p2_exactly_1_set', 'p2_exactly_2_sets',
        'p1_wins_a_set', 'p2_wins_a_set',
    }:
        if not sets:
            return 'void'
        w1, w2 = _set_wins(sets)
        actual = {
            'p1_exactly_1_set': w1 == 1,
            'p1_exactly_2_sets': w1 == 2,
            'p2_exactly_1_set': w2 == 1,
            'p2_exactly_2_sets': w2 == 2,
            'p1_wins_a_set': w1 >= 1,
            'p2_wins_a_set': w2 >= 1,
        }[market]
        return _settle_yes_no(actual, pick)
    if market == 'set_handicap':
        if not sets:
            return 'void'
        p1, p2 = final.get('p1'), final.get('p2')
        side = resolve_player_side(pick, final)
        if side is None:
            return 'unverifiable'
        try:
            line = float(signal.get('line'))
        except (TypeError, ValueError):
            return 'unverifiable'
        w1, w2 = _set_wins(sets)
        margin = (w1 - w2) if side == 1 else (w2 - w1)
        adjusted = margin + line
        if abs(adjusted) <= 1e-9:
            return 'void'
        return 'hit' if adjusted > 0 else 'miss'
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

    if market in ("game_state", "set2_game_state"):
        return "unverifiable"
    if market in (
        "match_winner", "total_sets", "exact_match", "match_total", "match_game_handicap", "player_total_games",
        "exact_sets", "match_games_parity", "any_set_to_nil",
        "p1_exactly_1_set", "p1_exactly_2_sets",
        "p2_exactly_1_set", "p2_exactly_2_sets",
        "p1_wins_a_set", "p2_wins_a_set", "set_handicap",
    ):
        return "void"

    if market in ("set1_winner", "set2_winner", "set3_winner"):
        idx = {"set1_winner": 0, "set2_winner": 1, "set3_winner": 2}[market]
        if len(sets) <= idx or len(complete) <= idx or not complete[idx] or not p1 or not p2:
            return "void"
        a, b = sets[idx]
        if a == b:
            return "void"
        actual = p1 if a > b else p2
        return _settle_named_winner(pick, actual, final)

    if market in ("set1_total", "set2_total", "set3_total"):
        idx = {"set1_total": 0, "set2_total": 1, "set3_total": 2}[market]
        if len(sets) <= idx or len(complete) <= idx or not complete[idx]:
            return "void"
        return _settle_over_under(sum(sets[idx]), signal)

    if market == "exact_set1":
        if not sets or not complete or not complete[0]:
            return "void"
        actual = f"{sets[0][0]}:{sets[0][1]}"
        return "hit" if pick.replace('-', ':') == actual else "miss"

    if market == "set1_tiebreak":
        if not sets or not complete or not complete[0]:
            return "void"
        return _settle_set1_tiebreak(pick, sets)

    if market in ("set1_games_parity", "set2_games_parity", "set2_exact_score", "set1_game_handicap", "set2_game_handicap"):
        idx = 0 if market in ("set1_games_parity", "set1_game_handicap") else 1
        if len(sets) <= idx or len(complete) <= idx or not complete[idx]:
            return "void"
        if market == "set2_exact_score":
            actual = f"{sets[1][0]}:{sets[1][1]}"
            return "hit" if pick.replace('-', ':') == actual else "miss"
        if market in ("set1_game_handicap", "set2_game_handicap"):
            return _settle_game_handicap(signal, final, sets, market)
        return _settle_parity(sum(sets[idx]), pick)

    return "unverifiable"


def settle_layers(entry, final, source, pending_only=False):
    out = dict(entry)
    final = {**final, "p1": entry.get("p1"), "p2": entry.get("p2")}
    for layer in SIGNAL_LAYERS:
        if layer not in entry:
            continue
        rows = []
        for signal in entry.get(layer) or []:
            resolved = signal.get("result") in ("hit", "miss", "void")
            if (pending_only and signal.get("result") != "pending") or (
                signal.get("market") in ("game_state", "set2_game_state") and resolved
            ):
                rows.append(signal)
                continue
            rows.append({**signal, "result": settle_signal_live(signal, final),
                         "settlement_source": source})
        out[layer] = rows
    return out


NAME_SETTLEMENT_CORRECTION = 'exact-participant-name-order-20261012'
NAMED_PICK_MARKETS = {
    'match_winner', 'set1_winner', 'set2_winner', 'set3_winner',
    'match_game_handicap', 'set1_game_handicap', 'set2_game_handicap', 'set_handicap',
}


def _repair_archived_name_results(entry, corrected_at):
    """Narrow, auditable migration of labels affected by display-name order.

    Original forecasts and terminal evidence are immutable. No unknown identity,
    void/retirement policy, PBP result or other market is retroactively inferred.
    """
    final = {**entry['result'], 'p1': entry.get('p1'), 'p2': entry.get('p2')}
    out = dict(entry)
    for layer in SIGNAL_LAYERS:
        if layer not in entry:
            continue
        rows = []
        for signal in entry.get(layer) or []:
            market = market_name(signal.get('market'))
            field = 'pick' if market in NAMED_PICK_MARKETS else 'player' if market == 'player_total_games' else None
            side = resolve_player_side(signal.get(field), final) if field else None
            if (side is None or signal.get('result') not in ('hit', 'miss', 'unverifiable')
                    or _key(signal.get(field)) == _key(final.get(f'p{side}'))):
                rows.append(signal)
                continue
            result = settle_signal_live(signal, final)
            if result not in ('hit', 'miss') or result == signal.get('result'):
                rows.append(signal)
                continue
            correction = {
                'version': NAME_SETTLEMENT_CORRECTION,
                'corrected_at': corrected_at,
                'previous_result': signal.get('result'),
                'previous_source': signal.get('settlement_source'),
                'corrected_result': result,
                'participant_side': side,
                'canonical_player': final.get(f'p{side}'),
                'evidence': 'unchanged archived terminal result',
            }
            rows.append({**signal, 'result': result,
                         'settlement_corrections': [*(signal.get('settlement_corrections') or []), correction]})
        out[layer] = rows
    return out


def reconcile_settled(entries):
    """Repair pending layers and the authorized exact-name-order label defect.

    Corrections retain prior labels/source beside unchanged frozen forecasts and
    terminal evidence. Correct results and all unrelated settled rows are kept.
    This is idempotent and deliberately performs no network access.
    """
    corrected_at = datetime.now(timezone.utc).isoformat()
    return [_repair_archived_name_results(
                settle_layers(e, e["result"], "archived final result", pending_only=True), corrected_at)
            if e.get("status") in ("settled", "void") and
               (e.get("result") or {}).get("status") in ("completed", "retired", "void")
            else e for e in entries]
