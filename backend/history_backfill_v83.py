from __future__ import annotations

import gzip
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
CACHE = ROOT / "data" / "cache" / "pbp_v7"
MATCH_CACHE = CACHE / "matches"
STATE_PATH = CACHE / "history_backfill_v83.json"
REPORT_PATH = OUT / "history_backfill_v83.json"
PBP_BACKTEST_PATH = OUT / "pbp_backtest.json"

BASE_URL = "https://api.livetennisapi.com/api/public/v1"
UA = "TenisAI-v8.3A-HistoricalBackfill/1.0"

DEFAULT_STOP_DATE = date(2023, 1, 1)
DEFAULT_DAILY_FRACTION = 0.12
DEFAULT_HARD_RESERVE_FRACTION = 0.45
DEFAULT_RUN_CAP = 18
DEFAULT_MIN_INTERVAL_HOURS = 3.0
DEFAULT_MAX_CACHE_MB = 900.0
LIST_LIMIT = 200


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


def _read_gzip_json(path: Path):
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def _write_gzip_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.gz")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as f:
        json.dump(value, f, ensure_ascii=False, separators=(",", ":"))
    tmp.replace(path)


def _parse_dt(value):
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _parse_date(value, fallback: date) -> date:
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return fallback


def _truthy_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().casefold() not in ("", "0", "false", "no", "off")


def _float_env(name: str, default: float, lo: float, hi: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(lo, min(hi, value))


def _int_env(name: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int(float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        value = default
    return max(lo, min(hi, value))


def _cache_size_mb() -> float:
    if not MATCH_CACHE.exists():
        return 0.0
    total = 0
    for p in MATCH_CACHE.glob("*.json.gz"):
        try:
            total += p.stat().st_size
        except OSError:
            pass
    return round(total / (1024 * 1024), 2)


def _candidate_ok(m: dict) -> bool:
    if not isinstance(m, dict) or m.get("is_doubles"):
        return False
    if m.get("id") is None:
        return False
    tape = m.get("tape") or {}
    if tape.get("coverage") != "from_start":
        return False
    if tape.get("starts_at_love") is False:
        return False
    completeness = tape.get("completeness")
    if completeness is not None:
        try:
            if float(completeness) < 0.95:
                return False
        except (TypeError, ValueError):
            pass
    try:
        if int(tape.get("rows") or 0) < 20:
            return False
    except (TypeError, ValueError):
        return False
    return True


def _match_cache_path(mid: int | str) -> Path:
    return MATCH_CACHE / f"{mid}.json.gz"


def _usage_numbers(payload: dict) -> tuple[int | None, int | None, int]:
    today = (payload or {}).get("today") or {}
    limits = (payload or {}).get("limits") or {}
    per_day = limits.get("per_day")
    remaining = today.get("remaining_day")
    calls = today.get("calls")
    try:
        per_day = int(per_day)
    except (TypeError, ValueError):
        per_day = None
    if remaining is None and per_day is not None:
        try:
            remaining = per_day - int(calls)
        except (TypeError, ValueError):
            remaining = None
    try:
        remaining = int(remaining) if remaining is not None else None
    except (TypeError, ValueError):
        remaining = None

    per_minute = (
        limits.get("per_minute")
        or limits.get("requests_per_minute")
        or limits.get("rpm")
        or 60
    )
    try:
        per_minute = max(1, int(per_minute))
    except (TypeError, ValueError):
        per_minute = 60
    return per_day, remaining, per_minute


def compute_backfill_budget(
    *,
    per_day: int | None,
    remaining_day: int | None,
    spent_today: int,
    daily_fraction: float = DEFAULT_DAILY_FRACTION,
    hard_reserve_fraction: float = DEFAULT_HARD_RESERVE_FRACTION,
    run_cap: int = DEFAULT_RUN_CAP,
) -> dict:
    """Pure quota policy used by tests and runtime.

    The returned remote_budget EXCLUDES the /usage request that has already happened.
    Backfill only gets quota above the hard reserve and below its own daily allowance.
    """
    if not per_day or per_day <= 0 or remaining_day is None:
        return {
            "remote_budget": 0,
            "daily_cap": 0,
            "hard_reserve": 0,
            "reason": "usage_unknown",
        }
    daily_cap = max(0, int(per_day * max(0.0, min(0.5, daily_fraction))))
    hard_reserve = max(1, int(per_day * max(0.25, min(0.9, hard_reserve_fraction))))
    own_left = max(0, daily_cap - max(0, int(spent_today)))
    room = max(0, int(remaining_day) - hard_reserve)
    remote_budget = max(0, min(int(run_cap), own_left, room))
    reason = "ok" if remote_budget > 0 else (
        "daily_backfill_cap" if own_left <= 0 else "hard_reserve"
    )
    return {
        "remote_budget": remote_budget,
        "daily_cap": daily_cap,
        "hard_reserve": hard_reserve,
        "reason": reason,
    }


def _usage(key: str) -> dict | None:
    try:
        r = requests.get(
            BASE_URL + "/usage",
            headers={"Authorization": f"Bearer {key}", "User-Agent": UA},
            timeout=(7, 18),
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


class API:
    def __init__(self, key: str, call_cap: int, per_minute: int):
        self.key = key
        self.call_cap = max(0, int(call_cap))
        self.calls = 0
        self.session = requests.Session()
        self.headers = {"Authorization": f"Bearer {key}", "User-Agent": UA}
        # A little slower than the documented limit. Current-match jobs run before us.
        self.min_interval = max(0.0, 60.0 / max(1, int(per_minute)) * 1.05)
        self.last_call_monotonic = 0.0
        self.rate_limited = False

    def _pace(self):
        if self.last_call_monotonic <= 0 or self.min_interval <= 0:
            return
        wait = self.min_interval - (time.monotonic() - self.last_call_monotonic)
        if wait > 0:
            time.sleep(wait)

    def get(self, path: str, params: dict | None = None) -> dict:
        if self.calls >= self.call_cap:
            raise RuntimeError("history_backfill_budget_exhausted")
        self._pace()
        r = self.session.get(
            BASE_URL + path,
            params=params,
            headers=self.headers,
            timeout=(7, 25),
        )
        self.calls += 1
        self.last_call_monotonic = time.monotonic()
        if r.status_code == 429:
            self.rate_limited = True
            retry_after = r.headers.get("Retry-After")
            try:
                wait = min(30.0, max(2.0, float(retry_after)))
            except (TypeError, ValueError):
                wait = 5.0
            time.sleep(wait)
            raise RuntimeError("history_backfill_rate_limited")
        r.raise_for_status()
        value = r.json()
        return value if isinstance(value, dict) else {}


def _state_for_today(state: dict, today: date) -> dict:
    if not isinstance(state, dict):
        state = {}
    state.setdefault("version", "v8.3A")
    if state.get("quota_day") != today.isoformat():
        state["quota_day"] = today.isoformat()
        state["backfill_calls_today"] = 0
    return state


def _initial_cursor(now: datetime) -> date:
    requested = os.getenv("HISTORY_BACKFILL_START_DATE", "").strip()
    if requested:
        try:
            return date.fromisoformat(requested)
        except ValueError:
            pass
    return (now - timedelta(days=1)).date()


def _stop_date() -> date:
    raw = os.getenv("HISTORY_BACKFILL_STOP_DATE", DEFAULT_STOP_DATE.isoformat()).strip()
    try:
        value = date.fromisoformat(raw)
    except ValueError:
        value = DEFAULT_STOP_DATE
    return max(DEFAULT_STOP_DATE, value)


def _interval_due(state: dict, now: datetime, min_hours: float) -> bool:
    last = _parse_dt(state.get("last_run_at"))
    return not last or now - last >= timedelta(hours=max(0.0, min_hours))


def _page_rows(payload: dict) -> tuple[list[dict], dict]:
    rows = payload.get("data") or []
    meta = payload.get("meta") or {}
    return (rows if isinstance(rows, list) else []), (meta if isinstance(meta, dict) else {})


def _write_report(report: dict, meta_update: bool = True) -> None:
    _write_json(REPORT_PATH, report)
    if not meta_update:
        return
    meta_path = OUT / "meta.json"
    meta = _read_json(meta_path, {})
    if not isinstance(meta, dict):
        meta = {}
    meta.update({
        "history_backfill_v83_status": report.get("status"),
        "history_backfill_v83_updated_at": report.get("updated_at"),
        "history_backfill_v83_cursor_date": report.get("cursor_date"),
        "history_backfill_v83_calls": report.get("calls_this_run"),
        "history_backfill_v83_downloaded": report.get("downloaded_tapes"),
        "history_backfill_v83_cached_tapes": report.get("cached_tapes"),
        "history_backfill_v83_cache_mb": report.get("cache_mb"),
        "history_backfill_v83_daily_cap": report.get("daily_cap"),
        "history_backfill_v83_hard_reserve": report.get("hard_reserve"),
    })
    _write_json(meta_path, meta)


def _analyze_cache(report: dict) -> None:
    """Immediately analyse every newly cached tape without making another API call."""
    try:
        from pbp_tracker import backtest_cache
        result = backtest_cache()
        _write_json(PBP_BACKTEST_PATH, result)
        report["analysis"] = {
            "status": "updated",
            "cached_tapes": result.get("cached_tapes"),
            "players": result.get("players"),
            "observations": ((result.get("overall") or {}).get("n")),
            "accuracy": ((result.get("overall") or {}).get("accuracy")),
            "green_n": ((result.get("overall") or {}).get("green_n")),
            "green_accuracy": ((result.get("overall") or {}).get("green_accuracy")),
        }
    except Exception as exc:
        report["analysis"] = {"status": "safe-skip", "error": type(exc).__name__}


def run_backfill(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    key = os.getenv("LIVE_TENNIS_API_KEY", "").strip()
    enabled = _truthy_env("HISTORY_BACKFILL_ENABLED", True)
    min_hours = _float_env(
        "HISTORY_BACKFILL_MIN_INTERVAL_HOURS",
        DEFAULT_MIN_INTERVAL_HOURS,
        0.0,
        24.0,
    )
    max_cache_mb = _float_env(
        "HISTORY_BACKFILL_MAX_CACHE_MB",
        DEFAULT_MAX_CACHE_MB,
        50.0,
        5000.0,
    )
    daily_fraction = _float_env(
        "HISTORY_BACKFILL_DAILY_FRACTION",
        DEFAULT_DAILY_FRACTION,
        0.01,
        0.40,
    )
    reserve_fraction = _float_env(
        "HISTORY_BACKFILL_HARD_RESERVE_FRACTION",
        DEFAULT_HARD_RESERVE_FRACTION,
        0.25,
        0.90,
    )
    run_cap = _int_env("HISTORY_BACKFILL_RUN_CAP", DEFAULT_RUN_CAP, 1, 120)

    CACHE.mkdir(parents=True, exist_ok=True)
    MATCH_CACHE.mkdir(parents=True, exist_ok=True)
    state = _state_for_today(_read_json(STATE_PATH, {}), now.date())
    cursor = _parse_date(state.get("cursor_date"), _initial_cursor(now))
    stop_date = _stop_date()
    if cursor < stop_date:
        cursor = _initial_cursor(now)
        state["offset"] = 0
        state["pending"] = []

    base_report = {
        "version": "v8.3A",
        "updated_at": now.isoformat(),
        "status": "init",
        "policy": "critical-current-jobs-first; spare-quota-only; fail-closed",
        "cursor_date": cursor.isoformat(),
        "stop_date": stop_date.isoformat(),
        "calls_this_run": 0,
        "downloaded_tapes": 0,
        "cache_hits": 0,
        "rejected_summaries": 0,
        "tape_parse_ok": 0,
        "tape_parse_failed": 0,
        "cached_tapes": len(list(MATCH_CACHE.glob("*.json.gz"))),
        "cache_mb": _cache_size_mb(),
    }

    if not enabled:
        base_report["status"] = "disabled"
        _write_report(base_report)
        return base_report
    if not key:
        base_report["status"] = "no-api-key"
        _write_report(base_report)
        return base_report
    if not _interval_due(state, now, min_hours):
        base_report["status"] = "interval-skip"
        base_report["last_run_at"] = state.get("last_run_at")
        _write_report(base_report)
        return base_report
    if base_report["cache_mb"] >= max_cache_mb:
        base_report["status"] = "cache-cap"
        base_report["max_cache_mb"] = max_cache_mb
        _write_report(base_report)
        return base_report

    usage = _usage(key)
    if usage is None:
        base_report["status"] = "usage-unavailable-safe-skip"
        _write_report(base_report)
        return base_report

    per_day, remaining_day, per_minute = _usage_numbers(usage)
    policy = compute_backfill_budget(
        per_day=per_day,
        remaining_day=remaining_day,
        spent_today=int(state.get("backfill_calls_today") or 0),
        daily_fraction=daily_fraction,
        hard_reserve_fraction=reserve_fraction,
        run_cap=run_cap,
    )
    base_report.update({
        "daily_limit": per_day,
        "remaining_before": remaining_day,
        "per_minute": per_minute,
        "daily_cap": policy["daily_cap"],
        "hard_reserve": policy["hard_reserve"],
        "backfill_calls_today_before": int(state.get("backfill_calls_today") or 0),
        "remote_budget": policy["remote_budget"],
    })

    if policy["remote_budget"] <= 0:
        base_report["status"] = f"quota-skip:{policy['reason']}"
        # Count the usage check against our own historical allowance.
        state["backfill_calls_today"] = int(state.get("backfill_calls_today") or 0) + 1
        state["last_run_at"] = now.isoformat()
        _write_json(STATE_PATH, state)
        base_report["calls_this_run"] = 1
        _write_report(base_report)
        return base_report

    api = API(key, policy["remote_budget"], per_minute)
    pending = state.get("pending") if isinstance(state.get("pending"), list) else []
    offset = int(state.get("offset") or 0)
    page_has_more = bool(state.get("page_has_more", True))
    page_size = int(state.get("page_size") or 0)

    downloaded = cache_hits = rejected = parse_ok = parse_failed = pages = 0
    fatal = None

    try:
        while api.calls < api.call_cap:
            if not pending:
                payload = api.get(
                    "/history/matches",
                    {
                        "from": cursor.isoformat(),
                        "to": cursor.isoformat(),
                        "limit": LIST_LIMIT,
                        "offset": offset,
                    },
                )
                pages += 1
                rows, meta = _page_rows(payload)
                page_size = len(rows)
                has_more_meta = meta.get("has_more")
                if isinstance(has_more_meta, bool):
                    page_has_more = has_more_meta
                else:
                    total = meta.get("total")
                    try:
                        page_has_more = offset + len(rows) < int(total)
                    except (TypeError, ValueError):
                        page_has_more = len(rows) >= LIST_LIMIT

                pending = []
                for m in rows:
                    if _candidate_ok(m):
                        pending.append(m)
                    else:
                        rejected += 1

                state["pending"] = pending
                state["page_has_more"] = page_has_more
                state["page_size"] = page_size
                _write_json(STATE_PATH, state)

                if not rows:
                    cursor = cursor - timedelta(days=1)
                    offset = 0
                    page_has_more = True
                    state["cursor_date"] = cursor.isoformat()
                    state["offset"] = 0
                    state["pending"] = []
                    if cursor < stop_date:
                        break
                    continue

                if not pending:
                    if page_has_more:
                        offset += page_size
                    else:
                        cursor = cursor - timedelta(days=1)
                        offset = 0
                    state["cursor_date"] = cursor.isoformat()
                    state["offset"] = offset
                    state["pending"] = []
                    if cursor < stop_date:
                        break
                    continue

            while pending and api.calls < api.call_cap:
                summary = pending.pop(0)
                mid = summary.get("id")
                if mid is None:
                    continue
                path = _match_cache_path(mid)
                if path.exists() and _read_gzip_json(path) is not None:
                    cache_hits += 1
                    continue
                try:
                    tape = api.get(f"/history/matches/{mid}", {"sequence": "clean"})
                except RuntimeError as exc:
                    fatal = str(exc)
                    pending.insert(0, summary)
                    break
                _write_gzip_json(path, tape)
                downloaded += 1

                # Analyse the tape immediately so we know whether it is useful.
                try:
                    from pbp_enrich import extract_first_set_games
                    if extract_first_set_games(tape):
                        parse_ok += 1
                    else:
                        parse_failed += 1
                except Exception:
                    parse_failed += 1

                if _cache_size_mb() >= max_cache_mb:
                    fatal = "cache_cap_reached"
                    break

            state["pending"] = pending
            if fatal or api.calls >= api.call_cap:
                break

            if not pending:
                if page_has_more:
                    offset += page_size
                else:
                    cursor = cursor - timedelta(days=1)
                    offset = 0
                state["cursor_date"] = cursor.isoformat()
                state["offset"] = offset
                state["page_has_more"] = True
                state["page_size"] = 0
                _write_json(STATE_PATH, state)
                if cursor < stop_date:
                    break

    except requests.HTTPError as exc:
        fatal = f"http_{getattr(exc.response, 'status_code', 'error')}"
    except Exception as exc:
        fatal = type(exc).__name__

    state["cursor_date"] = cursor.isoformat()
    state["offset"] = offset
    state["pending"] = pending
    state["last_run_at"] = now.isoformat()
    # The /usage call is also ours, so include it in the backfill daily allowance.
    spent_run = api.calls + 1
    state["backfill_calls_today"] = int(state.get("backfill_calls_today") or 0) + spent_run
    state["updated_at"] = now.isoformat()
    _write_json(STATE_PATH, state)

    base_report.update({
        "status": "rate-limit-stop" if api.rate_limited else ("safe-stop:" + fatal if fatal else "ok"),
        "cursor_date": cursor.isoformat(),
        "offset": offset,
        "pending": len(pending),
        "pages": pages,
        "calls_this_run": spent_run,
        "api_remote_calls": api.calls,
        "downloaded_tapes": downloaded,
        "cache_hits": cache_hits,
        "rejected_summaries": rejected,
        "tape_parse_ok": parse_ok,
        "tape_parse_failed": parse_failed,
        "backfill_calls_today_after": state["backfill_calls_today"],
        "remaining_estimate_after": (
            max(0, int(remaining_day) - api.calls) if remaining_day is not None else None
        ),
        "cached_tapes": len(list(MATCH_CACHE.glob("*.json.gz"))),
        "cache_mb": _cache_size_mb(),
        "max_cache_mb": max_cache_mb,
    })

    _analyze_cache(base_report)
    _write_report(base_report)
    return base_report


def main() -> None:
    # Background history must never block current-match production/deploy.
    try:
        report = run_backfill()
    except Exception as exc:
        now = datetime.now(timezone.utc)
        report = {
            "version": "v8.3A",
            "updated_at": now.isoformat(),
            "status": "fatal-safe-skip",
            "error": type(exc).__name__,
            "policy": "background history never fails production",
        }
        try:
            _write_report(report)
        except Exception:
            pass
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
