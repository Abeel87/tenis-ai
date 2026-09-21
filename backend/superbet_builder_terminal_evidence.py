from __future__ import annotations

"""Read-only exact Superbet Bet Builder terminal-evidence probe.

This module is an evidence collector, not a settlement engine. It follows a
small frozen manifest of exact event/combination/component identities through
match completion and records only operator-provided objects that contain those
exact identities. It never scores legs, maps operator result codes to outcomes,
computes payout, touches iNeed$/Supabase, or enables real betting.
"""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

try:
    from . import superbet_direct as direct
except ImportError:
    import superbet_direct as direct

MODE = "SHADOW_SUPERBET_BUILDER_TERMINAL_EVIDENCE"
MANIFEST_SCHEMA = "logic12-builder-terminal-evidence-manifest-v1"
EVIDENCE_SCHEMA = "logic12-builder-terminal-evidence-v1"
ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "audits" / "logic12_builder_terminal_evidence_manifest.json"
OUTPUT_PATH = ROOT / "frontend" / "data" / "superbet_builder_terminal_evidence.json"
MAX_CANDIDATES = 3
MAX_HITS_PER_TOKEN = 16


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


def validate_manifest(manifest: object) -> dict:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError("invalid terminal-evidence manifest")
    if manifest.get("status") != "FROZEN" or manifest.get("operator") != "superbet.pl" or manifest.get("market_id") != 238733:
        raise ValueError("invalid terminal-evidence manifest authority")
    for key in ("settlement_enabled", "production_influence", "ineed_runtime_influence", "automatic_real_betting"):
        if manifest.get(key) is not False:
            raise ValueError(f"manifest must keep {key}=false")
    if manifest.get("result_inference_allowed") not in (None, False):
        raise ValueError("result inference must remain disabled")
    if not _text(manifest.get("source_commit_sha")) or not _text(manifest.get("source_blob_sha")):
        raise ValueError("frozen source identity missing")
    rows = manifest.get("candidates")
    if not isinstance(rows, list) or not rows or len(rows) > MAX_CANDIDATES:
        raise ValueError("invalid terminal-evidence candidate count")
    seen_events: set[str] = set()
    seen_selections: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid terminal-evidence candidate")
        event_id = _text(row.get("event_id"))
        selection_id = _text(row.get("operator_selection_id"))
        components = [_text(x) for x in (row.get("component_selection_ids") or [])]
        start = _parse_utc(row.get("scheduled_time"))
        probe_from = _parse_utc(row.get("probe_from"))
        probe_until = _parse_utc(row.get("probe_until"))
        if not event_id.isdigit() or not selection_id or event_id in seen_events or selection_id in seen_selections:
            raise ValueError("duplicate/invalid frozen identity")
        if not _text(row.get("p1")) or not _text(row.get("p2")) or row.get("match_id") is None:
            raise ValueError("frozen fixture identity missing")
        if len(components) < 2 or any(not x for x in components) or len(set(components)) != len(components):
            raise ValueError("frozen component identity invalid")
        if start is None or probe_from is None or probe_until is None or probe_from != start or probe_until <= probe_from:
            raise ValueError("invalid bounded probe window")
        seen_events.add(event_id); seen_selections.add(selection_id)
    return manifest


def _scalar_equals(value, token: str) -> bool:
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value) == token
    return False


def _exact_object_hits(node: object, token: str, *, path: str = "$", limit: int = MAX_HITS_PER_TOKEN) -> list[dict]:
    """Return raw dict objects containing token exactly; never interpret values."""
    hits: list[dict] = []

    def walk(value: object, here: str) -> None:
        if len(hits) >= limit:
            return
        if isinstance(value, dict):
            immediate = any(_scalar_equals(v, token) for v in value.values())
            immediate = immediate or any(
                isinstance(v, list) and any(_scalar_equals(x, token) for x in v)
                for v in value.values()
            )
            if immediate:
                hits.append({"path": here, "object": deepcopy(value)})
                if len(hits) >= limit:
                    return
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    walk(child, f"{here}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                if isinstance(child, (dict, list)):
                    walk(child, f"{here}[{index}]")

    walk(node, path)
    return hits


def _event_finished(raw_state: object) -> bool:
    if isinstance(raw_state, dict):
        values = [_text(v).casefold() for v in raw_state.values() if _text(v)]
        return bool(values) and all(v == "finished" for v in values)
    return _text(raw_state).casefold() == "finished"


def _exact_offer_row(event_row: dict, candidate: dict) -> dict | None:
    wanted_selection = _text(candidate.get("operator_selection_id"))
    wanted_components = {_text(x) for x in candidate.get("component_selection_ids") or []}
    hits = []
    for odd in event_row.get("odds") or []:
        if not isinstance(odd, dict) or _text(odd.get("uuid")) != wanted_selection:
            continue
        components = odd.get("oddComponents") if isinstance(odd.get("oddComponents"), list) else []
        ids = {_text(x.get("UUID")) for x in components if isinstance(x, dict) and _text(x.get("UUID"))}
        if ids == wanted_components and len(ids) == len(wanted_components):
            hits.append(deepcopy(odd))
    return hits[0] if len(hits) == 1 else None


def _base_row(candidate: dict) -> dict:
    return {
        "match_id": candidate.get("match_id"),
        "event_id": _text(candidate.get("event_id")),
        "scheduled_time": candidate.get("scheduled_time"),
        "probe_from": candidate.get("probe_from"),
        "probe_until": candidate.get("probe_until"),
        "p1": candidate.get("p1"),
        "p2": candidate.get("p2"),
        "operator_selection_id": _text(candidate.get("operator_selection_id")),
        "component_selection_ids": list(candidate.get("component_selection_ids") or []),
        "combined_odds": candidate.get("combined_odds"),
        "event_identity_verified": False,
        "event_offer_state_status": None,
        "exact_combination_offer_present": False,
        "exact_combination_offer": None,
        "exact_combination_result_hits": [],
        "component_result_hits": {str(x): [] for x in candidate.get("component_selection_ids") or []},
        "raw_match_results": None,
        "odds_results_count": None,
        "evidence_status": "N/D",
        "settlement_result": None,
        "payout": None,
        "result_inferred": False,
        "automatic_real_betting": False,
    }


def _previous_exact_hit(previous: object, candidate: dict) -> dict | None:
    if not isinstance(previous, dict):
        return None
    for row in previous.get("candidates") or []:
        if not isinstance(row, dict):
            continue
        if _text(row.get("event_id")) != _text(candidate.get("event_id")):
            continue
        if _text(row.get("operator_selection_id")) != _text(candidate.get("operator_selection_id")):
            continue
        if row.get("evidence_status") == "EXACT_OPERATOR_IDENTITY_HIT" and row.get("exact_combination_result_hits"):
            preserved = deepcopy(row)
            preserved["evidence_status"] = "EXACT_OPERATOR_IDENTITY_HIT"
            preserved["preserved_from_previous"] = True
            preserved["settlement_result"] = None
            preserved["payout"] = None
            preserved["result_inferred"] = False
            return preserved
    return None


def _verify_event_identity(candidate: dict, event_row: dict) -> bool:
    if _text(event_row.get("eventId")) != _text(candidate.get("event_id")):
        return False
    p1, p2 = direct._players_from_event(event_row)
    observed = {
        "fixture_id": _text(event_row.get("eventId")),
        "event_id": _text(event_row.get("eventId")),
        "p1": p1,
        "p2": p2,
        "start_time": event_row.get("utcDate"),
    }
    selected = direct.fixture_matching.select_cached_fixture(candidate, [observed])
    return isinstance(selected, dict) and _text(selected.get("fixture_id")) == _text(candidate.get("event_id"))


def build_evidence(manifest: object, *, previous: object = None, fetcher=None, now: datetime | None = None) -> dict:
    frozen = validate_manifest(manifest)
    stamp_dt = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamp = stamp_dt.isoformat()
    event_fetch = fetcher or direct.fetch_event_payload_public
    rows: list[dict] = []
    requests = 0

    for candidate in frozen["candidates"]:
        row = _base_row(candidate)
        preserved = _previous_exact_hit(previous, candidate)
        if preserved is not None:
            rows.append(preserved)
            continue
        probe_from = _parse_utc(candidate.get("probe_from"))
        probe_until = _parse_utc(candidate.get("probe_until"))
        if stamp_dt < probe_from:
            row["evidence_status"] = "NOT_PROBE_WINDOW"
            rows.append(row); continue
        if stamp_dt > probe_until:
            row["evidence_status"] = "PROBE_WINDOW_EXPIRED"
            rows.append(row); continue
        try:
            requests += 1
            payload = event_fetch(_text(candidate.get("event_id")))
            event_row = direct._event_record(payload, _text(candidate.get("event_id")))
        except Exception as exc:
            row["evidence_status"] = "SOURCE_UNAVAILABLE"
            row["source_error"] = type(exc).__name__
            rows.append(row); continue
        if not isinstance(event_row, dict) or not _verify_event_identity(candidate, event_row):
            row["evidence_status"] = "EVENT_IDENTITY_MISMATCH"
            rows.append(row); continue

        row["event_identity_verified"] = True
        row["event_offer_state_status"] = deepcopy(event_row.get("offerStateStatus"))
        offer = _exact_offer_row(event_row, candidate)
        row["exact_combination_offer_present"] = offer is not None
        row["exact_combination_offer"] = offer
        result_sources = {
            "oddsResults": event_row.get("oddsResults"),
            "matchResults": event_row.get("matchResults"),
        }
        combo_token = _text(candidate.get("operator_selection_id"))
        combo_hits: list[dict] = []
        for key, source in result_sources.items():
            for hit in _exact_object_hits(source, combo_token, path=f"$.{key}"):
                combo_hits.append(hit)
        row["exact_combination_result_hits"] = combo_hits[:MAX_HITS_PER_TOKEN]
        for component in candidate.get("component_selection_ids") or []:
            token = _text(component)
            hits: list[dict] = []
            for key, source in result_sources.items():
                hits.extend(_exact_object_hits(source, token, path=f"$.{key}"))
            row["component_result_hits"][token] = hits[:MAX_HITS_PER_TOKEN]
        row["raw_match_results"] = deepcopy(event_row.get("matchResults"))
        odds_results = event_row.get("oddsResults")
        row["odds_results_count"] = len(odds_results) if isinstance(odds_results, list) else None
        if row["exact_combination_result_hits"]:
            row["evidence_status"] = "EXACT_OPERATOR_IDENTITY_HIT"
        elif _event_finished(event_row.get("offerStateStatus")):
            row["evidence_status"] = "EVENT_FINISHED_NO_EXACT_RESULT_EVIDENCE"
        else:
            row["evidence_status"] = "NO_EXACT_RESULT_EVIDENCE"
        rows.append(row)

    out = {
        "schema_version": EVIDENCE_SCHEMA,
        "mode": MODE,
        "status": "OK",
        "generated_at": stamp,
        "operator": "superbet.pl",
        "market_id": 238733,
        "manifest_source_commit_sha": frozen.get("source_commit_sha"),
        "manifest_source_blob_sha": frozen.get("source_blob_sha"),
        "selection_policy": frozen.get("selection_policy"),
        "candidates": rows,
        "candidate_count": len(rows),
        "external_requests": requests,
        "settlement_enabled": False,
        "settlement_result_available": False,
        "payout_computed": False,
        "result_inferred": False,
        "production_influence": False,
        "playable_influence": False,
        "symphony_influence": False,
        "ineed_runtime_influence": False,
        "automatic_real_betting": False,
    }
    return validate_evidence(out)


def validate_evidence(feed: object) -> dict:
    if not isinstance(feed, dict) or feed.get("schema_version") != EVIDENCE_SCHEMA or feed.get("mode") != MODE:
        raise ValueError("invalid terminal-evidence artifact")
    for key in (
        "settlement_enabled", "settlement_result_available", "payout_computed", "result_inferred",
        "production_influence", "playable_influence", "symphony_influence", "ineed_runtime_influence",
        "automatic_real_betting",
    ):
        if feed.get(key) is not False:
            raise ValueError(f"terminal evidence must keep {key}=false")
    rows = feed.get("candidates")
    if not isinstance(rows, list) or len(rows) != int(feed.get("candidate_count") or 0) or len(rows) > MAX_CANDIDATES:
        raise ValueError("terminal-evidence candidate count mismatch")
    if int(feed.get("external_requests") or 0) < 0 or int(feed.get("external_requests") or 0) > len(rows):
        raise ValueError("terminal-evidence request bound exceeded")
    for row in rows:
        if not isinstance(row, dict) or row.get("settlement_result") is not None or row.get("payout") is not None:
            raise ValueError("terminal evidence cannot contain settlement/payout")
        if row.get("result_inferred") is not False or row.get("automatic_real_betting") is not False:
            raise ValueError("terminal evidence cannot infer result or enable real betting")
    return feed


def write_evidence(feed: dict, path: Path | str = OUTPUT_PATH) -> Path:
    validate_evidence(feed)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
    return target


def refresh(*, manifest_path: Path | str = MANIFEST_PATH, output_path: Path | str = OUTPUT_PATH, fetcher=None, now: datetime | None = None) -> dict:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    target = Path(output_path)
    previous = None
    if target.exists():
        try:
            previous = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            previous = None
    feed = build_evidence(manifest, previous=previous, fetcher=fetcher, now=now)
    path = write_evidence(feed, target)
    return {
        "status": feed.get("status"),
        "written": True,
        "path": str(path),
        "candidate_count": feed.get("candidate_count"),
        "external_requests": feed.get("external_requests"),
        "exact_identity_hits": sum(1 for row in feed.get("candidates") or [] if row.get("evidence_status") == "EXACT_OPERATOR_IDENTITY_HIT"),
        "settlement_enabled": False,
        "result_inferred": False,
        "automatic_real_betting": False,
    }


def main() -> None:
    mode = _text(sys.argv[1] if len(sys.argv) > 1 else "refresh").casefold()
    if mode != "refresh":
        raise SystemExit("usage: superbet_builder_terminal_evidence.py refresh")
    print(json.dumps(refresh(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
