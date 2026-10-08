"""Read-only, prospective Superbet quote evidence archival (SHADOW research).

This is the owner of *archival evidence*, not the owner of market availability,
probabilities, quote production, betting execution, settlements or economics.
Each GitHub Actions run writes a unique, immutable run artifact. No history
is reconstructed from later/current odds.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "frontend" / "data"
VERSION = "self-evolution-quote-evidence-v1"
MAX_SOURCE_AGE_SECONDS = 7200
SOURCES = {
    "direct": DATA / "superbet_direct_current.json",
    "prepriced": DATA / "superbet_builder_quotes_current.json",
    "dynamic": DATA / "superbet_builder_dynamic_quotes_current.json",
}


def _time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(timezone.utc) if t.tzinfo else None


def _digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _id(value):
    return str(value).strip() if isinstance(value, (str, int)) and not isinstance(value, bool) else ""


def _price(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    f = float(value)
    return f if math.isfinite(f) and f > 1.0 else None


def _valid_observation(observed, scheduled, now):
    timestamp, kickoff = _time(observed), _time(scheduled)
    if timestamp is None or kickoff is None:
        return None
    if not timestamp < kickoff or timestamp > now:
        return None
    age = (now - timestamp).total_seconds()
    return timestamp.isoformat() if 0 <= age <= MAX_SOURCE_AGE_SECONDS else None


def build_snapshot(direct, prepriced, dynamic, *, now, run_id):
    now_utc = now.astimezone(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("UTC-aware archival timestamp required")
    if not _id(run_id):
        raise ValueError("Run id is mandatory")
    feeds = {"direct": direct, "prepriced": prepriced, "dynamic": dynamic}
    source_evidence = {}
    for name, doc in feeds.items():
        source_evidence[name] = {
            "sha256": _digest(doc) if isinstance(doc, dict) else None,
            "source_status": doc.get("status") if isinstance(doc, dict) else "UNAVAILABLE",
            "source_generated_at": doc.get("generated_at") if isinstance(doc, dict) else None,
        }
    reasons = Counter()
    rows = []
    unique = set()
    valid_matches = {}
    if isinstance(direct, dict) and direct.get("mode") == "SHADOW_SUPERBET_DIRECT_SELECTED_MATCH_FEED" and direct.get("status") == "OK" and direct.get("prices_used") is False:
        for match in direct.get("matches") or []:
            if not isinstance(match, dict):
                reasons["DIRECT_INVALID_ROW"] += 1
                continue
            mid, event = _id(match.get("match_id")), _id(match.get("event_id"))
            scheduled = match.get("scheduled_time")
            observed = match.get("observed_at") or direct.get("generated_at")
            if match.get("direct_match_verified") is not True or not mid or not event.isdigit() or not scheduled or not _valid_observation(observed, scheduled, now_utc):
                reasons["DIRECT_UNVERIFIED_IDENTITY_OR_ASOF"] += 1
                continue
            if mid in valid_matches:
                reasons["DUPLICATE_DIRECT_FIXTURE"] += 1
                valid_matches[mid] = None
                continue
            valid_matches[mid] = {
                "event_id": event, "scheduled_time": scheduled,
                "p1": match.get("p1"), "p2": match.get("p2"),
                "observed_at": observed,
            }
            for sel in match.get("canonical_selections") or []:
                if not isinstance(sel, dict):
                    reasons["DIRECT_INVALID_SELECTION"] += 1
                    continue
                price = _price(sel.get("operator_price"))
                selection_id = _id(sel.get("operator_selection_id"))
                market, pick = _id(sel.get("market")), _id(sel.get("pick"))
                if sel.get("operator_available") is not True or sel.get("operator_price_verified") is not True or price is None or not selection_id or not market or not pick or str(sel.get("operator_selection_status") or "").lower() != "active":
                    reasons["DIRECT_SELECTION_NOT_VERIFIED"] += 1
                    continue
                rows.append({
                    "kind": "SINGLE", "match_id": mid, "event_id": event,
                    "scheduled_time": scheduled, "quote_observed_at": _time(observed).isoformat(),
                    "source_sha256": source_evidence["direct"]["sha256"],
                    "operator_selection_id": selection_id,
                    "market": market, "pick": pick, "line": sel.get("line"),
                    "odds": price,
                })
    else:
        reasons["DIRECT_FEED_NOT_CURRENT_VERIFIED"] += 1
    # A later colliding direct fixture invalidates ALL rows from that app ID.
    # Never retain the first seen price from an ambiguous direct identity.
    invalid_direct = {mid for mid, fixture in valid_matches.items() if fixture is None}
    if invalid_direct:
        rows = [row for row in rows if row["match_id"] not in invalid_direct]
    for name, kind in (("prepriced", "BET_BUILDER_PREPRICED"), ("dynamic", "BET_BUILDER_DYNAMIC")):
        feed = feeds[name]
        if not isinstance(feed, dict) or feed.get("status") != "OK" or feed.get("prices_used") is not False or feed.get("synthetic_prices") is not False or feed.get("operator") != "superbet.pl":
            reasons[name.upper() + "_FEED_NOT_CURRENT_VERIFIED"] += 1
            continue
        expected_mode = ("SHADOW_SUPERBET_EXACT_BUILDER_QUOTE_FEED" if name == "prepriced" else "SHADOW_SUPERBET_DYNAMIC_BUILDER_QUOTE_FEED")
        if feed.get("mode") != expected_mode:
            reasons[name.upper() + "_BAD_MODE"] += 1
            continue
        for match in feed.get("matches") or []:
            if not isinstance(match, dict):
                reasons[name.upper() + "_INVALID_ROW"] += 1
                continue
            mid, event = _id(match.get("match_id")), _id(match.get("event_id"))
            fixture = valid_matches.get(mid)
            if not fixture or event != fixture["event_id"]:
                reasons[name.upper() + "_NO_EXACT_DIRECT_MATCH"] += 1
                continue
            quotes = (match.get("quotes") or []) if name == "prepriced" else [match.get("quote")]
            for quote in quotes:
                if not isinstance(quote, dict):
                    reasons[name.upper() + "_INVALID_QUOTE"] += 1
                    continue
                oid = _id(quote.get("operator_selection_id") if name == "prepriced" else quote.get("operator_combination_selection_id"))
                odds = _price(quote.get("combined_odds"))
                observed = quote.get("odds_timestamp")
                proof = _valid_observation(observed, fixture["scheduled_time"], now_utc)
                legs = quote.get("component_selection_ids")
                ids = [_id(x) for x in legs] if isinstance(legs, list) else []
                if (quote.get("operator_verified") is not True or quote.get("freshness_verified") is not True
                    or not proof or not oid or not odds or len(ids) < 2 or len(ids) > 6 or
                    any(not x for x in ids) or len(set(ids)) != len(ids)):
                    reasons[name.upper() + "_INCOMPLETE_PREMATCH_PROOF"] += 1
                    continue
                if name == "prepriced" and _id(quote.get("source_event_id")) != event:
                    reasons["PREPRICED_EVENT_CONFLICT"] += 1
                    continue
                if name == "dynamic" and _id(match.get("composition_id")) == "":
                    reasons["DYNAMIC_COMPOSITION_ID_MISSING"] += 1
                    continue
                rows.append({
                    "kind": kind, "match_id": mid, "event_id": event,
                    "scheduled_time": fixture["scheduled_time"],
                    "quote_observed_at": proof,
                    "source_sha256": source_evidence[name]["sha256"],
                    "operator_selection_id": oid, "component_selection_ids": ids,
                    "composition_id": match.get("composition_id") if name == "dynamic" else None,
                    "odds": odds,
                })
    # A conflicting operator selection cannot generate two independent samples.
    conflicted = set()
    for row in rows:
        key = (row["kind"], row["event_id"], row["operator_selection_id"])
        if key in unique:
            conflicted.add(key)
        unique.add(key)
    if conflicted:
        reasons["AMBIGUOUS_OPERATOR_SELECTION"] += len(conflicted)
        rows = [row for row in rows if (row["kind"], row["event_id"], row["operator_selection_id"]) not in conflicted]
    rows.sort(key=lambda x: (x["kind"], x["event_id"], x["operator_selection_id"]))
    evidence = {
        "schema_version": VERSION, "mode": "SHADOW_ONLY",
        "operator": "superbet.pl", "run_id": _id(run_id),
        "archived_at": now_utc.isoformat(),
        "source_evidence": source_evidence,
        "status": "CAPTURED_VERIFIED_PREMATCH_QUOTES" if rows else "NO_VERIFIED_PREMATCH_QUOTES",
        "observed_quotes": len(rows), "rejected_reasons": dict(sorted(reasons.items())),
        "rows": rows,
        "history_scope": "THIS_SINGLE_RUN_ONLY_NOT_RETROACTIVE",
        "durability": "ACTIONS_RUN_ARTIFACT_RETENTION_LIMITED",
        "join_to_frozen_prediction_ledger_verified": False,
        "economic_roi_evaluated": False,
        "model_probability_modified": False, "production_influence": False,
        "playable_influence": False, "symphony_influence": False,
        "ineed_influence": False, "real_betting_enabled": False,
        "new_requests": 0,
    }
    evidence["evidence_sha256"] = _digest(evidence)
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    def read(path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    report = build_snapshot(*(read(SOURCES[k]) for k in ("direct", "prepriced", "dynamic")),
                            now=datetime.now(timezone.utc), run_id=args.run_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(args.output)
    print(json.dumps({"status": report["status"], "observed_quotes": report["observed_quotes"],
                      "rejections": report["rejected_reasons"]}))


if __name__ == "__main__":
    main()
