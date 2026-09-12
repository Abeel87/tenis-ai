from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import model  # noqa: E402
import update  # noqa: E402
from history_hygiene_v78a import clean_history  # noqa: E402


def _load_exact_cached_history() -> tuple[pd.DataFrame, list[str]]:
    frames: list[pd.DataFrame] = []
    missing: list[str] = []
    for source in update.TML_SOURCES:
        df = update._read_cached(update.CACHE_DIR, source)
        if df is None or df.empty:
            missing.append(source["key"])
            continue
        df = df.copy()
        df["source_tour"] = source["tour"]
        frames.append(df)
    if not frames:
        return pd.DataFrame(), missing
    return pd.concat(frames, ignore_index=True, sort=False), missing


def _tokens(key: str) -> list[str]:
    return [part for part in str(key or "").split() if part]


def _candidate_modes(requested_key: str, candidate_key: str) -> list[str]:
    """Audit-only deterministic patterns not currently accepted by the resolver."""
    requested = _tokens(requested_key)
    candidate = _tokens(candidate_key)
    if len(requested) < 2 or len(candidate) < 2:
        return []
    modes: list[str] = []

    if requested != candidate and "".join(requested) == "".join(candidate):
        modes.append("full-name-spacing-compaction")

    if len(requested) == 2 and len(candidate) >= 3:
        if requested[0] == candidate[-1] and requested[1] == candidate[0]:
            modes.append("surname-first-with-middle-names")
    if len(candidate) == 2 and len(requested) >= 3:
        if candidate[0] == requested[-1] and candidate[1] == requested[0]:
            modes.append("surname-first-with-middle-names")

    def _multi_initial(short: list[str], full: list[str]) -> bool:
        if len(short) < 3 or len(full) < len(short):
            return False
        initials = short[:-1]
        if not initials or not all(len(part) == 1 for part in initials):
            return False
        if short[-1] != full[-1]:
            return False
        given = full[:-1]
        if len(given) < len(initials):
            return False
        return all(given[i].startswith(initials[i]) for i in range(len(initials)))

    if _multi_initial(requested, candidate) or _multi_initial(candidate, requested):
        modes.append("multiple-given-name-initials")

    return sorted(set(modes))


def _structural_candidates(history_keys: list[str], requested_key: str) -> list[dict]:
    out = []
    for key in history_keys:
        if key == requested_key or model._history_name_variant_matches(requested_key, key):
            continue
        modes = _candidate_modes(requested_key, key)
        if modes:
            out.append({"key": key, "modes": modes})
    return out[:12]


def _player_diag(long_df: pd.DataFrame, history_keys: list[str], result_stats: dict, player: str, surface: str, scheduled_time) -> dict:
    requested_key = model._core._key(player)
    resolved_key, identity_mode = model._resolve_history_player_key(long_df, player)
    cut = model._naive_cutoff(scheduled_time)

    total_matches = 0
    pre_match_rows = 0
    post_cutoff_rows = 0
    if resolved_key:
        rows = long_df[long_df["player_key"] == resolved_key].copy()
        total_matches = int(len(rows))
        if "date" in rows.columns:
            pre = rows[rows["date"] <= cut]
            post = rows[rows["date"] > cut]
            pre_match_rows = int(len(pre))
            post_cutoff_rows = int(len(post))
        else:
            pre_match_rows = total_matches

    matches = int((result_stats or {}).get("matches") or 0)
    quality = (result_stats or {}).get("quality") or "LOW"
    coverage = (result_stats or {}).get("coverage")
    structural = _structural_candidates(history_keys, requested_key) if not resolved_key else []

    if identity_mode == "ambiguous":
        reason = "ambiguous_identity"
    elif not resolved_key:
        reason = "identity_variant_unresolved" if structural else "no_safe_history_identity_candidate"
    elif matches == 0 and total_matches > 0 and pre_match_rows == 0:
        reason = "no_pre_match_history_before_fixture"
    elif matches < 5:
        reason = "pre_match_history_below_5" if total_matches >= 5 and pre_match_rows < 5 else "fewer_than_5_historical_matches"
    elif quality == "LOW":
        reason = "insufficient_required_stats" if coverage is None or float(coverage) < 0.62 else "low_quality_other"
    else:
        reason = "ready_player_history"

    return {
        "player": player,
        "requested_key": requested_key,
        "result_matches": matches,
        "quality": quality,
        "coverage": coverage,
        "identity_mode": identity_mode,
        "resolved_key": resolved_key,
        "total_history_rows": total_matches,
        "pre_match_rows": pre_match_rows,
        "post_cutoff_rows": post_cutoff_rows,
        "reason": reason,
        "structural_candidates": structural,
    }


def main() -> int:
    results_path = ROOT / "frontend" / "data" / "results.json"
    meta_path = ROOT / "frontend" / "data" / "meta.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    raw_history, missing_cache = _load_exact_cached_history()
    if missing_cache:
        print("HISTORY_COVERAGE_AUDIT_ERROR=" + json.dumps({"missing_cached_sources": missing_cache}, ensure_ascii=False))
        return 2

    clean, hygiene = clean_history(raw_history)
    long_df = model.normalize_matches(clean)
    long_df = model._dated_history(long_df)
    history_keys = sorted(str(v) for v in long_df["player_key"].dropna().unique().tolist() if str(v).strip())

    both_history = 0
    model_ready = 0
    missing_matches = []
    non_ready_with_both = []
    reason_counts: dict[str, int] = {}

    for row in results:
        p1_stats = row.get("p1_stats") or {}
        p2_stats = row.get("p2_stats") or {}
        p1_has = int(p1_stats.get("matches") or 0) > 0
        p2_has = int(p2_stats.get("matches") or 0) > 0
        both = p1_has and p2_has
        if both:
            both_history += 1
        if row.get("model_ready"):
            model_ready += 1

        if not both or not row.get("model_ready"):
            p1_diag = _player_diag(long_df, history_keys, p1_stats, row.get("p1") or "", row.get("surface") or "", row.get("scheduled_time"))
            p2_diag = _player_diag(long_df, history_keys, p2_stats, row.get("p2") or "", row.get("surface") or "", row.get("scheduled_time"))
            for diag in (p1_diag, p2_diag):
                if diag["reason"] != "ready_player_history":
                    reason_counts[diag["reason"]] = reason_counts.get(diag["reason"], 0) + 1
            item = {
                "id": row.get("id"),
                "scheduled_time": row.get("scheduled_time"),
                "tour": row.get("tour"),
                "tournament": row.get("tournament"),
                "surface": row.get("surface"),
                "p1": p1_diag,
                "p2": p2_diag,
                "model_ready": bool(row.get("model_ready")),
            }
            if not both:
                missing_matches.append(item)
            elif not row.get("model_ready"):
                non_ready_with_both.append(item)

    report = {
        "summary": {
            "meta_updated_at": meta.get("updated_at"),
            "visible_matches": len(results),
            "both_players_with_any_pre_match_history": both_history,
            "matches_without_both_players_history": len(results) - both_history,
            "model_ready": model_ready,
            "meta_model_ready": meta.get("model_ready"),
            "history_rows_raw_reloaded": int(len(raw_history)),
            "history_rows_after_hygiene": int(len(clean)),
            "player_rows_dated": int(len(long_df)),
            "history_hygiene_removed": hygiene.get("removed_rows"),
            "history_sources_cached": len(update.TML_SOURCES),
        },
        "reason_counts_players": dict(sorted(reason_counts.items())),
        "missing_both_player_history": missing_matches,
        "not_model_ready_despite_both_history": non_ready_with_both,
    }
    print("===HISTORY_COVERAGE_AUDIT===")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print("===END_HISTORY_COVERAGE_AUDIT===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
