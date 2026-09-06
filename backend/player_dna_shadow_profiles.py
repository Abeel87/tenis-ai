from __future__ import annotations

"""Leakage-safe SHADOW profile snapshots for Player DNA.

Profiles are built only from strict context-ready Player DNA point rows. For each
player-match target, the snapshot sees matches with scheduled_time strictly
earlier than the target. Same-time matches are snapshotted before either match is
added to history. No threshold is activated and no production model consumes
these profiles.
"""

import gzip
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.atomic_point_transition import game_point_flags, point_token
except ModuleNotFoundError:  # direct execution compatibility
    from atomic_point_transition import game_point_flags, point_token

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "data" / "derived" / "player_dna" / "point_events.jsonl.gz"
OUT_DIR = ROOT / "data" / "derived" / "player_dna"
OUT_JSONL = OUT_DIR / "profile_snapshots.jsonl.gz"
OUT_SUMMARY = ROOT / "frontend" / "data" / "player_dna_shadow_profile_summary.json"

VERSION = "player-dna-shadow-profiles-v1"
THRESHOLDS = (1, 3, 5, 10)
ROLLING_WINDOWS = (5, 10, 20)
ACCUMULATE_KEYS = (
    "serve_points", "serve_wins", "return_points", "return_wins",
    "tiebreak_points", "tiebreak_wins",
    "service_games", "holds", "return_games", "breaks",
    "bp_faced", "bp_saved", "bp_chances", "bp_converted",
    "deuce_serve_points", "deuce_serve_wins",
    "deuce_return_points", "deuce_return_wins",
    "thirty_all_serve_points", "thirty_all_serve_wins",
    "thirty_all_return_points", "thirty_all_return_wins",
    "early_service_game_1", "early_service_game_1_holds",
    "early_service_game_2", "early_service_game_2_holds",
    "early_service_game_3", "early_service_game_3_holds",
    "early_return_game_1", "early_return_game_1_breaks",
    "early_return_game_2", "early_return_game_2_breaks",
    "early_return_game_3", "early_return_game_3_breaks",
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


def _empty_stats() -> dict[str, int]:
    return {
        "matches": 0,
        **{key: 0 for key in ACCUMULATE_KEYS},
    }


def _rate(wins: int, points: int) -> float | None:
    return round(wins / points, 6) if points > 0 else None


def _project(stats: dict[str, int] | None) -> dict[str, Any]:
    stats = stats or _empty_stats()

    def count(key: str) -> int:
        return int(stats.get(key) or 0)

    out = {
        "matches": count("matches"),
        "serve_points": count("serve_points"),
        "serve_wins": count("serve_wins"),
        "serve_win_rate": _rate(count("serve_wins"), count("serve_points")),
        "return_points": count("return_points"),
        "return_wins": count("return_wins"),
        "return_win_rate": _rate(count("return_wins"), count("return_points")),
        "tiebreak_points": count("tiebreak_points"),
        "tiebreak_wins": count("tiebreak_wins"),
        "tiebreak_win_rate": _rate(count("tiebreak_wins"), count("tiebreak_points")),
        "service_games": count("service_games"),
        "holds": count("holds"),
        "hold_rate": _rate(count("holds"), count("service_games")),
        "return_games": count("return_games"),
        "breaks": count("breaks"),
        "break_rate": _rate(count("breaks"), count("return_games")),
        "bp_faced": count("bp_faced"),
        "bp_saved": count("bp_saved"),
        "bp_save_rate": _rate(count("bp_saved"), count("bp_faced")),
        "bp_chances": count("bp_chances"),
        "bp_converted": count("bp_converted"),
        "bp_conversion_rate": _rate(count("bp_converted"), count("bp_chances")),
        "deuce_serve_points": count("deuce_serve_points"),
        "deuce_serve_wins": count("deuce_serve_wins"),
        "deuce_serve_win_rate": _rate(
            count("deuce_serve_wins"), count("deuce_serve_points")
        ),
        "deuce_return_points": count("deuce_return_points"),
        "deuce_return_wins": count("deuce_return_wins"),
        "deuce_return_win_rate": _rate(
            count("deuce_return_wins"), count("deuce_return_points")
        ),
        "thirty_all_serve_points": count("thirty_all_serve_points"),
        "thirty_all_serve_wins": count("thirty_all_serve_wins"),
        "thirty_all_serve_win_rate": _rate(
            count("thirty_all_serve_wins"), count("thirty_all_serve_points")
        ),
        "thirty_all_return_points": count("thirty_all_return_points"),
        "thirty_all_return_wins": count("thirty_all_return_wins"),
        "thirty_all_return_win_rate": _rate(
            count("thirty_all_return_wins"), count("thirty_all_return_points")
        ),
    }
    for index in (1, 2, 3):
        service_key = f"early_service_game_{index}"
        service_wins_key = f"{service_key}_holds"
        return_key = f"early_return_game_{index}"
        return_wins_key = f"{return_key}_breaks"
        out[service_key] = count(service_key)
        out[service_wins_key] = count(service_wins_key)
        out[f"{service_key}_hold_rate"] = _rate(
            count(service_wins_key), count(service_key)
        )
        out[return_key] = count(return_key)
        out[return_wins_key] = count(return_wins_key)
        out[f"{return_key}_break_rate"] = _rate(
            count(return_wins_key), count(return_key)
        )
    return out


def _accumulate(target: dict[str, int], contribution: dict[str, int]) -> None:
    target["matches"] += 1
    for key in ACCUMULATE_KEYS:
        target[key] += int(contribution.get(key) or 0)

def _rolling_window(
    history: list[dict[str, int]],
    window: int,
) -> dict[str, Any]:
    selected = history[-window:]
    aggregate = _empty_stats()
    for contribution in selected:
        _accumulate(aggregate, contribution)
    projected = _project(aggregate)
    return {
        **projected,
        "requested_matches": int(window),
        "matches_used": len(selected),
        "window_full": len(selected) >= window,
        "match_coverage": round(len(selected) / window, 6) if window else 0.0,
    }


def _rate_delta(
    left: dict[str, Any],
    right: dict[str, Any],
    key: str,
) -> float | None:
    a = left.get(key)
    b = right.get(key)
    if not isinstance(a, (int, float)) or isinstance(a, bool):
        return None
    if not isinstance(b, (int, float)) or isinstance(b, bool):
        return None
    return round(float(a) - float(b), 6)


def _rolling_family(history: list[dict[str, int]]) -> dict[str, Any]:
    windows = {
        f"L{window}": _rolling_window(history, window)
        for window in ROLLING_WINDOWS
    }
    l5 = windows["L5"]
    l10 = windows["L10"]
    l20 = windows["L20"]

    rate_fields = {
        "serve": "serve_win_rate",
        "return": "return_win_rate",
        "hold": "hold_rate",
        "break": "break_rate",
        "bp_save": "bp_save_rate",
        "bp_conversion": "bp_conversion_rate",
        "deuce_serve": "deuce_serve_win_rate",
        "deuce_return": "deuce_return_win_rate",
        "thirty_all_serve": "thirty_all_serve_win_rate",
        "thirty_all_return": "thirty_all_return_win_rate",
    }
    for index in (1, 2, 3):
        rate_fields[f"early_service_game_{index}_hold"] = (
            f"early_service_game_{index}_hold_rate"
        )
        rate_fields[f"early_return_game_{index}_break"] = (
            f"early_return_game_{index}_break_rate"
        )

    trend: dict[str, float | None] = {}
    for label, key in rate_fields.items():
        trend[f"{label}_l5_minus_l10"] = _rate_delta(l5, l10, key)
        trend[f"{label}_l5_minus_l20"] = _rate_delta(l5, l20, key)

    return {
        "windows": windows,
        "trend": trend,
    }

def _rolling_prior(
    overall_history: list[dict[str, int]],
    surface_history: list[dict[str, int]],
    surface: str,
) -> dict[str, Any]:
    return {
        "all_surface": _rolling_family(overall_history),
        "same_surface": {
            "surface": surface,
            **_rolling_family(surface_history),
        },
        "policy": {
            "strictly_prior_matches_only": True,
            "same_time_matches_never_count_as_prior": True,
            "raw_windows_are_diagnostic_only": True,
            "training_join_enabled": False,
            "shrinkage_activation_enabled": False,
            "shrinkage_requires_separate_data_driven_gate": True,
            "long_baseline_remains_overall_prior": True,
        },
    }


def _player_side(player_id: int, p1: int, p2: int) -> int | None:
    if player_id == p1:
        return 1
    if player_id == p2:
        return 2
    return None


def _standard_pressure_state(
    row: dict[str, Any],
    p1: int,
    p2: int,
    server_player_id: int,
    receiver_player_id: int,
) -> tuple[int, int, int, str, str] | None:
    if row.get("is_tiebreak_before") is True:
        return None
    score = row.get("score_before")
    if not isinstance(score, dict):
        return None
    points = score.get("points")
    if not isinstance(points, list) or len(points) < 2:
        return None

    server_side = _player_side(server_player_id, p1, p2)
    receiver_side = _player_side(receiver_player_id, p1, p2)
    if server_side not in (1, 2) or receiver_side not in (1, 2) or server_side == receiver_side:
        return None

    server_token = point_token(points[server_side - 1])
    receiver_token = point_token(points[receiver_side - 1])
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


def _strict_atomic_game(row: dict[str, Any]) -> bool:
    return bool(
        row.get("transition_kind") == "game_score_changed"
        and row.get("trainable_point") is True
        and row.get("atomic_transition") is True
        and row.get("atomic_reason") == "atomic_game_boundary"
    )


def _pressure_contract() -> dict[str, Any]:
    return {
        "included_in_canonical_profiles": True,
        "shadow_only": True,
        "training_join_enabled": False,
        "scorer_feature_activation_enabled": False,
        "canonical_score_semantics": "backend.atomic_point_transition",
        "strict_atomic_game_boundaries_only": True,
        "set_boundary_reconstruction_enabled": False,
        "missing_game_reconstruction_enabled": False,
        "tiebreak_excluded_from_standard_bp_deuce_metrics": True,
        "early_game_order": "observed_proven_atomic_boundaries_only",
        "raw_support_counts_accompany_every_rate": True,
        "rolling_windows": list(ROLLING_WINDOWS),
    }


def _prepare_matches(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    matches: dict[str, dict[str, Any]] = {}
    counters = Counter()

    for row_index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        counters["point_rows_seen"] += 1
        if row.get("context_ready_player_point") is not True:
            counters["non_strict_rows_skipped"] += 1
            if row.get("atomic_reason") == "set_boundary_not_yet_proven":
                counters["set_boundary_not_yet_proven_rows_excluded"] += 1
            continue

        match_id = str(row.get("match_id") or "").strip()
        scheduled = _parse_utc(row.get("match_scheduled_time"))
        p1 = row.get("p1_player_id")
        p2 = row.get("p2_player_id")
        server = row.get("server_player_id")
        receiver = row.get("receiver_player_id")
        if (
            not match_id or scheduled is None
            or isinstance(p1, bool) or not isinstance(p1, int)
            or isinstance(p2, bool) or not isinstance(p2, int)
            or isinstance(server, bool) or not isinstance(server, int)
            or isinstance(receiver, bool) or not isinstance(receiver, int)
        ):
            counters["strict_rows_with_invalid_identity_or_time"] += 1
            continue

        surface = str(row.get("surface") or "unknown")
        entry = matches.setdefault(match_id, {
            "match_id": match_id,
            "scheduled": scheduled,
            "surface": surface,
            "tour": row.get("tour"),
            "format": row.get("match_format"),
            "round_code": row.get("round_code"),
            "p1": p1,
            "p2": p2,
            "p1_ranking": row.get("p1_ranking"),
            "p2_ranking": row.get("p2_ranking"),
            "contrib": {p1: _empty_stats(), p2: _empty_stats()},
            "game_boundaries": [],
            "conflict": False,
        })

        if (
            entry["scheduled"] != scheduled or entry["surface"] != surface
            or entry["p1"] != p1 or entry["p2"] != p2
        ):
            entry["conflict"] = True
            counters["conflicting_rows"] += 1
            continue

        for pid in (p1, p2):
            entry["contrib"].setdefault(pid, _empty_stats())

        if server not in entry["contrib"] or receiver not in entry["contrib"] or server == receiver:
            entry["conflict"] = True
            counters["side_identity_conflicts"] += 1
            continue

        server_stats = entry["contrib"][server]
        receiver_stats = entry["contrib"][receiver]
        server_stats["serve_points"] += 1
        server_stats["serve_wins"] += int(row.get("server_won") is True)
        receiver_stats["return_points"] += 1
        receiver_stats["return_wins"] += int(row.get("receiver_won") is True)

        pressure = _standard_pressure_state(row, p1, p2, server, receiver)
        if pressure is not None:
            _, receiver_gp, deuce, server_token, receiver_token = pressure
            if receiver_gp == 1:
                server_stats["bp_faced"] += 1
                receiver_stats["bp_chances"] += 1
                counters["break_point_opportunities_used"] += 1
                if row.get("server_won") is True:
                    server_stats["bp_saved"] += 1
                elif row.get("server_won") is False:
                    receiver_stats["bp_converted"] += 1

            if deuce == 1:
                server_stats["deuce_serve_points"] += 1
                receiver_stats["deuce_return_points"] += 1
                server_stats["deuce_serve_wins"] += int(row.get("server_won") is True)
                receiver_stats["deuce_return_wins"] += int(row.get("receiver_won") is True)
                counters["deuce_points_used"] += 1

            if server_token == "30" and receiver_token == "30":
                server_stats["thirty_all_serve_points"] += 1
                receiver_stats["thirty_all_return_points"] += 1
                server_stats["thirty_all_serve_wins"] += int(row.get("server_won") is True)
                receiver_stats["thirty_all_return_wins"] += int(row.get("receiver_won") is True)
                counters["thirty_all_points_used"] += 1

        if _strict_atomic_game(row):
            held = row.get("server_won") is True
            server_stats["service_games"] += 1
            receiver_stats["return_games"] += 1
            server_stats["holds"] += int(held)
            receiver_stats["breaks"] += int(not held)
            counters["strict_atomic_games_used"] += 1
            event_index = row.get("event_index")
            if isinstance(event_index, bool) or not isinstance(event_index, int):
                event_index = row_index
            entry["game_boundaries"].append(
                (int(event_index), int(server), int(receiver), bool(held))
            )

        if row.get("is_tiebreak_before") is True:
            winner = row.get("point_winner")
            winner_id = p1 if winner == 1 else p2 if winner == 2 else None
            for pid in (p1, p2):
                entry["contrib"][pid]["tiebreak_points"] += 1
                entry["contrib"][pid]["tiebreak_wins"] += int(winner_id == pid)

        counters["strict_rows_used"] += 1

    valid = []
    for entry in matches.values():
        serve_seen: Counter[int] = Counter()
        return_seen: Counter[int] = Counter()
        for _, server, receiver, held in sorted(entry.get("game_boundaries") or []):
            serve_seen[server] += 1
            return_seen[receiver] += 1
            serve_index = int(serve_seen[server])
            return_index = int(return_seen[receiver])
            if serve_index <= 3:
                key = f"early_service_game_{serve_index}"
                entry["contrib"][server][key] += 1
                entry["contrib"][server][f"{key}_holds"] += int(held)
                counters[f"{key}_used"] += 1
            if return_index <= 3:
                key = f"early_return_game_{return_index}"
                entry["contrib"][receiver][key] += 1
                entry["contrib"][receiver][f"{key}_breaks"] += int(not held)
                counters[f"{key}_used"] += 1
        entry.pop("game_boundaries", None)

        if entry.get("conflict"):
            counters["conflicting_matches_rejected"] += 1
            continue
        if not any(
            int(stats.get("serve_points") or 0) + int(stats.get("return_points") or 0) > 0
            for stats in entry["contrib"].values()
        ):
            counters["empty_strict_matches_rejected"] += 1
            continue
        valid.append(entry)

    valid.sort(key=lambda m: (m["scheduled"], m["match_id"]))
    counters["strict_matches"] = len(valid)
    return valid, dict(counters)

def build_snapshots_from_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    matches, source_counts = _prepare_matches(rows)

    overall: dict[int, dict[str, int]] = defaultdict(_empty_stats)
    by_surface: dict[int, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(_empty_stats))
    rolling_overall: dict[int, list[dict[str, int]]] = defaultdict(list)
    rolling_by_surface: dict[int, dict[str, list[dict[str, int]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    snapshots: list[dict[str, Any]] = []
    readiness_any = Counter()
    readiness_surface = Counter()
    same_time_groups = 0

    for scheduled, group_iter in groupby(matches, key=lambda m: m["scheduled"]):
        group = list(group_iter)
        if len(group) > 1:
            same_time_groups += 1

        # Snapshot the entire time group before adding any of its matches.
        for match in group:
            for side, pid, opponent, ranking, opponent_ranking in (
                ("p1", match["p1"], match["p2"], match.get("p1_ranking"), match.get("p2_ranking")),
                ("p2", match["p2"], match["p1"], match.get("p2_ranking"), match.get("p1_ranking")),
            ):
                overall_snapshot = _project(overall.get(pid))
                surface_snapshot = _project(by_surface.get(pid, {}).get(match["surface"]))

                for threshold in THRESHOLDS:
                    readiness_any[threshold] += int(overall_snapshot["matches"] >= threshold)
                    readiness_surface[threshold] += int(surface_snapshot["matches"] >= threshold)

                snapshots.append({
                    "version": VERSION,
                    "mode": "SHADOW_AS_OF_PROFILE",
                    "production_influence": False,
                    "training_join_enabled": False,
                    "profile_threshold_activation_enabled": False,
                    "strict_as_of": True,
                    "same_time_matches_count_as_prior": False,
                    "target_match_id": match["match_id"],
                    "target_scheduled_time": scheduled.isoformat(),
                    "target_surface": match["surface"],
                    "target_tour": match.get("tour"),
                    "target_format": match.get("format"),
                    "target_round_code": match.get("round_code"),
                    "player_side": side,
                    "player_id": pid,
                    "opponent_id": opponent,
                    "player_ranking": ranking,
                    "opponent_ranking": opponent_ranking,
                    "overall_prior": overall_snapshot,
                    "same_surface_prior": surface_snapshot,
                    "rolling_prior": _rolling_prior(
                        rolling_overall.get(pid, []),
                        rolling_by_surface.get(pid, {}).get(match["surface"], []),
                        match["surface"],
                    ),
                })

        # Only after all snapshots at this timestamp exist does history advance.
        for match in group:
            for pid in (match["p1"], match["p2"]):
                contribution = match["contrib"][pid]
                _accumulate(overall[pid], contribution)
                _accumulate(by_surface[pid][match["surface"]], contribution)
                rolling_overall[pid].append(dict(contribution))
                rolling_by_surface[pid][match["surface"]].append(dict(contribution))

    targets = len(snapshots)
    players = {int(row["player_id"]) for row in snapshots}
    summary = {
        "version": VERSION,
        "mode": "SHADOW_AS_OF_PROFILE",
        "source": "player-dna-point-dataset-v3 strict context-ready rows",
        "network_calls": 0,
        "production_influence": False,
        "training_join_enabled": False,
        "profile_threshold_activation_enabled": False,
        "strict_as_of_policy": "prior_match_scheduled_time < target_match_scheduled_time",
        "same_time_matches_count_as_prior": False,
        "strict_matches": int(source_counts.get("strict_matches") or 0),
        "player_match_snapshots": targets,
        "players": len(players),
        "same_time_groups": same_time_groups,
        "source_counts": source_counts,
        "readiness_any_surface": {
            str(threshold): {
                "targets": int(readiness_any[threshold]),
                "rate": round(readiness_any[threshold] / targets, 6) if targets else 0.0,
            }
            for threshold in THRESHOLDS
        },
        "readiness_same_surface": {
            str(threshold): {
                "targets": int(readiness_surface[threshold]),
                "rate": round(readiness_surface[threshold] / targets, 6) if targets else 0.0,
            }
            for threshold in THRESHOLDS
        },
        "features": {
            "overall_prior": list(_project(None).keys()),
            "same_surface_prior": list(_project(None).keys()),
            "rolling_prior": {
                "windows": list(ROLLING_WINDOWS),
                "all_surface": True,
                "same_surface": True,
                "trend_l5_vs_l10_l20": True,
                "pressure_rates_in_windows": True,
                "raw_support_counts": True,
                "training_join_enabled": False,
                "shrinkage_activation_enabled": False,
                "shrinkage_requires_separate_data_driven_gate": True,
            },
        },
        "pressure_profiles": _pressure_contract(),
        "note": (
            "SHADOW evidence only. Raw support counts accompany every rate. "
            "No minimum-history threshold, training join or production influence is activated."
        ),
    }
    return snapshots, summary



def build_current_target_profiles(
    point_rows: Iterable[dict[str, Any]],
    targets: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build SHADOW as-of profiles for current card using stable provider IDs only."""
    historical, source_counts = _prepare_matches(point_rows)

    normalized_targets = []
    rejected = Counter()
    target_ids = set()
    for raw in targets:
        if not isinstance(raw, dict):
            rejected["not_dict"] += 1
            continue
        match_id = str(raw.get("id") or raw.get("match_id") or "").strip()
        scheduled = _parse_utc(raw.get("scheduled_time"))
        p1 = raw.get("p1_id")
        p2 = raw.get("p2_id")
        if (
            not match_id or scheduled is None
            or isinstance(p1, bool) or not isinstance(p1, int)
            or isinstance(p2, bool) or not isinstance(p2, int)
            or p1 == p2
        ):
            rejected["missing_stable_identity_or_time"] += 1
            continue

        surface = str(raw.get("surface") or "unknown").strip().lower()
        tour = str(raw.get("tour") or "unknown").strip().upper()
        best_of = raw.get("best_of")
        match_format = f"BO{int(best_of)}" if isinstance(best_of, int) and not isinstance(best_of, bool) else "unknown"
        p1_rank = raw.get("p1_rank")
        p2_rank = raw.get("p2_rank")
        if isinstance(p1_rank, bool) or not isinstance(p1_rank, int) or p1_rank <= 0:
            p1_rank = None
        if isinstance(p2_rank, bool) or not isinstance(p2_rank, int) or p2_rank <= 0:
            p2_rank = None

        normalized_targets.append({
            "match_id": match_id,
            "scheduled": scheduled,
            "surface": surface,
            "tour": tour,
            "format": match_format,
            "p1": p1,
            "p2": p2,
            "p1_name": raw.get("p1"),
            "p2_name": raw.get("p2"),
            "p1_ranking": p1_rank,
            "p2_ranking": p2_rank,
        })
        target_ids.add(match_id)

    # Never allow any match currently on the card to become profile history,
    # even if PBP cache already contains partial/final observations for it.
    history = [match for match in historical if match["match_id"] not in target_ids]
    history.sort(key=lambda m: (m["scheduled"], m["match_id"]))
    normalized_targets.sort(key=lambda m: (m["scheduled"], m["match_id"]))

    overall: dict[int, dict[str, int]] = defaultdict(_empty_stats)
    by_surface: dict[int, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(_empty_stats))
    rolling_overall: dict[int, list[dict[str, int]]] = defaultdict(list)
    rolling_by_surface: dict[int, dict[str, list[dict[str, int]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    latest_provider_rank: dict[int, dict[str, Any]] = {}
    snapshots: list[dict[str, Any]] = []
    hist_index = 0
    excluded_current_history_matches = len(historical) - len(history)

    for scheduled, target_group_iter in groupby(normalized_targets, key=lambda m: m["scheduled"]):
        while hist_index < len(history) and history[hist_index]["scheduled"] < scheduled:
            match = history[hist_index]
            for side, pid, ranking in (
                ("p1", match["p1"], match.get("p1_ranking")),
                ("p2", match["p2"], match.get("p2_ranking")),
            ):
                _accumulate(overall[pid], match["contrib"][pid])
                _accumulate(by_surface[pid][match["surface"]], match["contrib"][pid])
                rolling_overall[pid].append(dict(match["contrib"][pid]))
                rolling_by_surface[pid][match["surface"]].append(
                    dict(match["contrib"][pid])
                )
                if (
                    isinstance(ranking, int)
                    and not isinstance(ranking, bool)
                    and ranking > 0
                ):
                    latest_provider_rank[pid] = {
                        "ranking": ranking,
                        "source_match_id": match["match_id"],
                        "source_scheduled_time": match["scheduled"].isoformat(),
                        "player_side": side,
                    }
            hist_index += 1

        target_group = list(target_group_iter)
        for target in target_group:
            for side, pid, opponent, name, opponent_name, ranking, opponent_ranking in (
                (
                    "p1", target["p1"], target["p2"],
                    target.get("p1_name"), target.get("p2_name"),
                    target.get("p1_ranking"), target.get("p2_ranking"),
                ),
                (
                    "p2", target["p2"], target["p1"],
                    target.get("p2_name"), target.get("p1_name"),
                    target.get("p2_ranking"), target.get("p1_ranking"),
                ),
            ):
                player_prior_rank = latest_provider_rank.get(pid) or {}
                opponent_prior_rank = latest_provider_rank.get(opponent) or {}
                effective_ranking = (
                    ranking
                    if isinstance(ranking, int) and not isinstance(ranking, bool) and ranking > 0
                    else player_prior_rank.get("ranking")
                )
                effective_opponent_ranking = (
                    opponent_ranking
                    if isinstance(opponent_ranking, int)
                    and not isinstance(opponent_ranking, bool)
                    and opponent_ranking > 0
                    else opponent_prior_rank.get("ranking")
                )
                player_rank_source = (
                    "current_fixture_provider"
                    if ranking is not None
                    else "latest_strict_prior_provider_match_context"
                    if effective_ranking is not None
                    else None
                )
                opponent_rank_source = (
                    "current_fixture_provider"
                    if opponent_ranking is not None
                    else "latest_strict_prior_provider_match_context"
                    if effective_opponent_ranking is not None
                    else None
                )
                snapshots.append({
                    "version": VERSION,
                    "mode": "SHADOW_CURRENT_AS_OF_PROFILE",
                    "production_influence": False,
                    "training_join_enabled": False,
                    "profile_threshold_activation_enabled": False,
                    "strict_as_of": True,
                    "current_card_excluded_from_history": True,
                    "same_time_matches_count_as_prior": False,
                    "target_match_id": target["match_id"],
                    "target_scheduled_time": scheduled.isoformat(),
                    "target_surface": target["surface"],
                    "target_tour": target["tour"],
                    "target_format": target["format"],
                    "player_side": side,
                    "player_id": pid,
                    "player_name": name,
                    "opponent_id": opponent,
                    "opponent_name": opponent_name,
                    "player_ranking": effective_ranking,
                    "opponent_ranking": effective_opponent_ranking,
                    "player_ranking_source": player_rank_source,
                    "opponent_ranking_source": opponent_rank_source,
                    "player_ranking_source_match_id": (
                        None if player_rank_source == "current_fixture_provider"
                        else player_prior_rank.get("source_match_id")
                    ),
                    "opponent_ranking_source_match_id": (
                        None if opponent_rank_source == "current_fixture_provider"
                        else opponent_prior_rank.get("source_match_id")
                    ),
                    "player_ranking_source_scheduled_time": (
                        None if player_rank_source == "current_fixture_provider"
                        else player_prior_rank.get("source_scheduled_time")
                    ),
                    "opponent_ranking_source_scheduled_time": (
                        None if opponent_rank_source == "current_fixture_provider"
                        else opponent_prior_rank.get("source_scheduled_time")
                    ),
                    "overall_prior": _project(overall.get(pid)),
                    "same_surface_prior": _project(by_surface.get(pid, {}).get(target["surface"])),
                    "rolling_prior": _rolling_prior(
                        rolling_overall.get(pid, []),
                        rolling_by_surface.get(pid, {}).get(target["surface"], []),
                        target["surface"],
                    ),
                })

    players = {row["player_id"] for row in snapshots}
    summary = {
        "version": VERSION,
        "mode": "SHADOW_CURRENT_AS_OF_PROFILE",
        "production_influence": False,
        "training_join_enabled": False,
        "profile_threshold_activation_enabled": False,
        "strict_as_of_policy": "history_match_scheduled_time < current_target_scheduled_time",
        "current_card_excluded_from_history": True,
        "same_time_matches_count_as_prior": False,
        "rolling_profiles": {
            "windows": list(ROLLING_WINDOWS),
            "all_surface": True,
            "same_surface": True,
            "trend_l5_vs_l10_l20": True,
            "pressure_rates_in_windows": True,
            "training_join_enabled": False,
            "shrinkage_activation_enabled": False,
            "shrinkage_requires_separate_data_driven_gate": True,
        },
        "pressure_profiles": _pressure_contract(),
        "targets_seen": len(normalized_targets),
        "snapshots": len(snapshots),
        "players": len(players),
        "excluded_current_history_matches": excluded_current_history_matches,
        "ranking_context": {
            "provider_backed_only": True,
            "name_or_fuzzy_fallback_forbidden": True,
            "current_fixture_preferred": True,
            "strict_prior_provider_context_fallback_enabled": True,
            "snapshots_with_player_rank": sum(
                1 for row in snapshots if row.get("player_ranking") is not None
            ),
            "snapshots_with_current_fixture_player_rank": sum(
                1 for row in snapshots
                if row.get("player_ranking_source") == "current_fixture_provider"
            ),
            "snapshots_with_prior_provider_player_rank": sum(
                1 for row in snapshots
                if row.get("player_ranking_source") == "latest_strict_prior_provider_match_context"
            ),
        },
        "source_counts": source_counts,
        "rejected_targets": dict(rejected),
    }
    return snapshots, summary

def build() -> dict[str, Any]:
    snapshots, summary = build_snapshots_from_rows(iter_point_rows() or ())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(OUT_JSONL, "wt", encoding="utf-8") as handle:
        for row in snapshots:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    summary["dataset_path"] = str(OUT_JSONL.relative_to(ROOT))
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    build()
