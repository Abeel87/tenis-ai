from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from history_coverage_audit import load_cached_history
from history_hygiene_v78a import clean_history
from model import _dated_history, _naive_cutoff, _resolve_history_player_key, normalize_matches

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "frontend" / "data" / "results.json"
ARTIFACT_PATH = ROOT / "artifacts" / "history_freshness_audit.json"
POSITIONS = (1, 5, 10, 20)
THRESHOLDS = (90, 180, 365)


def _iso_cut(value):
    cut = _naive_cutoff(value)
    if cut is None:
        return None
    return pd.Timestamp(cut).normalize()


def _days_old(cut: pd.Timestamp, value) -> int | None:
    d = pd.to_datetime(value, errors="coerce")
    if pd.isna(d):
        return None
    return max(0, int((cut - pd.Timestamp(d).normalize()).days))


def _quantiles(values: list[int]) -> dict:
    if not values:
        return {"n": 0, "median": None, "p90": None, "max": None}
    s = pd.Series(values, dtype="float64")
    return {
        "n": int(len(values)),
        "median": round(float(s.quantile(0.50)), 1),
        "p90": round(float(s.quantile(0.90)), 1),
        "max": int(s.max()),
    }


def _player_used_rows(long_df: pd.DataFrame, player: str, scheduled_time) -> tuple[pd.DataFrame, str | None, str]:
    dated = _dated_history(long_df)
    cut = _iso_cut(scheduled_time)
    if dated is None or dated.empty or cut is None:
        return pd.DataFrame(), None, "none"
    pre = dated[dated["date"].notna() & (dated["date"] <= cut)].copy()
    key, mode = _resolve_history_player_key(pre, player)
    if key is None:
        return pd.DataFrame(), None, mode
    if "player_key" in pre.columns:
        rows = pre[pre["player_key"] == key].copy()
    else:
        rows = pre[pre["player"] == player].copy()
    rows = rows.sort_values("date", ascending=False).head(20)
    return rows, key, mode


def build_audit(long_df: pd.DataFrame, results: list[dict]) -> dict:
    records = []
    seen = set()
    position_ages = {p: [] for p in POSITIONS}
    threshold_counts = {p: {t: 0 for t in THRESHOLDS} for p in POSITIONS}
    model_ready_any_old = {t: 0 for t in THRESHOLDS}
    all_any_old = {t: 0 for t in THRESHOLDS}
    short_history_any_old = {t: 0 for t in THRESHOLDS}
    modes = Counter()

    for match in results:
        for side in ("p1", "p2"):
            player = str(match.get(side) or "").strip()
            scheduled = match.get("scheduled_time")
            uniq = (player, str(scheduled or ""))
            if not player or uniq in seen:
                continue
            seen.add(uniq)
            rows, key, mode = _player_used_rows(long_df, player, scheduled)
            modes[mode] += 1
            cut = _iso_cut(scheduled)
            ages = [_days_old(cut, d) for d in rows.get("date", pd.Series(dtype="datetime64[ns]")).tolist()] if cut is not None else []
            ages = [x for x in ages if x is not None]

            pos = {}
            for p in POSITIONS:
                age = ages[p - 1] if len(ages) >= p else None
                pos[str(p)] = age
                if age is not None:
                    position_ages[p].append(age)
                    for t in THRESHOLDS:
                        if age > t:
                            threshold_counts[p][t] += 1

            any_old = {str(t): bool(ages and max(ages) > t) for t in THRESHOLDS}
            stats = match.get(f"{side}_stats") or {}
            current_matches = int(stats.get("matches") or 0)
            current_quality = str(stats.get("quality") or "LOW")
            match_ready = bool(match.get("model_ready"))
            for t in THRESHOLDS:
                if any_old[str(t)]:
                    all_any_old[t] += 1
                    if match_ready:
                        model_ready_any_old[t] += 1
                    if 0 < current_matches < 5:
                        short_history_any_old[t] += 1

            records.append({
                "match_id": match.get("id"),
                "scheduled_time": scheduled,
                "side": side,
                "player": player,
                "resolved_key": key,
                "identity_mode": mode,
                "model_ready_match": match_ready,
                "current_profile_matches": current_matches,
                "current_profile_quality": current_quality,
                "used_rows": int(len(rows)),
                "age_days_by_position": pos,
                "oldest_used_age_days": max(ages) if ages else None,
                "newest_used_age_days": min(ages) if ages else None,
                "any_used_older_than_days": any_old,
            })

    unique_players = len(records)
    summary = {
        "visible_matches": int(len(results)),
        "audited_player_fixture_profiles": unique_players,
        "identity_modes": dict(sorted(modes.items())),
        "position_age_days": {str(p): _quantiles(position_ages[p]) for p in POSITIONS},
        "profiles_position_older_than_days": {
            str(p): {str(t): int(threshold_counts[p][t]) for t in THRESHOLDS} for p in POSITIONS
        },
        "profiles_with_any_used_row_older_than_days": {str(t): int(all_any_old[t]) for t in THRESHOLDS},
        "model_ready_profiles_with_any_used_row_older_than_days": {str(t): int(model_ready_any_old[t]) for t in THRESHOLDS},
        "short_history_profiles_1_to_4_with_any_used_row_older_than_days": {str(t): int(short_history_any_old[t]) for t in THRESHOLDS},
        "model_has_explicit_max_history_age_days": False,
        "model_selection_rule": "pre-match rows sorted newest-first, then head(20); position decay 0.90**i; no age cutoff",
    }
    return {
        "version": "task-019-history-freshness-audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "audit_only": True,
            "runtime_change": False,
            "model_math_changed": False,
            "history_sources_changed": False,
            "live_tennis_api_calls": 0,
            "production_cache_writes": 0,
        },
        "summary": summary,
        "profiles": records,
    }


def main() -> None:
    raw = load_cached_history()
    if raw is None or raw.empty:
        raise SystemExit("production history cache unavailable")
    cleaned, _ = clean_history(raw)
    long_df = normalize_matches(cleaned)
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    report = build_audit(long_df, results if isinstance(results, list) else [])
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
