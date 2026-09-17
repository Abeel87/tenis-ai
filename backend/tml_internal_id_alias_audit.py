from __future__ import annotations

"""TASK 013: audit same-provider TennisMyLife player-ID alias evidence.

Diagnostic only. The audit never compares TennisMyLife IDs with Live Tennis API
IDs, never performs fuzzy matching, never changes the production identity
resolver, and never feeds discovered aliases into runtime/model history.

A candidate is considered only when the current runtime already resolves a
player name safely, that resolved TML name anchors exactly one player ID inside
one TML namespace before the fixture cutoff, and an alternate TML name carries
that same ID in that same namespace. ATP/CH/WTA are deliberately isolated.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from . import model
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
except ImportError:  # pragma: no cover
    import model
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "tml_internal_id_alias_audit.json"
VERSION = "task-013-tml-internal-id-alias-audit-v1"
MIN_MATCHES = 5


def _key(value: Any) -> str:
    return model._core._key(value)


def _id_token(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not pd.notna(value):
            return None
        return str(int(value)) if value.is_integer() else format(value, ".15g")
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _fixture_cases(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for match in results:
        if not isinstance(match, dict):
            continue
        for side in ("p1", "p2"):
            stats = match.get(f"{side}_stats") or {}
            try:
                matches = int(stats.get("matches") or 0)
            except (TypeError, ValueError):
                matches = 0
            if not 0 < matches < MIN_MATCHES:
                continue
            player = str(match.get(side) or "").strip()
            if not player:
                continue
            out.append({
                "match_id": match.get("id"),
                "scheduled_time": match.get("scheduled_time"),
                "side": side,
                "player": player,
                "requested_key": _key(player),
                "current_matches": matches,
                "identity_mode": str(stats.get("history_identity_mode") or "none"),
                "stored_history_player_key": stats.get("history_player_key"),
            })
    return out


def _cutoff(value: Any) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed.date())


def _match_uid(row: pd.Series) -> str:
    parts = [
        str(row.get("tourney_date") or "").strip(),
        str(row.get("tourney_name") or "").strip(),
        str(row.get("winner_name") or "").strip(),
        str(row.get("loser_name") or "").strip(),
        str(row.get("score") or "").strip(),
    ]
    return "|".join(parts)


def _participant_records(clean_history: pd.DataFrame) -> list[dict[str, Any]]:
    if clean_history is None or clean_history.empty:
        return []
    frame = model._core._dedupe_history(clean_history.copy())
    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        date = pd.to_datetime(str(row.get("tourney_date") or ""), format="%Y%m%d", errors="coerce")
        if pd.isna(date):
            continue
        namespace = str(row.get("source_tour") or "").strip().upper()
        if not namespace:
            continue
        uid = _match_uid(row)
        for side in ("winner", "loser"):
            name = str(row.get(f"{side}_name") or "").strip()
            player_id = _id_token(row.get(f"{side}_id"))
            if not name or player_id is None:
                continue
            records.append({
                "namespace": namespace,
                "player_id": player_id,
                "name": name,
                "name_key": _key(name),
                "date": pd.Timestamp(date.date()),
                "match_uid": uid,
                "tourney_name": str(row.get("tourney_name") or "").strip(),
                "score": str(row.get("score") or "").strip(),
            })
    return records


def _resolved_key(clean_long: pd.DataFrame, case: dict[str, Any]) -> tuple[str | None, str]:
    stored = case.get("stored_history_player_key")
    if isinstance(stored, str) and stored.strip():
        return stored.strip(), str(case.get("identity_mode") or "stored")
    return model._resolve_history_player_key(clean_long, case["player"])


def _audit_case(
    case: dict[str, Any],
    *,
    clean_long: pd.DataFrame,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    resolved_key, resolver_mode = _resolved_key(clean_long, case)
    cut = _cutoff(case.get("scheduled_time"))
    base = {
        **case,
        "resolved_key": resolved_key,
        "resolver_mode": resolver_mode,
        "cutoff_date": cut.isoformat() if cut is not None else None,
        "anchored_namespaces": [],
        "rejected_namespaces": [],
        "candidate_aliases": [],
        "net_new_candidate_matches": 0,
        "projected_matches_upper_bound": int(case["current_matches"]),
        "could_reach_minimum_5": False,
    }
    if not resolved_key or cut is None:
        return base

    pre = [r for r in records if r["date"] <= cut]
    namespaces = sorted({r["namespace"] for r in pre if r["name_key"] == resolved_key})
    baseline_uids = {r["match_uid"] for r in pre if r["name_key"] == resolved_key}
    candidate_uids: set[str] = set()
    aliases: dict[tuple[str, str, str], dict[str, Any]] = {}

    for namespace in namespaces:
        ns = [r for r in pre if r["namespace"] == namespace]
        anchor_ids = sorted({r["player_id"] for r in ns if r["name_key"] == resolved_key})
        if len(anchor_ids) != 1:
            base["rejected_namespaces"].append({
                "namespace": namespace,
                "reason": "anchor_name_maps_to_multiple_ids" if anchor_ids else "no_anchor_id",
                "anchor_ids": anchor_ids,
            })
            continue
        anchor_id = anchor_ids[0]
        id_rows = [r for r in ns if r["player_id"] == anchor_id]
        alias_keys = sorted({r["name_key"] for r in id_rows if r["name_key"] != resolved_key})

        rejected_aliases: list[dict[str, Any]] = []
        accepted_aliases: list[str] = []
        for alias_key in alias_keys:
            alias_ids = sorted({r["player_id"] for r in ns if r["name_key"] == alias_key})
            if alias_ids != [anchor_id]:
                rejected_aliases.append({
                    "alias_key": alias_key,
                    "reason": "alias_name_maps_to_multiple_ids",
                    "ids": alias_ids,
                })
                continue
            accepted_aliases.append(alias_key)
            rows = [r for r in id_rows if r["name_key"] == alias_key and r["match_uid"] not in baseline_uids]
            uids = sorted({r["match_uid"] for r in rows})
            candidate_uids.update(uids)
            display_names = sorted({r["name"] for r in rows})
            aliases[(namespace, anchor_id, alias_key)] = {
                "namespace": namespace,
                "anchor_id": anchor_id,
                "alias_key": alias_key,
                "display_names": display_names,
                "net_new_matches": len(uids),
                "example_match_uids": uids[:5],
            }

        base["anchored_namespaces"].append({
            "namespace": namespace,
            "anchor_id": anchor_id,
            "anchor_pre_match_rows": len({r["match_uid"] for r in ns if r["name_key"] == resolved_key}),
            "accepted_alias_keys": accepted_aliases,
            "rejected_aliases": rejected_aliases,
        })

    base["candidate_aliases"] = sorted(aliases.values(), key=lambda x: (x["namespace"], x["alias_key"]))
    base["net_new_candidate_matches"] = len(candidate_uids)
    base["projected_matches_upper_bound"] = int(case["current_matches"]) + len(candidate_uids)
    base["could_reach_minimum_5"] = base["projected_matches_upper_bound"] >= MIN_MATCHES
    return base


def build_report(
    raw_history: pd.DataFrame,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    cleaned, hygiene = clean_history(raw_history)
    clean_long = model.normalize_matches(cleaned)
    records = _participant_records(cleaned)
    cases = _fixture_cases(results)
    audited = [_audit_case(case, clean_long=clean_long, records=records) for case in cases]

    aliases = sum(len(row["candidate_aliases"]) for row in audited)
    net_new = sum(int(row["net_new_candidate_matches"]) for row in audited)
    reaching_slots = [row for row in audited if row["could_reach_minimum_5"]]
    reaching_players = sorted({row["player"] for row in reaching_slots})
    anchored_slots = sum(1 for row in audited if row["anchored_namespaces"])
    rejected = Counter(
        item["reason"]
        for row in audited
        for item in row["rejected_namespaces"]
    )

    id_columns = {
        "winner_id": bool(raw_history is not None and "winner_id" in raw_history.columns),
        "loser_id": bool(raw_history is not None and "loser_id" in raw_history.columns),
    }
    return {
        "version": VERSION,
        "policy": {
            "network_calls": 0,
            "provider_requests": 0,
            "production_cache_writes": 0,
            "fuzzy_matching": False,
            "manual_aliases": False,
            "cross_provider_id_comparison": False,
            "cross_tml_namespace_id_comparison": False,
            "tml_namespaces_isolated_by": "source_tour",
            "identity_anchor_requires_pre_cutoff_safe_runtime_name": True,
            "minimum_match_gate": MIN_MATCHES,
            "minimum_match_gate_changed": False,
            "identity_resolver_changed": False,
            "model_math_changed": False,
            "runtime_change_authorized": False,
            "discovered_aliases_authorized_for_runtime": False,
        },
        "source": {
            "raw_rows": int(len(raw_history)) if raw_history is not None else 0,
            "clean_rows": int(len(cleaned)) if cleaned is not None else 0,
            "hygiene_removed": int((hygiene or {}).get("removed_rows", 0)),
            "participant_records_with_tml_id": len(records),
            "id_columns_present": id_columns,
            "namespaces": sorted({r["namespace"] for r in records}),
        },
        "summary": {
            "visible_matches": len(results),
            "short_history_slots": len(cases),
            "short_history_players": len({case["player"] for case in cases}),
            "slots_with_safe_tml_id_anchor": anchored_slots,
            "candidate_alias_relations": aliases,
            "net_new_candidate_match_observations": net_new,
            "slots_reaching_minimum_5_upper_bound": len(reaching_slots),
            "players_reaching_minimum_5_upper_bound": len(reaching_players),
            "reaching_players": reaching_players,
            "rejected_namespace_reasons": dict(sorted(rejected.items())),
        },
        "decision": {
            "runtime_change": False,
            "authorize_aliases": False,
            "next_step": "Review only same-provider candidates with independent collision/coverage evidence before any resolver change.",
        },
        "cases": audited,
    }


def run(results_path: Path = DEFAULT_RESULTS, output_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    raw_history = load_cached_history()
    results = _read_json(results_path, [])
    if not isinstance(results, list):
        results = []
    report = build_report(raw_history, results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.results, args.output)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
