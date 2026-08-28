from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://api.oddspapi.io/v4"
SPORT_ID = 12
OUT = Path("oddspapi_player_prop_catalog_paid.json")


def get_json(path: str, api_key: str, **params):
    query = {"apiKey": api_key, **params}
    req = Request(
        f"{BASE}/{path}?{urlencode(query)}",
        headers={"User-Agent": "tenis-ai-player-prop-catalog/1.0", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"OddsPapi {path}: HTTP {exc.code}; {body}") from None
    except URLError as exc:
        raise RuntimeError(f"OddsPapi {path}: network error: {exc.reason}") from None


def current_superbet(account: dict) -> dict | None:
    current = str(account.get("current_subscription_id") or "")
    for sub in account.get("subscriptions") or []:
        if not isinstance(sub, dict) or str(sub.get("subscription_id") or "") != current:
            continue
        books = sub.get("bookmakers") or {}
        if not isinstance(books, dict):
            continue
        raw = books.get("superbet.pl")
        if isinstance(raw, dict):
            return {
                "bookmaker": "superbet.pl",
                "active": bool(sub.get("is_active", False)),
                "has_player_props": raw.get("has_player_props"),
                "has_live_odds": raw.get("has_live_odds"),
            }
    return None


def main() -> int:
    key = os.getenv("ODDSPAPI_API_KEY", "").strip()
    if not key:
        raise SystemExit("ODDSPAPI_API_KEY is missing")

    account = get_json("account", key)
    markets = get_json("markets", key, language="en")

    tennis_props = []
    serve_related = []
    needles = ("ace", "aces", "double fault", "fault", "serve")

    for row in markets if isinstance(markets, list) else []:
        if not isinstance(row, dict) or row.get("sportId") != SPORT_ID or not bool(row.get("playerProp", False)):
            continue
        item = {
            "market_id": row.get("marketId"),
            "market_name": row.get("marketName") or row.get("marketNameShort"),
            "market_type": row.get("marketType"),
            "period": row.get("period"),
            "handicap": row.get("handicap"),
            "player_prop": True,
        }
        tennis_props.append(item)
        hay = f"{item['market_name']} {item['market_type']}".casefold()
        if any(x in hay for x in needles):
            serve_related.append(item)

    tennis_props.sort(key=lambda x: (str(x.get("market_name") or ""), str(x.get("market_id") or "")))
    serve_related.sort(key=lambda x: (str(x.get("market_name") or ""), str(x.get("market_id") or "")))

    report = {
        "version": "player-prop-catalog-paid-v1",
        "superbet_access": current_superbet(account if isinstance(account, dict) else {}),
        "tennis_player_prop_count": len(tennis_props),
        "serve_related_count": len(serve_related),
        "serve_related": serve_related,
        "tennis_player_props": tennis_props,
        "contains_api_key": False,
        "contains_prices": False,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== ODDSPAPI PAID TENNIS PLAYER PROP CATALOGUE — SANITIZED ===")
    print(json.dumps(report["superbet_access"], ensure_ascii=False))
    print(f"tennis_player_prop_count={len(tennis_props)} serve_related_count={len(serve_related)}")
    for item in serve_related:
        print(f"  [{item['market_id']}] {item['market_name']} | type={item['market_type']} | period={item['period']} | handicap={item['handicap']}")
    print(f"sanitized_report={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
