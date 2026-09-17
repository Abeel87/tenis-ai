from __future__ import annotations

"""TASK 008: audit whether cached terminal PBP can reproduce model-history fields.

Audit only. This module never adds PBP rows to model history, changes the
minimum-five gate, changes model mathematics, or makes network requests.
It projects existing terminal PBP evidence into the *normalized* history fields
already consumed by Current Engine and calibrates that projection only against
TASK 007 deterministic PBP/TennisMyLife duplicates.
"""

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from . import model
    from . import pbp_enrich as pbp
    from . import pbp_tml_dedup_audit as task007
    from .canonical_point_event import canonical_point_events
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
    from .player_dna_pbp_service_split_readiness import (
        RAW_KEYS,
        _final_tape_score,
        _latest_stats_profile,
        _ratio_counts,
        _score_core,
    )
    from .player_identity import player_identity_map
except ImportError:  # pragma: no cover
    import model
    import pbp_enrich as pbp
    import pbp_tml_dedup_audit as task007
    from canonical_point_event import canonical_point_events
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history
    from player_dna_pbp_service_split_readiness import (
        RAW_KEYS,
        _final_tape_score,
        _latest_stats_profile,
        _ratio_counts,
        _score_core,
    )
    from player_identity import player_identity_map

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = ROOT / "data" / "cache"
DEFAULT_PBP_ROOT = DEFAULT_CACHE_ROOT / "pbp_v7"
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "pbp_history_schema_audit.json"
VERSION = "task-008-pbp-history-schema-audit-v1"

CORE_MODEL_FIELDS = (
    "hold_rate",
    "break_rate",
    "serve_points_won",
    "return_points_won",
    "first_set_won",
)
AUX_MODEL_FIELDS = ("first_serve_won", "second_serve_won", "won")
RATE_FIELDS = (
    "hold_rate",
    "break_rate",
    "serve_points_won",
    "return_points_won",
    "first_serve_won",
    "second_serve_won",
)
CALIBRATION_TOLERANCE = 0.02
MIN_CALIBRATION_OBSERVATIONS_FOR_PROOF = 20


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _ratio(left: int, right: int) -> float | None:
    return left / right if right > 0 else None


def _terminal_stats(payload: dict[str, Any]) -> dict[str, Any] | None:
    profile = _latest_stats_profile(payload)
    if not isinstance(profile, dict):
        return None
    state = profile.get("input_state") if isinstance(profile.get("input_state"), dict) else {}
    stats = state.get("stats") if isinstance(state.get("stats"), dict) else None
    if not isinstance(stats, dict):
        return None
    if _final_tape_score(payload) is None or _score_core(state.get("score")) != _final_tape_score(payload):
        return None
    return stats


def _service_split_metrics(stats: dict[str, Any], side: str) -> dict[str, Any]:
    raw = stats.get(side) if isinstance(stats.get(side), dict) else {}
    first = _ratio_counts(raw.get(RAW_KEYS["first_serve_win_rate"]))
    second = _ratio_counts(raw.get(RAW_KEYS["second_serve_win_rate"]))
    first_return = _ratio_counts(raw.get(RAW_KEYS["first_return_win_rate"]))
    second_return = _ratio_counts(raw.get(RAW_KEYS["second_return_win_rate"]))

    serve_wins = serve_points = return_wins = return_points = 0
    if first is not None:
        serve_wins += first[0]
        serve_points += first[1]
    if second is not None:
        serve_wins += second[0]
        serve_points += second[1]
    if first_return is not None:
        return_wins += first_return[0]
        return_points += first_return[1]
    if second_return is not None:
        return_wins += second_return[0]
        return_points += second_return[1]

    return {
        "first_serve_won": _ratio(*first) if first is not None else None,
        "second_serve_won": _ratio(*second) if second is not None else None,
        "serve_points_won": _ratio(serve_wins, serve_points) if first is not None and second is not None else None,
        "return_points_won": _ratio(return_wins, return_points) if first_return is not None and second_return is not None else None,
        "raw_first_serve_counts": list(first) if first is not None else None,
        "raw_second_serve_counts": list(second) if second is not None else None,
        "raw_first_return_counts": list(first_return) if first_return is not None else None,
        "raw_second_return_counts": list(second_return) if second_return is not None else None,
    }


def _expected_non_tiebreak_games(score: tuple[tuple[int, int], ...]) -> int:
    total = 0
    for left, right in score:
        if left < 0 or right < 0:
            return 0
        total += left + right
        if (left, right) in {(7, 6), (6, 7)}:
            total -= 1
    return total


def _game_metrics_from_events(
    events: list[dict[str, Any]],
    final_score: tuple[tuple[int, int], ...],
) -> dict[str, Any]:
    service_games = {1: 0, 2: 0}
    holds = {1: 0, 2: 0}
    breaks = {1: 0, 2: 0}
    accepted = 0

    for event in events:
        if event.get("transition_kind") not in {"game_score_changed", "set_score_changed"}:
            continue
        if event.get("is_tiebreak_before") or event.get("is_tiebreak_after"):
            continue
        quality = event.get("quality") if isinstance(event.get("quality"), dict) else {}
        if quality.get("trainable_point") is not True:
            continue
        server = event.get("server")
        winner = event.get("point_winner")
        if server not in (1, 2) or winner not in (1, 2):
            continue
        accepted += 1
        service_games[server] += 1
        if winner == server:
            holds[server] += 1
        else:
            breaks[winner] += 1

    expected = _expected_non_tiebreak_games(final_score)
    complete = expected > 0 and accepted == expected
    out: dict[str, Any] = {
        "expected_non_tiebreak_games": expected,
        "observed_non_tiebreak_game_events": accepted,
        "complete_game_boundary_coverage": complete,
    }
    for side in (1, 2):
        opponent = 3 - side
        out[f"p{side}_service_games"] = service_games[side]
        out[f"p{side}_holds"] = holds[side]
        out[f"p{side}_breaks"] = breaks[side]
        out[f"p{side}_hold_rate"] = _ratio(holds[side], service_games[side]) if complete else None
        out[f"p{side}_break_rate"] = _ratio(breaks[side], service_games[opponent]) if complete else None
    return out


def _set_features(score: tuple[tuple[int, int], ...], side: int) -> dict[str, Any]:
    oriented = score if side == 1 else tuple((b, a) for a, b in score)
    wins = [left > right for left, right in oriented]
    return {
        "first_set_won": int(wins[0]) if len(wins) >= 1 else None,
        "second_set_won": int(wins[1]) if len(wins) >= 2 else None,
        "third_set_won": int(wins[2]) if len(wins) >= 3 else None,
        "sets_played": len(oriented),
        "first_set_games": sum(oriented[0]) if oriented else None,
    }


def project_payload(payload: dict[str, Any], match_id: Any = None) -> dict[str, Any]:
    """Project one terminal cached PBP match into normalized-history-like rows."""
    identities = player_identity_map(payload)
    match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
    score = task007._pbp_score(payload)
    stats = _terminal_stats(payload)
    scheduled = task007._parse_dt(match.get("scheduled_time"))
    surface = task007._surface(match.get("surface"))

    if identities is None or not score or stats is None or scheduled is None:
        return {
            "ready": False,
            "reason": "missing_identity_score_terminal_stats_or_time",
            "rows": {},
        }

    events = canonical_point_events(payload, match_id=match_id or match.get("id"))
    game_metrics = _game_metrics_from_events(events, score)

    winner = match.get("winner")
    if winner not in (1, 2):
        p1_sets = sum(1 for a, b in score if a > b)
        p2_sets = sum(1 for a, b in score if b > a)
        winner = 1 if p1_sets > p2_sets else (2 if p2_sets > p1_sets else None)

    rows: dict[str, dict[str, Any]] = {}
    for side in (1, 2):
        record = identities[side]
        key = task007._key(record.get("name"))
        split = _service_split_metrics(stats, f"p{side}")
        features = _set_features(score, side)
        row = {
            "player": record.get("name"),
            "player_key": key,
            "opponent": identities[3 - side].get("name"),
            "opponent_key": task007._key(identities[3 - side].get("name")),
            "date": scheduled.date().isoformat(),
            "surface": surface,
            "won": int(winner == side) if winner in (1, 2) else None,
            "hold_rate": game_metrics.get(f"p{side}_hold_rate"),
            "break_rate": game_metrics.get(f"p{side}_break_rate"),
            **{k: split.get(k) for k in ("serve_points_won", "return_points_won", "first_serve_won", "second_serve_won")},
            **features,
        }
        row["core_fields_ready"] = all(row.get(field) is not None for field in CORE_MODEL_FIELDS)
        row["aux_fields_ready"] = all(row.get(field) is not None for field in AUX_MODEL_FIELDS)
        rows[key] = row

    both_ready = len(rows) == 2 and all(row["core_fields_ready"] and row["aux_fields_ready"] for row in rows.values())
    return {
        "ready": both_ready,
        "reason": "projection_ready" if both_ready else "partial_normalized_history_fields",
        "match_id": str(match_id or match.get("id") or ""),
        "scheduled_time": match.get("scheduled_time"),
        "surface": surface,
        "score": [list(pair) for pair in score],
        "terminal_stats_snapshot": True,
        "canonical_point_events": len(events),
        "game_metrics": game_metrics,
        "rows": rows,
    }


def _payload_for_match(pbp_root: Path, match_id: Any) -> dict[str, Any] | None:
    path = pbp_root / "matches" / f"{match_id}.json.gz"
    value = pbp._read_gzip_json(path)
    return value if isinstance(value, dict) else None


def _clean_tml_index(clean_history_df: pd.DataFrame):
    rows = task007._tml_rows(clean_history_df)
    return rows, task007._index_tml(rows)


def _exact_clean_tml_row(
    observation: dict[str, Any],
    clean_history_df: pd.DataFrame,
    clean_index: dict,
) -> pd.Series | None:
    pair = tuple(task007._key(value) for value in observation.get("pair") or [])
    if len(pair) != 2:
        pair = tuple(sorted((task007._key(observation.get("p1")), task007._key(observation.get("p2")))))
    score = tuple(tuple(int(x) for x in item) for item in (observation.get("score") or []))
    category, matches = task007.classify_overlap(
        pair=pair,
        score=score,
        scheduled_dt=task007._parse_dt(observation.get("scheduled_time")),
        surface=task007._surface(observation.get("surface")),
        clean_index=clean_index,
        raw_index=clean_index,
    )
    if category != "deterministic_duplicate_clean_tml" or len(matches) != 1:
        return None
    idx = matches[0].get("row_index")
    try:
        row = clean_history_df.loc[idx]
    except Exception:
        return None
    return row if isinstance(row, pd.Series) else None


def _normalized_tml_player_row(raw_row: pd.Series, player_key: str) -> dict[str, Any] | None:
    normalized = model.normalize_matches(pd.DataFrame([raw_row]))
    if normalized is None or normalized.empty:
        return None
    if "player_key" in normalized.columns:
        matches = normalized[normalized["player_key"].astype(str) == player_key]
    else:
        matches = normalized[normalized["player"].map(task007._key) == player_key]
    if len(matches) != 1:
        return None
    return matches.iloc[0].to_dict()


def _compare_rows(pbp_row: dict[str, Any], tml_row: dict[str, Any]) -> dict[str, Any]:
    comparisons = []
    for field in (*CORE_MODEL_FIELDS, *AUX_MODEL_FIELDS):
        left = _finite(pbp_row.get(field))
        right = _finite(tml_row.get(field))
        if left is None or right is None:
            continue
        error = abs(left - right)
        comparisons.append({
            "field": field,
            "pbp": left,
            "tml": right,
            "abs_error": error,
            "within_tolerance": error <= CALIBRATION_TOLERANCE,
        })
    return {
        "comparisons": comparisons,
        "comparable_fields": len(comparisons),
        "within_tolerance_fields": sum(1 for row in comparisons if row["within_tolerance"]),
        "all_comparable_within_tolerance": bool(comparisons and all(row["within_tolerance"] for row in comparisons)),
        "max_abs_error": max((row["abs_error"] for row in comparisons), default=None),
    }


def build_report(
    *,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    pbp_root: Path = DEFAULT_PBP_ROOT,
    results_path: Path = DEFAULT_RESULTS,
) -> dict[str, Any]:
    dedup = task007.build_report(cache_root=cache_root, pbp_root=pbp_root, results_path=results_path)
    observations = [row for row in dedup.get("observations") or [] if isinstance(row, dict)]
    raw_history = load_cached_history()
    clean_history_df, hygiene = clean_history(raw_history)
    _, clean_index = _clean_tml_index(clean_history_df)

    payload_cache: dict[str, dict[str, Any] | None] = {}
    projection_cache: dict[str, dict[str, Any]] = {}

    def projection(match_id: Any) -> dict[str, Any]:
        token = str(match_id)
        if token not in projection_cache:
            payload = _payload_for_match(pbp_root, token)
            payload_cache[token] = payload
            projection_cache[token] = project_payload(payload or {}, match_id=token)
        return projection_cache[token]

    calibration_rows = []
    calibration_counts = Counter()
    for obs in observations:
        if obs.get("category") != "deterministic_duplicate_clean_tml":
            continue
        proj = projection(obs.get("match_id"))
        pbp_row = (proj.get("rows") or {}).get(obs.get("player_key"))
        tml_source = _exact_clean_tml_row(obs, clean_history_df, clean_index)
        tml_row = _normalized_tml_player_row(tml_source, str(obs.get("player_key") or "")) if tml_source is not None else None
        if not isinstance(pbp_row, dict) or not isinstance(tml_row, dict):
            calibration_counts["unprojectable_duplicate_observations"] += 1
            continue
        comparison = _compare_rows(pbp_row, tml_row)
        calibration_counts["duplicate_observations_compared"] += 1
        calibration_counts["field_comparisons"] += int(comparison["comparable_fields"])
        calibration_counts["fields_within_tolerance"] += int(comparison["within_tolerance_fields"])
        calibration_counts["duplicates_all_comparable_within_tolerance"] += int(comparison["all_comparable_within_tolerance"])
        calibration_rows.append({
            "match_id": obs.get("match_id"),
            "player": obs.get("player"),
            "player_key": obs.get("player_key"),
            **comparison,
        })

    unmatched_rows = []
    player_supply: dict[str, dict[str, Any]] = {}
    for obs in observations:
        if obs.get("category") != "unmatched_in_tml_cache":
            continue
        proj = projection(obs.get("match_id"))
        target = (proj.get("rows") or {}).get(obs.get("player_key"))
        target_ready = bool(isinstance(target, dict) and target.get("core_fields_ready") and target.get("aux_fields_ready"))
        both_ready = bool(proj.get("ready"))
        item = {
            "match_id": obs.get("match_id"),
            "player": obs.get("player"),
            "player_key": obs.get("player_key"),
            "current_clean_history_matches": int(obs.get("current_clean_history_matches") or 0),
            "target_normalized_fields_ready": target_ready,
            "both_players_normalized_fields_ready": both_ready,
            "projection_reason": proj.get("reason"),
            "complete_game_boundary_coverage": bool((proj.get("game_metrics") or {}).get("complete_game_boundary_coverage")),
            "target_row": target,
        }
        unmatched_rows.append(item)
        key = str(obs.get("player_key") or "")
        bucket = player_supply.setdefault(key, {
            "player": obs.get("player"),
            "player_key": key,
            "current_clean_history_matches": int(obs.get("current_clean_history_matches") or 0),
            "unmatched_observations": 0,
            "target_projection_ready": 0,
            "both_players_projection_ready": 0,
            "ready_match_ids": set(),
        })
        bucket["unmatched_observations"] += 1
        bucket["target_projection_ready"] += int(target_ready)
        bucket["both_players_projection_ready"] += int(both_ready)
        if target_ready and obs.get("match_id") is not None:
            bucket["ready_match_ids"].add(str(obs.get("match_id")))

    players = []
    for bucket in player_supply.values():
        distinct_ready = len(bucket.pop("ready_match_ids"))
        bucket["distinct_target_projection_ready_matches"] = distinct_ready
        bucket["shadow_upper_bound_reaches_five"] = bucket["current_clean_history_matches"] + distinct_ready >= 5
        players.append(bucket)
    players.sort(key=lambda row: (row["shadow_upper_bound_reaches_five"], row["distinct_target_projection_ready_matches"]), reverse=True)

    compared = int(calibration_counts["duplicate_observations_compared"])
    field_checks = int(calibration_counts["field_comparisons"])
    within = int(calibration_counts["fields_within_tolerance"])
    calibration_rate = within / field_checks if field_checks else 0.0
    calibration_consistent = bool(field_checks and calibration_rate == 1.0)
    calibration_sample_sufficient = compared >= MIN_CALIBRATION_OBSERVATIONS_FOR_PROOF
    schema_proven = bool(calibration_consistent and calibration_sample_sufficient)

    summary = {
        "task007_terminal_pbp_player_observations": int(dedup.get("summary", {}).get("terminal_pbp_player_observations") or 0),
        "task007_unmatched_in_tml_cache": int(dedup.get("summary", {}).get("unmatched_in_tml_cache") or 0),
        "unique_payloads_projected": len(projection_cache),
        "projection_ready_payloads": sum(1 for item in projection_cache.values() if item.get("ready")),
        "duplicate_observations_compared": compared,
        "duplicate_field_comparisons": field_checks,
        "duplicate_fields_within_2pp": within,
        "duplicate_field_agreement_rate": round(calibration_rate, 6),
        "unmatched_observations_audited": len(unmatched_rows),
        "unmatched_target_projection_ready": sum(1 for row in unmatched_rows if row["target_normalized_fields_ready"]),
        "unmatched_both_players_projection_ready": sum(1 for row in unmatched_rows if row["both_players_normalized_fields_ready"]),
        "players_with_projection_ready_unmatched_supply": sum(1 for row in players if row["distinct_target_projection_ready_matches"] > 0),
        "shadow_upper_bound_players_reaching_five": sum(1 for row in players if row["shadow_upper_bound_reaches_five"]),
        "calibration_sample_sufficient_for_schema_proof": calibration_sample_sufficient,
        "schema_compatibility_proven": schema_proven,
    }

    return {
        "version": VERSION,
        "policy": {
            "network_calls": 0,
            "fuzzy_matching": False,
            "similarity_thresholds": False,
            "manual_aliases": False,
            "cross_provider_numeric_id_comparison": False,
            "minimum_match_gate_changed": False,
            "history_hygiene_changed": False,
            "identity_resolver_changed": False,
            "runtime_change_authorized": False,
            "pbp_authorized_for_main_history": False,
            "unmatched_pbp_authorized_as_new_history": False,
            "model_math_changed": False,
            "calibration_tolerance_absolute_rate": CALIBRATION_TOLERANCE,
            "minimum_duplicate_observations_for_schema_proof": MIN_CALIBRATION_OBSERVATIONS_FOR_PROOF,
            "schema_compatibility_proven": schema_proven,
        },
        "summary": summary,
        "history_hygiene": hygiene,
        "calibration": {
            "counts": dict(calibration_counts),
            "rows": calibration_rows,
            "interpretation": (
                "Agreement on deterministic duplicates validates the projection mechanics only. "
                "The sample must also meet the explicit minimum before schema compatibility can be proven."
            ),
        },
        "unmatched": unmatched_rows,
        "players": players,
        "decision": {
            "runtime_change": False,
            "history_gate_change": False,
            "authorize_pbp_history": False,
            "reason": (
                "TASK 008 is audit-only. Even fully projectable unmatched PBP rows remain excluded from Current Engine history. "
                "A later change would require sufficient duplicate calibration plus a separately reviewed ingestion adapter."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit PBP compatibility with normalized model-history fields")
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
    if report["summary"]["unmatched_observations_audited"] <= 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
