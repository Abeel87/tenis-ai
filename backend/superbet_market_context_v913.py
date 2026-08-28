from __future__ import annotations

"""Tenis AI v9.1.3 — bounded OddsPapi tournament batching.

OddsPapi accepts at most five tournament IDs in one `odds-by-tournaments`
request. v9.1 collected every matched tournament and sent them in one call,
which made the production Superbet feed fail with HTTP 400 on busy slates.

This adapter keeps the v9.1 schema and logic intact, but transparently splits
that one request into bounded batches. Prices remain discarded by v9.1.

The paid Normal plan gives enough quota to refresh the operator catalogue
hourly. We keep a local 4,000 request/month ceiling so the app still has
headroom below the account's 5,000 request/month allowance.
"""

import json
import sys
import time
from collections.abc import Callable

try:
    from . import superbet_market_context_v91 as base
except ImportError:
    import superbet_market_context_v91 as base

VERSION = "v9.1.3"
MAX_TOURNAMENT_IDS_PER_REQUEST = 5
BATCH_DELAY_SECONDS = 1.05
REFRESH_HOURS = 1
MONTHLY_REQUEST_CAP = 4000


def _tournament_ids(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw = value
    else:
        raw = str(value).split(",")
    out: list[str] = []
    seen = set()
    for item in raw:
        token = str(item or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _chunks(values: list[str], size: int = MAX_TOURNAMENT_IDS_PER_REQUEST):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def batched_request(
    original_request: Callable,
    path: str,
    api_key: str,
    quota: dict,
    **params,
):
    """Call v9.1 request normally, except tournament odds are batched <= 5 IDs."""
    ids = _tournament_ids(params.get("tournamentIds"))
    if path != "odds-by-tournaments" or len(ids) <= MAX_TOURNAMENT_IDS_PER_REQUEST:
        return original_request(path, api_key, quota, **params)

    rows: list[dict] = []
    for batch_no, chunk in enumerate(_chunks(ids)):
        if batch_no:
            time.sleep(BATCH_DELAY_SECONDS)
        batch_params = dict(params)
        batch_params["tournamentIds"] = ",".join(chunk)
        payload = original_request(path, api_key, quota, **batch_params)
        rows.extend(base._flatten_payload(payload))
    return rows


def _stamp_runtime_adapter() -> None:
    availability = base._read(base.AVAILABILITY, {})
    if not isinstance(availability, dict):
        return
    availability = dict(availability)
    availability["runtime_adapter_version"] = VERSION
    availability["tournament_batch_limit"] = MAX_TOURNAMENT_IDS_PER_REQUEST
    availability["refresh_hours"] = REFRESH_HOURS
    quota = availability.get("quota_guard")
    if isinstance(quota, dict):
        quota = dict(quota)
        quota["monthly_cap"] = MONTHLY_REQUEST_CAP
        availability["quota_guard"] = quota
    base._write(base.AVAILABILITY, availability)


def prepare() -> dict:
    original_request = base._request
    original_refresh_hours = base.REFRESH_HOURS
    original_monthly_cap = base.MONTHLY_REQUEST_CAP

    def request(path: str, api_key: str, quota: dict, **params):
        return batched_request(original_request, path, api_key, quota, **params)

    base._request = request
    base.REFRESH_HOURS = REFRESH_HOURS
    base.MONTHLY_REQUEST_CAP = MONTHLY_REQUEST_CAP
    try:
        result = dict(base.prepare())
    finally:
        base._request = original_request
        base.REFRESH_HOURS = original_refresh_hours
        base.MONTHLY_REQUEST_CAP = original_monthly_cap

    _stamp_runtime_adapter()
    result["runtime_adapter_version"] = VERSION
    result["tournament_batch_limit"] = MAX_TOURNAMENT_IDS_PER_REQUEST
    result["refresh_hours"] = REFRESH_HOURS
    result["monthly_request_cap"] = MONTHLY_REQUEST_CAP
    return result


def finalize() -> dict:
    result = dict(base.finalize())
    result["runtime_adapter_version"] = VERSION
    return result


def main() -> None:
    mode = str(sys.argv[1] if len(sys.argv) > 1 else "prepare").strip().casefold()
    if mode == "prepare":
        result = prepare()
    elif mode == "finalize":
        result = finalize()
    else:
        raise SystemExit("usage: superbet_market_context_v913.py [prepare|finalize]")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
