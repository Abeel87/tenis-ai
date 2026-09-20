from __future__ import annotations

"""Exact downstream selection evidence for the prospective prediction ledger.

This module is deliberately SHADOW-only and additive. It never mutates the
immutable pre-selection ledger and is not a production/runtime/learning owner.
Positive facts are emitted only from exact identities with proven pre-match
chronology. Missing or ambiguous evidence stays N/D rather than being inferred
as a negative selection fact.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from . import prediction_ledger_shadow
    from . import superbet_playable
    from . import symphony2_tracker
except ImportError:
    import prediction_ledger_shadow
    import superbet_playable
    import symphony2_tracker

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"
LEDGER = DATA / "prediction_ledger_shadow.json"
BASE_HISTORY = DATA / "history.json"
SYMPHONY_HISTORY = DATA / "symphony2_history.json"
OUT = DATA / "prediction_ledger_selection_shadow.json"

SCHEMA_VERSION = "prediction-ledger-selection-shadow-v1"
MODE = "SHADOW_ONLY"


def _read(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _score_token(value: Any) -> str | None:
    match = re.fullmatch(r"\s*(\d+)\s*[:\-]\s*(\d+)\s*", str(value or ""))
    if not match:
        return None
    return f"{int(match.group(1))}:{int(match.group(2))}"


def _ledger_signal(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    market = str(row.get("market") or "").strip()
    pick = row.get("pick")
    if not market or pick is None:
        return None, "MISSING_LEDGER_SELECTION_DIMENSION"

    signal: dict[str, Any] = {
        "market": market,
        "pick": pick,
        "line": row.get("line"),
        "checkpoint": None,
        "player": row.get("player"),
    }

    canonical_market = superbet_playable.signal_signature(signal)[0]
    if canonical_market == "game_state":
        candidate = str(row.get("candidate_key") or "")
        parsed = re.fullmatch(r"state\|(\d+)\|(.+)", candidate)
        if not parsed:
            return None, "MALFORMED_GAME_STATE_CANDIDATE"
        checkpoint = int(parsed.group(1))
        candidate_score = _score_token(parsed.group(2))
        pick_score = _score_token(pick)
        if candidate_score is None or pick_score is None or candidate_score != pick_score:
            return None, "GAME_STATE_SCORE_CONFLICT"
        signal["checkpoint"] = checkpoint

    return signal, None


def _ledger_is_prematch(row: dict[str, Any]) -> bool:
    captured = _parse_dt(row.get("captured_at"))
    scheduled = _parse_dt(row.get("scheduled_time"))
    return bool(captured and scheduled and captured < scheduled)


def _playable_indices(history: list[dict[str, Any]]) -> tuple[dict[tuple, list[dict]], set[tuple]]:
    valid: dict[tuple, list[dict]] = {}
    invalid_chronology: set[tuple] = set()
    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        match_key = superbet_playable._match_key(entry)
        captured = _parse_dt(entry.get("playable_captured_at_v912"))
        scheduled = _parse_dt(entry.get("scheduled_time"))
        chronology_ok = bool(captured and scheduled and captured < scheduled)
        for signal in entry.get("playable_autolearn_signals_v912") or []:
            if not isinstance(signal, dict):
                continue
            key = (match_key, superbet_playable.signal_signature(signal))
            if not chronology_ok:
                invalid_chronology.add(key)
                continue
            valid.setdefault(key, []).append({
                "owner": "superbet_playable",
                "owner_version": superbet_playable.VERSION,
                "captured_at": captured.isoformat() if captured else None,
                "scheduled_time": scheduled.isoformat() if scheduled else None,
                "signal_key": signal.get("key"),
                "signature": list(superbet_playable.signal_signature(signal)),
            })
    return valid, invalid_chronology


def _symphony_indices(history_doc: dict[str, Any]) -> tuple[dict[tuple, list[dict]], set[tuple]]:
    valid: dict[tuple, list[dict]] = {}
    invalid_chronology: set[tuple] = set()
    entries = history_doc.get("entries") if isinstance(history_doc, dict) else []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        mid = str(entry.get("match_id") or "").strip()
        if not mid:
            continue
        match_key = f"id:{mid}"
        captured = _parse_dt(entry.get("captured_at"))
        scheduled = _parse_dt(entry.get("scheduled_time"))
        chronology_ok = bool(captured and scheduled and captured < scheduled)
        prediction_id = str(entry.get("prediction_id") or "").strip()
        for leg in entry.get("selection") or []:
            if not isinstance(leg, dict):
                continue
            key = (match_key, symphony2_tracker.selection_signature(mid, leg))
            if not chronology_ok:
                invalid_chronology.add(key)
                continue
            valid.setdefault(key, []).append({
                "owner": "symphony2_tracker",
                "owner_version": entry.get("version") or symphony2_tracker.VERSION,
                "composition_prediction_id": prediction_id or None,
                "captured_at": captured.isoformat() if captured else None,
                "scheduled_time": scheduled.isoformat() if scheduled else None,
                "selection_id": leg.get("selection_id"),
                "signature": list(symphony2_tracker.selection_signature(mid, leg)),
            })
    return valid, invalid_chronology


def _nd(reason: str, owner: str) -> dict[str, Any]:
    return {"value": None, "status": "N/D", "reason": reason, "owner": owner}


def _playable_fact(
    row: dict[str, Any],
    signal: dict[str, Any],
    valid: dict[tuple, list[dict]],
    invalid_chronology: set[tuple],
) -> dict[str, Any]:
    key = (str(row.get("match_key") or ""), superbet_playable.signal_signature(signal))
    matches = valid.get(key) or []
    if len(matches) == 1:
        return {"value": True, "status": "MATCHED", **matches[0]}
    if len(matches) > 1:
        return {
            "value": None,
            "status": "N/D",
            "reason": "AMBIGUOUS_EXACT_PREMATCH_EVIDENCE",
            "owner": "superbet_playable",
            "matching_evidence_count": len(matches),
        }
    if key in invalid_chronology:
        return _nd("EXACT_EVIDENCE_WITHOUT_VALID_PREMATCH_CHRONOLOGY", "superbet_playable")
    return _nd("NO_EXACT_PREMATCH_EVIDENCE", "superbet_playable")


def _symphony_fact(
    row: dict[str, Any],
    signal: dict[str, Any],
    valid: dict[tuple, list[dict]],
    invalid_chronology: set[tuple],
) -> dict[str, Any]:
    match_key = str(row.get("match_key") or "")
    if not match_key.startswith("id:") or not match_key[3:]:
        return _nd("LEDGER_MATCH_ID_NOT_EXACT_NUMERIC_NAMESPACE_KEY", "symphony2_tracker")
    mid = match_key[3:]
    key = (match_key, symphony2_tracker.selection_signature(mid, signal))
    matches = valid.get(key) or []
    if len(matches) == 1:
        return {"value": True, "status": "MATCHED", **matches[0]}
    if len(matches) > 1:
        return {
            "value": None,
            "status": "N/D",
            "reason": "AMBIGUOUS_EXACT_PREMATCH_COMPOSITION_EVIDENCE",
            "owner": "symphony2_tracker",
            "matching_evidence_count": len(matches),
            "composition_prediction_ids": sorted({
                str(item.get("composition_prediction_id") or "")
                for item in matches if item.get("composition_prediction_id")
            }),
        }
    if key in invalid_chronology:
        return _nd("EXACT_EVIDENCE_WITHOUT_VALID_PREMATCH_CHRONOLOGY", "symphony2_tracker")
    return _nd("NO_EXACT_PREMATCH_EVIDENCE", "symphony2_tracker")


def build_sidecar(
    ledger_doc: dict[str, Any],
    base_history: list[dict[str, Any]],
    symphony_history: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    if not isinstance(ledger_doc, dict) or ledger_doc.get("schema_version") != prediction_ledger_shadow.SCHEMA_VERSION:
        raise ValueError("prediction ledger schema mismatch")
    rows = ledger_doc.get("rows")
    if not isinstance(rows, list):
        raise ValueError("prediction ledger rows must be a list")

    playable_valid, playable_invalid = _playable_indices(base_history)
    symphony_valid, symphony_invalid = _symphony_indices(symphony_history)
    out_rows: list[dict[str, Any]] = []

    for raw in rows:
        if not isinstance(raw, dict):
            continue
        base = {
            "prediction_id": raw.get("prediction_id"),
            "match_key": raw.get("match_key"),
            "candidate_key": raw.get("candidate_key"),
            "scheduled_time": raw.get("scheduled_time"),
            "ledger_captured_at": raw.get("captured_at"),
            "ledger_pre_match_valid": _ledger_is_prematch(raw),
        }
        signal, signal_error = _ledger_signal(raw)
        if not base["ledger_pre_match_valid"]:
            facts = {
                "playable": _nd("LEDGER_NOT_VALID_PREMATCH_EVIDENCE", "superbet_playable"),
                "symphony_selected": _nd("LEDGER_NOT_VALID_PREMATCH_EVIDENCE", "symphony2_tracker"),
                "ineed_selected": _nd("NO_LOCAL_PROSPECTIVE_OWNER_IN_BUILD", "ineed_shadow"),
            }
        elif signal is None:
            reason = signal_error or "INVALID_LEDGER_SELECTION_IDENTITY"
            facts = {
                "playable": _nd(reason, "superbet_playable"),
                "symphony_selected": _nd(reason, "symphony2_tracker"),
                "ineed_selected": _nd("NO_LOCAL_PROSPECTIVE_OWNER_IN_BUILD", "ineed_shadow"),
            }
        else:
            facts = {
                "playable": _playable_fact(raw, signal, playable_valid, playable_invalid),
                "symphony_selected": _symphony_fact(raw, signal, symphony_valid, symphony_invalid),
                "ineed_selected": _nd("NO_LOCAL_PROSPECTIVE_OWNER_IN_BUILD", "ineed_shadow"),
            }
        out_rows.append({**base, "facts": facts})

    model_common = {
        str(row.get("prediction_id"))
        for row in rows
        if isinstance(row, dict) and all(
            (((row.get("model_scores") or {}).get(name) or {}).get("available") is True)
            for name in ("current", "catboost", "tabpfn")
        )
    }
    playable_ids = {
        str(row.get("prediction_id")) for row in out_rows
        if ((row.get("facts") or {}).get("playable") or {}).get("value") is True
    }
    symphony_ids = {
        str(row.get("prediction_id")) for row in out_rows
        if ((row.get("facts") or {}).get("symphony_selected") or {}).get("value") is True
    }

    parsed_now = _parse_dt(now)
    if parsed_now is None:
        raise ValueError("generation time must be valid")
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "generated_at": parsed_now.isoformat(),
        "source_ledger_schema_version": ledger_doc.get("schema_version"),
        "source_ledger_sha256": _canonical_sha256(ledger_doc),
        "join_contract": "EXACT_IDENTITY_AND_STRICT_PREMATCH_CHRONOLOGY",
        "absence_semantics": "N/D_NOT_FALSE",
        "rows": out_rows,
        "summary": {
            "rows": len(out_rows),
            "population_counts": {
                "ALL": len(out_rows),
                "PLAYABLE": len(playable_ids),
                "GENERATOR_SELECTED": None,
                "SYMPHONY_SELECTED": len(symphony_ids),
                "INEED_SELECTED": None,
            },
            "common_current_catboost_tabpfn": len(model_common),
            "common_with_playable": len(model_common & playable_ids),
            "common_with_symphony": len(model_common & symphony_ids),
            "common_with_playable_and_symphony": len(model_common & playable_ids & symphony_ids),
        },
        "ineed_contract": {
            "status": "N/D",
            "reason": "NO_LOCAL_PROSPECTIVE_OWNER_IN_BUILD",
            "network_fetch_enabled": False,
            "historical_backfill_enabled": False,
            "required_future_chronology": "placement_snapshot.timestamp < exact_joined scheduled_time",
        },
        "production_influence": False,
        "runtime_gating_enabled": False,
        "learning_consumer_enabled": False,
        "telemetry_consumer_enabled": False,
        "auto_promote": False,
    }


def main() -> int:
    ledger_doc = _read(LEDGER, {})
    base_history = _read(BASE_HISTORY, [])
    symphony_history = _read(SYMPHONY_HISTORY, {})
    doc = build_sidecar(
        ledger_doc,
        base_history if isinstance(base_history, list) else [],
        symphony_history if isinstance(symphony_history, dict) else {},
        now=datetime.now(timezone.utc),
    )
    _write(OUT, doc)
    print(json.dumps(doc.get("summary") or {}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
