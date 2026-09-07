from __future__ import annotations

"""Audit real historical depth available to future Player DNA profiles.

The audit consumes the already-built SHADOW point dataset. It never aggregates
or activates a player profile and never trains a model. Historical readiness is
strictly as-of: only matches with scheduled_time < target scheduled_time count.

Pressure readiness reuses canonical score semantics from atomic_point_transition.
It does not reconstruct missing games or set-ending boundaries.
"""

import gzip
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.atomic_point_transition import game_point_flags, point_token
except ModuleNotFoundError:  # direct execution compatibility
    from atomic_point_transition import game_point_flags, point_token

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "data" / "derived" / "player_dna" / "point_events.jsonl.gz"
OUT = ROOT / "frontend" / "data" / "player_dna_profile_readiness.json"
VERSION = "player-dna-profile-readiness-audit-v1"
THRESHOLDS = (1, 3, 5, 10, 20)
PRESSURE_SUPPORT_METRICS = {
    "hold": "service_games",
    "break": "return_games",
    "bp_save": "bp_faced",
    "bp_conversion": "bp_chances",
    "deuce_serve": "deuce_serve_points",
    "deuce_return": "deuce_return_points",
    "thirty_all_serve": "thirty_all_serve_points",
    "thirty_all_return": "thirty_all_return_points",
    "early_service_game_1": "early_service_game_1",
    "early_service_game_2": "early_service_game_2",
    "early_service_game_3": "early_service_game_3",
    "early_return_game_1": "early_return_game_1",
    "early_return_game_2": "early_return_game_2",
    "early_return_game_3": "early_return_game_3",
}
PRESSURE_SEGMENT_THRESHOLD = 5
SMALL_SAMPLE_BANDS = (
    ("0", 0, 0),
    ("1-2", 1, 2),
    ("3-4", 3, 4),
    ("5-9", 5, 9),
    ("10+", 10, None),
)


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _player_id(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return int(value)


def iter_point_rows(path: Path = POINTS) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def _percentile(sorted_values: list[int], fraction: float) -> int | None:
    if not sorted_values:
        return None
    index = min(len(sorted_values) - 1, max(0, int((len(sorted_values) - 1) * fraction)))
    return int(sorted_values[index])


def _sample_band(depth: int) -> str:
    value = max(0, int(depth))
    for label, lo, hi in SMALL_SAMPLE_BANDS:
        if value < lo:
            continue
        if hi is None or value <= hi:
            return label
    raise AssertionError("unreachable sample-depth band")


def _strict_atomic_game(row: dict[str, Any]) -> bool:
    return bool(
        row.get("context_ready_player_point") is True
        and row.get("transition_kind") == "game_score_changed"
        and row.get("trainable_point") is True
        and row.get("atomic_transition") is True
        and row.get("atomic_reason") == "atomic_game_boundary"
    )


def _standard_pressure_flags(
    row: dict[str, Any],
) -> tuple[int, int, int, str, str] | None:
    if row.get("context_ready_player_point") is not True:
        return None
    if row.get("trainable_point") is not True or row.get("is_tiebreak_before") is True:
        return None
    server = row.get("server")
    receiver = row.get("receiver")
    score = row.get("score_before")
    if server not in (1, 2) or receiver not in (1, 2) or not isinstance(score, dict):
        return None
    points = score.get("points")
    if not isinstance(points, list) or len(points) < 2:
        return None
    server_token = point_token(points[server - 1])
    receiver_token = point_token(points[receiver - 1])
    if server_token is None or receiver_token is None:
        return None
    server_gp, receiver_gp, deuce, _, _ = game_point_flags(
        server_token,
        receiver_token,
        False,
    )
    if server_gp is None or receiver_gp is None or deuce is None:
        return None
    return int(server_gp), int(receiver_gp), int(deuce), server_token, receiver_token


def _add_pressure_point(
    row: dict[str, Any],
    pressure_by_match_player: dict[tuple[str, int], Counter[str]],
    global_pressure: Counter[str],
) -> None:
    flags = _standard_pressure_flags(row)
    if flags is None:
        return
    _, receiver_gp, deuce, server_token, receiver_token = flags
    match_id = str(row.get("match_id") or "").strip()
    server_pid = _player_id(row.get("server_player_id"))
    receiver_pid = _player_id(row.get("receiver_player_id"))
    if not match_id or server_pid is None or receiver_pid is None:
        return

    server_bucket = pressure_by_match_player[(match_id, server_pid)]
    receiver_bucket = pressure_by_match_player[(match_id, receiver_pid)]
    server_won = row.get("server_won")

    if receiver_gp == 1:
        server_bucket["bp_faced"] += 1
        receiver_bucket["bp_chances"] += 1
        global_pressure["break_point_opportunities"] += 1
        if server_won is True:
            server_bucket["bp_saved"] += 1
            global_pressure["break_points_saved"] += 1
        elif server_won is False:
            receiver_bucket["bp_converted"] += 1
            global_pressure["break_points_converted"] += 1

    if deuce == 1:
        server_bucket["deuce_serve_points"] += 1
        receiver_bucket["deuce_return_points"] += 1
        global_pressure["deuce_points"] += 1

    if server_token == "30" and receiver_token == "30":
        server_bucket["thirty_all_serve_points"] += 1
        receiver_bucket["thirty_all_return_points"] += 1
        global_pressure["thirty_all_points"] += 1


def _pressure_readiness(
    counters: dict[str, Counter[int]],
    targets: int,
) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        metric: {
            str(threshold): {
                "targets": int(counter[threshold]),
                "rate": round(counter[threshold] / targets, 6) if targets else 0.0,
            }
            for threshold in THRESHOLDS
        }
        for metric, counter in counters.items()
    }


def _segment_pressure_readiness(
    segment_targets: Counter[str],
    segment_hits: dict[str, Counter[str]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for segment, targets in sorted(segment_targets.items()):
        hits = segment_hits.get(segment) or Counter()
        out[segment] = {
            "targets": int(targets),
            "minimum_prior_observations": PRESSURE_SEGMENT_THRESHOLD,
            "metrics": {
                metric: {
                    "targets": int(hits[metric]),
                    "rate": round(hits[metric] / targets, 6) if targets else 0.0,
                }
                for metric in PRESSURE_SUPPORT_METRICS
            },
        }
    return out


def audit_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    matches: dict[str, dict[str, Any]] = {}
    pressure_by_match_player: dict[tuple[str, int], Counter[str]] = defaultdict(Counter)
    game_boundaries: dict[str, list[tuple[int, int, int, bool]]] = defaultdict(list)
    global_pressure: Counter[str] = Counter()
    boundary_quality: Counter[str] = Counter()
    total_rows = context_ready_rows = 0
    invalid_match_time_rows = 0

    for row_index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        total_rows += 1
        match_id = str(row.get("match_id") or "").strip()
        scheduled = _parse_utc(row.get("match_scheduled_time"))
        if not match_id or scheduled is None:
            invalid_match_time_rows += 1
            continue

        p1 = _player_id(row.get("p1_player_id"))
        p2 = _player_id(row.get("p2_player_id"))
        if p1 is None or p2 is None:
            continue

        if row.get("context_ready_player_point") is True:
            context_ready_rows += 1

        entry = matches.setdefault(match_id, {
            "match_id": match_id,
            "scheduled": scheduled,
            "surface": row.get("surface"),
            "tour": row.get("tour"),
            "p1": p1,
            "p2": p2,
            "has_context_ready_point": False,
        })
        if entry["scheduled"] != scheduled or entry["p1"] != p1 or entry["p2"] != p2:
            entry["conflict"] = True
        if row.get("context_ready_player_point") is True:
            entry["has_context_ready_point"] = True

        atomic_reason = str(row.get("atomic_reason") or "unknown")
        if row.get("transition_kind") in {"game_score_changed", "set_score_changed"}:
            boundary_quality[atomic_reason] += 1

        _add_pressure_point(row, pressure_by_match_player, global_pressure)

        if _strict_atomic_game(row):
            server_pid = _player_id(row.get("server_player_id"))
            receiver_pid = _player_id(row.get("receiver_player_id"))
            if server_pid is None or receiver_pid is None:
                continue
            event_index = row.get("event_index")
            if isinstance(event_index, bool) or not isinstance(event_index, int):
                event_index = row_index
            held = row.get("server_won") is True
            game_boundaries[match_id].append(
                (int(event_index), server_pid, receiver_pid, bool(held))
            )
            server_bucket = pressure_by_match_player[(match_id, server_pid)]
            receiver_bucket = pressure_by_match_player[(match_id, receiver_pid)]
            server_bucket["service_games"] += 1
            receiver_bucket["return_games"] += 1
            global_pressure["strict_atomic_games"] += 1
            if held:
                server_bucket["holds"] += 1
                global_pressure["holds"] += 1
            else:
                receiver_bucket["breaks"] += 1
                global_pressure["breaks"] += 1

    # Early-game support uses only observed/proven atomic game boundaries in
    # provider event order. Missing/unproven games are never reconstructed.
    for match_id, boundaries in game_boundaries.items():
        serve_seen: Counter[int] = Counter()
        return_seen: Counter[int] = Counter()
        for _, server_pid, receiver_pid, _ in sorted(boundaries):
            serve_seen[server_pid] += 1
            return_seen[receiver_pid] += 1
            serve_index = int(serve_seen[server_pid])
            return_index = int(return_seen[receiver_pid])
            if serve_index <= 3:
                pressure_by_match_player[(match_id, server_pid)][
                    f"early_service_game_{serve_index}"
                ] += 1
                global_pressure[f"early_service_game_{serve_index}"] += 1
            if return_index <= 3:
                pressure_by_match_player[(match_id, receiver_pid)][
                    f"early_return_game_{return_index}"
                ] += 1
                global_pressure[f"early_return_game_{return_index}"] += 1

    source_matches = [entry for entry in matches.values() if not entry.get("conflict")]
    valid_matches = [
        entry for entry in source_matches
        if entry.get("has_context_ready_point") is True
    ]

    player_matches: dict[int, list[dict[str, Any]]] = defaultdict(list)
    surface_counts: Counter[str] = Counter()
    for match in valid_matches:
        surface = str(match.get("surface") or "unknown")
        surface_counts[surface] += 1
        for pid in (match["p1"], match["p2"]):
            player_matches[int(pid)].append(match)

    per_player_match_depth: list[int] = []
    total_threshold_hits = Counter()
    surface_threshold_hits = Counter()
    pressure_any_hits = {
        metric: Counter() for metric in PRESSURE_SUPPORT_METRICS
    }
    pressure_surface_hits = {
        metric: Counter() for metric in PRESSURE_SUPPORT_METRICS
    }
    tour_targets: Counter[str] = Counter()
    surface_targets: Counter[str] = Counter()
    tour_pressure_hits: dict[str, Counter[str]] = defaultdict(Counter)
    surface_pressure_hits: dict[str, Counter[str]] = defaultdict(Counter)
    same_time_player_groups = 0
    targets = 0
    small_sample_any_bands: Counter[str] = Counter()
    small_sample_surface_bands: Counter[str] = Counter()

    for pid, history in player_matches.items():
        history.sort(key=lambda m: (m["scheduled"], m["match_id"]))
        time_counts = Counter(m["scheduled"] for m in history)
        same_time_player_groups += sum(1 for count in time_counts.values() if count > 1)

        for target in history:
            targets += 1
            prior = [m for m in history if m["scheduled"] < target["scheduled"]]
            target_surface = str(target.get("surface") or "unknown")
            target_tour = str(target.get("tour") or "unknown")
            same_surface_prior = [
                m for m in prior
                if str(m.get("surface") or "unknown") == target_surface
            ]
            total_depth = len(prior)
            surface_depth = len(same_surface_prior)
            small_sample_any_bands[_sample_band(total_depth)] += 1
            small_sample_surface_bands[_sample_band(surface_depth)] += 1
            per_player_match_depth.append(total_depth)
            for threshold in THRESHOLDS:
                if total_depth >= threshold:
                    total_threshold_hits[threshold] += 1
                if surface_depth >= threshold:
                    surface_threshold_hits[threshold] += 1

            tour_targets[target_tour] += 1
            surface_targets[target_surface] += 1
            for metric, support_key in PRESSURE_SUPPORT_METRICS.items():
                any_support = sum(
                    int(pressure_by_match_player[(m["match_id"], pid)][support_key])
                    for m in prior
                )
                same_surface_support = sum(
                    int(pressure_by_match_player[(m["match_id"], pid)][support_key])
                    for m in same_surface_prior
                )
                for threshold in THRESHOLDS:
                    if any_support >= threshold:
                        pressure_any_hits[metric][threshold] += 1
                    if same_surface_support >= threshold:
                        pressure_surface_hits[metric][threshold] += 1
                if any_support >= PRESSURE_SEGMENT_THRESHOLD:
                    tour_pressure_hits[target_tour][metric] += 1
                if same_surface_support >= PRESSURE_SEGMENT_THRESHOLD:
                    surface_pressure_hits[target_surface][metric] += 1

    player_match_counts = sorted(len(history) for history in player_matches.values())
    depth_sorted = sorted(per_player_match_depth)

    def readiness(counter: Counter[int]) -> dict[str, dict[str, Any]]:
        return {
            str(threshold): {
                "targets": int(counter[threshold]),
                "rate": round(counter[threshold] / targets, 6) if targets else 0.0,
            }
            for threshold in THRESHOLDS
        }

    pressure_player_match_evidence = sum(
        1 for bucket in pressure_by_match_player.values() if sum(bucket.values()) > 0
    )

    def sample_band_report(counter: Counter[str]) -> dict[str, dict[str, Any]]:
        return {
            label: {
                "targets": int(counter[label]),
                "rate": round(counter[label] / targets, 6) if targets else 0.0,
            }
            for label, _, _ in SMALL_SAMPLE_BANDS
        }

    return {
        "version": VERSION,
        "gate": "AUDIT_ONLY_NO_PROFILE_AGGREGATION",
        "network_calls": 0,
        "shadow_only": True,
        "strict_as_of_policy": "prior_match_scheduled_time < target_match_scheduled_time",
        "same_time_matches_count_as_prior": False,
        "training_join_enabled": False,
        "profile_aggregation_enabled": False,
        "readiness_threshold_activation_enabled": False,
        "pressure_profile_aggregation_enabled": False,
        "pressure_training_join_enabled": False,
        "pressure_feature_activation_enabled": False,
        "pressure_threshold_activation_enabled": False,
        "pressure_semantics": {
            "canonical_source": "backend.atomic_point_transition",
            "standard_score_pressure_only": True,
            "tiebreak_pressure_excluded_from_bp_deuce_metrics": True,
            "strict_atomic_game_boundaries_only": True,
            "set_boundary_reconstruction_enabled": False,
            "early_game_order": "observed_proven_atomic_boundaries_only",
            "missing_game_reconstruction_enabled": False,
            "same_time_matches_count_as_prior": False,
        },
        "point_rows": total_rows,
        "context_ready_point_rows": context_ready_rows,
        "invalid_match_time_rows": invalid_match_time_rows,
        "source_matches_seen": len(source_matches),
        "context_ready_matches": len(valid_matches),
        "matches_without_context_ready_points": len(source_matches) - len(valid_matches),
        "players": len(player_matches),
        "player_match_targets": targets,
        "surface_match_counts": dict(surface_counts.most_common()),
        "player_match_depth": {
            "min": player_match_counts[0] if player_match_counts else None,
            "p50": _percentile(player_match_counts, 0.50),
            "p75": _percentile(player_match_counts, 0.75),
            "p90": _percentile(player_match_counts, 0.90),
            "max": player_match_counts[-1] if player_match_counts else None,
            "players_ge_1": sum(v >= 1 for v in player_match_counts),
            "players_ge_3": sum(v >= 3 for v in player_match_counts),
            "players_ge_5": sum(v >= 5 for v in player_match_counts),
            "players_ge_10": sum(v >= 10 for v in player_match_counts),
            "players_ge_20": sum(v >= 20 for v in player_match_counts),
        },
        "prior_history_depth": {
            "p50": _percentile(depth_sorted, 0.50),
            "p75": _percentile(depth_sorted, 0.75),
            "p90": _percentile(depth_sorted, 0.90),
            "max": depth_sorted[-1] if depth_sorted else None,
        },
        "readiness_any_surface": readiness(total_threshold_hits),
        "readiness_same_surface": readiness(surface_threshold_hits),
        "small_sample_shrinkage_readiness": {
            "any_surface_depth_bands": sample_band_report(small_sample_any_bands),
            "same_surface_depth_bands": sample_band_report(small_sample_surface_bands),
            "targets_below_5_any_surface": int(
                small_sample_any_bands["0"]
                + small_sample_any_bands["1-2"]
                + small_sample_any_bands["3-4"]
            ),
            "targets_below_5_same_surface": int(
                small_sample_surface_bands["0"]
                + small_sample_surface_bands["1-2"]
                + small_sample_surface_bands["3-4"]
            ),
            "policy": {
                "diagnostic_only": True,
                "shrinkage_activation_enabled": False,
                "partial_pooling_activation_enabled": False,
                "prior_strength_selected": False,
                "candidate_parameter_selection_must_use_train_only_data": True,
                "raw_small_sample_rate_must_not_be_promoted_directly": True,
                "next_gate": "TRAIN_ONLY_EMPIRICAL_BAYES_OR_PARTIAL_POOLING_CHALLENGER",
            },
        },
        "pressure_evidence": {
            "player_match_evidence_cells": pressure_player_match_evidence,
            "counts": dict(global_pressure),
            "boundary_quality": dict(boundary_quality.most_common()),
            "support_metric_source": dict(PRESSURE_SUPPORT_METRICS),
        },
        "pressure_readiness_any_surface": _pressure_readiness(
            pressure_any_hits,
            targets,
        ),
        "pressure_readiness_same_surface": _pressure_readiness(
            pressure_surface_hits,
            targets,
        ),
        "pressure_readiness_by_target_tour_at_5": _segment_pressure_readiness(
            tour_targets,
            tour_pressure_hits,
        ),
        "pressure_readiness_by_target_surface_at_5": _segment_pressure_readiness(
            surface_targets,
            surface_pressure_hits,
        ),
        "same_time_player_groups": same_time_player_groups,
        "note": (
            "Evidence only. No minimum-history, pressure-support or shrinkage threshold is activated here. "
            "Small-sample depth bands quantify where raw rates need a separate train-only shrinkage/partial-pooling "
            "challenger. Any candidate must be validated out of sample before profile/model activation."
        ),
    }


def build() -> dict[str, Any]:
    report = audit_rows(iter_point_rows() or ())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": report["version"],
        "source_matches_seen": report["source_matches_seen"],
        "context_ready_matches": report["context_ready_matches"],
        "matches_without_context_ready_points": report["matches_without_context_ready_points"],
        "players": report["players"],
        "targets": report["player_match_targets"],
        "readiness_any_surface": report["readiness_any_surface"],
        "readiness_same_surface": report["readiness_same_surface"],
        "pressure_counts": (report.get("pressure_evidence") or {}).get("counts"),
        "pressure_any_surface_at_5": {
            metric: ((values or {}).get("5") or {})
            for metric, values in (report.get("pressure_readiness_any_surface") or {}).items()
        },
        "pressure_same_surface_at_5": {
            metric: ((values or {}).get("5") or {})
            for metric, values in (report.get("pressure_readiness_same_surface") or {}).items()
        },
        "same_time_player_groups": report["same_time_player_groups"],
        "gate": report["gate"],
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
