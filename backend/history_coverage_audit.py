from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path

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


def _utc(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except (ValueError, TypeError):
        return None


def _history_evidence(match, side, index, root, now):
    # Reuse the audited pair/score/date overlap rule, never cross-provider IDs.
    from pbp_tml_dedup_audit import (_canonical_pair_score, _parse_tml_score,
                                    _pbp_score, _index_tml, classify_overlap)
    from player_identity import player_identity_map
    from pbp_enrich import PROFILE_TTL_HOURS, MIN_RELIABLE_MATCHES

    name, pid = match.get(side), match.get(side + '_id')
    sample = (match.get(side + '_stats') or {}).get('history_sample')
    evidence = {'player': name, 'provider_player_id': pid, 'recent_observed': [],
                'missing_match_ids': [], 'model_sample_count': len(sample or [])}

    def finish(status):
        return {**evidence, 'status': status}

    if not isinstance(sample, list) or not sample:
        return finish('MODEL_SAMPLE_UNAVAILABLE')
    entries = index.get('players')
    entry = entries.get(_key(name)) if isinstance(entries, dict) else None
    if (not isinstance(entry, dict) or type(pid) is not int
            or type(entry.get('player_id')) is not int or entry.get('player_id') != pid
            or _key(entry.get('player')) != _key(name)):
        return finish('UNVERIFIED_PROVIDER_RESULTS')
    fetched = _utc(entry.get('fetched_at'))
    evidence['provider_index_at'] = entry.get('fetched_at')
    if fetched is None or not timedelta(0) <= now - fetched < timedelta(hours=PROFILE_TTL_HOURS):
        return finish('STALE_PROVIDER_INDEX')
    cutoff = _utc(match.get('scheduled_time'))
    if cutoff is None:
        return finish('UNVERIFIED_PROVIDER_RESULTS')
    cutoff = min(now, cutoff)
    model_rows = []
    for i, row in enumerate(sample):
        if not isinstance(row, dict) or _key(row.get('player')) != _key(name) or row.get('won') not in (0, 1):
            return finish('MODEL_SAMPLE_UNAVAILABLE')
        score = _parse_tml_score(row.get('score_text'))
        if row['won'] == 0:
            score = tuple((b, a) for a, b in score)
        canonical = _canonical_pair_score(name, row.get('opponent'), score)
        day = pd.to_datetime(row.get('date'), errors='coerce')
        if canonical is None or not score or pd.isna(day):
            return finish('MODEL_SAMPLE_UNAVAILABLE')
        model_rows.append({'row_index': i, 'pair': canonical[0], 'score': canonical[1],
                           'day': day.date(), 'surface': str(row.get('surface') or '').lower()})
    model_index = _index_tml(model_rows)
    dates = [r['day'].isoformat() for r in model_rows]
    evidence.update(latest_model_source_date=max(dates), oldest_model_source_date=min(dates),
                    model_date_precision='tournament')
    candidates = []
    summaries = entry.get('matches')
    if not isinstance(summaries, list):
        return finish('UNVERIFIED_PROVIDER_RESULTS')
    for row in summaries:
        stamp = _utc(row.get('scheduled_time')) if isinstance(row, dict) else None
        if stamp is None:
            return finish('UNVERIFIED_PROVIDER_RESULTS')
        if stamp < cutoff:
            candidates.append((stamp, row))
    seen = set()
    for stamp, summary in sorted(candidates, key=lambda x: x[0], reverse=True):
        mid = summary.get('id')
        if type(mid) is not int:
            return finish('UNVERIFIED_PROVIDER_RESULTS')
        if mid in seen:
            continue
        seen.add(mid)
        try:
            with gzip.open(root / 'matches' / f'{mid}.json.gz', 'rt', encoding='utf-8') as stream:
                payload = json.load(stream)
        except (OSError, ValueError, EOFError):
            return finish('UNVERIFIED_PROVIDER_RESULTS')
        if not isinstance(payload, dict) or not isinstance(payload.get('match'), dict):
            return finish('UNVERIFIED_PROVIDER_RESULTS')
        event = payload['match']
        identities, score = player_identity_map(payload), _pbp_score(payload)
        if not identities or event.get('id') != mid or _utc(event.get('scheduled_time')) != stamp or event.get('is_doubles'):
            return finish('UNVERIFIED_PROVIDER_RESULTS')
        player_side = next((s for s, p in identities.items() if p['id'] == pid and _key(p['name']) == _key(name)), None)
        winner = event.get('winner')
        score_doc = event.get('score')
        if not isinstance(score_doc, dict):
            return finish('UNVERIFIED_PROVIDER_RESULTS')
        sets, games = score_doc.get('sets'), score_doc.get('games')
        # Only completed singles outcomes. Retirements/partial scores cannot
        # certify a sample. An absent status needs a complete explicit score.
        if (player_side is None or type(winner) is not int or winner not in (1, 2)
                or str(event.get('event_status') or '').lower() not in ('', 'finished', 'completed', 'ended')
                or not isinstance(sets, list) or len(sets) != 2
                or any(type(v) is not int or v < 0 for v in sets)
                or not isinstance(games, list) or len(games) != 2
                or any(not isinstance(g, list) or any(type(v) is not int or v < 0 for v in g) for g in games)
                or len(games[0]) != len(games[1])
                or sets[winner - 1] not in (2, 3) or sets[2 - winner] >= sets[winner - 1]
                or not score or len(score) != sum(sets)
                or any(not ((max(a, b) == 6 and min(a, b) <= 4)
                    or (max(a, b) == 7 and min(a, b) in (5, 6))
                    or (max(a, b) >= 8 and abs(a-b) == 2)) for a, b in score)
                or [sum(a > b for a, b in score), sum(b > a for a, b in score)] != sets):
            return finish('UNVERIFIED_PROVIDER_RESULTS')
        canonical = _canonical_pair_score(identities[1]['name'], identities[2]['name'], score)
        if canonical is None:
            return finish('UNVERIFIED_PROVIDER_RESULTS')
        classification, _ = classify_overlap(pair=canonical[0], score=canonical[1], scheduled_dt=stamp,
            surface=str(event.get('surface') or '').lower(), clean_index=model_index, raw_index={})
        item = {'id': mid, 'scheduled_time': stamp.isoformat(), 'opponent': identities[3-player_side]['name'],
                'won': winner == player_side, 'source': 'LiveTennisAPI', 'overlap': classification,
                'score': [[a, b] if player_side == 1 else [b, a] for a, b in score]}
        evidence['recent_observed'].append(item)
        if classification != 'deterministic_duplicate_clean_tml':
            evidence['missing_match_ids'].append(mid)
        if len(evidence['recent_observed']) >= MIN_RELIABLE_MATCHES:
            break
    if evidence['missing_match_ids']:
        return finish('MISSING_RECENT_RESULTS')
    if len(evidence['recent_observed']) < MIN_RELIABLE_MATCHES:
        return finish('UNVERIFIED_PROVIDER_RESULTS')
    return finish('CHECKED')


def attach_current_history_evidence(results, *, pbp_root=None, now=None):
    """Assert input coverage before publication; never synthesize model stats.

    This checks the five latest *observed* completed provider results, not a
    claim that the PBP index includes the player's entire competitive history.
    Unknown evidence fails closed. Frozen historical predictions are untouched.
    """
    root = Path(pbp_root) if pbp_root is not None else Path(__file__).resolve().parents[1] / 'data/cache/pbp_v7'
    now = now or datetime.now(timezone.utc)
    try:
        index = json.loads((root / 'players.json').read_text(encoding='utf-8'))
        if not isinstance(index, dict):
            index = {}
    except (OSError, ValueError):
        index = {}
    output = []
    for match in results:
        players = {s: _history_evidence(match, s, index, root, now) for s in ('p1', 'p2')}
        allowed = all(p['status'] == 'CHECKED' for p in players.values())
        output.append({**match, 'history_input': {'version': 1, 'generated_at': now.isoformat(),
            'recommendation_allowed': allowed, 'status': 'CHECKED' if allowed else 'HISTORY_INPUT_UNVERIFIED',
            'scope': 'latest_5_observed_provider_results_vs_exact_model_sample', 'players': players}})
    return output


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
