from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://api.oddspapi.io/v4"
OUT = Path("oddspapi_superbet_capabilities.json")


def get_json(path: str, api_key: str, **params):
    query = {"apiKey": api_key, **params}
    req = Request(
        f"{BASE_URL}/{path}?{urlencode(query)}",
        headers={"User-Agent": "tenis-ai-oddspapi-capability-smoke/1.0", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"OddsPapi {path}: HTTP {exc.code}; {body}") from None
    except URLError as exc:
        raise RuntimeError(f"OddsPapi {path}: network error: {exc.reason}") from None


def superbet_access(account: dict) -> list[dict]:
    rows = []
    current = str(account.get("current_subscription_id") or "")
    for subscription in account.get("subscriptions") or []:
        if not isinstance(subscription, dict):
            continue
        books = subscription.get("bookmakers") or {}
        if not isinstance(books, dict):
            continue
        for slug, raw in books.items():
            if "superbet" not in str(slug).casefold() or not isinstance(raw, dict):
                continue
            rows.append(
                {
                    "bookmaker": str(slug),
                    "subscription_current": str(subscription.get("subscription_id") or "") == current,
                    "subscription_active": bool(subscription.get("is_active", False)),
                    "has_live_odds": raw.get("has_live_odds"),
                    "has_player_props": raw.get("has_player_props"),
                }
            )
    return rows


def serve_markets(markets) -> list[dict]:
    needles = ("ace", "aces", "double fault", "fault", "serve")
    out = []
    for row in markets if isinstance(markets, list) else []:
        if not isinstance(row, dict) or row.get("sportId") != 12:
            continue
        name = str(row.get("marketName") or row.get("marketNameShort") or "")
        market_type = str(row.get("marketType") or "")
        hay = f"{name} {market_type}".casefold()
        if not any(word in hay for word in needles):
            continue
        out.append(
            {
                "market_id": row.get("marketId"),
                "market_name": name,
                "market_type": market_type,
                "period": row.get("period"),
                "player_prop": row.get("playerProp"),
                "line": row.get("handicap"),
            }
        )
    out.sort(key=lambda x: (not bool(x.get("player_prop")), str(x.get("market_name") or ""), str(x.get("market_id") or "")))
    return out


def main() -> int:
    api_key = os.getenv("ODDSPAPI_API_KEY", "").strip()
    if not api_key:
        print("ODDSPAPI_API_KEY is missing", file=sys.stderr)
        return 2

    account = get_json("account", api_key)
    markets = get_json("markets", api_key, language="en")
    report = {
        "version": "oddspapi-superbet-capabilities-v1",
        "superbet_access": superbet_access(account if isinstance(account, dict) else {}),
        "tennis_serve_markets": serve_markets(markets),
        "contains_api_key": False,
        "contains_prices": False,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== ODDSPAPI SUPERBET CAPABILITIES — SANITIZED ===")
    for row in report["superbet_access"]:
        print(
            f"{row['bookmaker']}: active={row['subscription_active']} current={row['subscription_current']} "
            f"player_props={row['has_player_props']} live={row['has_live_odds']}"
        )
    print("Tennis serve-related market catalogue:")
    for row in report["tennis_serve_markets"]:
        print(
            f"  [{row['market_id']}] {row['market_name']} | type={row['market_type']} "
            f"| player_prop={row['player_prop']} | line={row['line']}"
        )
    print(f"Sanitized report: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
