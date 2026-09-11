from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from . import history_backfill_v83 as backfill
    from .api_quota import quota_budget
    from .pbp_enrich import extract_first_set_games
except ImportError:
    import history_backfill_v83 as backfill
    from api_quota import quota_budget
    from pbp_enrich import extract_first_set_games

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
CACHE = ROOT / "data" / "cache" / "pbp_v7"
INDEX_PATH = CACHE / "players.json"
STATE_PATH = CACHE / "history_player_priority_v83.json"
RESULTS_PATH = OUT / "results.json"
REPORT_PATH = OUT / "history_player_priority_v83.json"

VERSION = "v8.3B-player-priority-1"
DEFAULT_RUN_CAP = 240
DEFAULT_MAX_PLAYERS = 24
DEFAULT_MAX_LIST_PAGES = 2
DEFAULT_MAX_DOWNLOADS_PER_PLAYER = 12
DEFAULT_COOLDOWN_HOURS = 12.0
LIST_LIMIT = 100


def _key(value: Any) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def _read_json(path: Path, fallback):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _parse_dt(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _int_env(name: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int(float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        value = default
    return max(lo, min(hi, value))


def _float_env(name: str, default: float, lo: float, hi: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(lo, min(hi, value))


def _current_player_keys(results: Any) -> set[str]:
    if not isinstance(results, list):
        return set()
    out: set[str] = set()
    for row in results:
        if not isinstance(row, dict):
            continue
        for side in ("p1", "p2"):
            k = _key(row.get(side))
            if k:
                out.add(k)
    return out


def _cached_recent_count(entry: dict, cache_dir: Path = backfill.MATCH_CACHE) -> int:
    total = 0
    for match in entry.get("matches") or []:
        if not isinstance(match, dict) or match.get("id") is None:
            continue
        if (cache_dir / f"{match['id']}.json.gz").exists():
            total += 1
    return total


def _priority_players(
    index: dict,
    current_keys: set[str],
    state: dict,
    now: datetime,
    *,
    cooldown_hours: float = DEFAULT_COOLDOWN_HOURS,
    cache_dir: Path = backfill.MATCH_CACHE,
) -> list[dict]:
    players = index.get("players") if isinstance(index, dict) else {}
    players = players if isinstance(players, dict) else {}
    attempts = state.get("players") if isinstance(state, dict) else {}
    attempts = attempts if isinstance(attempts, dict) else {}
    rows: list[dict] = []

    for k, entry in players.items():
        if not isinstance(entry, dict):
            continue
        try:
            player_id = int(entry.get("player_id"))
        except (TypeError, ValueError):
            continue
        if player_id <= 0:
            continue

        last = _parse_dt((attempts.get(k) or {}).get("last_attempt_at"))
        if last is not None and now - last < timedelta(hours=max(0.0, cooldown_hours)):
            continue

        summaries = [m for m in (entry.get("matches") or []) if isinstance(m, dict)]
        cached_recent = _cached_recent_count(entry, cache_dir=cache_dir)
        rows.append(
            {
                "key": str(k),
                "player": entry.get("player") or k,
                "player_id": player_id,
                "current": str(k) in current_keys,
                "indexed_matches": len(summaries),
                "cached_recent": cached_recent,
                "last_attempt_at": last.isoformat() if last else None,
            }
        )

    rows.sort(
        key=lambda row: (
            0 if row["current"] else 1,
            int(row["cached_recent"]),
            int(row["indexed_matches"]),
            row["last_attempt_at"] or "",
            row["key"],
        )
    )
    return rows


def _detail_quality_ok(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    tape = payload.get("tape")
    if not isinstance(tape, list) or len(tape) < 20:
        return False
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    coverage = str(meta.get("coverage") or "").strip().casefold()
    if coverage and coverage != "from_start":
        return False
    return True


def run(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    key = os.getenv("LIVE_TENNIS_API_KEY", "").strip()
    run_cap = _int_env("API_QUOTA_HISTORY_BACKFILL_RUN_CAP", DEFAULT_RUN_CAP, 1, 500)
    max_players = _int_env("HISTORY_PLAYER_PRIORITY_MAX_PLAYERS", DEFAULT_MAX_PLAYERS, 1, 200)
    max_pages = _int_env("HISTORY_PLAYER_PRIORITY_MAX_LIST_PAGES", DEFAULT_MAX_LIST_PAGES, 1, 5)
    max_downloads_per_player = _int_env(
        "HISTORY_PLAYER_PRIORITY_MAX_DOWNLOADS_PER_PLAYER",
        DEFAULT_MAX_DOWNLOADS_PER_PLAYER,
        1,
        50,
    )
    cooldown_hours = _float_env(
        "HISTORY_PLAYER_PRIORITY_COOLDOWN_HOURS",
        DEFAULT_COOLDOWN_HOURS,
        0.0,
        168.0,
    )

    index = _read_json(INDEX_PATH, {"players": {}})
    state = _read_json(STATE_PATH, {"players": {}})
    results = _read_json(RESULTS_PATH, [])
    current_keys = _current_player_keys(results)

    report = {
        "version": VERSION,
        "updated_at": now.isoformat(),
        "status": "init",
        "policy": "current-players-first; strict-from-start-only; central-spare-quota; fail-closed",
        "calls_this_run": 0,
        "target_players_available": 0,
        "current_target_players": 0,
        "players_attempted": 0,
        "list_pages": 0,
        "downloaded_tapes": 0,
        "cache_hits": 0,
        "rejected_summaries": 0,
        "detail_quality_rejected": 0,
        "tape_parse_ok": 0,
        "tape_parse_failed": 0,
        "cached_tapes_before": len(list(backfill.MATCH_CACHE.glob("*.json.gz"))),
        "cache_mb_before": backfill._cache_size_mb(),
    }

    if not key:
        report["status"] = "no-api-key"
        _write_json(REPORT_PATH, report)
        return report

    candidates = _priority_players(
        index,
        current_keys,
        state,
        now,
        cooldown_hours=cooldown_hours,
    )
    report["target_players_available"] = len(candidates)
    report["current_target_players"] = sum(1 for row in candidates if row["current"])

    budget, usage = quota_budget("history_backfill", run_cap)
    q_today = usage.get("today") or {}
    q_limits = usage.get("limits") or {}
    q_meta = usage.get("quota_v83b") or {}
    report.update(
        {
            "daily_limit": q_limits.get("per_day"),
            "remaining_before": q_today.get("remaining_day"),
            "per_minute": q_limits.get("per_minute"),
            "daily_cap": q_meta.get("daily_cap"),
            "hard_reserve": q_meta.get("reserve"),
            "remote_budget": budget,
            "central_quota_reason": q_meta.get("reason"),
            "role_spent_today_before": q_meta.get("role_spent_today"),
        }
    )

    if budget <= 0:
        report["status"] = f"quota-skip:{q_meta.get('reason') or 'central_guard'}"
        report["cached_tapes_after"] = report["cached_tapes_before"]
        report["cache_mb_after"] = report["cache_mb_before"]
        _write_json(REPORT_PATH, report)
        return report

    api = backfill.API(key, budget, q_limits.get("per_minute") or 60)
    attempts = state.setdefault("players", {})
    if not isinstance(attempts, dict):
        attempts = {}
        state["players"] = attempts

    fatal = None
    for target in candidates[:max_players]:
        if api.calls >= api.call_cap:
            break

        pkey = target["key"]
        attempt = attempts.setdefault(pkey, {})
        attempt["last_attempt_at"] = now.isoformat()
        attempt["player_id"] = target["player_id"]
        attempt["player"] = target["player"]
        attempt["current"] = target["current"]
        report["players_attempted"] += 1
        downloaded_for_player = 0
        found_candidates = 0

        try:
            for page_no in range(max_pages):
                if api.calls >= api.call_cap or downloaded_for_player >= max_downloads_per_player:
                    break
                payload = api.get(
                    "/history/matches",
                    {
                        "player": int(target["player_id"]),
                        "to": now.date().isoformat(),
                        "coverage": "from_start",
                        "points_complete": "true",
                        "limit": LIST_LIMIT,
                        "offset": page_no * LIST_LIMIT,
                    },
                )
                report["list_pages"] += 1
                rows = payload.get("data") or []
                if not isinstance(rows, list):
                    rows = []

                for summary in rows:
                    if api.calls >= api.call_cap or downloaded_for_player >= max_downloads_per_player:
                        break
                    if not backfill._candidate_ok(summary):
                        report["rejected_summaries"] += 1
                        continue
                    found_candidates += 1
                    mid = summary.get("id")
                    if mid is None:
                        continue
                    path = backfill._match_cache_path(mid)
                    cached = backfill._read_gzip_json(path)
                    if isinstance(cached, dict):
                        report["cache_hits"] += 1
                        continue
                    try:
                        detail = api.get(f"/history/matches/{mid}", {"sequence": "clean"})
                    except Exception:
                        continue
                    if not _detail_quality_ok(detail):
                        report["detail_quality_rejected"] += 1
                        continue

                    backfill._write_gzip_json(path, detail)
                    report["downloaded_tapes"] += 1
                    downloaded_for_player += 1
                    if extract_first_set_games(detail):
                        report["tape_parse_ok"] += 1
                    else:
                        report["tape_parse_failed"] += 1

                # Coverage filters are applied after page slicing by the provider,
                # so a short/empty filtered page is NOT treated as end-of-history.
        except Exception as exc:
            fatal = type(exc).__name__
            attempt["last_error"] = fatal

        attempt["last_found_candidates"] = found_candidates
        attempt["last_downloaded"] = downloaded_for_player
        attempt["last_calls_total"] = api.calls

        # Persist progress after every player so a cancelled workflow does not
        # re-hit the same targets on the next run.
        state["updated_at"] = now.isoformat()
        _write_json(STATE_PATH, state)

        if getattr(api, "rate_limited", False):
            break

    report["calls_this_run"] = api.calls
    report["cached_tapes_after"] = len(list(backfill.MATCH_CACHE.glob("*.json.gz")))
    report["cache_mb_after"] = backfill._cache_size_mb()
    report["fatal"] = fatal
    report["status"] = "rate-limited" if getattr(api, "rate_limited", False) else ("partial" if fatal else "ok")
    report["yield_tapes_per_100_calls"] = round(
        100.0 * report["downloaded_tapes"] / max(1, api.calls), 2
    )

    if report["downloaded_tapes"] > 0:
        backfill._analyze_cache(report)

    _write_json(STATE_PATH, state)
    _write_json(REPORT_PATH, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    run()
