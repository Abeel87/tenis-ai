from __future__ import annotations

"""Audit raw historical service-split readiness for canonical Player DNA.

This Phase-1/3 source audit checks whether the restored historical CSV cache can
support stable-ID, strict-as-of first/second-serve matchup profiles before any
new canonical feature is added.

It measures source availability only. It does not build profiles, fit models,
change runtime scoring, or affect PROD / Symfonia 2.0 / Superbet PLAYABLE.
"""

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
OUT = ROOT / "frontend" / "data" / "player_dna_service_split_source_readiness.json"

VERSION = "player-dna-service-split-source-readiness-v1"
MODE = "SHADOW_SOURCE_READINESS_AUDIT_ONLY"
GATE = "AUDIT_ONLY_NO_PROFILE_BUILD"

ALIASES = {
    "date": ("tourney_date", "date", "event_date"),
    "winner_id": ("winner_id", "w_id"),
    "loser_id": ("loser_id", "l_id"),
    "winner_name": ("winner_name", "w_name"),
    "loser_name": ("loser_name", "l_name"),
    "w_svpt": ("w_svpt", "winner_svpt", "w_service_points"),
    "l_svpt": ("l_svpt", "loser_svpt", "l_service_points"),
    "w_1st_in": ("w_1stin", "w_1stIn", "winner_1stin", "w_first_in"),
    "l_1st_in": ("l_1stin", "l_1stIn", "loser_1stin", "l_first_in"),
    "w_1st_won": ("w_1stwon", "w_1stWon", "winner_1stwon", "w_first_won"),
    "l_1st_won": ("l_1stwon", "l_1stWon", "loser_1stwon", "l_first_won"),
    "w_2nd_won": ("w_2ndwon", "w_2ndWon", "winner_2ndwon", "w_second_won"),
    "l_2nd_won": ("l_2ndwon", "l_2ndWon", "loser_2ndwon", "l_second_won"),
    "w_ace": ("w_ace", "w_aces", "winner_ace"),
    "l_ace": ("l_ace", "l_aces", "loser_ace"),
    "w_df": ("w_df", "w_double_faults", "winner_df"),
    "l_df": ("l_df", "l_double_faults", "loser_df"),
    "w_svgms": ("w_svgms", "w_SvGms", "w_service_games"),
    "l_svgms": ("l_svgms", "l_SvGms", "l_service_games"),
}


def _colmap(df: pd.DataFrame) -> dict[str, str]:
    return {str(c).strip().casefold(): str(c) for c in df.columns}


def _resolve_columns(df: pd.DataFrame) -> dict[str, str | None]:
    cm = _colmap(df)
    out: dict[str, str | None] = {}
    for canonical, aliases in ALIASES.items():
        found = None
        for alias in aliases:
            col = cm.get(str(alias).casefold())
            if col is not None:
                found = col
                break
        out[canonical] = found
    return out


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _positive_int(value: Any) -> int | None:
    number = _num(value)
    if number is None or number <= 0 or abs(number - round(number)) > 1e-9:
        return None
    return int(round(number))


def _date_day(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        if raw.replace(".", "", 1).isdigit():
            raw = str(int(float(raw)))
    except (TypeError, ValueError):
        pass
    parsed = pd.to_datetime(raw, format="%Y%m%d", errors="coerce")
    if pd.isna(parsed):
        parsed = pd.to_datetime(raw, errors="coerce")
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).date().isoformat()


def _get(row: pd.Series, columns: dict[str, str | None], key: str) -> Any:
    col = columns.get(key)
    return row.get(col) if col is not None else None


def _service_split(row: pd.Series, columns: dict[str, str | None], side: str) -> dict[str, Any]:
    svpt = _num(_get(row, columns, f"{side}_svpt"))
    first_in = _num(_get(row, columns, f"{side}_1st_in"))
    first_won = _num(_get(row, columns, f"{side}_1st_won"))
    second_won = _num(_get(row, columns, f"{side}_2nd_won"))
    ace = _num(_get(row, columns, f"{side}_ace"))
    df = _num(_get(row, columns, f"{side}_df"))
    service_games = _num(_get(row, columns, f"{side}_svgms"))

    valid_total = svpt is not None and svpt > 0
    valid_first_in = (
        valid_total and first_in is not None and 0 <= first_in <= svpt
    )
    valid_first_won = (
        valid_first_in and first_in > 0 and first_won is not None
        and 0 <= first_won <= first_in
    )
    second_attempts = (
        svpt - first_in if valid_first_in else None
    )
    valid_second_won = (
        second_attempts is not None
        and second_attempts > 0
        and second_won is not None
        and 0 <= second_won <= second_attempts
    )
    valid_ace = valid_total and ace is not None and 0 <= ace <= svpt
    valid_df = valid_total and df is not None and 0 <= df <= svpt
    valid_service_games = service_games is not None and service_games > 0

    return {
        "service_points": svpt,
        "first_in": first_in,
        "first_won": first_won,
        "second_won": second_won,
        "second_attempts": second_attempts,
        "ace": ace,
        "df": df,
        "service_games": service_games,
        "first_serve_in_rate_ready": bool(valid_first_in),
        "first_serve_points_won_rate_ready": bool(valid_first_won),
        "second_serve_points_won_rate_ready": bool(valid_second_won),
        "ace_rate_ready": bool(valid_ace),
        "double_fault_rate_ready": bool(valid_df),
        "service_games_ready": bool(valid_service_games),
    }


def _pair_metric_ready(w: dict[str, Any], l: dict[str, Any], metric: str) -> bool:
    return bool(w.get(metric) is True and l.get(metric) is True)


def load_raw_history(cache_dir: Path = CACHE) -> pd.DataFrame:
    frames = []
    for path in sorted(cache_dir.glob("*.csv.gz")):
        try:
            frame = pd.read_csv(path, compression="gzip", low_memory=False)
        except Exception:
            continue
        if frame.empty:
            continue
        frame = frame.copy()
        frame["_source_file"] = path.name
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def audit_history(raw: pd.DataFrame) -> dict[str, Any]:
    if raw is None or raw.empty:
        return {
            "version": VERSION,
            "mode": MODE,
            "gate": GATE,
            "rows": 0,
            "columns_found": {},
            "coverage": {},
            "derived_matchup_source_readiness": {},
            "production_influence": False,
            "runtime_scoring_enabled": False,
            "profile_build_enabled": False,
            "training_join_enabled": False,
            "symphony2_influence": False,
            "superbet_playable_influence": False,
            "contract": {
                "source_readiness_only": True,
                "stable_provider_ids_required": True,
                "day_precision_same_day_must_be_excluded": True,
                "no_name_or_fuzzy_identity_for_canonical_profiles": True,
                "no_profile_values_published": True,
                "no_model_fit": True,
            },
        }

    columns = _resolve_columns(raw)
    counts = Counter()
    metric_counts = Counter()
    paired_counts = Counter()

    for _, row in raw.iterrows():
        counts["rows"] += 1
        date = _date_day(_get(row, columns, "date"))
        winner_id = _positive_int(_get(row, columns, "winner_id"))
        loser_id = _positive_int(_get(row, columns, "loser_id"))
        stable_identity = bool(
            winner_id is not None
            and loser_id is not None
            and winner_id != loser_id
        )
        date_ready = date is not None
        canonical_row = stable_identity and date_ready

        counts["date_ready_rows"] += int(date_ready)
        counts["stable_id_rows"] += int(stable_identity)
        counts["canonical_identity_time_rows"] += int(canonical_row)

        w = _service_split(row, columns, "w")
        l = _service_split(row, columns, "l")

        for metric in (
            "first_serve_in_rate_ready",
            "first_serve_points_won_rate_ready",
            "second_serve_points_won_rate_ready",
            "ace_rate_ready",
            "double_fault_rate_ready",
            "service_games_ready",
        ):
            metric_counts[f"winner_{metric}"] += int(canonical_row and w[metric])
            metric_counts[f"loser_{metric}"] += int(canonical_row and l[metric])
            paired_counts[metric] += int(
                canonical_row and _pair_metric_ready(w, l, metric)
            )

        # A return split can be derived from the opponent's observed serve split:
        # first-return points won = first serves faced - first-serve points won by server
        # second-return points won = second-serve attempts - second-serve points won by server.
        first_pair = bool(
            canonical_row
            and _pair_metric_ready(w, l, "first_serve_points_won_rate_ready")
        )
        second_pair = bool(
            canonical_row
            and _pair_metric_ready(w, l, "second_serve_points_won_rate_ready")
        )
        counts["first_serve_first_return_match_rows"] += int(first_pair)
        counts["second_serve_second_return_match_rows"] += int(second_pair)

    total = int(counts["rows"])
    canonical = int(counts["canonical_identity_time_rows"])

    def rate(value: int, denominator: int = total) -> float:
        return round(value / denominator, 6) if denominator else 0.0

    paired = {}
    for metric in (
        "first_serve_in_rate_ready",
        "first_serve_points_won_rate_ready",
        "second_serve_points_won_rate_ready",
        "ace_rate_ready",
        "double_fault_rate_ready",
        "service_games_ready",
    ):
        value = int(paired_counts[metric])
        paired[metric] = {
            "canonical_match_rows": value,
            "rate_of_all_rows": rate(value),
            "rate_of_canonical_identity_time_rows": rate(value, canonical),
        }

    first_rows = int(counts["first_serve_first_return_match_rows"])
    second_rows = int(counts["second_serve_second_return_match_rows"])
    ace_rows = int(paired_counts["ace_rate_ready"])
    df_rows = int(paired_counts["double_fault_rate_ready"])

    return {
        "version": VERSION,
        "mode": MODE,
        "gate": GATE,
        "rows": total,
        "source_files": int(raw["_source_file"].nunique()) if "_source_file" in raw.columns else None,
        "columns_found": {
            key: value for key, value in columns.items()
        },
        "identity_time_coverage": {
            "date_ready_rows": int(counts["date_ready_rows"]),
            "stable_id_rows": int(counts["stable_id_rows"]),
            "canonical_identity_time_rows": canonical,
            "canonical_identity_time_rate": rate(canonical),
        },
        "paired_metric_coverage": paired,
        "derived_matchup_source_readiness": {
            "first_serve_vs_first_return": {
                "canonical_match_rows": first_rows,
                "rate_of_all_rows": rate(first_rows),
                "rate_of_canonical_identity_time_rows": rate(first_rows, canonical),
                "return_split_derivable_from_opponent_serve_counts": True,
                "source_ready": first_rows > 0,
            },
            "second_serve_vs_second_return": {
                "canonical_match_rows": second_rows,
                "rate_of_all_rows": rate(second_rows),
                "rate_of_canonical_identity_time_rows": rate(second_rows, canonical),
                "return_split_derivable_from_opponent_serve_counts": True,
                "source_ready": second_rows > 0,
            },
            "ace_tendency": {
                "canonical_match_rows": ace_rows,
                "rate_of_all_rows": rate(ace_rows),
                "source_ready": ace_rows > 0,
            },
            "double_fault_tendency": {
                "canonical_match_rows": df_rows,
                "rate_of_all_rows": rate(df_rows),
                "source_ready": df_rows > 0,
            },
            "ace_vs_contact_return": {
                "source_ready": False,
                "reason": (
                    "ace counts are auditable, but an explicit contact/unreturned-return "
                    "field is not established by this source audit"
                ),
            },
            "double_fault_vs_return_pressure": {
                "source_ready": False,
                "reason": (
                    "double-fault counts are auditable, but a canonical independent "
                    "return-pressure exposure is not established by this source audit"
                ),
            },
        },
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "profile_build_enabled": False,
        "training_join_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "contract": {
            "source_readiness_only": True,
            "stable_provider_ids_required": True,
            "day_precision_same_day_must_be_excluded": True,
            "no_name_or_fuzzy_identity_for_canonical_profiles": True,
            "return_split_derivation_uses_only_opponent_match_serve_counts": True,
            "no_profile_values_published": True,
            "no_model_fit": True,
            "no_threshold_tuning": True,
            "coverage_is_not_predictive_signal": True,
        },
        "next_gate": (
            "If first/second-serve split coverage is material, add those fields to "
            "the canonical strict-as-of Player DNA profile store using stable IDs "
            "and exclude the entire target calendar day from day-precision history. "
            "Only after profile leakage tests pass may a single matchup challenger "
            "be evaluated chronologically."
        ),
    }


def build() -> dict[str, Any]:
    report = audit_history(load_raw_history())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
