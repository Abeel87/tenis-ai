from __future__ import annotations

"""Tenis AI v9.2.4 — canonical mapping for audited Superbet market families.

Zero extra API requests. This wrapper reuses the same OddsPapi market catalogue
and odds-by-tournaments payload already consumed by v9.2.3. It only teaches the
sanitizer how to name and parse market families discovered by the raw-family
audit. Prices remain discarded and MODEL/RAW remains independent of Superbet.

Actionable line contract: a line market is kept only when the concrete current
Superbet fixture carries line evidence for that exact market/outcome/player.
Catalogue/global handicaps are metadata only and are never sufficient to mark a
selection SUPERBET PLAYABLE.
"""

import json
import re
import sys
from contextlib import contextmanager

try:
    from . import superbet_fixture_matching_v927 as fixture_matching
    from . import superbet_market_context_v91 as base
    from . import superbet_market_context_v913 as v913
    from . import superbet_market_context_v923 as v923
except ImportError:
    import superbet_fixture_matching_v927 as fixture_matching
    import superbet_market_context_v91 as base
    import superbet_market_context_v913 as v913
    import superbet_market_context_v923 as v923

VERSION = "v9.2.4"
STRICT_FIXTURE_LINE_VERSION = "v9.3.2-core"
NEW_LINE_MARKETS = {"set_handicap"}
NEW_HANDICAP_MARKETS = {"set_handicap"}
NEW_MARKETS = {
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


def canonical_market(market_name: str):
    existing = _ORIGINAL_CANONICAL(market_name)
    if existing[0]:
        return existing
    n = base._norm(market_name)
    cp = base._checkpoint_from_market(market_name)
    mapping = {
        "any set to nil": ("any_set_to_nil", None, None),
        "correct score second set": ("set2_exact_score", None, None),
        "exact sets": ("exact_sets", None, None),
        "odd even games": ("match_games_parity", None, None),
        "odd even games first set": ("set1_games_parity", None, None),
        "odd even games second set": ("set2_games_parity", None, None),
        "participant 1 to exactly win one set": ("p1_exactly_1_set", None, "p1"),
        "participant 1 to exactly win two sets": ("p1_exactly_2_sets", None, "p1"),
        "participant 2 to exactly win one set": ("p2_exactly_1_set", None, "p2"),
        "participant 2 to exactly win two sets": ("p2_exactly_2_sets", None, "p2"),
        "participant 1 to win a set": ("p1_wins_a_set", None, "p1"),
        "participant 2 to win a set": ("p2_wins_a_set", None, "p2"),
        "set handicap": ("set_handicap", None, None),
    }
    if n in mapping:
        return mapping[n]
    if "correct score second set after" in n and cp:
        return "set2_game_state", cp, None
    return None, None, None


def _yes_no(*values):
    words = set(base._norm(" ".join(str(v or "") for v in values)).split())
    if words & {"yes", "tak", "true"}:
        return "yes"
    if words & {"no", "nie", "false"}:
        return "no"
    return None


def _parity(*values):
    words = set(base._norm(" ".join(str(v or "") for v in values)).split())
    if "odd" in words or "nieparzyste" in words:
        return "odd"
    if "even" in words or "parzyste" in words:
        return "even"
    return None


def _small_integer(*values):
    for value in values:
        nums = re.findall(r"(?<!\d)([1-5])(?!\d)", str(value or ""))
        if nums:
            return str(int(nums[0]))
    return None


def selection_pick(market, outcome_name, bookmaker_outcome_id, p1, p2):
    if market in {"set2_exact_score", "set2_game_state"}:
        return base._score_from_text(outcome_name, bookmaker_outcome_id)
    if market in {"match_games_parity", "set1_games_parity", "set2_games_parity"}:
        return _parity(outcome_name, bookmaker_outcome_id)
    if market == "exact_sets":
        return _small_integer(outcome_name, bookmaker_outcome_id)
    if market in {
        "any_set_to_nil",
        "p1_exactly_1_set", "p1_exactly_2_sets",
        "p2_exactly_1_set", "p2_exactly_2_sets",
        "p1_wins_a_set", "p2_wins_a_set",
    }:
        return _yes_no(outcome_name, bookmaker_outcome_id)
    if market == "set_handicap":
        return v913._winner_pick(outcome_name, bookmaker_outcome_id, p1, p2)
    return _ORIGINAL_SELECTION_PICK(market, outcome_name, bookmaker_outcome_id, p1, p2)


def _fixture_numeric(holder: dict, *fields):
    if not isinstance(holder, dict):
        return None, None
    for field in fields:
        value = base._line(holder.get(field))
        if value is not None:
            return value, field
    return None, None


def _fixture_line_for_selection(
    market: str,
    market_data: dict,
    outcome_data: dict,
    player_data: dict,
    outcome_name,
    bookmaker_outcome_id,
    *,
    pick=None,
    p1=None,
    p2=None,
):
    """Return line evidence from the concrete fixture only; never from catalogue metadata."""
    if market not in v913.LINE_MARKETS:
        return None, None

    # Player/outcome fields are selection-specific and therefore authoritative as-is.
    for holder, prefix in ((player_data, "player"), (outcome_data, "outcome")):
        value, field = _fixture_numeric(holder, "handicap", "line")
        if value is not None:
            return value, f"oddspapi_fixture_{prefix}_{field}"

    # A market-level handicap is participant-1 perspective for handicap markets.
    value, field = _fixture_numeric(market_data, "handicap", "line")
    if value is not None:
        if market in v913.HANDICAP_MARKETS:
            side = v913._handicap_side(outcome_name, bookmaker_outcome_id, pick, p1, p2)
            if side == "p2":
                value = -value
        elif market not in v913.HANDICAP_MARKETS:
            value = abs(value)
        return value, f"oddspapi_fixture_market_{field}"

    # Fixture-specific bookmaker identifiers/names may encode the current line.
    text_line = base._line_from_text(
        bookmaker_outcome_id,
        outcome_name,
        market_data.get("bookmakerMarketId") if isinstance(market_data, dict) else None,
        outcome_data.get("bookmakerOutcomeId") if isinstance(outcome_data, dict) else None,
    )
    if text_line is not None:
        if market not in v913.HANDICAP_MARKETS:
            text_line = abs(text_line)
        return text_line, "oddspapi_fixture_text_line"
    return None, None


def _matching_fixture_player(selection: dict, market_name: str, outcome_name, outcome_data: dict, p1: str, p2: str):
    players = (outcome_data.get("players") or {}) if isinstance(outcome_data, dict) else {}
    canonical, _checkpoint, player_side = base.canonical_market(market_name)
    wanted_pick = base._norm(selection.get("pick"))
    wanted_player = base._name_key(selection.get("player"))
    fallback = None
    for player_data in players.values():
        if not isinstance(player_data, dict) or player_data.get("active") is False:
            continue
        if fallback is None:
            fallback = player_data
        boid = player_data.get("bookmakerOutcomeId")
        candidate_pick = v913._selection_pick(canonical, outcome_name, boid, p1, p2)
        if wanted_pick and base._norm(candidate_pick) != wanted_pick:
            continue
        candidate_player = (
            p1 if player_side == "p1" else
            p2 if player_side == "p2" else
            player_data.get("playerName")
        )
        if wanted_player and candidate_player and base._name_key(candidate_player) != wanted_player:
            continue
        return player_data
    return fallback


def mapped_sanitize(row: dict, meta: dict):
    item = _ORIGINAL_SANITIZE(row, meta)
    if not isinstance(item, dict):
        return item

    bookmaker_odds = row.get("bookmakerOdds") or {}
    book = bookmaker_odds.get(base.BOOKMAKER)
    if not isinstance(book, dict):
        book = next(
            (value for key, value in bookmaker_odds.items()
             if "superbet" in str(key).casefold() and isinstance(value, dict)),
            None,
        )
    raw_markets = (book or {}).get("markets") if isinstance(book, dict) else {}
    if not isinstance(raw_markets, dict):
        raw_markets = {}

    p1 = str(row.get("participant1Name") or "")
    p2 = str(row.get("participant2Name") or "")
    selections = []
    suppressed_without_fixture_line = 0

    for selection in item.get("canonical_selections") or []:
        if not isinstance(selection, dict):
            continue
        selection = dict(selection)
        market = str(selection.get("market") or "")
        if market in NEW_MARKETS and not selection.get("pick"):
            continue

        if market in v913.LINE_MARKETS:
            market_id = str(selection.get("market_id") or "")
            outcome_id = str(selection.get("outcome_id") or "")
            market_data = raw_markets.get(market_id) or {}
            market_meta = meta.get(market_id, {}) if isinstance(meta, dict) else {}
            market_name = str(market_meta.get("marketName") or selection.get("market_name") or f"market {market_id}")
            outcome_data = (market_data.get("outcomes") or {}).get(outcome_id, {}) if isinstance(market_data, dict) else {}
            outcome_meta = (market_meta.get("outcomes") or {}).get(outcome_id, {}) if isinstance(market_meta, dict) else {}
            outcome_name = outcome_meta.get("outcomeName") or outcome_meta.get("outcomeNameShort")
            player_data = _matching_fixture_player(selection, market_name, outcome_name, outcome_data, p1, p2)
            boid = player_data.get("bookmakerOutcomeId") if isinstance(player_data, dict) else None
            line, source = _fixture_line_for_selection(
                market,
                market_data,
                outcome_data,
                player_data or {},
                outcome_name,
                boid,
                pick=selection.get("pick"),
                p1=p1,
                p2=p2,
            )
            if line is None:
                suppressed_without_fixture_line += 1
                continue
            selection["line"] = line
            selection["operator_line_source"] = source
            selection["operator_line_verified"] = True
            selection["fixture_line_verified"] = True
            selection["fixture_line_contract_version"] = STRICT_FIXTURE_LINE_VERSION

        selections.append(selection)

    item = dict(item)
    item["canonical_selections"] = selections
    item["recognized_markets"] = sorted({str(x.get("market")) for x in selections if x.get("market")})
    item["market_mapping_version"] = VERSION
    item["fixture_line_contract_version"] = STRICT_FIXTURE_LINE_VERSION
    item["suppressed_line_selections_without_fixture_evidence"] = suppressed_without_fixture_line
    return item


_ORIGINAL_CANONICAL = base.canonical_market
_ORIGINAL_SELECTION_PICK = v913._selection_pick
_ORIGINAL_SANITIZE = v913._sanitize_fixture


@contextmanager
def _patched_runtime():
    old_v923_version = v923.VERSION
    old_line = set(v913.LINE_MARKETS)
    old_handicap = set(v913.HANDICAP_MARKETS)
    old_winner = set(v913.WINNER_MARKETS)
    old_canonical = base.canonical_market
    old_pick = v913._selection_pick
    old_sanitize = v913._sanitize_fixture
    old_best_fixture = base._best_fixture_for_match
    old_best_cached = base._best_cached_fixture
    old_availability_due = base._availability_due
    fixture_matching.reset_telemetry()
    try:
        base.canonical_market = canonical_market
        v913._selection_pick = selection_pick
        v913._sanitize_fixture = mapped_sanitize
        base._best_fixture_for_match = fixture_matching.best_fixture_for_match
        base._best_cached_fixture = fixture_matching.best_cached_fixture
        base._availability_due = lambda previous, now: fixture_matching.availability_due(old_availability_due, previous, now)
        v913.LINE_MARKETS.update(NEW_LINE_MARKETS)
        v913.HANDICAP_MARKETS.update(NEW_HANDICAP_MARKETS)
        v913.WINNER_MARKETS.update(NEW_HANDICAP_MARKETS)
        # v9.2.3 uses its VERSION to force a normal parser refresh. Temporarily
        # bump it so existing cached fixtures are re-sanitized once after merge.
        v923.VERSION = STRICT_FIXTURE_LINE_VERSION
        yield
    finally:
        base.canonical_market = old_canonical
        v913._selection_pick = old_pick
        v913._sanitize_fixture = old_sanitize
        base._best_fixture_for_match = old_best_fixture
        base._best_cached_fixture = old_best_cached
        base._availability_due = old_availability_due
        v913.LINE_MARKETS.clear(); v913.LINE_MARKETS.update(old_line)
        v913.HANDICAP_MARKETS.clear(); v913.HANDICAP_MARKETS.update(old_handicap)
        v913.WINNER_MARKETS.clear(); v913.WINNER_MARKETS.update(old_winner)
        v923.VERSION = old_v923_version


def _stamp_alias() -> dict:
    availability = base._read(base.AVAILABILITY, {})
    if not isinstance(availability, dict):
        return {}
    availability = dict(availability)
    audit = dict(availability.get("raw_family_audit_v923") or {})
    if audit:
        audit["version"] = VERSION
        availability["raw_family_audit_v924"] = audit
    availability["market_mapping_version"] = VERSION
    availability["runtime_adapter_version"] = VERSION
    availability["fixture_line_contract"] = {
        "version": STRICT_FIXTURE_LINE_VERSION,
        "current_fixture_evidence_required": True,
        "catalogue_fallback_allowed": False,
        "model_line_fallback_allowed": False,
        "nearest_line_fallback_allowed": False,
        "prices_used": False,
    }
    base._write(base.AVAILABILITY, availability)
    return audit


def prepare() -> dict:
    with _patched_runtime():
        result = dict(v923.prepare())
        audit = _stamp_alias()
        matching = fixture_matching.stamp_availability()
    result["market_mapping_version"] = VERSION
    result["fixture_line_contract_version"] = STRICT_FIXTURE_LINE_VERSION
    result["raw_family_audit_v924"] = audit
    result["fixture_matching_v927"] = matching
    result["additional_external_requests"] = 0
    return result


def finalize() -> dict:
    with _patched_runtime():
        result = dict(v923.finalize())
        audit = _stamp_alias()
    result["market_mapping_version"] = VERSION
    result["fixture_line_contract_version"] = STRICT_FIXTURE_LINE_VERSION
    result["raw_family_audit_v924"] = audit
    result["additional_external_requests"] = 0
    return result


def main() -> None:
    mode = str(sys.argv[1] if len(sys.argv) > 1 else "prepare").strip().casefold()
    if mode == "prepare":
        result = prepare()
    elif mode == "finalize":
        result = finalize()
    else:
        raise SystemExit("usage: superbet_market_context_v924.py [prepare|finalize]")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
