from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://api.oddspapi.io/v4"
SPORT_ID = 12
OUT = Path("oddspapi_player_props_paid_smoke.json")
MAX_FIXTURES = 12


def get_json(path: str, api_key: str, **params):
    query = {"apiKey": api_key, **{k: v for k, v in params.items() if v is not None}}
    req = Request(
        f"{BASE}/{path}?{urlencode(query)}",
        headers={"User-Agent": "tenis-ai-player-props-paid-smoke/1.1", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"OddsPapi {path}: HTTP {exc.code}; {body}") from None
    except URLError as exc:
        raise RuntimeError(f"OddsPapi {path}: network error: {exc.reason}") from None


def find_superbet_access(account: dict) -> list[dict]:
    current = str(account.get("current_subscription_id") or "")
    rows = []
    for sub in account.get("subscriptions") or []:
        if not isinstance(sub, dict):
            continue
        books = sub.get("bookmakers") or {}
        if not isinstance(books, dict):
            continue
        for slug, raw in books.items():
            if "superbet" not in str(slug).casefold() or not isinstance(raw, dict):
                continue
            rows.append({
                "bookmaker": str(slug),
                "current": str(sub.get("subscription_id") or "") == current,
                "active": bool(sub.get("is_active", False)),
                "has_player_props": raw.get("has_player_props"),
                "has_live_odds": raw.get("has_live_odds"),
            })
    return rows


def pick_superbet(bookmakers) -> str:
    candidates = []
    for row in bookmakers if isinstance(bookmakers, list) else []:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or "")
        name = str(row.get("bookmakerName") or "")
        if "superbet" in f"{slug} {name}".casefold():
            candidates.append(slug)
    for preferred in ("superbet.pl", "superbet-pl", "superbet"):
        if preferred in candidates:
            return preferred
    if not candidates:
        raise RuntimeError("Superbet not found in bookmaker catalogue")
    return candidates[0]


def market_index(markets) -> dict[str, dict]:
    out = {}
    for row in markets if isinstance(markets, list) else []:
        if not isinstance(row, dict) or row.get("marketId") is None:
            continue
        if row.get("sportId") not in (None, SPORT_ID):
            continue
        outcomes = {}
        for outcome in row.get("outcomes") or []:
            if isinstance(outcome, dict) and outcome.get("outcomeId") is not None:
                outcomes[str(outcome["outcomeId"])] = outcome
        out[str(row["marketId"])] = {**row, "_outcomes": outcomes}
    return out


def extract_line(meta: dict, bookmaker_outcome_id) -> float | None:
    try:
        value = float(meta.get("handicap"))
        if abs(value) > 1e-9 or any(x in str(meta.get("marketType") or "").casefold() for x in ("total", "spread", "handicap")):
            return value
    except (TypeError, ValueError):
        pass
    nums = re.findall(r"(?<!\d)(\d+(?:\.\d+)?)(?!\d)", str(bookmaker_outcome_id or ""))
    decimals = [float(x) for x in nums if "." in x]
    return decimals[0] if decimals else None


def prop_markets(payload: dict, slug: str, idx: dict[str, dict]) -> list[dict]:
    books = payload.get("bookmakerOdds") or {}
    book = books.get(slug) if isinstance(books, dict) else None
    if not isinstance(book, dict) and isinstance(books, dict):
        book = next((v for k, v in books.items() if "superbet" in str(k).casefold() and isinstance(v, dict)), None)
    if not isinstance(book, dict):
        return []
    out = []
    for market_id, market_data in (book.get("markets") or {}).items():
        if not isinstance(market_data, dict):
            continue
        meta = idx.get(str(market_id), {})
        if not bool(meta.get("playerProp", False)):
            continue
        selections = []
        for outcome_id, outcome_data in (market_data.get("outcomes") or {}).items():
            if not isinstance(outcome_data, dict):
                continue
            outcome_name = (meta.get("_outcomes") or {}).get(str(outcome_id), {}).get("outcomeName")
            for player_data in (outcome_data.get("players") or {}).values():
                if not isinstance(player_data, dict) or not player_data.get("active", True):
                    continue
                selections.append({
                    "outcome": outcome_name,
                    "player": player_data.get("playerName"),
                    "line": extract_line(meta, player_data.get("bookmakerOutcomeId")),
                    "main_line": bool(player_data.get("mainLine", False)),
                })
        if selections:
            out.append({
                "market_id": str(market_id),
                "market_name": meta.get("marketName") or meta.get("marketNameShort") or f"market {market_id}",
                "market_type": meta.get("marketType"),
                "period": meta.get("period"),
                "selections": selections,
            })
    out.sort(key=lambda x: str(x.get("market_name") or ""))
    return out


def fixture_priority(row: dict):
    text = " ".join(
        str(row.get(k) or "")
        for k in ("tournamentName", "categoryName", "tournamentSlug", "categorySlug")
    ).casefold()
    if "us open" in text or "grand slam" in text:
        tier = 0
    elif "atp" in text or "wta" in text:
        tier = 1
    elif "challenger" in text:
        tier = 2
    else:
        tier = 3
    return tier, str(row.get("startTime") or "")


def main() -> int:
    key = os.getenv("ODDSPAPI_API_KEY", "").strip()
    if not key:
        raise SystemExit("ODDSPAPI_API_KEY is missing")

    account = get_json("account", key)
    time.sleep(0.5)
    bookmakers = get_json("bookmakers", key)
    slug = pick_superbet(bookmakers)
    time.sleep(0.5)
    markets = get_json("markets", key, language="en")
    idx = market_index(markets)
    time.sleep(0.5)

    now = datetime.now(timezone.utc)
    fixtures = get_json(
        "fixtures", key, sportId=SPORT_ID,
        **{"from": now.date().isoformat(), "to": (now + timedelta(days=2)).date().isoformat()},
        language="en",
    )
    fixtures = [x for x in fixtures if isinstance(x, dict) and x.get("hasOdds")] if isinstance(fixtures, list) else []
    fixtures.sort(key=fixture_priority)

    report = {
        "version": "player-props-paid-smoke-v1.1",
        "generated_at": now.isoformat(),
        "superbet_access": find_superbet_access(account if isinstance(account, dict) else {}),
        "bookmaker": slug,
        "fixtures_seen": len(fixtures),
        "fixtures_checked": 0,
        "fixtures_with_player_props": 0,
        "fixtures": [],
        "contains_api_key": False,
        "contains_prices": False,
    }

    for fixture in fixtures[:MAX_FIXTURES]:
        fixture_id = fixture.get("fixtureId")
        if not fixture_id:
            continue
        payload = get_json("odds", key, fixtureId=fixture_id, bookmakers=slug, language="en", verbosity=3, oddsFormat="decimal")
        report["fixtures_checked"] += 1
        props = prop_markets(payload if isinstance(payload, dict) else {}, slug, idx)
        if props:
            report["fixtures_with_player_props"] += 1
        report["fixtures"].append({
            "fixture_id": fixture_id,
            "p1": fixture.get("participant1Name"),
            "p2": fixture.get("participant2Name"),
            "tournament": fixture.get("tournamentName"),
            "start_time": fixture.get("startTime"),
            "player_prop_markets": props,
        })
        time.sleep(0.5)
        if props:
            break

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== ODDSPAPI PAID PLAYER PROPS SMOKE — SANITIZED ===")
    for row in report["superbet_access"]:
        print(f"{row['bookmaker']}: active={row['active']} current={row['current']} player_props={row['has_player_props']} live={row['has_live_odds']}")
    print(f"bookmaker={slug} fixtures_seen={report['fixtures_seen']} checked={report['fixtures_checked']} with_props={report['fixtures_with_player_props']}")
    for fixture in report["fixtures"]:
        if not fixture["player_prop_markets"]:
            continue
        print(f"PROP FIXTURE: {fixture['p1']} vs {fixture['p2']} | {fixture['tournament']}")
        for market in fixture["player_prop_markets"]:
            sample = market["selections"][:8]
            print(f"  {market['market_name']} | type={market['market_type']} | selections={json.dumps(sample, ensure_ascii=False)}")
    print(f"sanitized_report={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
