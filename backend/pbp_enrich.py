from __future__ import annotations

import gzip
import json
import math
import os
import re
import time
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
CACHE = ROOT / "data" / "cache" / "pbp_v7"
RESULTS_PATH = OUT / "results.json"
META_PATH = OUT / "meta.json"
INDEX_PATH = CACHE / "players.json"

BASE_URL = "https://api.livetennisapi.com/api/public/v1"
UA = "TenisAI-v7.1-Tendencies/1.0"
PROFILE_TTL_HOURS = 12
EARLY_HOLD_MATCHES = 8
MAX_PROFILE_MATCHES = 20
MAX_LIST_PAGES = 2
LIST_LIMIT = 100
RUN_CALL_CAP = 560
DAILY_RESERVE = 180
MIN_RELIABLE_MATCHES = 5


def _key(value: Any) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


def _read_json(path: Path, fallback):
    try:
        x = json.loads(path.read_text(encoding="utf-8"))
        return x
    except (FileNotFoundError, json.JSONDecodeError, OSError):
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


class API:
    def __init__(self, key: str, call_cap: int = RUN_CALL_CAP):
        self.key = key
        self.calls = 0
        self.call_cap = max(0, int(call_cap))
        self.session = requests.Session()
        self.headers = {"Authorization": f"Bearer {key}", "User-Agent": UA}

    def get(self, path: str, params: dict | None = None):
        if self.calls >= self.call_cap:
            raise RuntimeError("pbp_run_budget_exhausted")
        r = self.session.get(BASE_URL + path, params=params, headers=self.headers, timeout=(7, 25))
        self.calls += 1
        if r.status_code == 429:
            retry = min(10, max(1, int(float(r.headers.get("Retry-After", "2") or 2))))
            time.sleep(retry)
            if self.calls >= self.call_cap:
                raise RuntimeError("pbp_run_budget_exhausted")
            r = self.session.get(BASE_URL + path, params=params, headers=self.headers, timeout=(7, 25))
            self.calls += 1
        r.raise_for_status()
        return r.json()


def _usage_budget(key: str) -> tuple[int, dict]:
    """One cheap request before enrichment. Keep a daily reserve for normal fixture refreshes."""
    try:
        r = requests.get(
            BASE_URL + "/usage",
            headers={"Authorization": f"Bearer {key}", "User-Agent": UA},
            timeout=(7, 18),
        )
        r.raise_for_status()
        u = r.json() or {}
        today = u.get("today") or {}
        limits = u.get("limits") or {}
        remaining = today.get("remaining_day")
        if remaining is None:
            per_day = limits.get("per_day")
            calls = today.get("calls")
            if isinstance(per_day, (int, float)) and isinstance(calls, (int, float)):
                remaining = int(per_day) - int(calls)
        if isinstance(remaining, (int, float)):
            return max(0, min(RUN_CALL_CAP, int(remaining) - DAILY_RESERVE)), u
        return RUN_CALL_CAP, u
    except Exception:
        # Fail conservative if usage endpoint is temporarily unavailable.
        return 180, {}


def _player_cache_entry(index: dict, player: str) -> dict | None:
    return (index.get("players") or {}).get(_key(player))


def _entry_fresh(entry: dict | None, now: datetime) -> bool:
    if not entry:
        return False
    d = _parse_dt(entry.get("fetched_at"))
    return bool(d and now - d < timedelta(hours=PROFILE_TTL_HOURS))


def _candidate_ok(m: dict, as_of: datetime | None = None) -> bool:
    if not isinstance(m, dict) or m.get("is_doubles"):
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
        except Exception:
            pass
    try:
        if int(tape.get("rows") or 0) < 20:
            return False
    except Exception:
        return False
    if as_of:
        d = _parse_dt(m.get("scheduled_time"))
        if d and d >= as_of:
            return False
    return m.get("id") is not None


def _refresh_player_index(api: API, index: dict, player: str, player_id: int, as_of: datetime, now: datetime) -> dict:
    """Refresh one player's completed-match index.

    IMPORTANT: /history/matches?player= expects a numeric roster player id,
    not a player name. v7.0 used the name and the API correctly returned HTTP 400.
    """
    players = index.setdefault("players", {})
    k = _key(player)
    prior = players.get(k)
    if _entry_fresh(prior, now) and int(prior.get("player_id") or 0) == int(player_id):
        return prior
    # If today's API budget is exhausted, stale cached history is better than deleting PBP from the UI.
    if prior and int(prior.get("player_id") or 0) == int(player_id) and api.calls >= api.call_cap:
        return prior

    rows: list[dict] = []
    seen = set()
    for page_no in range(MAX_LIST_PAGES):
        payload = api.get(
            "/history/matches",
            {
                "player": int(player_id),
                "to": as_of.date().isoformat(),
                "limit": LIST_LIMIT,
                "offset": page_no * LIST_LIMIT,
            },
        )
        page = payload.get("data") or []
        meta = payload.get("meta") or {}
        for m in page:
            mid = m.get("id")
            if mid in seen or not _candidate_ok(m, as_of):
                continue
            seen.add(mid)
            rows.append(m)
        if len(rows) >= MAX_PROFILE_MATCHES:
            break
        # No coverage filter is sent, so an empty page really is an end signal.
        if not page or meta.get("has_more") is False:
            break

    rows.sort(key=lambda m: m.get("scheduled_time") or "", reverse=True)
    entry = {
        "player": player,
        "player_id": int(player_id),
        "fetched_at": now.isoformat(),
        "matches": rows[: max(MAX_PROFILE_MATCHES + 2, MAX_PROFILE_MATCHES)],
    }
    players[k] = entry
    index["updated_at"] = now.isoformat()
    return entry


def _match_cache_path(mid: int | str) -> Path:
    return CACHE / "matches" / f"{mid}.json.gz"


def _get_tape(api: API, mid: int | str):
    p = _match_cache_path(mid)
    cached = _read_gzip_json(p)
    if cached is not None:
        return cached, True
    payload = api.get(f"/history/matches/{mid}", {"sequence": "clean"})
    _write_gzip_json(p, payload)
    return payload, False


def _first_set_state(row: dict) -> tuple[int, int] | None:
    games = row.get("games")
    try:
        a = int(games[0][0])
        b = int(games[1][0])
        if a < 0 or b < 0:
            return None
        return a, b
    except Exception:
        return None


def extract_first_set_games(tape_payload: dict) -> dict | None:
    """Convert clean point states into first-set games with server + hold/break.

    Each game is inferred from a +1 transition in the first-set game score.
    Missing server on the first row is repaired only by strict serve alternation
    from another observed server in that same set.
    """
    rows = tape_payload.get("tape") or []
    if not isinstance(rows, list) or len(rows) < 12:
        return None

    transitions = []
    last_state = None
    last_server = None
    state_server = None

    for row in rows:
        st = _first_set_state(row)
        if st is None:
            continue
        server = row.get("server")
        try:
            server = int(server) if server is not None else None
        except Exception:
            server = None
        if server not in (1, 2):
            server = None

        if last_state is None:
            last_state = st
            state_server = server
            last_server = server
            continue

        if st == last_state:
            if server in (1, 2):
                state_server = server
                last_server = server
            continue

        old_total = sum(last_state)
        new_total = sum(st)
        if new_total != old_total + 1:
            # Score correction or a skipped game -> not reliable enough for Early Hold.
            if new_total < old_total:
                last_state = st
                state_server = server
                last_server = server
                transitions = []
                continue
            return None

        da, db = st[0] - last_state[0], st[1] - last_state[1]
        if (da, db) not in ((1, 0), (0, 1)):
            return None
        winner = 1 if da == 1 else 2
        transitions.append(
            {
                "game_no": new_total,
                "before": list(last_state),
                "after": list(st),
                "winner": winner,
                "server": state_server or last_server,
            }
        )
        last_state = st
        state_server = server
        last_server = server

        # First set is over.
        if (st[0] >= 6 or st[1] >= 6) and abs(st[0] - st[1]) >= 2:
            break
        if st in ((7, 6), (6, 7)):
            break

    if len(transitions) < 6:
        return None

    # Fill isolated missing servers only by alternating from a known game.
    known = next((i for i, g in enumerate(transitions) if g.get("server") in (1, 2)), None)
    if known is None:
        return None
    anchor = transitions[known]["server"]
    for i, g in enumerate(transitions):
        expected = anchor if (i - known) % 2 == 0 else (3 - anchor)
        if g.get("server") is None:
            g["server"] = expected
        elif g["server"] != expected:
            return None
        g["hold"] = bool(g["winner"] == g["server"])

    checkpoints = {}
    for g in transitions:
        if g["game_no"] in (1, 2, 4, 6):
            checkpoints[str(g["game_no"])] = f'{g["after"][0]}:{g["after"][1]}'

    if not all(str(n) in checkpoints for n in (1, 2, 4, 6)):
        return None

    service_no = {1: 0, 2: 0}
    service_games = {1: {}, 2: {}}
    for g in transitions:
        s = g["server"]
        service_no[s] += 1
        n = service_no[s]
        if n <= 3:
            service_games[s][str(n)] = 1.0 if g["hold"] else 0.0

    return {
        "games": transitions,
        "checkpoints": checkpoints,
        "service_games": service_games,
        "first_set_score": f'{transitions[-1]["after"][0]}:{transitions[-1]["after"][1]}',
    }


def _match_object(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def resolve_current_player_ids(api: API, targets: list[dict], counters: dict, seed: dict[str, int] | None = None) -> dict[str, int]:
    """Resolve stable roster ids from the current fixture's match detail.

    This avoids ambiguous name-search matching and gives the exact id required
    by /history/matches?player=<integer>.
    """
    out: dict[str, int] = dict(seed or {})
    for m in targets:
        # Future-proof: if update.py starts carrying ids, use them without an extra call.
        for side in ("p1", "p2"):
            name = m.get(side)
            pid = m.get(f"{side}_id")
            try:
                if name and pid is not None:
                    out[_key(name)] = int(pid)
            except (TypeError, ValueError):
                pass

        if all(_key(m.get(s)) in out for s in ("p1", "p2")):
            continue

        mid = m.get("id")
        if mid is None:
            continue
        try:
            detail = _match_object(api.get(f"/matches/{mid}"))
            counters["match_detail_calls"] += 1
        except Exception:
            counters["match_detail_errors"] += 1
            continue

        players = detail.get("players") or {}
        for side in ("p1", "p2"):
            target_name = m.get(side)
            target_key = _key(target_name)
            # Prefer the same side, but verify the name to avoid accidental swaps.
            cand = players.get(side) or {}
            cand_name = cand.get("name")
            cand_id = cand.get("id")
            if cand_id is not None and (not target_key or _key(cand_name) == target_key):
                try:
                    out[target_key] = int(cand_id)
                    continue
                except (TypeError, ValueError):
                    pass
            # Safe fallback: scan both participants for an exact normalized name.
            for obj in players.values():
                if isinstance(obj, dict) and _key(obj.get("name")) == target_key and obj.get("id") is not None:
                    try:
                        out[target_key] = int(obj["id"])
                    except (TypeError, ValueError):
                        pass
                    break
    return out


def _participant_side(payload: dict, player: str) -> int | None:
    match = payload.get("match") or {}
    players = match.get("players") or {}
    p1 = (players.get("p1") or {}).get("name")
    p2 = (players.get("p2") or {}).get("name")
    k = _key(player)
    if _key(p1) == k:
        return 1
    if _key(p2) == k:
        return 2
    return None


def _source_weight(payload: dict) -> float:
    meta = payload.get("meta") or {}
    src = str(meta.get("point_source") or "").lower()
    if src == "observed":
        return 1.0
    if src in ("mixed", "observed+reconstructed"):
        return 0.84
    if src == "reconstructed":
        return 0.70
    return 0.76


def _weighted_mean(pairs: list[tuple[float, float]]) -> float | None:
    pairs = [(float(v), float(w)) for v, w in pairs if v is not None and w > 0]
    if not pairs:
        return None
    z = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / z if z else None



def _event_ratio(values: list[float | None]) -> dict:
    x = [float(v) for v in values if v in (0.0, 1.0)]
    if not x:
        return {"hits": 0, "n": 0, "pct": None}
    hits = int(sum(x))
    n = len(x)
    return {"hits": hits, "n": n, "pct": round(100.0 * hits / n, 1)}


def _pbp_window(samples: list[dict], n: int) -> dict:
    x = samples[:n]
    def state(key, expected):
        return _event_ratio([1.0 if s.get(key) == expected else 0.0 for s in x if s.get(key) is not None])
    return {
        "requested": n,
        "sample_matches": len(x),
        "metrics": {
            "hold1": _event_ratio([s.get("hold1") for s in x]),
            "hold2": _event_ratio([s.get("hold2") for s in x]),
            "hold3": _event_ratio([s.get("hold3") for s in x]),
            "after2_11": state("after2", "1:1"),
            "after4_22": state("after4", "2:2"),
            "after6_33": state("after6", "3:3"),
            "sequence_11_22_33": _event_ratio([
                1.0 if s.get("after2") == "1:1" and s.get("after4") == "2:2" and s.get("after6") == "3:3" else 0.0
                for s in x
            ]),
            "set1_win": _event_ratio([s.get("set1_win") for s in x]),
            "set1_over_8.5": _event_ratio([s.get("over85") for s in x]),
            "set1_over_9.5": _event_ratio([s.get("over95") for s in x]),
        },
    }


def _pbp_tendency_windows(samples: list[dict], surface: str) -> dict:
    surf = str(surface or "").lower()
    same_surface = [s for s in samples if surf and s.get("surface") == surf]
    return {
        "source": "Live Tennis API BASIC point-by-point",
        "surface_name": surf,
        "all": {str(n): _pbp_window(samples, n) for n in (5, 10, 20)},
        "surface": {str(n): _pbp_window(same_surface, n) for n in (5, 10, 20)},
    }


def build_profile(api: API, index: dict, player: str, player_id: int | None, surface: str, as_of: datetime, now: datetime, counters: dict) -> dict:
    if player_id is None:
        return {"player": player, "matches": 0, "ready": False, "ehs": None, "quality": "N/D", "error": "player_id_unresolved"}
    try:
        entry = _refresh_player_index(api, index, player, int(player_id), as_of, now)
    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        detail = ""
        try:
            detail = str((e.response.json() or {}).get("error") or "")
        except Exception:
            pass
        return {"player": player, "player_id": player_id, "matches": 0, "ready": False, "ehs": None, "quality": "N/D", "error": f"HTTP_{status}:{detail}"}
    except Exception as e:
        return {"player": player, "player_id": player_id, "matches": 0, "ready": False, "ehs": None, "quality": "N/D", "error": type(e).__name__}

    samples = []
    for summary in (entry.get("matches") or [])[: MAX_PROFILE_MATCHES + 2]:
        if len(samples) >= MAX_PROFILE_MATCHES:
            break
        mid = summary.get("id")
        if mid is None:
            continue
        try:
            payload, hit = _get_tape(api, mid)
            counters["tape_cache_hits" if hit else "tape_downloads"] += 1
        except Exception:
            counters["tape_errors"] += 1
            continue
        parsed = extract_first_set_games(payload)
        if not parsed:
            continue
        side = _participant_side(payload, player)
        if side not in (1, 2):
            continue
        sg = parsed["service_games"].get(side) or {}
        if not sg.get("1") in (0.0, 1.0) or not sg.get("2") in (0.0, 1.0):
            continue
        try:
            fs_a, fs_b = [int(v) for v in str(parsed.get("first_set_score") or "").split(":", 1)]
            first_set_games = fs_a + fs_b
            set1_win = 1.0 if (side == 1 and fs_a > fs_b) or (side == 2 and fs_b > fs_a) else 0.0
            over85 = 1.0 if first_set_games > 8.5 else 0.0
            over95 = 1.0 if first_set_games > 9.5 else 0.0
        except Exception:
            set1_win = over85 = over95 = None

        samples.append(
            {
                "id": mid,
                "date": summary.get("scheduled_time"),
                "surface": str(summary.get("surface") or "").lower(),
                "source_weight": _source_weight(payload),
                "hold1": sg.get("1"),
                "hold2": sg.get("2"),
                "hold3": sg.get("3"),
                "after2": parsed["checkpoints"].get("2"),
                "after4": parsed["checkpoints"].get("4"),
                "after6": parsed["checkpoints"].get("6"),
                "set1_win": set1_win,
                "over85": over85,
                "over95": over95,
            }
        )

    # Early Hold score remains deliberately based on the latest 8.
    # The longer sample (up to 20) is exposed only as descriptive player tendencies.
    eh_samples = samples[:EARLY_HOLD_MATCHES]

    # Recent 5 high weight, previous 3 lower. Same surface gets a strong bonus.
    hold_pairs = {1: [], 2: [], 3: []}
    state_pairs = {"1:1": [], "2:2": [], "3:3": [], "sequence": []}
    surface_matches = 0
    for i, s in enumerate(eh_samples):
        recency = 1.0 if i < 5 else 0.55
        same_surface = bool(surface and s["surface"] == surface.lower())
        surf_w = 1.35 if same_surface else (0.76 if surface else 1.0)
        if same_surface:
            surface_matches += 1
        w = recency * surf_w * float(s["source_weight"])
        for n in (1, 2, 3):
            v = s.get(f"hold{n}")
            if v in (0.0, 1.0):
                hold_pairs[n].append((v, w))
        state_pairs["1:1"].append((1.0 if s["after2"] == "1:1" else 0.0, w))
        state_pairs["2:2"].append((1.0 if s["after4"] == "2:2" else 0.0, w))
        state_pairs["3:3"].append((1.0 if s["after6"] == "3:3" else 0.0, w))
        seq = s["after2"] == "1:1" and s["after4"] == "2:2" and s["after6"] == "3:3"
        state_pairs["sequence"].append((1.0 if seq else 0.0, w))

    n = len(eh_samples)
    holds = {str(i): _weighted_mean(hold_pairs[i]) for i in (1, 2, 3)}
    reliable = n >= MIN_RELIABLE_MATCHES and sum(1 for x in holds.values() if x is not None) == 3
    if reliable:
        ehs = 100.0 * (0.45 * holds["1"] + 0.33 * holds["2"] + 0.22 * holds["3"])
        ehs = round(ehs, 1)
    else:
        ehs = None

    quality = "N/D"
    if reliable:
        quality = "HIGH" if n >= 8 and surface_matches >= 4 else "MEDIUM"

    return {
        "player": player,
        "player_id": int(player_id),
        "matches": n,
        "surface_matches": surface_matches,
        "ready": bool(reliable),
        "quality": quality,
        "ehs": ehs,
        "hold1": round(100 * holds["1"], 1) if holds["1"] is not None else None,
        "hold2": round(100 * holds["2"], 1) if holds["2"] is not None else None,
        "hold3": round(100 * holds["3"], 1) if holds["3"] is not None else None,
        "after2_11": round(100 * (_weighted_mean(state_pairs["1:1"]) or 0), 1) if n else None,
        "after4_22": round(100 * (_weighted_mean(state_pairs["2:2"]) or 0), 1) if n else None,
        "after6_33": round(100 * (_weighted_mean(state_pairs["3:3"]) or 0), 1) if n else None,
        "sequence_11_22_33": round(100 * (_weighted_mean(state_pairs["sequence"]) or 0), 1) if n else None,
        "sample_ids": [s["id"] for s in eh_samples],
        "trend_matches": len(samples),
        "pbp_tendencies": _pbp_tendency_windows(samples, surface),
    }


def _blend_hold(base: float, observed_pct: float | None, profile: dict) -> float:
    if not profile.get("ready") or observed_pct is None:
        return _clamp(base, 0.35, 0.97)
    n = int(profile.get("matches") or 0)
    sm = int(profile.get("surface_matches") or 0)
    alpha = _clamp(0.30 + 0.04 * max(0, n - 5) + 0.03 * min(5, sm), 0.35, 0.62)
    return _clamp((1 - alpha) * base + alpha * (float(observed_pct) / 100.0), 0.35, 0.97)


def _early_sequences(base1: float, base2: float, p1: dict, p2: dict):
    s1 = [_blend_hold(base1, p1.get(f"hold{i}"), p1) for i in (1, 2, 3)]
    s2 = [_blend_hold(base2, p2.get(f"hold{i}"), p2) for i in (1, 2, 3)]
    return s1, s2


def _game_hold(seq: list[float], fallback: float, service_no: int) -> float:
    return seq[service_no - 1] if 1 <= service_no <= len(seq) else fallback


def _states_for_n(seq1, seq2, base1, base2, games: int, p1_first: bool):
    states = {(0, 0): 1.0}
    service_count = {1: 0, 2: 0}
    # Server order is deterministic, so service number is deterministic by game index.
    for g in range(games):
        p1_serves = p1_first if g % 2 == 0 else not p1_first
        server = 1 if p1_serves else 2
        service_count[server] += 1
        if server == 1:
            p1_game = _game_hold(seq1, base1, service_count[1])
        else:
            p1_game = 1.0 - _game_hold(seq2, base2, service_count[2])
        nxt = {}
        for (a, b), pr in states.items():
            nxt[(a + 1, b)] = nxt.get((a + 1, b), 0.0) + pr * p1_game
            nxt[(a, b + 1)] = nxt.get((a, b + 1), 0.0) + pr * (1 - p1_game)
        states = nxt
    return states


def _state_probs(seq1, seq2, base1, base2, games: int):
    a = _states_for_n(seq1, seq2, base1, base2, games, True)
    b = _states_for_n(seq1, seq2, base1, base2, games, False)
    keys = set(a) | set(b)
    return {
        f"{x}:{y}": round(50.0 * (a.get((x, y), 0.0) + b.get((x, y), 0.0)), 1)
        for x, y in sorted(keys, key=lambda z: (-z[0], z[1]))
    }


def _tb_p1(base1: float, base2: float) -> float:
    strength = (base1 + (1.0 - base2)) / 2.0
    return _clamp(1.0 / (1.0 + math.exp(-(strength - 0.5) * 8.0)), 0.20, 0.80)


def _set_sim_one(seq1, seq2, base1, base2, p1_first: bool):
    # state=(p1 games,p2 games,lead6 marker); marker: 1 p1 lead, -1 p2 lead, 0 tie, None before 6.
    live = {(0, 0, None): 1.0}
    terminal = {}
    while live:
        nxt = {}
        for (a, b, lead6), pr in live.items():
            if a == 6 and b == 6:
                tb = _tb_p1(base1, base2)
                terminal[(7, 6, lead6)] = terminal.get((7, 6, lead6), 0) + pr * tb
                terminal[(6, 7, lead6)] = terminal.get((6, 7, lead6), 0) + pr * (1 - tb)
                continue
            if (a >= 6 or b >= 6) and abs(a - b) >= 2:
                terminal[(a, b, lead6)] = terminal.get((a, b, lead6), 0) + pr
                continue

            g = a + b
            p1_serves = p1_first if g % 2 == 0 else not p1_first
            if p1_serves:
                service_no = (g // 2) + 1 if p1_first else ((g + 1) // 2)
                p1_game = _game_hold(seq1, base1, service_no)
            else:
                service_no = (g // 2) + 1 if not p1_first else ((g + 1) // 2)
                p1_game = 1.0 - _game_hold(seq2, base2, service_no)

            for da, p in ((1, p1_game), (0, 1 - p1_game)):
                na, nb = a + da, b + (1 - da)
                marker = lead6
                if na + nb == 6:
                    marker = 1 if na > nb else (-1 if nb > na else 0)
                key = (na, nb, marker)
                nxt[key] = nxt.get(key, 0.0) + pr * p
        live = nxt
    return terminal


def _set_sim(seq1, seq2, base1, base2):
    a = _set_sim_one(seq1, seq2, base1, base2, True)
    b = _set_sim_one(seq1, seq2, base1, base2, False)
    keys = set(a) | set(b)
    return {k: 0.5 * (a.get(k, 0.0) + b.get(k, 0.0)) for k in keys}


def _reweight_terminal(terminal: dict, target_p1: float):
    raw_win = sum(pr for (a, b, _), pr in terminal.items() if a > b)
    if not 0 < raw_win < 1:
        return terminal
    target = _clamp(target_p1, 0.04, 0.96)
    out = {}
    for k, pr in terminal.items():
        a, b, _ = k
        factor = target / raw_win if a > b else (1 - target) / (1 - raw_win)
        out[k] = pr * factor
    z = sum(out.values()) or 1.0
    return {k: v / z for k, v in out.items()}


def enrich_match(match: dict, p1: dict, p2: dict) -> dict:
    eh = {
        "version": "v7.1-pbp",
        "ready": bool(p1.get("ready") and p2.get("ready")),
        "p1": p1,
        "p2": p2,
        "source": "Live Tennis API BASIC point-by-point",
        "rule": "EHS only when >=5 reliable game-by-game matches per player",
    }
    match["early_hold_v7"] = eh
    if not eh["ready"]:
        return match

    service = match.get("service_model") or {}
    try:
        base1 = float(service.get("p1_hold")) / 100.0
        base2 = float(service.get("p2_hold")) / 100.0
    except Exception:
        return match

    seq1, seq2 = _early_sequences(base1, base2, p1, p2)
    blended1 = 0.45 * seq1[0] + 0.33 * seq1[1] + 0.22 * seq1[2]
    blended2 = 0.45 * seq2[0] + 0.33 * seq2[1] + 0.22 * seq2[2]

    state_probs = {str(n): _state_probs(seq1, seq2, blended1, blended2, n) for n in (1, 2, 4, 6)}
    terminal_raw = _set_sim(seq1, seq2, blended1, blended2)
    raw_p1 = sum(pr for (a, b, _), pr in terminal_raw.items() if a > b)

    old_first = match.get("first_set_win") or {}
    old_target = old_first.get(match.get("p1"))
    try:
        old_target = float(old_target) / 100.0
    except Exception:
        old_target = raw_p1
    # Keep ranking/form from Adaptive as a correction, but make point-by-point the dominant component.
    target_p1 = _clamp(0.80 * raw_p1 + 0.20 * old_target, 0.05, 0.95)
    terminal = _reweight_terminal(terminal_raw, target_p1)

    dist = {}
    for (a, b, _), pr in terminal.items():
        dist[(a, b)] = dist.get((a, b), 0.0) + pr

    p1win = sum(pr for (a, b), pr in dist.items() if a > b)
    over_under = {}
    for line in (8.5, 9.5, 10.5, 11.5, 12.5):
        ov = sum(pr for (a, b), pr in dist.items() if a + b > line)
        over_under[f"{line:.1f}"] = {"over": round(100 * ov, 1), "under": round(100 * (1 - ov), 1)}
    exact = {
        f"{a}:{b}": round(100 * pr, 1)
        for (a, b), pr in sorted(dist.items(), key=lambda kv: kv[1], reverse=True)
    }

    match["service_model_base"] = dict(service)
    match["service_model"] = {
        **service,
        "p1_hold": round(100 * blended1, 1),
        "p2_hold": round(100 * blended2, 1),
        "pbp_adjusted": True,
    }
    # The main "po gemach" market is now truly PBP-aware. Other full-match markets remain Adaptive v0.5.
    match["game_states"] = state_probs
    match["early_first_set_win"] = {
        match["p1"]: round(100 * p1win, 1),
        match["p2"]: round(100 * (1 - p1win), 1),
    }
    match["early_over_under"] = over_under
    match["early_exact_first_set"] = exact

    pick = max(match["early_first_set_win"], key=match["early_first_set_win"].get)
    pick_side = 1 if pick == match["p1"] else 2
    states6 = state_probs["6"]
    lead6 = 0.0
    for state, pct in states6.items():
        a, b = map(int, state.split(":"))
        if (pick_side == 1 and a > b) or (pick_side == 2 and b > a):
            lead6 += pct / 100.0

    wanted_marker = 1 if pick_side == 1 else -1
    joint = 0.0
    for (a, b, marker), pr in terminal.items():
        winner_ok = (pick_side == 1 and a > b) or (pick_side == 2 and b > a)
        over_ok = a + b > 8.5
        if marker == wanted_marker and winner_ok and over_ok:
            joint += pr

    match["pick_first_set_early"] = pick
    match["score_first_set_early"] = match["early_first_set_win"][pick]
    match["score_lead_after6"] = round(100 * lead6, 1)
    match["score_joint_builder"] = round(100 * joint, 1)
    eh.update(
        {
            "p1_service_holds": [round(100 * x, 1) for x in seq1],
            "p2_service_holds": [round(100 * x, 1) for x in seq2],
            "lead_pick": pick,
            "lead_after6": match["score_lead_after6"],
            "joint_builder": match["score_joint_builder"],
            "balanced_after6": state_probs["6"].get("3:3"),
        }
    )
    return match


def main() -> None:
    now = datetime.now(timezone.utc)
    key = os.getenv("LIVE_TENNIS_API_KEY", "").strip()
    rows = _read_json(RESULTS_PATH, [])
    meta = _read_json(META_PATH, {})
    if not isinstance(rows, list):
        rows = []
    if not isinstance(meta, dict):
        meta = {}

    if not key or not rows:
        meta.update(
            {
                "pbp_v7_mode": "skipped",
                "pbp_v7_reason": "missing_key_or_results",
                "pbp_v7_updated_at": now.isoformat(),
            }
        )
        _write_json(META_PATH, meta)
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return

    budget, usage = _usage_budget(key)
    api = API(key, budget)
    CACHE.mkdir(parents=True, exist_ok=True)
    index = _read_json(INDEX_PATH, {"players": {}})
    if not isinstance(index, dict):
        index = {"players": {}}
    index.setdefault("players", {})

    # Only enrich matches the base model already considers usable.
    targets = [m for m in rows if m.get("model_ready") and m.get("service_model")]
    targets.sort(key=lambda m: m.get("scheduled_time") or "")
    unique = []
    seen = set()
    for m in targets:
        for name in (m.get("p1"), m.get("p2")):
            k = _key(name)
            if name and k not in seen:
                seen.add(k)
                unique.append((name, str(m.get("surface") or "").lower(), m.get("scheduled_time")))

    counters = {
        "tape_downloads": 0,
        "tape_cache_hits": 0,
        "tape_errors": 0,
        "match_detail_calls": 0,
        "match_detail_errors": 0,
    }
    seed_ids = {}
    for k, entry in (index.get("players") or {}).items():
        try:
            if entry.get("player_id") is not None:
                seed_ids[k] = int(entry["player_id"])
        except (TypeError, ValueError):
            pass
    player_ids = resolve_current_player_ids(api, targets, counters, seed=seed_ids)
    profiles = {}
    for name, surface, scheduled in unique:
        if api.calls >= api.call_cap:
            break
        as_of = _parse_dt(scheduled) or now
        profiles[_key(name)] = build_profile(api, index, name, player_ids.get(_key(name)), surface, as_of, now, counters)

    ready_matches = 0
    for m in rows:
        if not m.get("model_ready") or not m.get("service_model"):
            continue
        p1 = profiles.get(_key(m.get("p1"))) or {
            "player": m.get("p1"), "matches": 0, "ready": False, "ehs": None, "quality": "N/D"
        }
        p2 = profiles.get(_key(m.get("p2"))) or {
            "player": m.get("p2"), "matches": 0, "ready": False, "ehs": None, "quality": "N/D"
        }
        enrich_match(m, p1, p2)
        if (m.get("early_hold_v7") or {}).get("ready"):
            ready_matches += 1

    _write_json(INDEX_PATH, index)
    _write_json(RESULTS_PATH, rows)

    usage_today = usage.get("today") or {}
    limits = usage.get("limits") or {}
    meta.update(
        {
            "pbp_v7_mode": "basic-point-by-point",
            "pbp_v7_updated_at": now.isoformat(),
            "pbp_v7_ready_matches": ready_matches,
            "pbp_v7_target_matches": len(targets),
            "pbp_v7_profiles": len(profiles),
            "pbp_v7_player_ids_resolved": len(player_ids),
            "pbp_v7_match_detail_calls": counters["match_detail_calls"],
            "pbp_v7_match_detail_errors": counters["match_detail_errors"],
            "pbp_v7_api_calls": api.calls + 1,  # + usage request
            "pbp_v7_tape_downloads": counters["tape_downloads"],
            "pbp_v7_tape_cache_hits": counters["tape_cache_hits"],
            "pbp_v7_tape_errors": counters["tape_errors"],
            "pbp_v7_daily_limit": limits.get("per_day"),
            "pbp_v7_calls_before_run": usage_today.get("calls"),
            "pbp_v7_note": "EHS only with >=5 reliable point-by-point matches; cache under data/cache/pbp_v7.",
        }
    )
    _write_json(META_PATH, meta)
    print(json.dumps({k: v for k, v in meta.items() if k.startswith("pbp_v7_")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
