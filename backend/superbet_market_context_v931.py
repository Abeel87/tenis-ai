from __future__ import annotations

"""Tenis AI v9.3.1 — fixture-authoritative Superbet line parsing.

Fixes a PLAYABLE integrity bug where a generic/catalogue handicap could be used
as the actionable line even when the concrete Superbet fixture/outcome exposed a
different tennis total.  For non-handicap line markets the fixture payload is
now authoritative whenever it contains an explicit line; the catalogue value is
only a fallback for opaque fixture identifiers.

No prices are read. MODEL/RAW, training, weights, PROD/SHADOW and settlement are
unchanged.
"""

import json
import sys
from contextlib import contextmanager

try:
    from . import superbet_market_context_v91 as base
    from . import superbet_market_context_v913 as v913
    from . import superbet_market_context_v924 as v924
except ImportError:
    import superbet_market_context_v91 as base
    import superbet_market_context_v913 as v913
    import superbet_market_context_v924 as v924

VERSION = "v9.3.1"


def _fixture_line(market: str, market_meta: dict, market_data: dict, outcome_data: dict,
                  player_data: dict, outcome_name, bookmaker_outcome_id,
                  *, pick=None, p1=None, p2=None):
    """Resolve a real fixture line before falling back to catalogue metadata."""
    if market not in v913.LINE_MARKETS:
        return None, None

    # Handicaps retain v9.1.5's participant-sign semantics. This patch targets
    # O/U-style totals where the exact threshold must equal the fixture offer.
    if market in v913.HANDICAP_MARKETS:
        return v913._market_line(
            market, market_meta, outcome_name, bookmaker_outcome_id,
            pick=pick, p1=p1, p2=p2,
        )

    # Prefer explicit structured fixture fields when OddsPapi supplies them.
    for holder, field in (
        (player_data, "handicap"), (player_data, "line"),
        (outcome_data, "handicap"), (outcome_data, "line"),
        (market_data, "handicap"), (market_data, "line"),
    ):
        if isinstance(holder, dict):
            value = base._line(holder.get(field))
            if value is not None:
                return value, f"oddspapi_fixture_{field}"

    # Fixture-specific textual IDs/names can carry the actual step (e.g. 18.5)
    # even when the global market catalogue still reports a different threshold.
    explicit = base._line_from_text(
        outcome_name,
        bookmaker_outcome_id,
        market_data.get("bookmakerMarketId") if isinstance(market_data, dict) else None,
        outcome_data.get("bookmakerOutcomeId") if isinstance(outcome_data, dict) else None,
    )
    if explicit is not None:
        return explicit, "oddspapi_fixture_text_line"

    # Opaque fixture IDs: catalogue handicap remains the only trustworthy line.
    catalogue = base._line(market_meta.get("handicap"))
    if catalogue is not None:
        return catalogue, "oddspapi_market_handicap_fallback"
    return None, None


def _sanitize_fixture(row: dict, meta: dict):
    bookmaker_odds = row.get("bookmakerOdds") or {}
    book = bookmaker_odds.get(base.BOOKMAKER)
    if not isinstance(book, dict):
        book = next(
            (value for key, value in bookmaker_odds.items()
             if "superbet" in str(key).casefold() and isinstance(value, dict)),
            None,
        )
    if not isinstance(book, dict):
        return None
    raw_markets = book.get("markets") or {}
    if not isinstance(raw_markets, dict):
        return None

    p1 = str(row.get("participant1Name") or "")
    p2 = str(row.get("participant2Name") or "")
    selections = []
    recognized_markets = set()

    for market_id, market_data in raw_markets.items():
        if not isinstance(market_data, dict) or market_data.get("marketActive") is False:
            continue
        market_meta = meta.get(str(market_id), {})
        market_name = str(market_meta.get("marketName") or f"market {market_id}")
        canonical, checkpoint, player_side = base.canonical_market(market_name)
        if not canonical:
            continue
        recognized_markets.add(canonical)

        for outcome_id, outcome_data in (market_data.get("outcomes") or {}).items():
            if not isinstance(outcome_data, dict):
                continue
            outcome_meta = (market_meta.get("outcomes") or {}).get(str(outcome_id), {})
            outcome_name = outcome_meta.get("outcomeName") or outcome_meta.get("outcomeNameShort")

            for player_data in (outcome_data.get("players") or {}).values():
                if not isinstance(player_data, dict) or player_data.get("active") is False:
                    continue
                boid = player_data.get("bookmakerOutcomeId")
                pick = v913._selection_pick(canonical, outcome_name, boid, p1, p2)
                line, line_source = _fixture_line(
                    canonical, market_meta, market_data, outcome_data, player_data,
                    outcome_name, boid, pick=pick, p1=p1, p2=p2,
                )

                if canonical in v913.LINE_MARKETS and line is None:
                    continue
                if canonical in {
                    "match_total", "set1_total", "set2_total", "set3_total",
                    "total_sets", "player_total_games", "match_total_aces",
                } and pick not in {"over", "under"}:
                    continue
                if canonical in {"set1_exact_score", "exact_match_score", "game_state"} and not pick:
                    continue

                player = (
                    p1 if player_side == "p1" else
                    p2 if player_side == "p2" else
                    player_data.get("playerName")
                )
                selection = {
                    "market": canonical,
                    "pick": pick,
                    "line": line,
                    "checkpoint": checkpoint,
                    "player": player,
                    "market_name": market_name,
                    "market_id": str(market_id),
                    "outcome_id": str(outcome_id),
                    "main_line": bool(player_data.get("mainLine", False)),
                    "operator_available": True,
                    "operator_line_verified": True,
                }
                if line_source:
                    selection["operator_line_source"] = line_source
                selections.append(selection)

    dedup = {}
    for selection in selections:
        sig = (
            selection.get("market"),
            base._norm(selection.get("pick")),
            base._line(selection.get("line")),
            int(selection.get("checkpoint") or 0),
            base._name_key(selection.get("player")),
        )
        if sig not in dedup or selection.get("main_line"):
            dedup[sig] = selection
    selections = sorted(
        dedup.values(),
        key=lambda selection: (
            str(selection.get("market")),
            float(selection.get("line") or -999),
            str(selection.get("pick")),
        ),
    )
    return {
        "fixture_id": row.get("fixtureId"),
        "p1": p1,
        "p2": p2,
        "start_time": row.get("startTime"),
        "tournament": row.get("tournamentName"),
        "tournament_id": row.get("tournamentId"),
        "bookmaker": base.BOOKMAKER,
        "bookmaker_active": bool(book.get("bookmakerIsActive", True)),
        "suspended": bool(book.get("suspended", False)),
        "raw_markets": len(raw_markets),
        "recognized_markets": sorted(recognized_markets),
        "canonical_selections": selections,
        "fixture_line_authority_version": VERSION,
    }


@contextmanager
def _patched_runtime():
    old = v913._sanitize_fixture
    try:
        v913._sanitize_fixture = _sanitize_fixture
        yield
    finally:
        v913._sanitize_fixture = old


def _stamp() -> None:
    availability = base._read(base.AVAILABILITY, {})
    if not isinstance(availability, dict):
        return
    availability = dict(availability)
    availability["fixture_line_authority_v931"] = {
        "version": VERSION,
        "fixture_specific_total_line_precedes_catalogue_fallback": True,
        "prices_used": False,
        "model_raw_changed": False,
    }
    availability["runtime_adapter_version"] = VERSION
    base._write(base.AVAILABILITY, availability)


def prepare() -> dict:
    with _patched_runtime():
        result = dict(v924.prepare())
    _stamp()
    result["fixture_line_authority_version"] = VERSION
    result["prices_used"] = False
    return result


def finalize() -> dict:
    with _patched_runtime():
        result = dict(v924.finalize())
    _stamp()
    result["fixture_line_authority_version"] = VERSION
    result["prices_used"] = False
    return result


def main() -> None:
    mode = str(sys.argv[1] if len(sys.argv) > 1 else "prepare").strip().casefold()
    if mode == "prepare":
        result = prepare()
    elif mode == "finalize":
        result = finalize()
    else:
        raise SystemExit("usage: superbet_market_context_v931.py [prepare|finalize]")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
