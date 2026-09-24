from __future__ import annotations

"""Bounded read-only dynamic Superbet Bet Builder quote sidecar.

This LOGIC-12 producer bridges the already-proven Phase-3 public dynamic SGA
source into an immutable SHADOW artifact. It never places bets, computes model
probability, settles tickets, or mutates iNeed$/Supabase state.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

try:
    from . import superbet_direct as direct
    from .ineed_builder_shadow import build_shadow_composition, resolve_dynamic_combined_quote
    from .ineed_money import direct_quote
    from .ineed_scope import filter_results
except ImportError:
    import superbet_direct as direct
    from ineed_builder_shadow import build_shadow_composition, resolve_dynamic_combined_quote
    from ineed_money import direct_quote
    from ineed_scope import filter_results

MODE = "SHADOW_SUPERBET_DYNAMIC_BUILDER_QUOTE_FEED"
SCHEMA_VERSION = "logic12-builder-dynamic-quote-artifact-v1"
OPERATOR = "superbet.pl"
MAX_DYNAMIC_REQUESTS = 8
MAX_DIRECT_AGE_SECONDS = 2 * 60 * 60
MAX_FUTURE_SKEW_SECONDS = 5 * 60
SAFE_STATUSES = {
    "OK",
    "NO_CURRENT_OVERLAP",
    "NO_ELIGIBLE_COMPOSITIONS",
    "NO_EXACT_DYNAMIC_QUOTES",
    "DIRECT_INPUT_INVALID",
    "DIRECT_INPUT_UNSAFE",
    "DIRECT_INPUT_STALE",
    "RESULTS_INPUT_INVALID",
    "CANDIDATE_LIMIT_EXCEEDED",
    "SOURCE_UNAVAILABLE",
}
DATA_DIR = Path(__file__).resolve().parents[1] / "frontend" / "data"
RESULTS_PATH = DATA_DIR / "results.json"
DIRECT_PATH = DATA_DIR / "superbet_direct_current.json"
OUTPUT_PATH = DATA_DIR / "superbet_builder_dynamic_quotes_current.json"


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
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "status": status,
        "generated_at": generated_at,
        "direct_generated_at": direct_generated_at,
        "operator": OPERATOR,
        "source": direct.DYNAMIC_SGA_SOURCE,
        "quote_kind": direct.DYNAMIC_SGA_QUOTE_KIND,
        "scope": "FINAL_SYMPHONY_X_VERIFIED_CURRENT_SUPERBET_DIRECT",
        "matches": [],
        "rejected": [],
        "candidate_count": 0,
        "quotes_count": 0,
        "external_requests": 0,
        "request_cap": MAX_DYNAMIC_REQUESTS,
        "contains_prices": False,
        "operator_prices_metadata_only": True,
        "prices_used": False,
        "synthetic_prices": False,
        "writes_canonical_context": False,
        "production_influence": False,
        "playable_influence": False,
        "player_dna_influence": False,
        "symphony_influence": False,
        "ineed_runtime_influence": False,
        "settlement_enabled": False,
        "result_inferred": False,
        "payout_computed": False,
        "automatic_real_betting": False,
    }


def _direct_input_status(direct_feed: object, *, now_utc: datetime) -> tuple[str | None, str | None]:
    if not isinstance(direct_feed, dict):
        return "DIRECT_INPUT_INVALID", None
    generated_at = direct_feed.get("generated_at")
    if direct_feed.get("prices_used") is not False:
        return "DIRECT_INPUT_UNSAFE", generated_at
    if direct_feed.get("status") == "NO_CURRENT_OVERLAP":
        return "NO_CURRENT_OVERLAP", generated_at
    if direct_feed.get("status") != "OK":
        return "DIRECT_INPUT_UNSAFE", generated_at
    stamp = _parse_utc(generated_at)
    if stamp is None:
        return "DIRECT_INPUT_STALE", generated_at
    age = (now_utc - stamp).total_seconds()
    if age > MAX_DIRECT_AGE_SECONDS or age < -MAX_FUTURE_SKEW_SECONDS:
        return "DIRECT_INPUT_STALE", generated_at
    return None, generated_at


def _composition_map(results: object) -> tuple[dict[str, dict] | None, dict]:
    if not isinstance(results, list):
        return None, {}
    scoped, scope = filter_results(results, economic_unit="BET_BUILDER_COMPOSITION")
    out: dict[str, dict] = {}
    for match in scoped:
        composition = build_shadow_composition(match)
        if composition is None:
            continue
        match_id = _text(composition.get("match_id"))
        if not match_id or match_id in out:
            return None, scope
        out[match_id] = composition
    return out, scope


def _candidate(composition: dict, direct_feed: dict, direct_match: dict) -> tuple[dict | None, str | None]:
    match_id = _text(composition.get("match_id"))
    event_id = _text(direct_match.get("event_id"))
    if direct_match.get("direct_match_verified") is not True or not event_id.isdigit():
        return None, "DIRECT_MATCH_UNVERIFIED"
    if _text(direct_match.get("p1")) != _text(composition.get("p1")):
        return None, "DIRECT_MATCH_IDENTITY_MISMATCH"
    if _text(direct_match.get("p2")) != _text(composition.get("p2")):
        return None, "DIRECT_MATCH_IDENTITY_MISMATCH"
    component_ids: list[str] = []
    for leg in composition.get("legs") or []:
        resolved = direct_quote(direct_feed, match_id, leg)
        selection_id = _text((resolved or {}).get("operator_selection_id"))
        if not selection_id:
            return None, "DIRECT_COMPONENT_IDENTITY_UNAVAILABLE"
        component_ids.append(selection_id)
    if len(component_ids) < 2 or len(component_ids) > 6:
        return None, "UNSUPPORTED_COMPONENT_COUNT"
    if len(set(component_ids)) != len(component_ids):
        return None, "DUPLICATE_COMPONENT_IDENTITY"
    source_url = direct.build_dynamic_sga_quote_url(event_id, component_ids)
    if not source_url:
        return None, "DYNAMIC_URL_UNAVAILABLE"
    return {
        "match_id": match_id,
        "p1": composition.get("p1"),
        "p2": composition.get("p2"),
        "composition": composition,
        "composition_id": composition.get("composition_id"),
        "event_id": event_id,
        "component_selection_ids": component_ids,
        "source_url": source_url,
    }, None


def build_artifact(results: object, direct_feed: object, *, fetcher=None, now: datetime | None = None) -> dict:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamp = now_utc.isoformat()
    direct_status, direct_generated_at = _direct_input_status(direct_feed, now_utc=now_utc)
    if direct_status is not None:
        return _empty(direct_status, generated_at=stamp, direct_generated_at=direct_generated_at)
    compositions, market_scope = _composition_map(results)
    if compositions is None:
        return _empty("RESULTS_INPUT_INVALID", generated_at=stamp, direct_generated_at=direct_generated_at)

    feed = direct_feed if isinstance(direct_feed, dict) else {}
    candidates: list[dict] = []
    rejected: list[dict] = []
    for row in feed.get("matches") or []:
        if not isinstance(row, dict):
            continue
        row_id = _text(row.get("match_id") if row.get("match_id") is not None else row.get("id"))
        composition = compositions.get(row_id)
        if composition is None:
            continue
        candidate, reason = _candidate(composition, feed, row)
        if candidate is None:
            rejected.append({"match_id": row_id, "event_id": row.get("event_id"), "status": reason})
            continue
        candidates.append(candidate)

    candidates.sort(key=lambda row: _text(row.get("composition_id")))
    out = _empty("NO_ELIGIBLE_COMPOSITIONS", generated_at=stamp, direct_generated_at=direct_generated_at)
    out["market_scope"] = market_scope
    out["candidate_count"] = len(candidates)
    out["rejected"] = rejected
    if len(candidates) > MAX_DYNAMIC_REQUESTS:
        out["status"] = "CANDIDATE_LIMIT_EXCEEDED"
        return out
    if not candidates:
        return out

    dynamic_fetch = fetcher or direct.fetch_dynamic_sga_payload_public
    matches: list[dict] = []
    requests = 0
    for candidate in candidates:
        try:
            requests += 1
            payload = dynamic_fetch(candidate["event_id"], candidate["component_selection_ids"])
        except Exception as exc:
            failed = _empty("SOURCE_UNAVAILABLE", generated_at=stamp, direct_generated_at=direct_generated_at)
            failed["market_scope"] = market_scope
            failed["candidate_count"] = len(candidates)
            failed["external_requests"] = requests
            failed["rejected"] = rejected + [{
                "match_id": candidate["match_id"],
                "event_id": candidate["event_id"],
                "status": "DYNAMIC_FETCH_FAILED",
                "error": type(exc).__name__,
            }]
            return failed

        quote = resolve_dynamic_combined_quote(
            candidate["composition"],
            feed,
            payload,
            observed_at=stamp,
            source_url=candidate["source_url"],
        )
        if quote is None:
            rejected.append({
                "match_id": candidate["match_id"],
                "event_id": candidate["event_id"],
                "composition_id": candidate["composition_id"],
                "status": "NO_EXACT_DYNAMIC_QUOTE",
            })
            continue
        matches.append({
            "match_id": candidate["match_id"],
            "p1": candidate["p1"],
            "p2": candidate["p2"],
            "event_id": candidate["event_id"],
            "composition_id": candidate["composition_id"],
            "observed_at": stamp,
            "quote": quote,
        })

    out.update({
        "status": "OK" if matches else "NO_EXACT_DYNAMIC_QUOTES",
        "matches": matches,
        "rejected": rejected,
        "quotes_count": len(matches),
        "external_requests": requests,
        "contains_prices": bool(matches),
    })
    return out


def _validate_quote(row: dict) -> None:
    event_id = _text(row.get("event_id"))
    composition_id = _text(row.get("composition_id"))
    quote = row.get("quote")
    if not event_id or not composition_id or not isinstance(quote, dict):
        raise ValueError("dynamic quote row identity missing")
    if quote.get("operator") != OPERATOR or quote.get("quote_kind") != "BET_BUILDER_COMBINED":
        raise ValueError("dynamic quote normalized provenance mismatch")
    if quote.get("source_quote_kind") != direct.DYNAMIC_SGA_QUOTE_KIND:
        raise ValueError("dynamic quote source kind mismatch")
    if quote.get("source") != direct.DYNAMIC_SGA_SOURCE:
        raise ValueError("dynamic quote source mismatch")
    if _text(quote.get("source_event_id")) != event_id:
        raise ValueError("dynamic quote event mismatch")
    if _text(quote.get("composition_id")) != composition_id:
        raise ValueError("dynamic quote composition mismatch")
    if quote.get("operator_verified") is not True or quote.get("freshness_verified") is not True:
        raise ValueError("dynamic quote verification missing")
    ids = [_text(x) for x in (quote.get("component_selection_ids") or [])]
    if len(ids) < 2 or len(ids) > 6 or any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("dynamic quote component identity invalid")
    try:
        odds = float(quote.get("combined_odds"))
    except (TypeError, ValueError):
        raise ValueError("dynamic quote combined odds invalid") from None
    if odds <= 1.0 or not _text(quote.get("odds_timestamp")):
        raise ValueError("dynamic quote odds/timestamp invalid")
    if not _text(quote.get("operator_combination_selection_id")):
        raise ValueError("dynamic quote SGA identity missing")
    expected_url = direct.build_dynamic_sga_quote_url(event_id, ids)
    if _text(quote.get("source_url")) != _text(expected_url):
        raise ValueError("dynamic quote source URL mismatch")


def validate_artifact(feed: object) -> dict:
    if not isinstance(feed, dict) or feed.get("mode") != MODE or feed.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("invalid dynamic builder artifact")
    if feed.get("status") not in SAFE_STATUSES:
        raise ValueError("unsafe dynamic builder status")
    for key in ("prices_used", "synthetic_prices", "writes_canonical_context", "production_influence",
                "playable_influence", "player_dna_influence", "symphony_influence", "ineed_runtime_influence",
                "settlement_enabled", "result_inferred", "payout_computed", "automatic_real_betting"):
        if feed.get(key) is not False:
            raise ValueError(f"dynamic builder artifact must keep {key}=false")
    requests = int(feed.get("external_requests") or 0)
    candidates = int(feed.get("candidate_count") or 0)
    if requests < 0 or requests > MAX_DYNAMIC_REQUESTS or candidates < 0:
        raise ValueError("dynamic builder request budget invalid")
    if feed.get("status") == "CANDIDATE_LIMIT_EXCEEDED" and requests != 0:
        raise ValueError("candidate-limit failure must make zero requests")
    rows = feed.get("matches") or []
    if not isinstance(rows, list):
        raise ValueError("dynamic builder matches must be a list")
    seen_compositions: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("dynamic builder match row must be a dict")
        _validate_quote(row)
        composition_id = _text(row.get("composition_id"))
        if composition_id in seen_compositions:
            raise ValueError("duplicate dynamic builder composition")
        seen_compositions.add(composition_id)
    if len(rows) != int(feed.get("quotes_count") or 0):
        raise ValueError("dynamic builder quote count mismatch")
    if bool(rows) != (feed.get("contains_prices") is True):
        raise ValueError("dynamic builder contains_prices mismatch")
    if rows and requests == 0:
        raise ValueError("dynamic builder quote cannot exist without a request")
    return feed


def write_artifact(feed: dict, path: Path | str = OUTPUT_PATH) -> Path:
    validate_artifact(feed)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
    return target


def refresh(*, fetcher=None, now: datetime | None = None, output_path: Path | str = OUTPUT_PATH) -> dict:
    try:
        results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        direct_feed = json.loads(DIRECT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        out = _empty("SOURCE_UNAVAILABLE", generated_at=stamp)
        write_artifact(out, output_path)
        return out
    out = build_artifact(results, direct_feed, fetcher=fetcher, now=now)
    write_artifact(out, output_path)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("refresh", "validate"))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args(argv)
    if args.command == "refresh":
        out = refresh(output_path=args.output)
    else:
        out = json.loads(Path(args.output).read_text(encoding="utf-8"))
        validate_artifact(out)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
