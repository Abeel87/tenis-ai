from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

import pandas as pd

from model import (
    _dated_history,
    _history_name_variant_matches,
    _naive_cutoff,
    _resolve_history_player_key,
    normalize_matches,
)
from model_core import _key

AUDIT_VERSION = "v9.4.9-history-coverage"


def _available_keys(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty:
        return []
    if "player_key" in df.columns:
        values = df["player_key"].dropna().tolist()
        return sorted({str(value).strip() for value in values if str(value).strip()})
    if "player" in df.columns:
        return sorted({_key(value) for value in df["player"].dropna().tolist() if _key(value)})
    return []


def _variant_candidates(df: pd.DataFrame, player: str) -> list[str]:
    requested = _key(player)
    if not requested:
        return []
    return [
        candidate
        for candidate in _available_keys(df)
        if candidate != requested and _history_name_variant_matches(requested, candidate)
    ]


def _token_hints(df: pd.DataFrame, player: str, limit: int = 12) -> dict:
    """Diagnostic-only exact token hints. These never resolve or merge identities."""
    requested = _key(player).split()
    if not requested:
        return {"same_first_token": [], "same_last_token": []}
    keys = _available_keys(df)
    first, last = requested[0], requested[-1]
    same_first = [key for key in keys if key.split() and key.split()[0] == first and key != " ".join(requested)]
    same_last = [key for key in keys if key.split() and key.split()[-1] == last and key != " ".join(requested)]
    return {
        "same_first_token": same_first[:limit],
        "same_last_token": same_last[:limit],
    }


def _rows_for_key(df: pd.DataFrame, key: str | None) -> int:
    if not key or df is None or df.empty:
        return 0
    if "player_key" in df.columns:
        return int((df["player_key"] == key).sum())
    if "player" in df.columns:
        return int(df["player"].map(_key).eq(key).sum())
    return 0


def _stage(df: pd.DataFrame, player: str) -> dict:
    resolved_key, mode = _resolve_history_player_key(df, player)
    return {
        "mode": mode,
        "resolved_key": resolved_key,
        "rows": _rows_for_key(df, resolved_key),
        "variant_candidates": _variant_candidates(df, player),
    }


def classify_player_history(
    *,
    player: str,
    stats: dict,
    scheduled_time,
    raw_long: pd.DataFrame,
    clean_long: pd.DataFrame,
) -> dict:
    stats = stats if isinstance(stats, dict) else {}
    matches = int(stats.get("matches") or 0)
    quality = str(stats.get("quality") or "LOW")
    current_mode = str(stats.get("history_identity_mode") or "none")
    current_key = stats.get("history_player_key") or (_key(player) if current_mode == "exact" else None)

    dated = _dated_history(clean_long)
    cut = _naive_cutoff(scheduled_time)
    pre = dated
    if dated is not None and not dated.empty and "date" in dated.columns and cut is not None:
        pre = dated[dated["date"] <= cut].copy()

    raw_stage = _stage(raw_long, player)
    clean_stage = _stage(clean_long, player)
    dated_stage = _stage(dated, player)
    pre_stage = _stage(pre, player)

    if current_mode == "ambiguous":
        reason = "ambiguous_identity"
    elif matches >= 5 and quality == "LOW":
        reason = "insufficient_required_statistics"
    elif 0 < matches < 5:
        reason = "insufficient_pre_match_sample"
    elif matches >= 5:
        reason = "sufficient_history"
    elif raw_stage["resolved_key"] and not clean_stage["resolved_key"]:
        reason = "history_removed_by_hygiene"
    elif clean_stage["resolved_key"] and not dated_stage["resolved_key"]:
        reason = "undated_history_rows"
    elif dated_stage["resolved_key"] and not pre_stage["resolved_key"]:
        reason = "post_cutoff_only"
    elif pre_stage["resolved_key"] and current_mode in {"none", "ambiguous"}:
        reason = "runtime_resolution_inconsistency"
    elif current_key and current_mode not in {"none", "ambiguous"}:
        reason = "no_pre_match_rows_after_resolution"
    else:
        reason = "no_safe_identity_candidate"

    return {
        "player": player,
        "requested_key": _key(player),
        "matches": matches,
        "quality": quality,
        "current_identity_mode": current_mode,
        "current_history_player_key": current_key,
        "reason": reason,
        "raw": raw_stage,
        "after_hygiene": clean_stage,
        "dated": dated_stage,
        "pre_match": pre_stage,
        "token_hints_raw": _token_hints(raw_long, player) if reason in {"no_safe_identity_candidate", "ambiguous_identity"} else {},
    }


def build_history_coverage_audit(
    raw_history: pd.DataFrame,
    cleaned_history: pd.DataFrame,
    long_df: pd.DataFrame,
    results: list[dict],
    *,
    now: datetime | None = None,
) -> dict:
    raw_long = normalize_matches(raw_history)
    clean_long = long_df if long_df is not None else normalize_matches(cleaned_history)
    rows = []
    reasons = Counter()

    for match in results:
        players = []
        for side in ("p1", "p2"):
            item = classify_player_history(
                player=str(match.get(side) or ""),
                stats=match.get(f"{side}_stats") or {},
                scheduled_time=match.get("scheduled_time"),
                raw_long=raw_long,
                clean_long=clean_long,
            )
            players.append(item)
            reasons[item["reason"]] += 1
        if any(p["reason"] != "sufficient_history" for p in players) or not match.get("model_ready"):
            rows.append({
                "id": match.get("id"),
                "scheduled_time": match.get("scheduled_time"),
                "surface": match.get("surface"),
                "model_ready": bool(match.get("model_ready")),
                "players": players,
            })

    both_history = sum(
        1 for match in results
        if int((match.get("p1_stats") or {}).get("matches") or 0) > 0
        and int((match.get("p2_stats") or {}).get("matches") or 0) > 0
    )
    both_minimum = sum(
        1 for match in results
        if int((match.get("p1_stats") or {}).get("matches") or 0) >= 5
        and int((match.get("p2_stats") or {}).get("matches") or 0) >= 5
    )
    model_ready = sum(1 for match in results if match.get("model_ready"))

    stamp = now or datetime.now(timezone.utc)
    return {
        "version": AUDIT_VERSION,
        "generated_at": stamp.isoformat(),
        "policy": "diagnostic-only; no fuzzy identity merge; model rules unchanged",
        "summary": {
            "visible_matches": len(results),
            "both_players_have_history": both_history,
            "both_players_minimum_5": both_minimum,
            "model_ready": model_ready,
            "matches_with_missing_player_history": len(results) - both_history,
            "reason_counts_players": dict(sorted(reasons.items())),
        },
        "matches": rows,
    }


def load_cached_history() -> pd.DataFrame:
    """Read the exact TML cache used by update.py, without making network requests."""
    from update import CACHE_DIR, TML_SOURCES

    frames = []
    for source in TML_SOURCES:
        path = CACHE_DIR / f"{source['key']}.csv.gz"
        if not path.exists() or path.stat().st_size <= 0:
            continue
        frame = pd.read_csv(path, compression="gzip", low_memory=False)
        if frame.empty:
            continue
        frame = frame.copy()
        frame["source_tour"] = source["tour"]
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def write_current_audit() -> dict:
    import json
    from pathlib import Path
    from history_hygiene_v78a import clean_history

    root = Path(__file__).resolve().parents[1]
    out = root / "frontend" / "data"
    results_path = out / "results.json"
    rows = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else []
    raw = load_cached_history()
    cleaned, hygiene = clean_history(raw)
    long_df = normalize_matches(cleaned)
    audit = build_history_coverage_audit(raw, cleaned, long_df, rows)
    audit["source_snapshot"] = {
        "raw_rows": int(len(raw)),
        "clean_rows": int(len(cleaned)),
        "hygiene_removed": int((hygiene or {}).get("removed_rows", 0)),
    }
    target = out / "history_coverage_audit_v949.json"
    target.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


def main() -> None:
    import json
    audit = write_current_audit()
    print(json.dumps(audit["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
