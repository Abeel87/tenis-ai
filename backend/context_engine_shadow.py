from __future__ import annotations

"""LOGIC-04 SHADOW context engine.

Builds descriptive, provenance-carrying pre-match context from the exact local
TennisMyLife cache and current fixture snapshot. It does not produce predictive
outputs and is not wired into Current, Player DNA, Symphony, PLAYABLE or PROD.
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
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
except ImportError:  # pragma: no cover
    import model
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "frontend" / "data" / "results.json"
ARTIFACT_PATH = ROOT / "artifacts" / "context_engine_shadow.json"
VERSION = "logic-04-context-engine-shadow-v1"
RECORD_LIMIT = 20
GAP_WINDOWS = (30, 60, 90, 180)


def _read_json(path: Path, fallback):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict) and isinstance(value.get("matches"), list):
        return [row for row in value["matches"] if isinstance(row, dict)]
    return []


def _fixture_cut(value: Any) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    stamp = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(stamp):
        return None
    return pd.Timestamp(stamp.date())


def _surface(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text or None


def _positive_rank(value: Any) -> int | None:
    try:
        rank = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(rank) or rank <= 0:
        return None
    return int(round(rank))


def _freshness_bucket(days_old: int | None) -> str | None:
    if days_old is None or days_old < 0:
        return None
    if days_old <= 30:
        return "0-30"
    if days_old <= 60:
        return "31-60"
    if days_old <= 90:
        return "61-90"
    if days_old <= 120:
        return "91-120"
    if days_old <= 180:
        return "121-180"
    if days_old <= 365:
        return "181-365"
    return ">365"


def _season_bucket(date: pd.Timestamp | None, fixture_year: int | None) -> str | None:
    if date is None or pd.isna(date) or fixture_year is None:
        return None
    year = int(pd.Timestamp(date).year)
    if year == fixture_year:
        return "current_season"
    if year == fixture_year - 1:
        return "previous_season"
    if year < fixture_year - 1:
        return "career_prior"
    return None


def _opponent_rank_band(rank: int | None) -> str | None:
    if rank is None:
        return None
    if rank <= 20:
        return "top_20"
    if rank <= 50:
        return "21-50"
    if rank <= 100:
        return "51-100"
    if rank <= 200:
        return "101-200"
    return "201_plus"


def _strict_pre_history(long_df: pd.DataFrame, cut: pd.Timestamp | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    dated = model._dated_history(long_df)
    if dated is None:
        empty = pd.DataFrame()
        return empty, empty
    if dated.empty or cut is None:
        return dated.iloc[0:0].copy(), dated.iloc[0:0].copy()
    dates = pd.to_datetime(dated["date"], errors="coerce").dt.normalize()
    pre = dated[dates < cut].copy()
    same_day = dated[dates == cut].copy()
    return pre, same_day


def _raw_tourney_date(value: Any) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    stamp = pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    return None if pd.isna(stamp) else pd.Timestamp(stamp).normalize()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None


def _raw_event_index(raw_history: pd.DataFrame) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    if raw_history is None or raw_history.empty:
        return {}
    source = model._dedupe_history(raw_history)
    for _, row in source.iterrows():
        date = _raw_tourney_date(row.get("tourney_date"))
        winner = model._key(row.get("winner_name"))
        loser = model._key(row.get("loser_name"))
        if date is None or not winner or not loser:
            continue
        metadata = {
            "event_name": _clean_text(row.get("tourney_name")),
            "event_level": _clean_text(row.get("tourney_level")),
            "source_tour": _clean_text(row.get("source_tour")),
        }
        date_key = date.date().isoformat()
        index[(date_key, winner, loser)].append(dict(metadata))
        index[(date_key, loser, winner)].append(dict(metadata))
    return dict(index)


def _event_metadata(
    event_index: dict[tuple[str, str, str], list[dict[str, Any]]],
    *,
    date: pd.Timestamp,
    player_key: str,
    opponent_key: str,
) -> dict[str, Any]:
    key = (pd.Timestamp(date).date().isoformat(), player_key, opponent_key)
    candidates = event_index.get(key, [])
    unique = {}
    for item in candidates:
        signature = (
            item.get("event_name"),
            item.get("event_level"),
            item.get("source_tour"),
        )
        unique[signature] = item
    if not unique:
        return {
            "event_name": None,
            "event_level": None,
            "resolution": "unavailable",
            "reason": "no_exact_raw_event_match",
        }
    if len(unique) != 1:
        return {
            "event_name": None,
            "event_level": None,
            "resolution": "unavailable",
            "reason": "ambiguous_raw_event_metadata",
        }
    item = next(iter(unique.values()))
    if item.get("event_level") is None:
        reason = "event_level_missing_in_source"
    else:
        reason = None
    return {
        "event_name": item.get("event_name"),
        "event_level": item.get("event_level"),
        "resolution": "direct",
        "reason": reason,
    }


def _gap_windows(dates: list[pd.Timestamp], cut: pd.Timestamp) -> dict[str, Any]:
    dates = sorted(pd.Timestamp(value).normalize() for value in dates if value is not None and not pd.isna(value))
    if not dates:
        return {
            str(window): {
                "threshold_days": window,
                "fixture_gap_meets_threshold": None,
                "matches_played_since_last_observed_gap": None,
                "last_observed_gap_days": None,
            }
            for window in GAP_WINDOWS
        }

    fixture_gap = int((cut - dates[-1]).days)
    diffs = [None] + [int((dates[i] - dates[i - 1]).days) for i in range(1, len(dates))]
    out = {}
    for window in GAP_WINDOWS:
        qualifying = [i for i, gap in enumerate(diffs) if i > 0 and gap is not None and gap >= window]
        if fixture_gap >= window:
            last_gap = fixture_gap
            matches_since = 0
            fixture_meets = True
        elif qualifying:
            idx = qualifying[-1]
            last_gap = diffs[idx]
            matches_since = len(dates) - idx
            fixture_meets = False
        else:
            last_gap = None
            matches_since = None
            fixture_meets = False
        out[str(window)] = {
            "threshold_days": window,
            "fixture_gap_meets_threshold": fixture_meets,
            "matches_played_since_last_observed_gap": matches_since,
            "last_observed_gap_days": last_gap,
        }
    return out


def _record_contexts(
    player_rows: pd.DataFrame,
    *,
    cut: pd.Timestamp,
    fixture_surface: str | None,
    event_index: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    if player_rows.empty:
        return []
    ordered = player_rows.sort_values("date", ascending=True).copy()
    ordered_dates = [pd.Timestamp(value).normalize() for value in ordered["date"].tolist()]
    gaps = [None] + [
        int((ordered_dates[i] - ordered_dates[i - 1]).days)
        for i in range(1, len(ordered_dates))
    ]
    records = []
    for position in range(len(ordered) - 1, max(-1, len(ordered) - 1 - RECORD_LIMIT), -1):
        row = ordered.iloc[position]
        date = ordered_dates[position]
        days_old = int((cut - date).days)
        player_rank = _positive_rank(row.get("rank"))
        opponent_rank = _positive_rank(row.get("opponent_rank"))
        rank_gap = player_rank - opponent_rank if player_rank is not None and opponent_rank is not None else None
        record_surface = _surface(row.get("surface"))
        same_surface = record_surface == fixture_surface if record_surface is not None and fixture_surface is not None else None
        player_key = str(row.get("player_key") or "").strip()
        opponent_key = str(row.get("opponent_key") or "").strip()
        event = _event_metadata(
            event_index,
            date=date,
            player_key=player_key,
            opponent_key=opponent_key,
        )
        records.append({
            "date": date.date().isoformat(),
            "days_old": days_old,
            "freshness_bucket": _freshness_bucket(days_old),
            "season_bucket": _season_bucket(date, cut.year),
            "surface": record_surface,
            "same_surface": same_surface,
            "source_tour": _clean_text(row.get("source_tour")),
            "opponent": _clean_text(row.get("opponent")),
            "player_rank": player_rank,
            "opponent_rank": opponent_rank,
            "rank_gap_player_minus_opponent": rank_gap,
            "opponent_rank_band": _opponent_rank_band(opponent_rank),
            "gap_from_previous_match_days": gaps[position],
            "event_name": event["event_name"],
            "event_level": event["event_level"],
            "event_metadata_resolution": event["resolution"],
            "event_metadata_reason": event["reason"],
            "provenance": {
                "date": {"source": "TML.tourney_date", "resolution": "direct", "granularity": "day"},
                "surface": {"source": "TML.surface", "resolution": "direct" if record_surface else "unavailable"},
                "source_tour": {"source": "update.TML_SOURCES/source_tour", "resolution": "direct"},
                "player_rank": {"source": "TML winner_rank/loser_rank", "resolution": "direct" if player_rank is not None else "unavailable", "observation_date": date.date().isoformat()},
                "opponent_rank": {"source": "TML winner_rank/loser_rank", "resolution": "direct" if opponent_rank is not None else "unavailable", "observation_date": date.date().isoformat()},
                "rank_gap_player_minus_opponent": {"source": "derived from same-record TML ranks", "resolution": "derived" if rank_gap is not None else "unavailable"},
                "opponent_rank_band": {"source": "descriptive rank band only; not opponent-strength score", "resolution": "derived" if opponent_rank is not None else "unavailable"},
                "event_name": {"source": "TML.tourney_name exact raw-row match", "resolution": event["resolution"] if event["event_name"] else "unavailable"},
                "event_level": {"source": "TML.tourney_level exact raw-row match", "resolution": "direct" if event["event_level"] else "unavailable"},
                "gap_from_previous_match_days": {"source": "derived from ordered TML tourney_date", "resolution": "derived" if gaps[position] is not None else "unavailable"},
            },
        })
    return records


def _player_context(
    long_df: pd.DataFrame,
    *,
    player: str,
    cut: pd.Timestamp | None,
    fixture_surface: str | None,
    event_index: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    requested_key = model._key(player)
    if cut is None:
        return {
            "player": player,
            "requested_key": requested_key,
            "identity": {"mode": "none", "resolved_key": None, "reason": "invalid_fixture_time"},
            "history": {"pre_fixture_matches": 0, "same_day_rows_excluded": 0},
            "records": [],
        }

    pre, same_day = _strict_pre_history(long_df, cut)
    resolved_key, identity_mode = model._resolve_history_player_key(pre, player)
    if resolved_key is None:
        return {
            "player": player,
            "requested_key": requested_key,
            "identity": {"mode": identity_mode, "resolved_key": None, "reason": "identity_unresolved_pre_fixture"},
            "history": {"pre_fixture_matches": 0, "same_day_rows_excluded": 0},
            "records": [],
            "provenance": {
                "identity": {
                    "source": "model._resolve_history_player_key",
                    "resolution": "fail_closed",
                    "as_of": "strict pre-fixture dated history only",
                }
            },
        }

    player_rows = pre[pre["player_key"].astype(str) == resolved_key].copy()
    same_day_rows = same_day[same_day["player_key"].astype(str) == resolved_key].copy()
    player_rows = player_rows.sort_values("date", ascending=True)
    dates = [pd.Timestamp(value).normalize() for value in player_rows["date"].tolist()]
    fixture_year = int(cut.year)
    season_counts = Counter(
        _season_bucket(date, fixture_year)
        for date in dates
        if _season_bucket(date, fixture_year) is not None
    )
    latest_date = dates[-1] if dates else None
    inactivity = int((cut - latest_date).days) if latest_date is not None else None

    return {
        "player": player,
        "requested_key": requested_key,
        "identity": {"mode": identity_mode, "resolved_key": resolved_key, "reason": None},
        "history": {
            "pre_fixture_matches": int(len(player_rows)),
            "same_day_rows_excluded": int(len(same_day_rows)),
            "history_date_granularity": "day",
            "same_day_policy": "excluded_fail_closed",
            "latest_observation_date": latest_date.date().isoformat() if latest_date is not None else None,
            "days_since_last_pre_fixture_match": inactivity,
            "season_counts": {
                "fixture_year": fixture_year,
                "current_season": int(season_counts.get("current_season", 0)),
                "previous_season": int(season_counts.get("previous_season", 0)),
                "career_prior": int(season_counts.get("career_prior", 0)),
            },
            "gap_windows": _gap_windows(dates, cut),
        },
        "records": _record_contexts(
            player_rows,
            cut=cut,
            fixture_surface=fixture_surface,
            event_index=event_index,
        ),
        "provenance": {
            "identity": {
                "source": "model._resolve_history_player_key",
                "resolution": identity_mode,
                "as_of": "strict pre-fixture dated history only",
            },
            "season_counts": {
                "source": "derived from TML.tourney_date relative to fixture year",
                "resolution": "derived",
            },
            "days_since_last_pre_fixture_match": {
                "source": "derived from latest strict-pre TML.tourney_date",
                "resolution": "derived" if inactivity is not None else "unavailable",
            },
            "gap_windows": {
                "source": "derived descriptive windows 30/60/90/180 days",
                "resolution": "derived",
                "policy": "audit windows only; no medical/comeback inference",
            },
        },
    }


def _direct_fixture_field(match: dict[str, Any], keys: tuple[str, ...]) -> tuple[Any, str | None]:
    for key in keys:
        value = match.get(key)
        if value is not None and str(value).strip() != "":
            return value, key
    return None, None


def build_report(
    raw_history: pd.DataFrame,
    long_df: pd.DataFrame,
    results: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    stamp = now or datetime.now(timezone.utc)
    event_index = _raw_event_index(raw_history)
    fixtures = []
    identity_modes = Counter()
    unresolved = 0
    same_day_excluded = 0
    records_emitted = 0
    event_level_direct = 0
    rank_gap_records = 0
    missing_fixture_surface = 0
    invalid_fixture_time = 0

    for match in results:
        cut = _fixture_cut(match.get("scheduled_time"))
        if cut is None:
            invalid_fixture_time += 1
        fixture_surface = _surface(match.get("surface"))
        if fixture_surface is None:
            missing_fixture_surface += 1

        fixture_event_name, fixture_event_name_key = _direct_fixture_field(
            match, ("event_name", "tournament", "tourney_name")
        )
        fixture_event_level, fixture_event_level_key = _direct_fixture_field(
            match, ("event_level", "tourney_level")
        )
        p1_fixture_rank = _positive_rank(match.get("p1_rank"))
        p2_fixture_rank = _positive_rank(match.get("p2_rank"))
        fixture_rank_gap = p1_fixture_rank - p2_fixture_rank if p1_fixture_rank is not None and p2_fixture_rank is not None else None

        players = {}
        for side in ("p1", "p2"):
            context = _player_context(
                long_df,
                player=str(match.get(side) or ""),
                cut=cut,
                fixture_surface=fixture_surface,
                event_index=event_index,
            )
            players[side] = context
            mode = str((context.get("identity") or {}).get("mode") or "none")
            identity_modes[mode] += 1
            if not (context.get("identity") or {}).get("resolved_key"):
                unresolved += 1
            same_day_excluded += int((context.get("history") or {}).get("same_day_rows_excluded") or 0)
            records_emitted += len(context.get("records") or [])
            for record in context.get("records") or []:
                event_level_direct += int(record.get("event_level") is not None)
                rank_gap_records += int(record.get("rank_gap_player_minus_opponent") is not None)

        fixtures.append({
            "match_id": match.get("id"),
            "scheduled_time": match.get("scheduled_time"),
            "as_of_date": cut.date().isoformat() if cut is not None else None,
            "fixture": {
                "surface": fixture_surface,
                "tour": _clean_text(match.get("tour")),
                "event_name": _clean_text(fixture_event_name),
                "event_level": _clean_text(fixture_event_level),
                "model_ready_at_snapshot": bool(match.get("model_ready")),
                "ranking_snapshot": {
                    "p1_rank": p1_fixture_rank,
                    "p2_rank": p2_fixture_rank,
                    "p1_minus_p2_rank_gap": fixture_rank_gap,
                    "effective_date": None,
                    "effective_date_reason": "provider snapshot does not supply ranking effective date",
                },
                "provenance": {
                    "scheduled_time": {"source": "frontend/data/results.json scheduled_time", "resolution": "direct" if cut is not None else "unavailable"},
                    "surface": {"source": "frontend/data/results.json surface", "resolution": "direct" if fixture_surface else "unavailable"},
                    "tour": {"source": "frontend/data/results.json tour", "resolution": "direct" if _clean_text(match.get("tour")) else "unavailable"},
                    "event_name": {"source": f"frontend/data/results.json {fixture_event_name_key}" if fixture_event_name_key else None, "resolution": "direct" if fixture_event_name_key else "unavailable"},
                    "event_level": {"source": f"frontend/data/results.json {fixture_event_level_key}" if fixture_event_level_key else None, "resolution": "direct" if fixture_event_level_key else "unavailable", "policy": "never inferred from event name or tour"},
                    "ranking_snapshot": {"source": "frontend/data/results.json p1_rank/p2_rank provider snapshot", "resolution": "direct" if p1_fixture_rank is not None or p2_fixture_rank is not None else "unavailable", "effective_date": None, "policy": "provenance only; LOGIC-02 proved fixture rank is not a Current feature"},
                },
            },
            "players": players,
        })

    return {
        "version": VERSION,
        "generated_at": stamp.isoformat(),
        "policy": {
            "audit_only": True,
            "shadow_only": True,
            "runtime_wiring": False,
            "predictive_output_generated": False,
            "model_math_changed": False,
            "thresholds_changed": False,
            "weights_changed": False,
            "training_changed": False,
            "player_dna_changed": False,
            "surface_elo_changed": False,
            "symphony_changed": False,
            "neuron_changed": False,
            "playable_changed": False,
            "settlement_changed": False,
            "ineed_calculations_changed": False,
            "live_tennis_api_calls": 0,
            "production_cache_writes": 0,
            "fuzzy_matching": False,
            "manual_aliases": False,
            "injury_inference": False,
            "event_level_inference": False,
        },
        "contract": {
            "owner": "backend/context_engine_shadow.py",
            "identity_owner_reused": "model._resolve_history_player_key",
            "history_owner_reused": "model._dated_history + model_core.normalize_matches",
            "history_date_granularity": "day",
            "same_day_history_policy": "excluded_fail_closed because TML rows do not contain match time",
            "season_partition": "current fixture year / previous year / older career prior",
            "freshness_buckets": ["0-30", "31-60", "61-90", "91-120", "121-180", "181-365", ">365"],
            "gap_windows_days": list(GAP_WINDOWS),
            "gap_windows_policy": "descriptive audit windows only; no comeback/injury diagnosis",
            "event_level_policy": "direct source field only; unavailable otherwise",
            "opponent_rank_band_policy": "descriptive rank band only; not opponent-strength score",
            "record_limit_per_player": RECORD_LIMIT,
        },
        "sources": {
            "history": "exact restored TennisMyLife cache used by update.py",
            "normalized_history": "model_core.normalize_matches after current history hygiene",
            "fixtures": "frontend/data/results.json",
            "raw_event_metadata": "exact TML raw row keyed by date+player+opponent when unique",
        },
        "summary": {
            "visible_matches": len(results),
            "player_contexts": len(results) * 2,
            "identity_modes": dict(sorted(identity_modes.items())),
            "unresolved_player_contexts": unresolved,
            "same_day_history_rows_excluded": same_day_excluded,
            "history_records_emitted": records_emitted,
            "records_with_direct_event_level": event_level_direct,
            "records_with_rank_gap": rank_gap_records,
            "fixtures_missing_surface": missing_fixture_surface,
            "fixtures_invalid_scheduled_time": invalid_fixture_time,
        },
        "fixtures": fixtures,
        "decision": {
            "runtime_promotion_authorized": False,
            "model_consumption_authorized": False,
            "player_dna_consumption_authorized": False,
            "opponent_strength_promotion_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LOGIC-04 SHADOW context engine")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--output", type=Path, default=ARTIFACT_PATH)
    args = parser.parse_args()

    raw = load_cached_history()
    if raw is None or raw.empty:
        raise SystemExit("production history cache unavailable")
    cleaned, _ = clean_history(raw)
    long_df = model.normalize_matches(cleaned)
    if long_df is None or long_df.empty:
        raise SystemExit("normalized production history unavailable")

    results = _rows(_read_json(args.results, []))
    if not results:
        raise SystemExit("current results snapshot unavailable or empty")

    report = build_report(raw, long_df, results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
