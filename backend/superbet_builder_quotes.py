from __future__ import annotations

"""Read-only exact Superbet Bet Builder quote artifact.

This producer is intentionally isolated from iNeed$ runtime. It consumes only
matches already verified by ``superbet_direct_current.json`` and re-reads the
exact public event JSON to extract operator-provided pre-priced combination
market rows. It never multiplies leg prices, never computes probability/EV,
and never reserves bankroll.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

try:
    from . import superbet_direct as direct
except ImportError:
    import superbet_direct as direct

MODE = "SHADOW_SUPERBET_EXACT_BUILDER_QUOTE_FEED"
QUOTE_POLICY = "EXACT_PREPRICED_OPERATOR_ONLY"
SAFE_STATUSES = {"OK", "NO_EXACT_BUILDER_QUOTES", "NO_CURRENT_OVERLAP", "SOURCE_UNAVAILABLE"}
MAX_DIRECT_AGE_SECONDS = 2 * 60 * 60
MAX_FUTURE_SKEW_SECONDS = 5 * 60
DATA_DIR = Path(__file__).resolve().parents[1] / "frontend" / "data"
DIRECT_PATH = DATA_DIR / "superbet_direct_current.json"
OUTPUT_PATH = DATA_DIR / "superbet_builder_quotes_current.json"
MAX_MATCHES = 64


def _text(value) -> str:
    return str(value or "").strip()


def _parse_utc(value) -> datetime | None:
    token = _text(value)
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _empty(status: str, *, generated_at: str, direct_generated_at=None) -> dict:
    return {
        "mode": MODE,
        "status": status,
        "generated_at": generated_at,
        "direct_generated_at": direct_generated_at,
        "operator": "superbet.pl",
        "source": direct.EVENT_JSON_SOURCE,
        "quote_kind": direct.SUPERBETS_QUOTE_KIND,
        "quote_policy": QUOTE_POLICY,
        "scope": "VERIFIED_CURRENT_SUPERBET_DIRECT_MATCHES",
        "matches": [],
        "rejected": [],
        "quotes_count": 0,
        "contains_prices": False,
        "operator_prices_metadata_only": True,
        "prices_used": False,
        "synthetic_prices": False,
        "external_requests": 0,
        "dynamic_sga_requests": 0,
        "writes_canonical_context": False,
        "production_influence": False,
        "playable_influence": False,
        "player_dna_influence": False,
        "symphony_influence": False,
        "ineed_runtime_influence": False,
        "automatic_real_betting": False,
    }


def build_artifact(direct_feed: object, *, fetcher=None, now: datetime | None = None) -> dict:
    """Extract exact pre-priced builder quotes for already-verified Direct matches."""
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    if not isinstance(direct_feed, dict):
        return _empty("DIRECT_INPUT_INVALID", generated_at=stamp)
    direct_status = _text(direct_feed.get("status"))
    direct_generated_at = direct_feed.get("generated_at")
    direct_stamp = _parse_utc(direct_generated_at)
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if direct_feed.get("prices_used") is not False:
        return _empty("DIRECT_INPUT_UNSAFE", generated_at=stamp, direct_generated_at=direct_generated_at)
    if direct_status == "NO_CURRENT_OVERLAP":
        return _empty("NO_CURRENT_OVERLAP", generated_at=stamp, direct_generated_at=direct_generated_at)
    if direct_status != "OK":
        return _empty("DIRECT_INPUT_UNSAFE", generated_at=stamp, direct_generated_at=direct_generated_at)
    if direct_stamp is None:
        return _empty("DIRECT_INPUT_STALE", generated_at=stamp, direct_generated_at=direct_generated_at)
    age_seconds = (now_utc - direct_stamp).total_seconds()
    if age_seconds > MAX_DIRECT_AGE_SECONDS or age_seconds < -MAX_FUTURE_SKEW_SECONDS:
        return _empty("DIRECT_INPUT_STALE", generated_at=stamp, direct_generated_at=direct_generated_at)
    raw_matches = [x for x in (direct_feed.get("matches") or []) if isinstance(x, dict)]
    if len(raw_matches) > MAX_MATCHES:
        return _empty("DIRECT_INPUT_UNSAFE", generated_at=stamp, direct_generated_at=direct_generated_at)
    event_fetch = fetcher or direct.fetch_event_payload_public
    out = _empty("NO_EXACT_BUILDER_QUOTES", generated_at=stamp, direct_generated_at=direct_generated_at)
    quote_matches: list[dict] = []
    rejected: list[dict] = []
    requests = 0
    for match in raw_matches:
        match_id = match.get("match_id")
        event_id = _text(match.get("event_id"))
        if match.get("direct_match_verified") is not True or match.get("prices_used") is not False or not event_id.isdigit():
            rejected.append({"match_id": match_id, "event_id": event_id or None, "status": "UNVERIFIED_DIRECT_MATCH"})
            continue
        try:
            requests += 1
            payload = event_fetch(event_id)
            event_row = direct._event_record(payload, event_id)
            if not isinstance(event_row, dict):
                raise ValueError("current event fixture missing")
            fixture_p1, fixture_p2 = direct._players_from_event(event_row)
            candidate = {"fixture_id": event_id, "event_id": event_id, "p1": fixture_p1, "p2": fixture_p2, "start_time": event_row.get("utcDate")}
            selected = direct.fixture_matching.select_cached_fixture(match, [candidate])
            if not isinstance(selected, dict) or _text(selected.get("fixture_id")) != event_id:
                raise ValueError("current event fixture identity mismatch")
            parsed = direct.parse_event_combination_quotes(payload, event_id=event_id, observed_at=stamp)
        except Exception as exc:
            failed = _empty("EVENT_FETCH_FAILED", generated_at=stamp, direct_generated_at=direct_generated_at)
            failed["rejected"] = rejected + [{"match_id": match_id, "event_id": event_id, "status": "EVENT_FETCH_FAILED", "error": type(exc).__name__}]
            failed["external_requests"] = requests
            return failed
        quotes = [dict(x) for x in (parsed.get("quotes") or []) if isinstance(x, dict)]
        quotes.sort(key=lambda row: _text(row.get("operator_selection_id")))
        operator_ids = [_text(row.get("operator_selection_id")) for row in quotes]
        if any(not value for value in operator_ids) or len(operator_ids) != len(set(operator_ids)):
            failed = _empty("QUOTE_IDENTITY_CONFLICT", generated_at=stamp, direct_generated_at=direct_generated_at)
            failed["external_requests"] = requests
            return failed
        quote_matches.append({"match_id": match_id, "p1": match.get("p1"), "p2": match.get("p2"), "scheduled_time": match.get("scheduled_time"), "event_id": event_id, "event_url": match.get("event_url"), "direct_match_verified": True, "observed_at": stamp, "quotes": quotes, "quotes_count": len(quotes)})
    quotes_count = sum(int(row.get("quotes_count") or 0) for row in quote_matches)
    out.update({"status": "OK" if quotes_count > 0 else "NO_EXACT_BUILDER_QUOTES", "matches": quote_matches, "rejected": rejected, "quotes_count": quotes_count, "contains_prices": quotes_count > 0, "external_requests": requests})
    return out


def _validate_quote(match: dict, quote: dict) -> None:
    event_id = _text(match.get("event_id"))
    ids = [_text(x) for x in (quote.get("component_selection_ids") or [])]
    if quote.get("operator") != "superbet.pl" or quote.get("quote_kind") != direct.SUPERBETS_QUOTE_KIND:
        raise ValueError("builder quote provenance mismatch")
    if quote.get("operator_verified") is not True or quote.get("freshness_verified") is not True:
        raise ValueError("builder quote verification missing")
    if _text(quote.get("source_event_id")) != event_id or quote.get("source") != direct.EVENT_JSON_SOURCE:
        raise ValueError("builder quote event/source mismatch")
    if not _text(quote.get("odds_timestamp")) or not _text(quote.get("operator_selection_id")):
        raise ValueError("builder quote timestamp/operator id missing")
    if len(ids) < 2 or any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("builder quote component identity invalid")
    price = direct._float_token(quote.get("combined_odds"))
    if price is None or price <= 1.0:
        raise ValueError("builder quote combined price invalid")


def validate_artifact(feed: object) -> dict:
    if not isinstance(feed, dict) or feed.get("mode") != MODE:
        raise ValueError("invalid builder quote artifact")
    if feed.get("status") not in SAFE_STATUSES:
        raise ValueError("unsafe builder quote status")
    if feed.get("prices_used") is not False or feed.get("synthetic_prices") is not False:
        raise ValueError("builder quote artifact must remain metadata-only")
    if int(feed.get("dynamic_sga_requests") or 0) != 0:
        raise ValueError("dynamic SGA is outside this artifact contract")
    for key in ("production_influence", "playable_influence", "player_dna_influence", "symphony_influence", "ineed_runtime_influence", "automatic_real_betting"):
        if feed.get(key) is not False:
            raise ValueError(f"builder quote artifact must keep {key}=false")
    counted = 0
    for match in feed.get("matches") or []:
        if not isinstance(match, dict) or match.get("direct_match_verified") is not True or not _text(match.get("event_id")):
            raise ValueError("builder quote artifact requires verified match identity")
        for quote in match.get("quotes") or []:
            if not isinstance(quote, dict):
                raise ValueError("builder quote row must be a dict")
            _validate_quote(match, quote)
            counted += 1
    if counted != int(feed.get("quotes_count") or 0):
        raise ValueError("builder quote count mismatch")
    if (counted > 0) != (feed.get("contains_prices") is True):
        raise ValueError("builder quote contains_prices mismatch")
    return feed


def write_artifact(feed: dict, path: Path | str = OUTPUT_PATH) -> Path:
    validate_artifact(feed)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
    return target


def _persist_unavailable(*, source_status: str, output_path: Path | str, direct_generated_at=None, external_requests: int = 0, now: datetime | None = None) -> dict:
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    safe = _empty("SOURCE_UNAVAILABLE", generated_at=stamp, direct_generated_at=direct_generated_at)
    safe["source_status"] = _text(source_status) or "UNKNOWN"
    safe["external_requests"] = int(external_requests or 0)
    path = write_artifact(safe, output_path)
    return {"status": "SOURCE_UNAVAILABLE", "source_status": safe["source_status"], "written": True, "path": str(path), "generated_at": safe.get("generated_at"), "matches": 0, "quotes_count": 0, "external_requests": safe.get("external_requests"), "prices_used": False, "ineed_runtime_influence": False, "automatic_real_betting": False}


def refresh_current(*, direct_path: Path | str = DIRECT_PATH, output_path: Path | str = OUTPUT_PATH, fetcher=None, now: datetime | None = None) -> dict:
    source = Path(direct_path)
    if not source.exists():
        return _persist_unavailable(source_status="DIRECT_INPUT_MISSING", output_path=output_path, now=now)
    try:
        direct_feed = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return _persist_unavailable(source_status="DIRECT_INPUT_INVALID", output_path=output_path, now=now)
    artifact = build_artifact(direct_feed, fetcher=fetcher, now=now)
    if artifact.get("status") not in SAFE_STATUSES:
        return _persist_unavailable(source_status=_text(artifact.get("status")) or "ARTIFACT_UNSAFE", output_path=output_path, direct_generated_at=artifact.get("direct_generated_at"), external_requests=int(artifact.get("external_requests") or 0), now=now)
    path = write_artifact(artifact, output_path)
    return {"status": artifact.get("status"), "written": True, "path": str(path), "generated_at": artifact.get("generated_at"), "matches": len(artifact.get("matches") or []), "quotes_count": artifact.get("quotes_count"), "external_requests": artifact.get("external_requests"), "prices_used": False, "ineed_runtime_influence": False, "automatic_real_betting": False}


def main() -> None:
    mode = _text(sys.argv[1] if len(sys.argv) > 1 else "refresh-current").casefold()
    if mode == "refresh-current":
        result = refresh_current()
    elif mode == "invalidate":
        source_status = _text(sys.argv[2] if len(sys.argv) > 2 else "UPSTREAM_REFRESH_FAILED")
        result = _persist_unavailable(source_status=source_status, output_path=OUTPUT_PATH)
    else:
        raise SystemExit("usage: superbet_builder_quotes.py [refresh-current|invalidate [reason]]")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") not in SAFE_STATUSES:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
