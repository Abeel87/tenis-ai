from __future__ import annotations

"""Temporary sanitized probe for current OddsPapi Superbet bookmaker slugs.

No prices, selections or API key are persisted. The probe only reports whether
the supported /fixtures hasOdds filter finds current tennis fixtures for each
Superbet slug and whether a tiny sample /odds response contains that slug.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://api.oddspapi.io/v4"
SLUGS = ("superbet", "superbet.pl")
SPORT_ID = 12
SAMPLE = 3


def get_json(path: str, api_key: str, **params):
    query = {"apiKey": api_key, **{k: v for k, v in params.items() if v is not None}}
    req = Request(
        f"{BASE}/{path}?{urlencode(query)}",
        headers={"User-Agent": "tenis-ai-superbet-slug-probe/1.0", "Accept": "application/json"},
    )
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def bookmaker_keys(payload):
    if not isinstance(payload, dict):
        return []
    value = payload.get("bookmakerOdds")
    return sorted(str(k) for k in value) if isinstance(value, dict) else []


def main():
    api_key = os.environ["ODDSPAPI_API_KEY"].strip()
    now = datetime.now(timezone.utc)
    date_from = now.date().isoformat()
    date_to = (now + timedelta(days=2)).date().isoformat()

    bookmakers = get_json("bookmakers", api_key)
    catalog = {}
    for row in bookmakers if isinstance(bookmakers, list) else []:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or "")
        if slug in SLUGS:
            catalog[slug] = {
                "bookmakerName": row.get("bookmakerName"),
                "liveOdds": row.get("liveOdds"),
                "cloneOf": row.get("cloneOf"),
            }

    report = {
        "generated_at": now.isoformat(),
        "catalog": catalog,
        "slugs": {},
        "contains_prices": False,
        "contains_api_key": False,
    }

    for slug in SLUGS:
        try:
            fixtures = get_json(
                "fixtures",
                api_key,
                sportId=SPORT_ID,
                **{"from": date_from, "to": date_to},
                statusId=0,
                hasOdds="true",
                bookmakers=slug,
                language="en",
            )
            fixtures = fixtures if isinstance(fixtures, list) else []
            sample_rows = []
            for fixture in fixtures[:SAMPLE]:
                if not isinstance(fixture, dict) or not fixture.get("fixtureId"):
                    continue
                odds = get_json(
                    "odds",
                    api_key,
                    fixtureId=fixture["fixtureId"],
                    bookmakers=slug,
                    language="en",
                    verbosity=1,
                    oddsFormat="decimal",
                )
                keys = bookmaker_keys(odds)
                sample_rows.append({
                    "fixture_id": fixture.get("fixtureId"),
                    "start_time": fixture.get("startTime"),
                    "tournament": fixture.get("tournamentName"),
                    "has_odds": fixture.get("hasOdds"),
                    "requested_slug_present": slug in keys,
                    "bookmaker_keys": keys,
                })
            report["slugs"][slug] = {
                "fixtures_with_has_odds": len(fixtures),
                "sample": sample_rows,
                "error": None,
            }
        except Exception as exc:
            report["slugs"][slug] = {
                "fixtures_with_has_odds": 0,
                "sample": [],
                "error": f"{type(exc).__name__}: {exc}"[:300],
            }

    print("SUPERBET_SLUG_PROBE " + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
