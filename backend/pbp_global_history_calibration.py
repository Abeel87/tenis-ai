from __future__ import annotations

"""TASK 009: global zero-network calibration of PBP -> normalized history.

This is audit-only. It scans existing local PBP and TennisMyLife caches, finds
only deterministic cross-source duplicate matches using TASK 007 rules, and
checks whether a conservative PBP projection reproduces the normalized fields
already consumed by Current Engine.

No PBP row is added to model history and no production/model rule is changed.
"""

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from . import model
    from . import pbp_enrich as pbp
    from . import pbp_history_schema_audit as task008
    from . import pbp_tml_dedup_audit as task007
    from .canonical_point_event import canonical_point_events
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
    from . import player_dna_pbp_service_split_readiness as split
    from .player_identity import player_identity_map
except ImportError:  # pragma: no cover
    import model
    import pbp_enrich as pbp
    import pbp_history_schema_audit as task008
    import pbp_tml_dedup_audit as task007
    from canonical_point_event import canonical_point_events
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history
    import player_dna_pbp_service_split_readiness as split
    from player_identity import player_identity_map

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = ROOT / "data" / "cache"
DEFAULT_PBP_ROOT = DEFAULT_CACHE_ROOT / "pbp_v7"
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "pbp_global_history_calibration.json"
VERSION = "task-009-pbp-global-history-calibration-v1"

RATE_TOLERANCE = 0.02
MIN_FULL_DUPLICATE_PLAYER_ROWS = 20
MIN_PER_FIELD_AGREEMENT_RATE = 0.97
REQUIRED_FIELDS = (*task008.CORE_MODEL_FIELDS, *task008.AUX_MODEL_FIELDS)


def _parse_profile_time(value: Any) -> datetime:
    parsed = split._parse_utc(value)
    return parsed or datetime.min.replace(tzinfo=timezone.utc)


def _terminal_profile_candidates(payload: dict[str, Any]) -> list[tuple[int, datetime, int, dict[str, Any]]]:
    final_score = split._final_tape_score(payload)
    profiles = payload.get("profiles")
    if final_score is None or not isinstance(profiles, list):
        return []
    out = []
    for index, profile in enumerate(profiles):
        if not isinstance(profile, dict):
            continue
        state = profile.get("input_state") if isinstance(profile.get("input_state"), dict) else {}
        stats = state.get("stats") if isinstance(state.get("stats"), dict) else None
        if not isinstance(stats, dict) or split._score_core(state.get("score")) != final_score:
            continue
        slots = 0
        for side in ("p1", "p2"):
            raw = stats.get(side) if isinstance(stats.get(side), dict) else {}
            for field in split.SPLIT_FIELDS:
                slots += int(split._ratio_counts(raw.get(split.RAW_KEYS[field])) is not None)
        out.append((slots, _parse_profile_time(profile.get("created_at")), index, profile))
    return out


def best_terminal_stats(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Choose one terminal snapshot; never merge fields across snapshots."""
    candidates = _terminal_profile_candidates(payload)
    if not candidates:
        return None, {"terminal_profiles": 0, "best_raw_split_slots": 0}
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    slots, created, index, profile = candidates[-1]
    state = profile.get("input_state") if isinstance(profile.get("input_state"), dict) else {}
    stats = state.get("stats") if isinstance(state.get("stats"), dict) else None
    return stats if isinstance(stats, dict) else None, {
        "terminal_profiles": len(candidates),
        "best_raw_split_slots": slots,
        "selected_profile_index": index,
        "selected_profile_created_at": profile.get("created_at"),
        "selection_rule": "max_raw_split_slots_then_latest_terminal_profile",
        "cross_profile_field_merge": False,
    }


def boundary_game_metrics(
    payload: dict[str, Any],
    score: tuple[tuple[int, int], ...],
    *,
    match_id: Any = None,
) -> dict[str, Any]:
    """Derive game outcomes without requiring every intervening point to be atomic.

    For hold/break, only the completed game's server and winner are needed.  The
    canonical event module already resolves the completed-point server from the
    previous provider row at game boundaries.  We still fail closed unless the
    number of observed non-tiebreak game boundaries equals the terminal score's
    expected non-tiebreak games.
    """
    events = canonical_point_events(payload, match_id=match_id)
    expected = task008._expected_non_tiebreak_games(score)
    service_games = {1: 0, 2: 0}
    holds = {1: 0, 2: 0}
    breaks = {1: 0, 2: 0}
    boundary_events = observed = atomic = 0

    for event in events:
        if event.get("transition_kind") not in {"game_score_changed", "set_score_changed"}:
            continue
        if event.get("is_tiebreak_before") or event.get("is_tiebreak_after"):
            continue
        boundary_events += 1
        quality = event.get("quality") if isinstance(event.get("quality"), dict) else {}
        atomic += int(quality.get("atomic_transition") is True)
        server = event.get("server")
        winner = event.get("point_winner")
        if server not in (1, 2) or winner not in (1, 2):
            continue
        observed += 1
        service_games[server] += 1
        if winner == server:
            holds[server] += 1
        else:
            breaks[winner] += 1

    complete = expected > 0 and observed == expected and boundary_events == expected
    result: dict[str, Any] = {
        "expected_non_tiebreak_games": expected,
        "boundary_events": boundary_events,
        "boundary_events_with_server_and_winner": observed,
        "atomic_boundary_events": atomic,
        "complete_observed_game_boundaries": complete,
    }
    for side in (1, 2):
        opponent = 3 - side
        result[f"p{side}_service_games"] = service_games[side]
        result[f"p{side}_holds"] = holds[side]
        result[f"p{side}_breaks"] = breaks[side]
        result[f"p{side}_hold_rate"] = task008._ratio(holds[side], service_games[side]) if complete else None
        result[f"p{side}_break_rate"] = task008._ratio(breaks[side], service_games[opponent]) if complete else None
    return result


def project_payload_relaxed(payload: dict[str, Any], match_id: Any = None) -> dict[str, Any]:
    identities = player_identity_map(payload)
    match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
    score = task007._pbp_score(payload)
    scheduled = task007._parse_dt(match.get("scheduled_time"))
    surface = task007._surface(match.get("surface"))
    stats, profile_evidence = best_terminal_stats(payload)
    if identities is None or not score or scheduled is None or stats is None:
        return {
            "ready": False,
            "reason": "missing_identity_score_time_or_terminal_stats",
            "profile_evidence": profile_evidence,
            "rows": {},
        }

    game = boundary_game_metrics(payload, score, match_id=match_id or match.get("id"))
    winner = match.get("winner")
    if winner not in (1, 2):
        p1_sets = sum(1 for a, b in score if a > b)
        p2_sets = sum(1 for a, b in score if b > a)
        winner = 1 if p1_sets > p2_sets else (2 if p2_sets > p1_sets else None)

    rows: dict[str, dict[str, Any]] = {}
    for side in (1, 2):
        identity = identities[side]
        key = task007._key(identity.get("name"))
        split_metrics = task008._service_split_metrics(stats, f"p{side}")
        row = {
            "player": identity.get("name"),
            "player_key": key,
            "opponent": identities[3 - side].get("name"),
            "opponent_key": task007._key(identities[3 - side].get("name")),
            "date": scheduled.date().isoformat(),
            "surface": surface,
            "won": int(winner == side) if winner in (1, 2) else None,
            "hold_rate": game.get(f"p{side}_hold_rate"),
            "break_rate": game.get(f"p{side}_break_rate"),
            "serve_points_won": split_metrics.get("serve_points_won"),
            "return_points_won": split_metrics.get("return_points_won"),
            "first_serve_won": split_metrics.get("first_serve_won"),
            "second_serve_won": split_metrics.get("second_serve_won"),
            **task008._set_features(score, side),
        }
        row["core_fields_ready"] = all(row.get(field) is not None for field in task008.CORE_MODEL_FIELDS)
        row["aux_fields_ready"] = all(row.get(field) is not None for field in task008.AUX_MODEL_FIELDS)
        rows[key] = row

    ready = len(rows) == 2 and all(row["core_fields_ready"] and row["aux_fields_ready"] for row in rows.values())
    return {
        "ready": ready,
        "reason": "projection_ready" if ready else "partial_normalized_history_fields",
        "match_id": str(match_id or match.get("id") or ""),
        "score": [list(pair) for pair in score],
        "surface": surface,
        "profile_evidence": profile_evidence,
        "game_evidence": game,
        "rows": rows,
    }


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def compare_full_player_row(pbp_row: dict[str, Any], tml_row: dict[str, Any]) -> dict[str, Any]:
    fields = []
    complete = True
    for field in REQUIRED_FIELDS:
        left, right = _finite(pbp_row.get(field)), _finite(tml_row.get(field))
        if left is None or right is None:
            complete = False
            fields.append({"field": field, "comparable": False})
            continue
        error = abs(left - right)
        fields.append({
            "field": field,
            "comparable": True,
            "pbp": left,
            "tml": right,
            "abs_error": error,
            "within_2pp": error <= RATE_TOLERANCE,
        })
    comparable = [row for row in fields if row.get("comparable")]
    return {
        "complete_required_field_comparison": complete,
        "fields": fields,
        "comparable_fields": len(comparable),
        "fields_within_2pp": sum(1 for row in comparable if row.get("within_2pp")),
        "all_required_within_2pp": bool(complete and all(row.get("within_2pp") for row in comparable)),
        "max_abs_error": max((row.get("abs_error", 0.0) for row in comparable), default=None),
    }


def _normalized_tml_rows(clean_df: pd.DataFrame, row_index: Any) -> dict[str, dict[str, Any]]:
    try:
        source = clean_df.loc[row_index]
    except Exception:
        return {}
    if not isinstance(source, pd.Series):
        return {}
    normalized = model.normalize_matches(pd.DataFrame([source]))
    if normalized is None or normalized.empty:
        return {}
    out = {}
    for _, row in normalized.iterrows():
        key = str(row.get("player_key") or task007._key(row.get("player"))).strip()
        if key:
            out[key] = row.to_dict()
    return out


def _calibration_gate(field_counts: dict[str, Counter[str]], full_rows: int) -> tuple[bool, dict[str, Any]]:
    field_rates = {}
    all_fields_pass = True
    for field in REQUIRED_FIELDS:
        c = field_counts.get(field, Counter())
        comparable = int(c["comparable"])
        within = int(c["within"])
        rate = within / comparable if comparable else 0.0
        field_rates[field] = {
            "comparable": comparable,
            "within_2pp": within,
            "agreement_rate": round(rate, 6),
        }
        if comparable < MIN_FULL_DUPLICATE_PLAYER_ROWS or rate < MIN_PER_FIELD_AGREEMENT_RATE:
            all_fields_pass = False
    sample_ok = full_rows >= MIN_FULL_DUPLICATE_PLAYER_ROWS
    return bool(sample_ok and all_fields_pass), {
        "full_duplicate_player_rows": full_rows,
        "minimum_full_duplicate_player_rows": MIN_FULL_DUPLICATE_PLAYER_ROWS,
        "minimum_per_field_agreement_rate": MIN_PER_FIELD_AGREEMENT_RATE,
        "fields": field_rates,
        "sample_sufficient": sample_ok,
        "all_fields_pass": all_fields_pass,
    }


def build_report(
    *,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    pbp_root: Path = DEFAULT_PBP_ROOT,
    results_path: Path = DEFAULT_RESULTS,
) -> dict[str, Any]:
    raw_history = load_cached_history()
    clean_df, hygiene = clean_history(raw_history)
    clean_rows = task007._tml_rows(clean_df)
    clean_index = task007._index_tml(clean_rows)

    scan = Counter()
    calibration_examples = []
    field_counts: dict[str, Counter[str]] = defaultdict(Counter)
    full_rows = 0
    full_rows_all_within = 0
    global_duplicate_matches = 0
    global_duplicate_projectable_matches = 0

    for path in sorted((pbp_root / "matches").glob("*.json.gz")):
        scan["pbp_files_scanned"] += 1
        payload = pbp._read_gzip_json(path)
        if not isinstance(payload, dict):
            continue
        scan["pbp_payloads_readable"] += 1
        identities = player_identity_map(payload)
        if identities is None:
            continue
        scan["stable_identity_payloads"] += 1
        match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
        if match.get("is_doubles") is True:
            continue
        payload_mid, payload_time = pbp._cached_match_identity_and_time(payload)
        if payload_mid is None or str(payload_mid) != path.name.removesuffix(".json.gz"):
            scan["file_payload_id_mismatches"] += 1
            continue
        scheduled = task007._parse_dt(payload_time)
        score = task007._pbp_score(payload)
        canonical = task007._canonical_pair_score(identities[1].get("name"), identities[2].get("name"), score)
        if scheduled is None or canonical is None or not pbp._cache_has_terminal_stats(payload):
            continue
        pair, canonical_score = canonical
        category, matches = task007.classify_overlap(
            pair=pair,
            score=canonical_score,
            scheduled_dt=scheduled,
            surface=task007._surface(match.get("surface")),
            clean_index=clean_index,
            raw_index=clean_index,
        )
        if category != "deterministic_duplicate_clean_tml" or len(matches) != 1:
            continue
        global_duplicate_matches += 1
        projection = project_payload_relaxed(payload, match_id=payload_mid)
        if projection.get("ready"):
            global_duplicate_projectable_matches += 1
        tml_rows = _normalized_tml_rows(clean_df, matches[0].get("row_index"))
        match_full = True
        match_player_comparisons = []
        for key, pbp_row in (projection.get("rows") or {}).items():
            tml_row = tml_rows.get(key)
            if not isinstance(tml_row, dict):
                match_full = False
                continue
            comparison = compare_full_player_row(pbp_row, tml_row)
            if comparison["complete_required_field_comparison"]:
                full_rows += 1
                full_rows_all_within += int(comparison["all_required_within_2pp"])
            else:
                match_full = False
            for item in comparison["fields"]:
                field = item["field"]
                if not item.get("comparable"):
                    continue
                field_counts[field]["comparable"] += 1
                field_counts[field]["within"] += int(item.get("within_2pp"))
            match_player_comparisons.append({"player_key": key, **comparison})
        if len(calibration_examples) < 20:
            calibration_examples.append({
                "match_id": payload_mid,
                "scheduled_time": payload_time,
                "projection_ready": bool(projection.get("ready")),
                "best_raw_split_slots": (projection.get("profile_evidence") or {}).get("best_raw_split_slots"),
                "complete_game_boundaries": (projection.get("game_evidence") or {}).get("complete_observed_game_boundaries"),
                "player_comparisons": match_player_comparisons,
                "both_players_compared": match_full and len(match_player_comparisons) == 2,
            })

    calibration_passed, calibration = _calibration_gate(field_counts, full_rows)
    calibration["full_rows_all_required_within_2pp"] = full_rows_all_within
    calibration["full_row_agreement_rate"] = round(full_rows_all_within / full_rows, 6) if full_rows else 0.0

    # Reuse TASK 007 for the current short-history target population, then apply
    # the globally calibrated projection mechanics to unmatched observations.
    current = task007.build_report(cache_root=cache_root, pbp_root=pbp_root, results_path=results_path)
    unmatched = [row for row in current.get("observations") or [] if isinstance(row, dict) and row.get("category") == "unmatched_in_tml_cache"]
    current_rows = []
    by_player: dict[str, dict[str, Any]] = {}
    projection_cache: dict[str, dict[str, Any]] = {}
    for obs in unmatched:
        mid = str(obs.get("match_id"))
        if mid not in projection_cache:
            payload = pbp._read_gzip_json(pbp_root / "matches" / f"{mid}.json.gz")
            projection_cache[mid] = project_payload_relaxed(payload or {}, match_id=mid)
        projection = projection_cache[mid]
        target = (projection.get("rows") or {}).get(obs.get("player_key"))
        target_ready = bool(isinstance(target, dict) and target.get("core_fields_ready") and target.get("aux_fields_ready"))
        current_rows.append({
            "match_id": obs.get("match_id"),
            "player": obs.get("player"),
            "player_key": obs.get("player_key"),
            "current_clean_history_matches": int(obs.get("current_clean_history_matches") or 0),
            "target_projection_ready": target_ready,
            "both_players_projection_ready": bool(projection.get("ready")),
            "best_raw_split_slots": (projection.get("profile_evidence") or {}).get("best_raw_split_slots"),
            "terminal_profiles": (projection.get("profile_evidence") or {}).get("terminal_profiles"),
            "complete_game_boundaries": (projection.get("game_evidence") or {}).get("complete_observed_game_boundaries"),
            "expected_non_tiebreak_games": (projection.get("game_evidence") or {}).get("expected_non_tiebreak_games"),
            "observed_game_boundaries": (projection.get("game_evidence") or {}).get("boundary_events_with_server_and_winner"),
            "target_row": target,
        })
        key = str(obs.get("player_key") or "")
        bucket = by_player.setdefault(key, {
            "player": obs.get("player"),
            "player_key": key,
            "current_clean_history_matches": int(obs.get("current_clean_history_matches") or 0),
            "ready_match_ids": set(),
        })
        if target_ready:
            bucket["ready_match_ids"].add(mid)

    players = []
    for bucket in by_player.values():
        ready = len(bucket.pop("ready_match_ids"))
        bucket["distinct_projection_ready_unmatched_matches"] = ready
        bucket["shadow_upper_bound_reaches_five"] = bucket["current_clean_history_matches"] + ready >= 5
        players.append(bucket)
    players.sort(key=lambda row: (row["shadow_upper_bound_reaches_five"], row["distinct_projection_ready_unmatched_matches"]), reverse=True)

    summary = {
        **{key: int(value) for key, value in scan.items()},
        "tml_clean_rows_indexed": len(clean_rows),
        "global_deterministic_duplicate_matches": global_duplicate_matches,
        "global_duplicate_projection_ready_matches": global_duplicate_projectable_matches,
        "global_full_duplicate_player_rows": full_rows,
        "global_full_rows_all_fields_within_2pp": full_rows_all_within,
        "global_calibration_gate_passed": calibration_passed,
        "current_unmatched_observations": len(unmatched),
        "current_unmatched_target_projection_ready": sum(1 for row in current_rows if row["target_projection_ready"]),
        "current_unmatched_both_players_projection_ready": sum(1 for row in current_rows if row["both_players_projection_ready"]),
        "current_players_with_projection_ready_supply": sum(1 for row in players if row["distinct_projection_ready_unmatched_matches"] > 0),
        "current_shadow_upper_bound_players_reaching_five": sum(1 for row in players if row["shadow_upper_bound_reaches_five"]),
        "schema_compatibility_proven": calibration_passed,
    }

    return {
        "version": VERSION,
        "policy": {
            "network_calls": 0,
            "fuzzy_matching": False,
            "similarity_thresholds": False,
            "manual_aliases": False,
            "cross_provider_numeric_id_comparison": False,
            "single_terminal_profile_only": True,
            "cross_profile_field_merge": False,
            "minimum_match_gate_changed": False,
            "history_hygiene_changed": False,
            "identity_resolver_changed": False,
            "model_math_changed": False,
            "runtime_change_authorized": False,
            "pbp_authorized_for_main_history": False,
            "calibration_rate_tolerance": RATE_TOLERANCE,
            "schema_compatibility_proven": calibration_passed,
        },
        "summary": summary,
        "history_hygiene": hygiene,
        "global_calibration": calibration,
        "global_calibration_examples": calibration_examples,
        "current_unmatched": current_rows,
        "current_players": players,
        "decision": {
            "runtime_change": False,
            "history_gate_change": False,
            "authorize_pbp_history": False,
            "reason": (
                "Global duplicate calibration can validate projection semantics, but TASK 009 never mutates Current Engine history. "
                "Any later ingestion requires an explicit separately reviewed adapter and must preserve the existing model gate."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Globally calibrate PBP normalized-history projection")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--pbp-root", type=Path, default=DEFAULT_PBP_ROOT)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report(cache_root=args.cache_root, pbp_root=args.pbp_root, results_path=args.results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    if report["policy"]["network_calls"] != 0 or report["decision"]["runtime_change"]:
        return 2
    if report["summary"]["pbp_files_scanned"] <= 0:
        return 3
    if report["summary"]["global_deterministic_duplicate_matches"] <= 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
