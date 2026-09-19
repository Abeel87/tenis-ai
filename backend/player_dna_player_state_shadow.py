from __future__ import annotations

"""Leakage-safe descriptive Player State for Player DNA (SHADOW only).

LOGIC-07 deliberately separates long-term Player DNA from short/current player
state. This module does not fit a model, does not create probabilities and does
not alter the PROD Current Engine. It reuses the canonical strict-as-of Player
DNA match timeline and LOGIC-06 opponent-adjusted expectations, then exposes
auditable descriptive state with raw support/provenance.

All state for a target match is frozen before that target (and before every
other match sharing its provider timestamp) is allowed to enter history.
"""

import gzip
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.player_dna_shadow_profiles import (
        _accumulate,
        _empty_stats,
        _prepare_matches,
        _project,
        build_current_target_profiles,
        iter_point_rows,
        iter_service_split_matches,
    )
    from backend.player_dna_opponent_adjustment_audit import (
        _adjusted_components,
        build_target_adjustment_index,
    )
except ModuleNotFoundError:  # direct execution compatibility
    from player_dna_shadow_profiles import (
        _accumulate,
        _empty_stats,
        _prepare_matches,
        _project,
        build_current_target_profiles,
        iter_point_rows,
        iter_service_split_matches,
    )
    from player_dna_opponent_adjustment_audit import (
        _adjusted_components,
        build_target_adjustment_index,
    )

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "data" / "derived" / "player_dna" / "profile_snapshots.jsonl.gz"
RESULTS = ROOT / "frontend" / "data" / "results.json"
RECENT_FORM_REPORT = ROOT / "frontend" / "data" / "player_dna_recent_form_challenger.json"
OUT = ROOT / "frontend" / "data" / "player_dna_player_state_shadow.json"

VERSION = "player-dna-player-state-shadow-v1"
MODE = "SHADOW_PLAYER_STATE_DESCRIPTIVE_ONLY"
GAP_SCENARIOS_DAYS = (30, 60, 90, 180)
RATE_FIELDS = ("serve_win_rate", "return_win_rate", "hold_rate", "break_rate")
TREND_LABELS = ("serve", "return", "hold", "break")


def _parse_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _iter_jsonl_gz(path: Path) -> Iterable[dict[str, Any]]:
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


def _rate_delta(left: dict[str, Any], right: dict[str, Any], key: str) -> float | None:
    a = _finite(left.get(key))
    b = _finite(right.get(key))
    return round(a - b, 6) if a is not None and b is not None else None


def _season_delta(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_minus_previous": {
            key: _rate_delta(current, previous, key)
            for key in RATE_FIELDS
        },
        "support": {
            "current_matches": int(current.get("matches") or 0),
            "previous_matches": int(previous.get("matches") or 0),
        },
        "activation_enabled": False,
    }


def _compact_window(raw: Any) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    return {
        "requested_matches": int(raw.get("requested_matches") or 0),
        "matches_used": int(raw.get("matches_used") or raw.get("matches") or 0),
        "window_full": bool(raw.get("window_full") is True),
        "match_coverage": _finite(raw.get("match_coverage")),
        "serve_win_rate": _finite(raw.get("serve_win_rate")),
        "return_win_rate": _finite(raw.get("return_win_rate")),
        "hold_rate": _finite(raw.get("hold_rate")),
        "break_rate": _finite(raw.get("break_rate")),
    }


def _rolling_state(profile: dict[str, Any] | None, recent_form_status: str | None) -> dict[str, Any]:
    profile = profile if isinstance(profile, dict) else {}
    rolling = profile.get("rolling_prior") if isinstance(profile.get("rolling_prior"), dict) else {}
    all_surface = rolling.get("all_surface") if isinstance(rolling.get("all_surface"), dict) else {}
    same_surface = rolling.get("same_surface") if isinstance(rolling.get("same_surface"), dict) else {}
    all_windows = all_surface.get("windows") if isinstance(all_surface.get("windows"), dict) else {}
    surface_windows = same_surface.get("windows") if isinstance(same_surface.get("windows"), dict) else {}
    all_trend = all_surface.get("trend") if isinstance(all_surface.get("trend"), dict) else {}
    surface_trend = same_surface.get("trend") if isinstance(same_surface.get("trend"), dict) else {}

    def selected_trends(source: dict[str, Any]) -> dict[str, Any]:
        out = {}
        for label in TREND_LABELS:
            for suffix in ("l5_minus_l10", "l5_minus_l20"):
                key = f"{label}_{suffix}"
                out[key] = _finite(source.get(key))
        return out

    return {
        "recent_form_l5": {
            "all_surface": _compact_window(all_windows.get("L5")),
            "same_surface": _compact_window(surface_windows.get("L5")),
            "historical_evidence_status": recent_form_status,
            "descriptive_only": True,
            "probability_feature_enabled": False,
            "weight_enabled": False,
            "promotion_enabled": False,
        },
        "serve_return_hold_break_trend": {
            "all_surface": selected_trends(all_trend),
            "same_surface": selected_trends(surface_trend),
            "source": "backend.player_dna_shadow_profiles.rolling_prior",
            "descriptive_only": True,
        },
    }


def _profile_index(profile_rows: Iterable[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for row in profile_rows:
        if not isinstance(row, dict):
            continue
        match_id = str(row.get("target_match_id") or "").strip()
        player = _positive_int(row.get("player_id"))
        if not match_id or player is None:
            continue
        if row.get("strict_as_of") is not True:
            continue
        if row.get("same_time_matches_count_as_prior") is not False:
            continue
        out[(match_id, player)] = row
    return out


def _raw_observed_rates(contribution: dict[str, Any]) -> dict[str, float | None]:
    stats = _empty_stats()
    for key, value in contribution.items():
        if key in stats and key != "matches":
            try:
                stats[key] = max(0, int(value))
            except (TypeError, ValueError):
                pass
    stats["matches"] = 1
    projected = _project(stats)
    return {
        "serve": projected.get("serve_win_rate"),
        "return": projected.get("return_win_rate"),
        "hold": projected.get("hold_rate"),
        "break": projected.get("break_rate"),
    }


def _realized_adjusted_residual(
    contribution: dict[str, Any],
    adjustment: dict[str, Any] | None,
) -> dict[str, Any]:
    observed = _raw_observed_rates(contribution)
    adjustment = adjustment if isinstance(adjustment, dict) else {}
    out: dict[str, Any] = {"overall": {}, "surface": {}}
    for context in ("overall", "surface"):
        source = adjustment.get(context) if isinstance(adjustment.get(context), dict) else {}
        for component in ("serve", "return", "hold", "break"):
            expected_item = source.get(component) if isinstance(source.get(component), dict) else {}
            expected = _finite(expected_item.get("expected_rate"))
            actual = _finite(observed.get(component))
            out[context][component] = (
                round(actual - expected, 6)
                if actual is not None and expected is not None
                else None
            )
    return out


def _mean(values: Iterable[Any]) -> float | None:
    clean = []
    for value in values:
        number = _finite(value)
        if number is not None:
            clean.append(number)
    return round(sum(clean) / len(clean), 6) if clean else None


def _adjusted_trend(
    history: list[dict[str, Any]],
    *,
    target_year: int,
    target_surface: str,
) -> dict[str, Any]:
    def usable(row: dict[str, Any]) -> bool:
        residuals = row.get("residuals") if isinstance(row.get("residuals"), dict) else {}
        overall = residuals.get("overall") if isinstance(residuals.get("overall"), dict) else {}
        surface = residuals.get("surface") if isinstance(residuals.get("surface"), dict) else {}
        return any(
            _finite(value) is not None
            for value in list(overall.values()) + list(surface.values())
        )

    prior = [row for row in history if usable(row)]
    season = [row for row in prior if row["scheduled"].year == target_year]
    surface_season = [
        row for row in season if str(row.get("surface") or "") == target_surface
    ]
    recent = prior[-5:]

    def block(rows: list[dict[str, Any]], context: str) -> dict[str, Any]:
        return {
            component: _mean(
                ((row.get("residuals") or {}).get(context) or {}).get(component)
                for row in rows
            )
            for component in ("serve", "return", "hold", "break")
        }

    return {
        "all_prior_mean": block(prior, "overall"),
        "current_season_mean": block(season, "overall"),
        "current_surface_season_mean": block(surface_season, "surface"),
        "recent_5_match_mean": block(recent, "overall"),
        "support": {
            "all_prior_matches": len(prior),
            "current_season_matches": len(season),
            "current_surface_season_matches": len(surface_season),
            "recent_matches_used": len(recent),
        },
        "expectation_owner": "backend.player_dna_opponent_adjustment_audit.build_target_adjustment_index",
        "descriptive_only": True,
        "probability_feature_enabled": False,
    }


def _ranking_state(
    rank_history: list[dict[str, Any]],
    *,
    target_rank: int | None,
    target_year: int,
) -> dict[str, Any]:
    prior = list(rank_history)
    latest_prior = prior[-1] if prior else None
    effective = target_rank if target_rank is not None else (
        latest_prior.get("rank") if latest_prior else None
    )
    current_season = [row for row in prior if row["scheduled"].year == target_year]
    season_first = current_season[0] if current_season else None

    delta_latest = None
    if target_rank is not None and latest_prior is not None:
        delta_latest = int(target_rank) - int(latest_prior["rank"])

    delta_season_start = None
    if effective is not None and season_first is not None:
        delta_season_start = int(effective) - int(season_first["rank"])

    return {
        "effective_rank": effective,
        "source": (
            "target_provider_context"
            if target_rank is not None
            else "latest_strict_prior_provider_match_context"
            if effective is not None
            else None
        ),
        "latest_prior_rank": latest_prior.get("rank") if latest_prior else None,
        "latest_prior_source_match_id": latest_prior.get("match_id") if latest_prior else None,
        "delta_vs_latest_prior": delta_latest,
        "current_season_first_prior_rank": season_first.get("rank") if season_first else None,
        "delta_vs_current_season_start": delta_season_start,
        "prior_rank_observations": len(prior),
        "current_season_prior_rank_observations": len(current_season),
        "lower_rank_number_is_better": True,
        "descriptive_only": True,
    }


def _gap_state(
    *,
    scheduled: datetime,
    last_match_time: datetime | None,
    trackers: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    days = None
    if last_match_time is not None:
        days = round((scheduled - last_match_time).total_seconds() / 86400.0, 6)

    scenarios = {}
    for window in GAP_SCENARIOS_DAYS:
        prior_tracker = trackers.get(window) or {}
        current_gap = days is not None and days >= window
        scenarios[str(window)] = {
            "window_days": window,
            "current_gap_exceeds_scenario": bool(current_gap),
            "observed_gap_days": days if current_gap else prior_tracker.get("gap_days"),
            "matches_since_observed_gap": 0 if current_gap else prior_tracker.get("matches_since_gap"),
            "gap_return_match_id": None if current_gap else prior_tracker.get("return_match_id"),
            "cause_inferred": False,
            "injury_or_medical_inference": False,
        }
    return {
        "days_since_last_match": days,
        "scenarios": scenarios,
        "single_cutoff_selected": False,
        "scenario_windows_days": list(GAP_SCENARIOS_DAYS),
        "cause_inferred": False,
    }


def _update_gap_trackers(
    trackers: dict[int, dict[str, Any]],
    *,
    scheduled: datetime,
    match_id: str,
    last_match_time: datetime | None,
) -> None:
    if last_match_time is None:
        return
    gap_days = round((scheduled - last_match_time).total_seconds() / 86400.0, 6)
    for window in GAP_SCENARIOS_DAYS:
        if gap_days >= window:
            trackers[window] = {
                "gap_days": gap_days,
                "matches_since_gap": 1,
                "return_match_id": match_id,
            }
        elif window in trackers:
            trackers[window]["matches_since_gap"] = int(
                trackers[window].get("matches_since_gap") or 0
            ) + 1


def _support_confidence(
    *,
    current_season: dict[str, Any],
    previous_season: dict[str, Any],
    current_surface: dict[str, Any],
    previous_surface: dict[str, Any],
    rolling: dict[str, Any],
    adjusted: dict[str, Any],
    ranking: dict[str, Any],
) -> dict[str, Any]:
    l5 = ((rolling.get("recent_form_l5") or {}).get("all_surface") or {})
    available = {
        "current_season": int(current_season.get("matches") or 0) > 0,
        "previous_season": int(previous_season.get("matches") or 0) > 0,
        "current_surface_season": int(current_surface.get("matches") or 0) > 0,
        "previous_surface_season": int(previous_surface.get("matches") or 0) > 0,
        "recent_l5": int(l5.get("matches_used") or 0) > 0,
        "opponent_adjusted_history": int(
            (adjusted.get("support") or {}).get("all_prior_matches") or 0
        ) > 0,
        "provider_rank": ranking.get("effective_rank") is not None,
    }
    return {
        "mode": "RAW_SUPPORT_AND_MISSINGNESS_ONLY",
        "available_components": [key for key, present in available.items() if present],
        "missing_components": [key for key, present in available.items() if not present],
        "support": {
            "current_season_matches": int(current_season.get("matches") or 0),
            "previous_season_matches": int(previous_season.get("matches") or 0),
            "current_surface_season_matches": int(current_surface.get("matches") or 0),
            "previous_surface_season_matches": int(previous_surface.get("matches") or 0),
            "recent_l5_matches_used": int(l5.get("matches_used") or 0),
            "opponent_adjusted_prior_matches": int(
                (adjusted.get("support") or {}).get("all_prior_matches") or 0
            ),
            "provider_rank_observations": int(ranking.get("prior_rank_observations") or 0),
        },
        "numeric_confidence_score": None,
        "activation_threshold": None,
        "strength_proxy_from_support": False,
    }


def _target_rank(match: dict[str, Any], player: int) -> int | None:
    if player == match.get("p1"):
        return _positive_int(match.get("p1_ranking"))
    if player == match.get("p2"):
        return _positive_int(match.get("p2_ranking"))
    return None


def _target_state(
    *,
    match: dict[str, Any],
    player: int,
    opponent: int,
    profile: dict[str, Any] | None,
    season_stats: dict[int, dict[int, dict[str, int]]],
    season_surface_stats: dict[int, dict[int, dict[str, dict[str, int]]]],
    rank_history: dict[int, list[dict[str, Any]]],
    residual_history: dict[int, list[dict[str, Any]]],
    gap_trackers: dict[int, dict[int, dict[str, Any]]],
    last_match_time: dict[int, datetime],
    recent_form_status: str | None,
) -> dict[str, Any]:
    scheduled = match["scheduled"]
    year = scheduled.year
    surface = str(match.get("surface") or "unknown")

    current_raw = season_stats.get(player, {}).get(year)
    previous_raw = season_stats.get(player, {}).get(year - 1)
    current_surface_raw = season_surface_stats.get(player, {}).get(year, {}).get(surface)
    previous_surface_raw = season_surface_stats.get(player, {}).get(year - 1, {}).get(surface)
    current = _project(current_raw)
    previous = _project(previous_raw)
    current_surface = _project(current_surface_raw)
    previous_surface = _project(previous_surface_raw)

    rolling = _rolling_state(profile, recent_form_status)
    ranking = _ranking_state(
        rank_history.get(player, []),
        target_rank=_target_rank(match, player),
        target_year=year,
    )
    adjusted = _adjusted_trend(
        residual_history.get(player, []),
        target_year=year,
        target_surface=surface,
    )
    gap = _gap_state(
        scheduled=scheduled,
        last_match_time=last_match_time.get(player),
        trackers=gap_trackers.get(player, {}),
    )

    return {
        "target_match_id": match["match_id"],
        "target_scheduled_time": scheduled.isoformat(),
        "target_surface": surface,
        "player_id": player,
        "opponent_id": opponent,
        "strict_as_of": True,
        "same_time_matches_count_as_prior": False,
        "target_match_outcome_used_in_state": False,
        "current_season": current,
        "previous_season": previous,
        "season_delta": _season_delta(current, previous),
        "current_surface_state": {
            "surface": surface,
            "current_season": current_surface,
            "previous_season": previous_surface,
            "delta": _season_delta(current_surface, previous_surface),
        },
        "ranking_momentum": ranking,
        **rolling,
        "opponent_adjusted_performance_trend": adjusted,
        "inactivity": gap,
        "support_confidence": _support_confidence(
            current_season=current,
            previous_season=previous,
            current_surface=current_surface,
            previous_surface=previous_surface,
            rolling=rolling,
            adjusted=adjusted,
            ranking=ranking,
        ),
        "provenance": {
            "timeline_owner": "backend.player_dna_shadow_profiles._prepare_matches",
            "rolling_owner": "backend.player_dna_shadow_profiles.rolling_prior",
            "opponent_adjusted_owner": "backend.player_dna_opponent_adjustment_audit",
            "identity": "stable_provider_player_id",
            "surface_isolated": True,
            "season_boundary": "UTC calendar year of provider scheduled_time",
        },
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "training_join_enabled": False,
        "player_dna_write_enabled": False,
        "current_engine_write_enabled": False,
        "probability_feature_activation_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "promotion_gate": False,
    }


def build_historical_state_rows(
    matches: Iterable[dict[str, Any]],
    profile_rows: Iterable[dict[str, Any]],
    *,
    recent_form_status: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build strict-prior state for historical targets.

    Entire same-provider-timestamp groups are snapshotted before any member of
    the group updates season, ranking, gap, or realized adjusted-performance
    history.
    """

    ordered = sorted(
        [dict(row) for row in matches if isinstance(row, dict)],
        key=lambda row: (row.get("scheduled"), str(row.get("match_id") or "")),
    )
    profiles_list = list(profile_rows)
    profiles = _profile_index(profiles_list)
    adjustment_index, adjustment_counts = build_target_adjustment_index(profiles_list)

    season_stats = defaultdict(lambda: defaultdict(_empty_stats))
    season_surface_stats = defaultdict(lambda: defaultdict(lambda: defaultdict(_empty_stats)))
    rank_history: dict[int, list[dict[str, Any]]] = defaultdict(list)
    residual_history: dict[int, list[dict[str, Any]]] = defaultdict(list)
    gap_trackers: dict[int, dict[int, dict[str, Any]]] = defaultdict(dict)
    last_match_time: dict[int, datetime] = {}

    rows: list[dict[str, Any]] = []
    same_time_groups = 0

    for scheduled, group_iter in groupby(ordered, key=lambda row: row.get("scheduled")):
        if not isinstance(scheduled, datetime):
            continue
        group = list(group_iter)
        if len(group) > 1:
            same_time_groups += 1

        for match in group:
            match_id = str(match.get("match_id") or "")
            p1 = _positive_int(match.get("p1"))
            p2 = _positive_int(match.get("p2"))
            if not match_id or p1 is None or p2 is None or p1 == p2:
                continue
            for player, opponent in ((p1, p2), (p2, p1)):
                rows.append(
                    _target_state(
                        match=match,
                        player=player,
                        opponent=opponent,
                        profile=profiles.get((match_id, player)),
                        season_stats=season_stats,
                        season_surface_stats=season_surface_stats,
                        rank_history=rank_history,
                        residual_history=residual_history,
                        gap_trackers=gap_trackers,
                        last_match_time=last_match_time,
                        recent_form_status=recent_form_status,
                    )
                )

        for match in group:
            match_id = str(match.get("match_id") or "")
            surface = str(match.get("surface") or "unknown")
            p1 = _positive_int(match.get("p1"))
            p2 = _positive_int(match.get("p2"))
            if not match_id or p1 is None or p2 is None or p1 == p2:
                continue
            for player in (p1, p2):
                contribution = (match.get("contrib") or {}).get(player)
                if not isinstance(contribution, dict):
                    continue

                _update_gap_trackers(
                    gap_trackers[player],
                    scheduled=scheduled,
                    match_id=match_id,
                    last_match_time=last_match_time.get(player),
                )
                _accumulate(season_stats[player][scheduled.year], contribution)
                _accumulate(season_surface_stats[player][scheduled.year][surface], contribution)

                rank = _target_rank(match, player)
                if rank is not None:
                    rank_history[player].append(
                        {"scheduled": scheduled, "match_id": match_id, "rank": rank}
                    )

                residual_history[player].append(
                    {
                        "scheduled": scheduled,
                        "match_id": match_id,
                        "surface": surface,
                        "residuals": _realized_adjusted_residual(
                            contribution,
                            adjustment_index.get((match_id, player)),
                        ),
                    }
                )
                last_match_time[player] = scheduled

    return rows, {
        "target_states": len(rows),
        "paired_matches": len(ordered),
        "same_time_groups": same_time_groups,
        "profile_targets": len(profiles),
        "adjustment_counts": adjustment_counts,
    }


def _aggregate_before(
    matches: list[dict[str, Any]],
    *,
    player: int,
    scheduled: datetime,
    excluded_match_ids: set[str],
):
    season = defaultdict(_empty_stats)
    surface = defaultdict(lambda: defaultdict(_empty_stats))
    ranks: list[dict[str, Any]] = []
    last_time: datetime | None = None
    trackers: dict[int, dict[str, Any]] = {}

    for match in matches:
        if match["scheduled"] >= scheduled:
            break
        match_id = str(match.get("match_id") or "")
        if match_id in excluded_match_ids:
            continue
        if player not in (match.get("p1"), match.get("p2")):
            continue
        contribution = (match.get("contrib") or {}).get(player)
        if not isinstance(contribution, dict):
            continue
        _update_gap_trackers(
            trackers,
            scheduled=match["scheduled"],
            match_id=match_id,
            last_match_time=last_time,
        )
        year = match["scheduled"].year
        match_surface = str(match.get("surface") or "unknown")
        _accumulate(season[year], contribution)
        _accumulate(surface[year][match_surface], contribution)
        rank = _target_rank(match, player)
        if rank is not None:
            ranks.append(
                {"scheduled": match["scheduled"], "match_id": match_id, "rank": rank}
            )
        last_time = match["scheduled"]

    return season, surface, ranks, last_time, trackers


def _current_engine_reference(result: dict[str, Any]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for key, value in result.items():
        name = str(key).lower()
        if (
            key in {"model_ready", "model_confidence", "status", "service_model", "model_version"}
            or "prob" in name
        ):
            if value is None or isinstance(value, (str, int, float, bool)):
                selected[key] = value
    return {
        "read_only": True,
        "recomputed": False,
        "source": "frontend/data/results.json existing Current Engine output",
        "selected_existing_fields": selected,
        "source_keys": sorted(str(key) for key in result.keys()),
    }


def build_current_card_states(
    matches: Iterable[dict[str, Any]],
    current_results: Iterable[dict[str, Any]],
    current_profiles: Iterable[dict[str, Any]],
    historical_residual_rows: Iterable[dict[str, Any]],
    *,
    recent_form_status: str | None = None,
) -> list[dict[str, Any]]:
    """Build descriptive state for current fixtures without modifying Current."""

    ordered = sorted(list(matches), key=lambda row: (row["scheduled"], row["match_id"]))
    profiles = _profile_index(current_profiles)
    result_rows = [row for row in current_results if isinstance(row, dict)]
    current_ids = {str(row.get("id") or "") for row in result_rows if row.get("id") is not None}

    residual_by_player: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in historical_residual_rows:
        player = _positive_int(row.get("player_id"))
        if player is not None:
            residual_by_player[player].append(row)

    out = []
    for result in result_rows:
        match_id = str(result.get("id") or "").strip()
        scheduled = _parse_utc(result.get("scheduled_time"))
        p1 = _positive_int(result.get("p1_id"))
        p2 = _positive_int(result.get("p2_id"))
        if not match_id or scheduled is None or p1 is None or p2 is None or p1 == p2:
            continue

        pseudo_match = {
            "match_id": match_id,
            "scheduled": scheduled,
            "surface": str(result.get("surface") or "unknown").strip().lower(),
            "p1": p1,
            "p2": p2,
            "p1_ranking": _positive_int(result.get("p1_rank")),
            "p2_ranking": _positive_int(result.get("p2_rank")),
        }
        match_state = {
            "match_id": match_id,
            "scheduled_time": scheduled.isoformat(),
            "p1_id": p1,
            "p2_id": p2,
            "current_engine_reference": _current_engine_reference(result),
            "player_state": {},
        }

        for side, player, opponent in (("p1", p1, p2), ("p2", p2, p1)):
            season, by_surface, ranks, last_time, trackers = _aggregate_before(
                ordered,
                player=player,
                scheduled=scheduled,
                excluded_match_ids=current_ids,
            )
            residual_history = [
                row for row in residual_by_player.get(player, [])
                if row.get("scheduled") < scheduled
                and str(row.get("match_id") or "") not in current_ids
            ]
            match_state["player_state"][side] = _target_state(
                match=pseudo_match,
                player=player,
                opponent=opponent,
                profile=profiles.get((match_id, player)),
                season_stats={player: season},
                season_surface_stats={player: by_surface},
                rank_history={player: ranks},
                residual_history={player: residual_history},
                gap_trackers={player: trackers},
                last_match_time={player: last_time} if last_time is not None else {},
                recent_form_status=recent_form_status,
            )
        out.append(match_state)
    return out


def _historical_residual_rows(
    matches: Iterable[dict[str, Any]],
    profile_rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    profiles_list = list(profile_rows)
    adjustment_index, _ = build_target_adjustment_index(profiles_list)
    out = []
    for match in sorted(matches, key=lambda row: (row["scheduled"], row["match_id"])):
        match_id = str(match.get("match_id") or "")
        for player in (match.get("p1"), match.get("p2")):
            player = _positive_int(player)
            if player is None:
                continue
            contribution = (match.get("contrib") or {}).get(player)
            if not isinstance(contribution, dict):
                continue
            out.append(
                {
                    "player_id": player,
                    "scheduled": match["scheduled"],
                    "match_id": match_id,
                    "surface": str(match.get("surface") or "unknown"),
                    "residuals": _realized_adjusted_residual(
                        contribution,
                        adjustment_index.get((match_id, player)),
                    ),
                }
            )
    return out


def _summarize_historical(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter()
    for row in rows:
        counts["states"] += 1
        if int((row.get("current_season") or {}).get("matches") or 0) > 0:
            counts["with_current_season_history"] += 1
        if int((row.get("previous_season") or {}).get("matches") or 0) > 0:
            counts["with_previous_season_history"] += 1
        if (row.get("ranking_momentum") or {}).get("effective_rank") is not None:
            counts["with_provider_rank"] += 1
        if int(
            ((row.get("opponent_adjusted_performance_trend") or {}).get("support") or {}).get("all_prior_matches")
            or 0
        ) > 0:
            counts["with_opponent_adjusted_history"] += 1
        l5 = (((row.get("recent_form_l5") or {}).get("all_surface") or {}).get("matches_used") or 0)
        if int(l5) > 0:
            counts["with_recent_l5_history"] += 1
        for window in GAP_SCENARIOS_DAYS:
            scenario = (((row.get("inactivity") or {}).get("scenarios") or {}).get(str(window)) or {})
            if scenario.get("current_gap_exceeds_scenario") is True:
                counts[f"current_gap_ge_{window}d"] += 1

    total = max(1, counts["states"])
    coverage = {
        key: round(value / total, 6)
        for key, value in counts.items()
        if key != "states"
    }
    return {
        "counts": dict(counts),
        "coverage": coverage,
        "sample_first": rows[:2],
        "sample_last": rows[-2:] if rows else [],
    }


def build_state_report(
    matches: Iterable[dict[str, Any]],
    profile_rows: Iterable[dict[str, Any]],
    *,
    current_results: Iterable[dict[str, Any]] = (),
    current_profiles: Iterable[dict[str, Any]] = (),
    recent_form_evidence: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc)
    matches_list = list(matches)
    profiles_list = list(profile_rows)
    evidence = recent_form_evidence if isinstance(recent_form_evidence, dict) else {}
    recent_signal = evidence.get("signal") if isinstance(evidence.get("signal"), dict) else {}
    recent_status = recent_signal.get("status")

    historical_rows, build_counts = build_historical_state_rows(
        matches_list,
        profiles_list,
        recent_form_status=recent_status,
    )
    residual_rows = _historical_residual_rows(matches_list, profiles_list)
    current_card = build_current_card_states(
        matches_list,
        current_results,
        current_profiles,
        residual_rows,
        recent_form_status=recent_status,
    )

    return {
        "version": VERSION,
        "mode": MODE,
        "generated_at": generated_at.isoformat(),
        "status": "PLAYER_STATE_SHADOW_EVIDENCE_READY",
        "network_calls": 0,
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "training_join_enabled": False,
        "canonical_profile_write_enabled": False,
        "player_dna_overwrite": False,
        "current_engine_write_enabled": False,
        "current_engine_recalculation_enabled": False,
        "probability_created": False,
        "weights_created": False,
        "thresholds_created": False,
        "feature_activation": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "auto_promote": False,
        "candidate_may_replace_reference": False,
        "promotion_gate": False,
        "architecture": {
            "player_dna_is_long_term_identity": True,
            "player_state_is_separate_short_current_context": True,
            "timeline_owner": "backend.player_dna_shadow_profiles",
            "opponent_adjusted_owner": "backend.player_dna_opponent_adjustment_audit",
            "recent_form_reference": "backend.player_dna_recent_form_challenger",
            "current_engine_reference_is_read_only": True,
            "legacy_player_trends_is_canonical_source": False,
            "parallel_probability_engine_created": False,
        },
        "recent_form_evidence": {
            "source_status": recent_status,
            "positive_holdout": recent_signal.get("positive_holdout"),
            "robust_walk_forward": recent_signal.get("robust_walk_forward"),
            "fresh_confirmation_required": recent_signal.get("fresh_confirmation_required"),
            "l5_state_activation_enabled": False,
            "l5_probability_feature_enabled": False,
        },
        "gap_policy": {
            "scenario_windows_days": list(GAP_SCENARIOS_DAYS),
            "single_magic_cutoff_selected": False,
            "cause_inference_enabled": False,
            "injury_or_medical_inference_enabled": False,
            "matches_since_gap_counts_completed_return_match": True,
        },
        "leakage_contract": {
            "stable_provider_player_ids_only": True,
            "strictly_prior_history_only": True,
            "same_timestamp_matches_never_count_as_prior": True,
            "target_match_outcome_never_enters_own_state": True,
            "future_match_results_never_used_for_earlier_state": True,
            "season_state_isolated_by_utc_calendar_year": True,
            "surface_state_isolated_by_target_surface": True,
            "opponent_adjusted_expectation_reused_from_logic06": True,
            "current_card_matches_excluded_from_current_state_history": True,
        },
        "build_counts": build_counts,
        "historical_evidence": _summarize_historical(historical_rows),
        "current_card": {
            "matches": current_card,
            "match_count": len(current_card),
            "current_engine_reference_read_only": True,
            "state_does_not_modify_current_engine": True,
        },
    }


def build() -> dict[str, Any]:
    point_rows = list(iter_point_rows() or ())
    service_split_matches = list(iter_service_split_matches() or ())
    matches, source_counts = _prepare_matches(
        point_rows,
        service_split_matches=service_split_matches,
    )
    profile_rows = list(_iter_jsonl_gz(PROFILES) or ())
    current_results = _read_json(RESULTS, [])
    if not isinstance(current_results, list):
        current_results = []
    current_profiles, current_profile_summary = build_current_target_profiles(
        point_rows,
        current_results,
        service_split_matches=service_split_matches,
    )
    recent_form_evidence = _read_json(RECENT_FORM_REPORT, {})

    report = build_state_report(
        matches,
        profile_rows,
        current_results=current_results,
        current_profiles=current_profiles,
        recent_form_evidence=recent_form_evidence,
    )
    report["source_counts"] = source_counts
    report["current_profile_summary"] = current_profile_summary
    report["point_rows_seen"] = len(point_rows)
    report["profile_rows_seen"] = len(profile_rows)
    report["service_split_matches_seen"] = len(service_split_matches)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "version": report["version"],
                "status": report["status"],
                "historical_states": ((report.get("historical_evidence") or {}).get("counts") or {}).get("states"),
                "current_card_matches": (report.get("current_card") or {}).get("match_count"),
                "production_influence": report["production_influence"],
                "probability_created": report["probability_created"],
            },
            ensure_ascii=False,
        )
    )
    return report


if __name__ == "__main__":
    build()
