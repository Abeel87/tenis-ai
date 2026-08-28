from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://api.oddspapi.io/v4"
SPORT_ID_TENNIS = 12
MAX_FIXTURE_REQUESTS = 8
OUT = Path("oddspapi_superbet_market_catalog.json")


def _get_json(path: str, api_key: str, **params):
    query = {"apiKey": api_key, **{k: v for k, v in params.items() if v is not None}}
    url = f"{BASE_URL}/{path}?{urlencode(query)}"
    req = Request(url, headers={"User-Agent": "tenis-ai-oddspapi-smoke/1.0", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"OddsPapi {path}: HTTP {exc.code}; {body}") from None
    except URLError as exc:
        raise RuntimeError(f"OddsPapi {path}: network error: {exc.reason}") from None


def _pick_superbet_slug(bookmakers) -> str | None:
    rows = bookmakers if isinstance(bookmakers, list) else []
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or "").strip()
        name = str(row.get("bookmakerName") or "").strip()
        hay = f"{slug} {name}".casefold()
        if "superbet" in hay:
            candidates.append((slug, name))
    if not candidates:
        return None
    preferred = ("superbet.pl", "superbet-pl", "superbet")
    for target in preferred:
        for slug, _ in candidates:
            if slug.casefold() == target:
                return slug
    return candidates[0][0]


def _market_index(markets) -> dict[str, dict]:
    out = {}
    for row in markets if isinstance(markets, list) else []:
        if not isinstance(row, dict):
            continue
        if row.get("sportId") not in (None, SPORT_ID_TENNIS):
            continue
        market_id = row.get("marketId")
        if market_id is None:
            continue
        outcomes = {}
        for outcome in row.get("outcomes") or []:
            if isinstance(outcome, dict) and outcome.get("outcomeId") is not None:
                outcomes[str(outcome["outcomeId"])] = outcome
        out[str(market_id)] = {**row, "_outcomes": outcomes}
    return out


def _line_from_outcome(bookmaker_outcome_id) -> float | None:
    text = str(bookmaker_outcome_id or "")
    nums = re.findall(r"(?<!\d)(\d+(?:\.\d+)?)(?!\d)", text)
    if not nums:
        return None
    # Handicap/total lines are usually the decimal number embedded in bookmakerOutcomeId.
    decimals = [float(x) for x in nums if "." in x]
    if decimals:
        return decimals[0]
    return None


def _sanitize_fixture(odds_payload: dict, bookmaker_slug: str, market_meta: dict[str, dict]) -> dict | None:
    bookmaker_odds = odds_payload.get("bookmakerOdds") or {}
    if not isinstance(bookmaker_odds, dict):
        return None

    book = bookmaker_odds.get(bookmaker_slug)
    if not isinstance(book, dict):
        book = next((v for k, v in bookmaker_odds.items() if "superbet" in str(k).casefold() and isinstance(v, dict)), None)
    if not isinstance(book, dict):
        return None

    markets = book.get("markets") or {}
    if not isinstance(markets, dict) or not markets:
        return None

    sanitized_markets = []
    for market_id, market_data in markets.items():
        if not isinstance(market_data, dict):
            continue
        meta = market_meta.get(str(market_id), {})
        market_active = bool(market_data.get("marketActive", True))
        selections = []
        for outcome_id, outcome_data in (market_data.get("outcomes") or {}).items():
            if not isinstance(outcome_data, dict):
                continue
            outcome_meta = (meta.get("_outcomes") or {}).get(str(outcome_id), {})
            for _, player_data in (outcome_data.get("players") or {}).items():
                if not isinstance(player_data, dict) or not player_data.get("active", True):
                    continue
                bookmaker_outcome_id = player_data.get("bookmakerOutcomeId")
                selections.append(
                    {
                        "outcome_id": str(outcome_id),
                        "outcome_name": outcome_meta.get("outcomeName"),
                        "player_name": player_data.get("playerName"),
                        "bookmaker_outcome_id": bookmaker_outcome_id,
                        "line": _line_from_outcome(bookmaker_outcome_id),
                        "main_line": bool(player_data.get("mainLine", False)),
                        "active": True,
                    }
                )
        if not selections:
            continue
        sanitized_markets.append(
            {
                "market_id": str(market_id),
                "market_name": meta.get("marketName") or meta.get("marketNameShort") or f"market {market_id}",
                "market_type": meta.get("marketType"),
                "period": meta.get("period"),
                "player_prop": meta.get("playerProp"),
                "handicap_market": meta.get("handicap"),
                "active": market_active,
                "selections": selections,
            }
        )

    if not sanitized_markets:
        return None
    sanitized_markets.sort(key=lambda x: (str(x.get("market_name") or ""), str(x.get("market_id") or "")))
    return {
        "fixture_id": odds_payload.get("fixtureId"),
        "start_time": odds_payload.get("startTime"),
        "status": odds_payload.get("statusName"),
        "tournament": odds_payload.get("tournamentName"),
        "p1": odds_payload.get("participant1Name"),
        "p2": odds_payload.get("participant2Name"),
        "bookmaker": bookmaker_slug,
        "bookmaker_active": bool(book.get("bookmakerIsActive", True)),
        "suspended": bool(book.get("suspended", False)),
        "markets": sanitized_markets,
    }


def _print_summary(report: dict) -> None:
    print("\n=== SUPERBET TENNIS MARKET CATALOG — NO ODDS ===")
    print(f"Bookmaker slug: {report.get('bookmaker_slug')}")
    print(f"Fixtures returned by OddsPapi: {report.get('fixtures_seen', 0)}")
    print(f"Fixtures checked for Superbet: {report.get('fixtures_checked', 0)}")
    print(f"Fixtures with Superbet markets: {len(report.get('fixtures') or [])}")
    for fixture in report.get("fixtures") or []:
        print(f"\n{fixture.get('p1')} vs {fixture.get('p2')} | {fixture.get('tournament')} | {fixture.get('start_time')}")
        for market in fixture.get("markets") or []:
            lines = sorted({s.get("line") for s in market.get("selections") or [] if s.get("line") is not None})
            players = sorted({str(s.get("player_name")) for s in market.get("selections") or [] if s.get("player_name")})
            line_text = ",".join(f"{x:g}" for x in lines) if lines else "—"
            player_text = ", ".join(players[:4]) if players else "—"
            print(
                f"  [{market.get('market_id')}] {market.get('market_name')}"
                f" | prop={market.get('player_prop')} | lines={line_text} | players={player_text}"
            )
    print(f"\nSanitized report: {OUT}")
    print("Prices/odds are intentionally discarded and never written to the report.")


def main() -> int:
    api_key = os.getenv("ODDSPAPI_API_KEY", "").strip()
    if not api_key:
        print("ODDSPAPI_API_KEY is missing", file=sys.stderr)
        return 2

    bookmakers = _get_json("bookmakers", api_key)
    bookmaker_slug = _pick_superbet_slug(bookmakers)
    if not bookmaker_slug:
        raise RuntimeError("OddsPapi bookmaker catalogue does not contain Superbet")
    time.sleep(1.05)

    markets = _get_json("markets", api_key, language="en")
    market_meta = _market_index(markets)
    time.sleep(1.05)

    now = datetime.now(timezone.utc)
    date_from = now.date().isoformat()
    date_to = (now + timedelta(days=2)).date().isoformat()
    fixtures = _get_json("fixtures", api_key, sportId=SPORT_ID_TENNIS, **{"from": date_from, "to": date_to}, language="en")
    fixtures = fixtures if isinstance(fixtures, list) else []
    fixtures = [x for x in fixtures if isinstance(x, dict) and x.get("hasOdds")]
    fixtures.sort(key=lambda x: str(x.get("startTime") or ""))

    report = {
        "version": "oddspapi-superbet-smoke-v1",
        "generated_at": now.isoformat(),
        "sport_id": SPORT_ID_TENNIS,
        "bookmaker_slug": bookmaker_slug,
        "date_from": date_from,
        "date_to": date_to,
        "fixtures_seen": len(fixtures),
        "fixtures_checked": 0,
        "fixtures": [],
        "contains_prices": False,
    }

    for fixture in fixtures[:MAX_FIXTURE_REQUESTS]:
        fixture_id = fixture.get("fixtureId")
        if not fixture_id:
            continue
        payload = _get_json(
            "odds",
            api_key,
            fixtureId=fixture_id,
            bookmakers=bookmaker_slug,
            language="en",
            verbosity=3,
            oddsFormat="decimal",
        )
        report["fixtures_checked"] += 1
        sanitized = _sanitize_fixture(payload if isinstance(payload, dict) else {}, bookmaker_slug, market_meta)
        if sanitized:
            report["fixtures"].append(sanitized)
        time.sleep(0.55)
        # Two real Superbet fixtures are enough to validate market/line coverage without burning the free quota.
        if len(report["fixtures"]) >= 2:
            break

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_summary(report)

    if not report["fixtures"]:
        print("\nNo Superbet tennis markets found in sampled fixtures. This is a valid diagnostic result, not a crash.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
