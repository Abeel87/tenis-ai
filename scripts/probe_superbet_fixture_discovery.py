from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import superbet_market_core as core


def _rows(payload):
    return payload if isinstance(payload, list) else core._flatten_payload(payload)


def _request_with_rate_limit_retry(path, api_key, quota, **params):
    for attempt in range(3):
        try:
            return core._request(path, api_key, quota, **params)
        except RuntimeError as exc:
            message = str(exc)
            if "HTTP 429" not in message or "RATE_LIMITED" not in message or attempt == 2:
                raise
            match = re.search(r'"retryMs"\s*:\s*(\d+)', message)
            retry_ms = int(match.group(1)) if match else 2000
            time.sleep((retry_ms + 500) / 1000.0)
    raise RuntimeError("unreachable")


def main() -> None:
    api_key = os.environ.get("ODDSPAPI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("ODDSPAPI_API_KEY missing")

    now = datetime.now(timezone.utc)
    date_from = now.date().isoformat()
    date_to = (now + timedelta(days=core.FIXTURE_HORIZON_DAYS)).date().isoformat()
    quota = {"requests_used_by_v91": 0, "monthly_cap": 10}

    variants = {
        "discovery_only": {
            "sportId": core.SPORT_ID_TENNIS,
            "from": date_from,
            "to": date_to,
            "statusId": 0,
            "language": "en",
        },
        "has_odds_any_bookmaker": {
            "sportId": core.SPORT_ID_TENNIS,
            "from": date_from,
            "to": date_to,
            "statusId": 0,
            "hasOdds": "true",
            "language": "en",
        },
        "has_odds_superbet": {
            "sportId": core.SPORT_ID_TENNIS,
            "from": date_from,
            "to": date_to,
            "statusId": 0,
            "hasOdds": "true",
            "bookmakers": core.BOOKMAKER,
            "language": "en",
        },
    }

    report = {
        "window": {"from": date_from, "to": date_to},
        "sport_id": core.SPORT_ID_TENNIS,
        "bookmaker": core.BOOKMAKER,
        "variants": {},
    }
    for index, (name, params) in enumerate(variants.items()):
        if index:
            time.sleep(2.2)
        payload = _request_with_rate_limit_retry("fixtures", api_key, quota, **params)
        rows = _rows(payload)
        report["variants"][name] = {
            "fixtures": len(rows),
            "sample": [
                {
                    "fixtureId": row.get("fixtureId"),
                    "participant1Name": row.get("participant1Name"),
                    "participant2Name": row.get("participant2Name"),
                    "startTime": row.get("startTime"),
                    "tournamentId": row.get("tournamentId"),
                }
                for row in rows[:5]
                if isinstance(row, dict)
            ],
        }

    report["requests_used"] = quota["requests_used_by_v91"]
    print("SUPERBET_FIXTURE_DISCOVERY_PROBE " + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
