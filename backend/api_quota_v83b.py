from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
OUT = ROOT / "frontend" / "data"
STATE_PATH = CACHE / "api_quota_v83b.json"
REPORT_PATH = OUT / "api_quota_v83b.json"
META_PATH = OUT / "meta.json"

BASE_URL = "https://api.livetennisapi.com/api/public/v1"
UA = "TenisAI-v8.3B-CentralQuota/1.0"

# Total planned managed spend stays below the full daily allowance on purpose.
# The rest is a safety buffer for retries, provider accounting drift and future steps.
DEFAULT_POLICIES = {
    "fixtures": {
        "daily_fraction": 0.08,
        "run_cap": 12,
        "reserve_fraction": 0.03,
        "fallback": 2,
        "priority": "critical",
    },
    "pbp_current": {
        "daily_fraction": 0.42,
        "run_cap": 90,
        "reserve_fraction": 0.20,
        "fallback": 12,
        "priority": "critical-current",
    },
    "pbp_tracker": {
        "daily_fraction": 0.07,
        "run_cap": 18,
        "reserve_fraction": 0.15,
        "fallback": 2,
        "priority": "settlement",
    },
    "history_settle": {
        "daily_fraction": 0.10,
        "run_cap": 24,
        "reserve_fraction": 0.12,
        "fallback": 2,
        "priority": "settlement",
    },
    "history_backfill": {
        "daily_fraction": 0.08,
        "run_cap": 18,
        "reserve_fraction": 0.45,
        "fallback": 0,
        "priority": "background",
    },
}


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


def _policy(role: str) -> dict:
    base = dict(DEFAULT_POLICIES.get(role) or DEFAULT_POLICIES["history_backfill"])
    prefix = "API_QUOTA_" + role.upper()
    base["daily_fraction"] = _float_env(prefix + "_DAILY_FRACTION", base["daily_fraction"], 0.0, 0.80)
    base["run_cap"] = _int_env(prefix + "_RUN_CAP", base["run_cap"], 0, 500)
    base["reserve_fraction"] = _float_env(prefix + "_RESERVE_FRACTION", base["reserve_fraction"], 0.0, 0.95)
    base["fallback"] = _int_env(prefix + "_FALLBACK", base["fallback"], 0, 50)
    return base


def _usage_numbers(payload: dict) -> tuple[int | None, int | None, int | None, int]:
    today = (payload or {}).get("today") or {}
    limits = (payload or {}).get("limits") or {}
    per_day = limits.get("per_day")
    remaining = today.get("remaining_day")
    calls = today.get("calls")
    per_minute = limits.get("per_minute") or limits.get("requests_per_minute") or limits.get("rpm") or 60

    try:
        per_day = int(per_day) if per_day is not None else None
    except (TypeError, ValueError):
        per_day = None
    try:
        calls = int(calls) if calls is not None else None
    except (TypeError, ValueError):
        calls = None
    if remaining is None and per_day is not None and calls is not None:
        remaining = per_day - calls
    try:
        remaining = int(remaining) if remaining is not None else None
    except (TypeError, ValueError):
        remaining = None
    try:
        per_minute = max(1, int(per_minute))
    except (TypeError, ValueError):
        per_minute = 60
    return per_day, remaining, calls, per_minute


def _new_day_state(now: datetime, old: dict | None = None) -> dict:
    old = old if isinstance(old, dict) else {}
    day = now.date().isoformat()
    if old.get("quota_day") == day:
        old.setdefault("categories", {})
        return old
    return {
        "version": "v8.3B",
        "quota_day": day,
        "categories": {},
        "run": {},
        "last_good": old.get("last_good") or {},
    }


def _category_calls(state: dict, role: str) -> int:
    try:
        return max(0, int(((state.get("categories") or {}).get(role) or {}).get("calls") or 0))
    except (TypeError, ValueError):
        return 0


def compute_budget(
    *,
    per_day: int | None,
    remaining: int | None,
    role_spent: int,
    requested: int,
    daily_fraction: float,
    run_cap: int,
    reserve_fraction: float,
) -> dict:
    """Pure central quota policy. No network or filesystem access."""
    requested = max(0, int(requested))
    if not per_day or per_day <= 0 or remaining is None:
        return {
            "budget": 0,
            "daily_cap": 0,
            "reserve": 0,
            "cap_left": 0,
            "room": 0,
            "reason": "usage_unknown",
        }
    daily_cap = max(0, int(per_day * max(0.0, min(0.80, float(daily_fraction)))))
    reserve = max(0, int(per_day * max(0.0, min(0.95, float(reserve_fraction)))))
    cap_left = max(0, daily_cap - max(0, int(role_spent)))
    room = max(0, int(remaining) - reserve)
    budget = max(0, min(requested, max(0, int(run_cap)), cap_left, room))
    if budget > 0:
        reason = "ok"
    elif cap_left <= 0:
        reason = "role_daily_cap"
    elif room <= 0:
        reason = "protected_reserve"
    elif requested <= 0 or run_cap <= 0:
        reason = "requested_zero"
    else:
        reason = "no_room"
    return {
        "budget": budget,
        "daily_cap": daily_cap,
        "reserve": reserve,
        "cap_left": cap_left,
        "room": room,
        "reason": reason,
    }


def _write_report(state: dict) -> None:
    run = state.get("run") or {}
    per_day = run.get("per_day")
    remaining_start = run.get("remaining_start")
    managed = int(run.get("managed_calls") or 0)
    remaining_estimate = max(0, int(remaining_start) - managed) if isinstance(remaining_start, int) else None
    categories = {
        role: {
            "calls": _category_calls(state, role),
            "policy": _policy(role),
        }
        for role in DEFAULT_POLICIES
    }
    report = {
        "version": "v8.3B",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": run.get("status") or "not-started",
        "quota_day": state.get("quota_day"),
        "daily_limit": per_day,
        "calls_at_begin": run.get("calls_at_begin"),
        "remaining_at_begin": remaining_start,
        "managed_calls_this_run": managed,
        "remaining_estimate": remaining_estimate,
        "per_minute": run.get("per_minute"),
        "categories": categories,
        "last_allocation": state.get("last_allocation"),
        "policy_note": "fixtures/current PBP first; settlements next; historical backfill only from spare quota",
    }
    _write_json(REPORT_PATH, report)

    meta = _read_json(META_PATH, {})
    if not isinstance(meta, dict):
        meta = {}
    meta.update({
        "api_quota_v83b_status": report["status"],
        "api_quota_v83b_updated_at": report["updated_at"],
        "api_quota_v83b_daily_limit": report["daily_limit"],
        "api_quota_v83b_calls_at_begin": report["calls_at_begin"],
        "api_quota_v83b_managed_calls_run": report["managed_calls_this_run"],
        "api_quota_v83b_remaining_estimate": report["remaining_estimate"],
        "api_quota_v83b_categories": {k: v["calls"] for k, v in categories.items()},
        "api_quota_v83b_last_allocation": report["last_allocation"],
    })
    _write_json(META_PATH, meta)


def begin_guard(key: str | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    key = (key if key is not None else os.getenv("LIVE_TENNIS_API_KEY", "")).strip()
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    state = _new_day_state(now, _read_json(STATE_PATH, {}))
    categories = state.setdefault("categories", {})
    guard = categories.setdefault("guard", {"calls": 0})

    # One shared /usage check per workflow run replaces several independent checks.
    usage = None
    attempted = False
    if key:
        attempted = True
        try:
            r = requests.get(
                BASE_URL + "/usage",
                headers={"Authorization": f"Bearer {key}", "User-Agent": UA},
                timeout=(7, 18),
            )
            r.raise_for_status()
            value = r.json()
            usage = value if isinstance(value, dict) else None
        except Exception:
            usage = None
    if attempted:
        guard["calls"] = int(guard.get("calls") or 0) + 1

    per_day, remaining, calls, per_minute = _usage_numbers(usage or {})
    if usage is not None and per_day and remaining is not None:
        status = "ready"
        state["last_good"] = {
            "at": now.isoformat(),
            "per_day": per_day,
            "remaining": remaining,
            "calls": calls,
            "per_minute": per_minute,
        }
    else:
        status = "usage-unavailable" if key else "no-api-key"

    state["version"] = "v8.3B"
    state["run"] = {
        "started_at": now.isoformat(),
        "status": status,
        "per_day": per_day,
        "remaining_start": remaining,
        "calls_at_begin": calls,
        "per_minute": per_minute,
        "managed_calls": 0,
    }
    state["updated_at"] = now.isoformat()
    _write_json(STATE_PATH, state)
    _write_report(state)
    return state


def quota_budget(role: str, requested: int) -> tuple[int, dict]:
    """Return a role budget plus a usage-shaped compatibility snapshot."""
    now = datetime.now(timezone.utc)
    role = str(role or "history_backfill")
    requested = max(0, int(requested))
    state = _new_day_state(now, _read_json(STATE_PATH, {}))
    run = state.get("run") or {}
    policy = _policy(role)
    status = run.get("status")

    per_day = run.get("per_day")
    remaining_start = run.get("remaining_start")
    managed = int(run.get("managed_calls") or 0)
    remaining = max(0, int(remaining_start) - managed) if isinstance(remaining_start, int) else None
    role_spent = _category_calls(state, role)

    if status == "ready":
        calc = compute_budget(
            per_day=per_day,
            remaining=remaining,
            role_spent=role_spent,
            requested=requested,
            daily_fraction=policy["daily_fraction"],
            run_cap=policy["run_cap"],
            reserve_fraction=policy["reserve_fraction"],
        )
        budget = calc["budget"]
    else:
        budget = min(requested, int(policy["fallback"]))
        calc = {
            "budget": budget,
            "daily_cap": None,
            "reserve": None,
            "cap_left": None,
            "room": None,
            "reason": "guard_unavailable_fallback" if budget else "guard_unavailable_safe_skip",
        }

    calls_before = None
    if isinstance(per_day, int) and isinstance(remaining, int):
        calls_before = max(0, per_day - remaining)
    elif run.get("calls_at_begin") is not None:
        try:
            calls_before = int(run.get("calls_at_begin")) + managed
        except (TypeError, ValueError):
            calls_before = None

    alloc = {
        "role": role,
        "requested": requested,
        "budget": budget,
        "reason": calc["reason"],
        "remaining_before": remaining,
        "role_spent_today": role_spent,
        "daily_cap": calc.get("daily_cap"),
        "reserve": calc.get("reserve"),
        "priority": policy.get("priority"),
        "at": now.isoformat(),
    }
    state["last_allocation"] = alloc
    state["updated_at"] = now.isoformat()
    _write_json(STATE_PATH, state)
    _write_report(state)

    usage_like = {
        "today": {
            "calls": calls_before,
            "remaining_day": remaining,
        },
        "limits": {
            "per_day": per_day,
            "per_minute": run.get("per_minute") or 60,
        },
        "quota_v83b": alloc,
    }
    return int(budget), usage_like


def record_calls(role: str, calls: int) -> None:
    try:
        calls = max(0, int(calls))
    except (TypeError, ValueError):
        return
    if calls <= 0:
        return
    now = datetime.now(timezone.utc)
    state = _new_day_state(now, _read_json(STATE_PATH, {}))
    categories = state.setdefault("categories", {})
    rec = categories.setdefault(str(role), {"calls": 0})
    rec["calls"] = int(rec.get("calls") or 0) + calls
    rec["last_call_at"] = now.isoformat()
    run = state.setdefault("run", {})
    run["managed_calls"] = int(run.get("managed_calls") or 0) + calls
    state["updated_at"] = now.isoformat()
    _write_json(STATE_PATH, state)


def current_report() -> dict:
    state = _new_day_state(datetime.now(timezone.utc), _read_json(STATE_PATH, {}))
    _write_report(state)
    return _read_json(REPORT_PATH, {})


def main() -> None:
    import sys

    cmd = (sys.argv[1] if len(sys.argv) > 1 else "report").strip().casefold()
    if cmd == "begin":
        state = begin_guard()
        out = _read_json(REPORT_PATH, {})
    elif cmd in ("report", "status"):
        out = current_report()
    else:
        raise SystemExit("usage: api_quota_v83b.py [begin|report]")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
