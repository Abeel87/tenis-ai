from __future__ import annotations

"""Tenis AI v9.1 — Superbet market availability + model context.

Reads the real Superbet PL pre-match offer through OddsPapi but intentionally
throws prices away. PREPARE refreshes/caches the market catalogue and attaches
available markets/lines to results.json. FINALIZE evaluates those real lines
with Tenis AI's already-built model distributions.

The bookmaker feed is context, never a training target and never modifies the
core PROD/Adaptive/SHADOW prediction scores.
"""

import json
import math
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
RESULTS = OUT / "results.json"
META = OUT / "meta.json"
AVAILABILITY = OUT / "superbet_market_availability_v91.json"

VERSION = "v9.1"
BASE_URL = "https://api.oddspapi.io/v4"
BOOKMAKER = "superbet.pl"
SPORT_ID_TENNIS = 12
REFRESH_HOURS = 10
MARKET_META_TTL_DAYS = 7
MONTHLY_REQUEST_CAP = 150
FIXTURE_HORIZON_DAYS = 2
MAX_MATCH_TIME_DELTA_HOURS = 4

STRICT_ACTIONABLE_MARKETS = {
    "match_winner",
    "set1_winner",
    "set2_winner",
    "set3_winner",
    "match_total",
    "set1_total",
    "set2_total",
    "set3_total",
    "total_sets",
    "set1_exact_score",
    "exact_match_score",
    "game_state",
    "set1_tiebreak",
    "match_game_handicap",
    "set1_game_handicap",
    "set2_game_handicap",
    "player_total_games",
    "match_total_aces",
    "most_aces",
}


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _parse_dt(value):
    try:
        d = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _norm(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).casefold()
    return " ".join(text.split())


def _name_key(value) -> str:
    return " ".join(sorted(_norm(value).split()))


def _pair_key(p1, p2):
    return tuple(sorted((_name_key(p1), _name_key(p2))))


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _pct(value):
    x = _num(value)
    if x is None:
        return None
    if 0 <= x <= 1:
        x *= 100
    return max(0.0, min(100.0, x))


def _line(value):
    x = _num(value)
    return float(x) if x is not None else None


def _line_from_text(*values):
    text = " ".join(str(x or "") for x in values)
    nums = re.findall(r"(?<!\d)(-?\d+(?:\.\d+)?)(?!\d)", text)
    decimals = [float(x) for x in nums if "." in x]
    return decimals[0] if decimals else None


def _score_from_text(*values):
    text = " ".join(str(x or "") for x in values)
    m = re.search(r"(?<!\d)(\d+)\s*[:\-]\s*(\d+)(?!\d)", text)
    return f"{int(m.group(1))}:{int(m.group(2))}" if m else None


def _ou_side(*values):
    words = set(_norm(" ".join(str(x or "") for x in values)).split())
    if "over" in words or "powyzej" in words:
        return "over"
    if "under" in words or "ponizej" in words:
        return "under"
    return None


def _checkpoint_from_market(name: str):
    n = _norm(name)
    if "after two games" in n or "po dwoch gemach" in n:
        return 2
    if "after four games" in n or "po czterech gemach" in n:
        return 4
    if "after six games" in n or "po szesciu gemach" in n:
        return 6
    return None


def canonical_market(market_name: str):
    n = _norm(market_name)
    cp = _checkpoint_from_market(market_name)
    if "correct score first set after" in n and cp:
        return "game_state", cp, None
    mapping = {
        "winner": ("match_winner", None),
        "winner first set": ("set1_winner", None),
        "first set winner": ("set1_winner", None),
        "winner second set": ("set2_winner", None),
        "second set winner": ("set2_winner", None),
        "winner third set": ("set3_winner", None),
        "third set winner": ("set3_winner", None),
        "correct score": ("exact_match_score", None),
        "correct score first set": ("set1_exact_score", None),
        "total games over under": ("match_total", None),
        "total games first set": ("set1_total", None),
        "total games second set": ("set2_total", None),
        "total games third set": ("set3_total", None),
        "total sets over under": ("total_sets", None),
        "game handicap": ("match_game_handicap", None),
        "game handicap first set": ("set1_game_handicap", None),
        "game handicap second set": ("set2_game_handicap", None),
        "participant 1 total games": ("player_total_games", "p1"),
        "participant 2 total games": ("player_total_games", "p2"),
        "total aces": ("match_total_aces", None),
        "aces result": ("most_aces", None),
    }
    if n in mapping:
        market, player_side = mapping[n]
        return market, None, player_side
    if "tie break" in n and "first set" in n:
        return "set1_tiebreak", None, None
    return None, None, None


def _winner_pick(outcome_name, bookmaker_outcome_id, p1, p2):
    text = _norm(f"{outcome_name or ''} {bookmaker_outcome_id or ''}")
    if text in {"1", "p1", "participant 1", "player 1"} or "participant 1" in text:
        return p1
    if text in {"2", "p2", "participant 2", "player 2"} or "participant 2" in text:
        return p2
    if "draw" in text or "tie" in text:
        return "draw"
    n1, n2 = _norm(p1), _norm(p2)
    if n1 and n1 in text:
        return p1
    if n2 and n2 in text:
        return p2
    return str(outcome_name or bookmaker_outcome_id or "").strip() or None


def _selection_pick(market, outcome_name, bookmaker_outcome_id, p1, p2):
    if market in {
        "match_total", "set1_total", "set2_total", "set3_total",
        "total_sets", "player_total_games", "match_total_aces",
    }:
        return _ou_side(outcome_name, bookmaker_outcome_id)
    if market in {"set1_exact_score", "exact_match_score", "game_state"}:
        return _score_from_text(outcome_name, bookmaker_outcome_id)
    if market in {"match_winner", "set1_winner", "set2_winner", "set3_winner", "most_aces"}:
        return _winner_pick(outcome_name, bookmaker_outcome_id, p1, p2)
    if market == "set1_tiebreak":
        words = set(_norm(f"{outcome_name or ''} {bookmaker_outcome_id or ''}").split())
        if "yes" in words or "tak" in words:
            return "yes"
        if "no" in words or "nie" in words:
            return "no"
    if market in {"match_game_handicap", "set1_game_handicap", "set2_game_handicap"}:
        return _winner_pick(outcome_name, bookmaker_outcome_id, p1, p2)
    return None


def _request(path: str, api_key: str, quota: dict, **params):
    used = int(quota.get("requests_used_by_v91") or 0)
    cap = int(quota.get("monthly_cap") or MONTHLY_REQUEST_CAP)
    if used >= cap:
        raise RuntimeError("OddsPapi v9.1 monthly safety budget exhausted")
    quota["requests_used_by_v91"] = used + 1
    query = {"apiKey": api_key, **{k: v for k, v in params.items() if v is not None}}
    url = f"{BASE_URL}/{path}?{urlencode(query)}"
    req = Request(url, headers={"User-Agent": "tenis-ai-superbet-v91/1.0", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=35) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if path == "fixtures" and exc.code == 404:
            try:
                payload = json.loads(body)
            except (TypeError, ValueError):
                payload = None
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict) and error.get("code") == "FIXTURE_NOT_FOUND":
                return []
        raise RuntimeError(f"OddsPapi {path}: HTTP {exc.code}; {body[:300]}") from None
    except URLError as exc:
        raise RuntimeError(f"OddsPapi {path}: network error: {exc.reason}") from None


def _quota_state(previous: dict, now: datetime):
    month = now.strftime("%Y-%m")
    old = previous.get("quota_guard") if isinstance(previous, dict) else {}
    old = old if isinstance(old, dict) else {}
    used = int(old.get("requests_used_by_v91") or 0) if old.get("month") == month else 0
    return {
        "month": month,
        "monthly_cap": MONTHLY_REQUEST_CAP,
        "requests_used_by_v91": used,
        "note": "local safety cap; OddsPapi account can include other/manual requests",
    }


def _market_index(markets):
    out = {}
    rows = markets if isinstance(markets, list) else []
    for row in rows:
        if not isinstance(row, dict) or row.get("sportId") not in (None, SPORT_ID_TENNIS):
            continue
        market_id = row.get("marketId")
        if market_id is None:
            continue
        outcomes = {}
        for outcome in row.get("outcomes") or []:
            if isinstance(outcome, dict) and outcome.get("outcomeId") is not None:
                outcomes[str(outcome["outcomeId"])] = {
                    "outcomeName": outcome.get("outcomeName"),
                    "outcomeNameShort": outcome.get("outcomeNameShort"),
                }
        out[str(market_id)] = {
            "marketName": row.get("marketName") or row.get("marketNameShort"),
            "marketType": row.get("marketType"),
            "period": row.get("period"),
            "playerProp": row.get("playerProp"),
            "handicap": row.get("handicap"),
            "outcomes": outcomes,
        }
    return out


def _flatten_payload(payload):
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "fixtures", "events", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    if payload.get("fixtureId"):
        return [payload]
    return [x for x in payload.values() if isinstance(x, dict) and x.get("fixtureId")]


def _best_fixture_for_match(match: dict, fixtures: list[dict]):
    key = _pair_key(match.get("p1"), match.get("p2"))
    scheduled = _parse_dt(match.get("scheduled_time"))
    candidates = [f for f in fixtures if _pair_key(f.get("participant1Name"), f.get("participant2Name")) == key]
    if not candidates:
        return None
    if scheduled is None:
        return candidates[0]
    scored = []
    for row in candidates:
        start = _parse_dt(row.get("startTime"))
        delta = abs((start - scheduled).total_seconds()) / 3600 if start else 9999
        scored.append((delta, row))
    delta, best = min(scored, key=lambda x: x[0])
    return best if delta <= MAX_MATCH_TIME_DELTA_HOURS else None


def _identity_debug_snapshot(row: dict) -> dict:
    """Expose only non-odds identity metadata for diagnosing provider response shape."""
    if not isinstance(row, dict):
        return {}

    sensitive_tokens = ("odds", "price", "market", "outcome")
    identity_tokens = (
        "fixture", "participant", "player", "competitor", "home", "away",
        "start", "time", "tournament", "event", "match",
    )

    def keep_scalar(key: str, value):
        name = str(key).casefold()
        if any(token in name for token in sensitive_tokens):
            return False
        return any(token in name for token in identity_tokens) and isinstance(value, (str, int, float, bool))

    out = {"top_level_keys": sorted(str(k) for k in row.keys())}
    for key, value in row.items():
        if keep_scalar(key, value):
            out[str(key)] = value
        elif isinstance(value, dict) and not any(token in str(key).casefold() for token in sensitive_tokens):
            nested = {}
            for child_key, child_value in value.items():
                if keep_scalar(child_key, child_value):
                    nested[str(child_key)] = child_value
            if nested:
                out[str(key)] = nested
        elif isinstance(value, list) and len(value) <= 4 and not any(token in str(key).casefold() for token in sensitive_tokens):
            nested_rows = []
            for child in value:
                if not isinstance(child, dict):
                    continue
                slim = {str(k): v for k, v in child.items() if keep_scalar(k, v)}
                if slim:
                    nested_rows.append(slim)
            if nested_rows:
                out[str(key)] = nested_rows
    return out


def _same_discovered_fixture(discovered: dict, operator_row: dict) -> tuple[bool, str | None]:
    """Join neutral discovery to the operator response without assuming shared IDs."""
    discovered_id = str(discovered.get("fixtureId") or "")
    operator_id = str(operator_row.get("fixtureId") or "")
    if discovered_id and operator_id and discovered_id == operator_id:
        return True, "fixture_id"

    discovered_pair = _pair_key(discovered.get("participant1Name"), discovered.get("participant2Name"))
    operator_pair = _pair_key(operator_row.get("participant1Name"), operator_row.get("participant2Name"))
    if not all(discovered_pair) or discovered_pair != operator_pair:
        return False, None

    discovered_start = _parse_dt(discovered.get("startTime"))
    operator_start = _parse_dt(operator_row.get("startTime"))
    if discovered_start is None or operator_start is None:
        return False, None
    delta = abs((operator_start - discovered_start).total_seconds()) / 3600.0
    if delta > MAX_MATCH_TIME_DELTA_HOURS:
        return False, None
    return True, "pair_time"


def _sanitize_fixture(row: dict, meta: dict):
    bookmaker_odds = row.get("bookmakerOdds") or {}
    book = bookmaker_odds.get(BOOKMAKER)
    if not isinstance(book, dict):
        book = next((v for k, v in bookmaker_odds.items() if "superbet" in str(k).casefold() and isinstance(v, dict)), None)
    if not isinstance(book, dict):
        return None
    raw_markets = book.get("markets") or {}
    if not isinstance(raw_markets, dict):
        return None

    p1 = str(row.get("participant1Name") or "")
    p2 = str(row.get("participant2Name") or "")
    selections = []
    recognized_markets = set()
    for market_id, market_data in raw_markets.items():
        if not isinstance(market_data, dict) or market_data.get("marketActive") is False:
            continue
        market_meta = meta.get(str(market_id), {})
        market_name = str(market_meta.get("marketName") or f"market {market_id}")
        canonical, checkpoint, player_side = canonical_market(market_name)
        if not canonical:
            continue
        recognized_markets.add(canonical)
        for outcome_id, outcome_data in (market_data.get("outcomes") or {}).items():
            if not isinstance(outcome_data, dict):
                continue
            outcome_meta = (market_meta.get("outcomes") or {}).get(str(outcome_id), {})
            outcome_name = outcome_meta.get("outcomeName") or outcome_meta.get("outcomeNameShort")
            for player_data in (outcome_data.get("players") or {}).values():
                if not isinstance(player_data, dict) or player_data.get("active") is False:
                    continue
                boid = player_data.get("bookmakerOutcomeId")
                pick = _selection_pick(canonical, outcome_name, boid, p1, p2)
                line = _line_from_text(boid, outcome_name)
                if canonical in {
                    "match_total", "set1_total", "set2_total", "set3_total", "total_sets",
                    "player_total_games", "match_total_aces", "match_game_handicap",
                    "set1_game_handicap", "set2_game_handicap",
                } and line is None:
                    continue
                if canonical in {
                    "match_total", "set1_total", "set2_total", "set3_total",
                    "total_sets", "player_total_games", "match_total_aces",
                } and pick not in {"over", "under"}:
                    continue
                if canonical in {"set1_exact_score", "exact_match_score", "game_state"} and not pick:
                    continue
                player = p1 if player_side == "p1" else p2 if player_side == "p2" else player_data.get("playerName")
                selections.append({
                    "market": canonical,
                    "pick": pick,
                    "line": line,
                    "checkpoint": checkpoint,
                    "player": player,
                    "market_name": market_name,
                    "market_id": str(market_id),
                    "outcome_id": str(outcome_id),
                    "main_line": bool(player_data.get("mainLine", False)),
                    "operator_available": True,
                    "operator_line_verified": True,
                })

    dedup = {}
    for s in selections:
        sig = (s.get("market"), _norm(s.get("pick")), _line(s.get("line")), int(s.get("checkpoint") or 0), _name_key(s.get("player")))
        if sig not in dedup or s.get("main_line"):
            dedup[sig] = s
    selections = sorted(dedup.values(), key=lambda s: (str(s.get("market")), float(s.get("line") or -999), str(s.get("pick"))))
    return {
        "fixture_id": row.get("fixtureId"),
        "p1": p1,
        "p2": p2,
        "start_time": row.get("startTime"),
        "tournament": row.get("tournamentName"),
        "tournament_id": row.get("tournamentId"),
        "bookmaker": BOOKMAKER,
        "bookmaker_active": bool(book.get("bookmakerIsActive", True)),
        "suspended": bool(book.get("suspended", False)),
        "raw_markets": len(raw_markets),
        "recognized_markets": sorted(recognized_markets),
        "canonical_selections": selections,
    }


def _availability_due(previous: dict, now: datetime):
    generated = _parse_dt(previous.get("generated_at") if isinstance(previous, dict) else None)
    return generated is None or now - generated >= timedelta(hours=REFRESH_HOURS)


def _meta_due(previous: dict, now: datetime):
    stamp = _parse_dt(previous.get("market_meta_generated_at") if isinstance(previous, dict) else None)
    cache = previous.get("market_meta_cache") if isinstance(previous, dict) else None
    return not isinstance(cache, dict) or not cache or stamp is None or now - stamp >= timedelta(days=MARKET_META_TTL_DAYS)


def refresh_availability(results: list[dict], now=None):
    now = now or datetime.now(timezone.utc)
    previous = _read(AVAILABILITY, {})
    quota = _quota_state(previous, now)
    if not _availability_due(previous, now):
        previous = dict(previous)
        previous["refresh_status"] = "CACHE_FRESH"
        previous["quota_guard"] = quota
        return previous

    api_key = os.getenv("ODDSPAPI_API_KEY", "").strip()
    if not api_key:
        if isinstance(previous, dict) and previous.get("fixtures"):
            previous = dict(previous)
            previous["refresh_status"] = "CACHE_NO_KEY"
            previous["quota_guard"] = quota
            return previous
        return {"version": VERSION, "generated_at": None, "refresh_status": "NO_KEY_NO_CACHE", "bookmaker": BOOKMAKER, "contains_prices": False, "fixtures": [], "quota_guard": quota}

    cap = int(quota["monthly_cap"])
    if int(quota["requests_used_by_v91"]) + 2 > cap:
        previous = dict(previous) if isinstance(previous, dict) else {}
        previous.update({"version": VERSION, "refresh_status": "MONTHLY_SAFETY_CAP", "bookmaker": BOOKMAKER, "contains_prices": False, "quota_guard": quota})
        return previous

    market_meta = previous.get("market_meta_cache") if isinstance(previous, dict) else {}
    market_meta = market_meta if isinstance(market_meta, dict) else {}
    market_meta_generated_at = previous.get("market_meta_generated_at") if isinstance(previous, dict) else None
    try:
        date_from = now.date().isoformat()
        date_to = (now + timedelta(days=FIXTURE_HORIZON_DAYS)).date().isoformat()
        # Fixture discovery is bookmaker-neutral. The Superbet filter belongs only
        # to the later operator-offer query, after app matches are matched to fixtures.
        fixture_rows = _request(
            "fixtures",
            api_key,
            quota,
            sportId=SPORT_ID_TENNIS,
            **{"from": date_from, "to": date_to},
            statusId=0,
            language="en",
        )
        fixture_rows = fixture_rows if isinstance(fixture_rows, list) else _flatten_payload(fixture_rows)
        wanted_fixture_ids = set()
        discovered_matches = []
        tournament_ids = set()
        for match in results:
            if not isinstance(match, dict):
                continue
            fixture = _best_fixture_for_match(match, fixture_rows)
            if not fixture:
                continue
            discovered_matches.append(fixture)
            if fixture.get("fixtureId"):
                wanted_fixture_ids.add(str(fixture["fixtureId"]))
            if fixture.get("tournamentId") is not None:
                tournament_ids.add(str(fixture["tournamentId"]))

        if not tournament_ids:
            report = {
                "version": VERSION, "generated_at": now.isoformat(), "refresh_status": "OK_NO_MATCHED_FIXTURES",
                "bookmaker": BOOKMAKER, "contains_prices": False, "prices_used": False,
                "fixtures_seen": len(fixture_rows), "app_matches": len(results), "fixtures": [],
                "market_meta_generated_at": market_meta_generated_at, "market_meta_cache": market_meta, "quota_guard": quota,
            }
            _write(AVAILABILITY, report)
            return report

        if _meta_due(previous, now) and int(quota["requests_used_by_v91"]) < cap:
            time.sleep(1.05)
            market_meta = _market_index(_request("markets", api_key, quota, language="en"))
            market_meta_generated_at = now.isoformat()
        if not market_meta:
            raise RuntimeError("OddsPapi market metadata unavailable")
        if int(quota["requests_used_by_v91"]) >= cap:
            raise RuntimeError("OddsPapi v9.1 monthly safety budget exhausted before odds-by-tournaments")

        time.sleep(1.05)
        odds_rows = _flatten_payload(_request(
            "odds-by-tournaments", api_key, quota,
            tournamentIds=",".join(sorted(tournament_ids)), bookmakers=BOOKMAKER,
            language="en", verbosity=3, oddsFormat="decimal",
        ))
        sanitized = []
        operator_fixture_candidates = 0
        fixture_id_matches = 0
        pair_time_matches = 0
        neutral_fixture_ids = {
            str(row.get("fixtureId")) for row in fixture_rows
            if isinstance(row, dict) and row.get("fixtureId")
        }
        operator_fixture_ids_in_neutral_catalogue = 0
        operator_rows_in_horizon = 0
        operator_rows_in_horizon_with_requested_bookmaker = 0
        operator_rows_with_requested_bookmaker = 0
        operator_bookmakers_seen = set()
        operator_start_times = []
        for row in odds_rows:
            if not isinstance(row, dict):
                continue
            operator_id = str(row.get("fixtureId") or "")
            if operator_id and operator_id in neutral_fixture_ids:
                operator_fixture_ids_in_neutral_catalogue += 1

            bookmaker_odds = row.get("bookmakerOdds")
            bookmaker_keys = set(bookmaker_odds.keys()) if isinstance(bookmaker_odds, dict) else set()
            operator_bookmakers_seen.update(str(key) for key in bookmaker_keys)
            has_requested_bookmaker = (
                BOOKMAKER in bookmaker_keys
                or any("superbet" in str(key).casefold() for key in bookmaker_keys)
            )
            if has_requested_bookmaker:
                operator_rows_with_requested_bookmaker += 1

            operator_start = _parse_dt(row.get("startTime"))
            in_current_horizon = False
            if operator_start is not None:
                operator_start_times.append(operator_start)
                in_current_horizon = date_from <= operator_start.date().isoformat() <= date_to
                if in_current_horizon:
                    operator_rows_in_horizon += 1
                    if has_requested_bookmaker:
                        operator_rows_in_horizon_with_requested_bookmaker += 1

            # odds-by-tournaments can return historical fixtures from the same
            # tournament. They are not current operator offer and must never
            # reach identity matching, even if an ID/name happens to collide.
            if not in_current_horizon or not has_requested_bookmaker:
                continue

            match_kind = None
            for discovered in discovered_matches:
                same, kind = _same_discovered_fixture(discovered, row)
                if same:
                    match_kind = kind
                    break
            if match_kind is None:
                continue
            operator_fixture_candidates += 1
            if match_kind == "fixture_id":
                fixture_id_matches += 1
            elif match_kind == "pair_time":
                pair_time_matches += 1
            item = _sanitize_fixture(row, market_meta)
            if item:
                sanitized.append(item)
        report = {
            "version": VERSION, "generated_at": now.isoformat(), "refresh_status": "OK", "bookmaker": BOOKMAKER,
            "sport_id": SPORT_ID_TENNIS, "contains_prices": False, "prices_used": False, "refresh_hours": REFRESH_HOURS,
            "fixtures_seen": len(fixture_rows), "app_matches": len(results), "matched_fixture_candidates": len(wanted_fixture_ids),
            "tournaments_queried": len(tournament_ids), "operator_odds_rows_seen": len(odds_rows),
            "operator_fixture_candidates": operator_fixture_candidates,
            "operator_fixture_id_matches": fixture_id_matches,
            "operator_pair_time_matches": pair_time_matches,
            "operator_fixture_ids_in_neutral_catalogue": operator_fixture_ids_in_neutral_catalogue,
            "operator_rows_with_requested_bookmaker": operator_rows_with_requested_bookmaker,
            "operator_rows_in_horizon": operator_rows_in_horizon,
            "operator_rows_in_horizon_with_requested_bookmaker": operator_rows_in_horizon_with_requested_bookmaker,
            "operator_bookmakers_seen": sorted(operator_bookmakers_seen),
            "operator_start_min": min(operator_start_times).isoformat() if operator_start_times else None,
            "operator_start_max": max(operator_start_times).isoformat() if operator_start_times else None,
            "fixtures": sanitized,
            "market_meta_generated_at": market_meta_generated_at, "market_meta_cache": market_meta, "quota_guard": quota,
            "contract": {
                "bookmaker_prices_discarded": True,
                "market_availability_only": True,
                "bookmaker_data_never_trains_prod_models": True,
                "monthly_request_safety_cap": MONTHLY_REQUEST_CAP,
                "current_operator_horizon_required": True,
                "requested_bookmaker_required_before_join": True,
            },
        }
        _write(AVAILABILITY, report)
        return report
    except Exception as exc:
        fallback = dict(previous) if isinstance(previous, dict) else {}
        fallback.update({
            "version": VERSION,
            "refresh_status": "ERROR_CACHE_FALLBACK" if fallback.get("fixtures") else "ERROR_NO_CACHE",
            "last_error": f"{type(exc).__name__}: {exc}",
            "bookmaker": BOOKMAKER,
            "contains_prices": False,
            "prices_used": False,
            "quota_guard": quota,
        })
        _write(AVAILABILITY, fallback)
        return fallback


def _fixture_index(availability: dict):
    rows = availability.get("fixtures") if isinstance(availability, dict) else []
    out = {}
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict):
            out.setdefault(_pair_key(row.get("p1"), row.get("p2")), []).append(row)
    return out


def _best_cached_fixture(match: dict, index: dict):
    candidates = index.get(_pair_key(match.get("p1"), match.get("p2"))) or []
    if not candidates:
        return None
    scheduled = _parse_dt(match.get("scheduled_time"))
    if scheduled is None:
        return candidates[0]
    scored = []
    for row in candidates:
        start = _parse_dt(row.get("start_time"))
        delta = abs((start - scheduled).total_seconds()) / 3600 if start else 9999
        scored.append((delta, row))
    delta, best = min(scored, key=lambda x: x[0])
    return best if delta <= MAX_MATCH_TIME_DELTA_HOURS else None


def _compact_market_summary(selections):
    summary = {}
    for s in selections or []:
        if not isinstance(s, dict):
            continue
        market = str(s.get("market") or "")
        if not market:
            continue
        row = summary.setdefault(market, {"lines": set(), "picks": set(), "players": set(), "count": 0})
        row["count"] += 1
        if s.get("line") is not None:
            row["lines"].add(float(s["line"]))
        if s.get("pick"):
            row["picks"].add(str(s["pick"]))
        if s.get("player"):
            row["players"].add(str(s["player"]))
    return {market: {"lines": sorted(row["lines"]), "picks": sorted(row["picks"]), "players": sorted(row["players"]), "count": row["count"]} for market, row in sorted(summary.items())}


def prepare_results(results: list[dict], availability: dict, now=None):
    now = now or datetime.now(timezone.utc)
    idx = _fixture_index(availability)
    generated = _parse_dt(availability.get("generated_at") if isinstance(availability, dict) else None)
    age_hours = (now - generated).total_seconds() / 3600 if generated else None
    fresh = age_hours is not None and 0 <= age_hours <= REFRESH_HOURS * 1.8
    out, matched = [], 0
    for raw in results:
        if not isinstance(raw, dict):
            continue
        m = dict(raw)
        fixture = _best_cached_fixture(m, idx)
        if fixture:
            matched += 1
            selections = [dict(x) for x in (fixture.get("canonical_selections") or []) if isinstance(x, dict)]
            m["superbet_market_v91"] = {
                "version": VERSION,
                "status": "VERIFIED" if fresh else "CACHE_STALE",
                "operator": BOOKMAKER,
                "fixture_id": fixture.get("fixture_id"),
                "operator_start_time": fixture.get("start_time"),
                "source_generated_at": availability.get("generated_at"),
                "source_max_age_hours": REFRESH_HOURS * 1.8,
                "source_age_hours": round(float(age_hours or 0.0), 2) if age_hours is not None else None,
                "operator_verified": bool(fresh and not fixture.get("suspended")),
                "suspended": bool(fixture.get("suspended")),
                "operator_offer_source": fixture.get("operator_offer_source") or "oddspapi_superbet_pl",
                "prices_used": False,
                "canonical_markets": _compact_market_summary(selections),
                "canonical_selections": selections,
                "strict_actionable_markets": sorted(STRICT_ACTIONABLE_MARKETS),
                "contract": {
                    "market_lines_are_operator_context": True,
                    "market_lines_do_not_modify_core_model_score": True,
                    "prices_are_not_used": True,
                },
            }
        else:
            m["superbet_market_v91"] = {
                "version": VERSION, "status": "NOT_FOUND", "operator": BOOKMAKER,
                "source_generated_at": availability.get("generated_at") if isinstance(availability, dict) else None,
                "operator_verified": False, "prices_used": False, "canonical_markets": {}, "canonical_selections": [],
            }
        out.append(m)
    return out, matched


def _lookup_ou(block, line, pick):
    if not isinstance(block, dict) or line is None or pick not in {"over", "under"}:
        return None
    for key in (f"{float(line):.1f}", f"{float(line):g}", str(line)):
        row = block.get(key)
        if isinstance(row, dict):
            value = _pct(row.get(pick))
            if value is not None:
                return value
    return None


def _lookup_player_map(block, player):
    if not isinstance(block, dict):
        return None
    target = _name_key(player)
    for name, value in block.items():
        if _name_key(name) == target:
            return _pct(value)
    return None


def _lookup_score_map(block, score):
    if not isinstance(block, dict) or not score:
        return None
    target = str(score).replace("-", ":")
    for key, value in block.items():
        if str(key).replace("-", ":") == target:
            # Core exact-score and game-state maps are already expressed in
            # percentage points (e.g. 0.7 means 0.7%, not probability 0.7).
            # Do not pass them through _pct(), whose fraction-friendly contract
            # would incorrectly inflate every value <= 1.0 by 100x.
            x = _num(value)
            return max(0.0, min(100.0, x)) if x is not None else None
    return None


def _total_sets_probability(block, line, pick):
    if not isinstance(block, dict) or line is None or pick not in {"over", "under"}:
        return None
    counts = {}
    for key, value in block.items():
        m = re.search(r"(\d+)", str(key))
        p = _pct(value)
        if m and p is not None:
            counts[int(m.group(1))] = p
    total = sum(counts.values())
    if total <= 0:
        return None
    selected = sum(p for count, p in counts.items() if (count > line if pick == "over" else count < line))
    return max(0.0, min(100.0, 100.0 * selected / total))


def _poisson_over_under(mean, line, pick):
    mean = _num(mean)
    if mean is None or mean < 0 or line is None or pick not in {"over", "under"}:
        return None
    threshold = math.floor(float(line))
    pmf = math.exp(-mean)
    cdf = pmf
    for k in range(1, threshold + 1):
        pmf *= mean / k
        cdf += pmf
    under = max(0.0, min(1.0, cdf))
    return 100.0 * ((1.0 - under) if pick == "over" else under)


def _match_total_aces_probability(match, line, pick):
    props = match.get("serve_props_v72") or {}
    if not isinstance(props, dict) or not props.get("ready"):
        return None
    means = []
    for side in ("p1", "p2"):
        mean = _num((((props.get(side) or {}).get("aces") or {}).get("mean")))
        if mean is None:
            return None
        means.append(mean)
    return _poisson_over_under(sum(means), line, pick)


def _model_probability(match: dict, selection: dict):
    market = str(selection.get("market") or "")
    pick = selection.get("pick")
    line = _line(selection.get("line"))
    player = selection.get("player")
    lab = match.get("market_lab_v741") or {}
    if market == "match_winner":
        return _lookup_player_map(match.get("match_win"), pick), "match_win"
    if market == "set1_winner":
        return _lookup_player_map(match.get("first_set_win"), pick), "first_set_win"
    if market == "set2_winner":
        return _lookup_player_map(match.get("second_set_win"), pick), "second_set_win"
    if market == "set3_winner":
        return _lookup_player_map(match.get("third_set_win"), pick), "third_set_win"
    if market == "match_total":
        p = _lookup_ou(lab.get("match_total"), line, pick)
        return (p, "market_lab_v741") if p is not None else (_lookup_ou(match.get("match_over_under"), line, pick), "match_over_under")
    if market == "set1_total":
        p = _lookup_ou(lab.get("set1_total"), line, pick)
        return (p, "market_lab_v741") if p is not None else (_lookup_ou(match.get("over_under"), line, pick), "over_under")
    if market == "set2_total":
        return _lookup_ou(lab.get("set2_total"), line, pick), "market_lab_v741"
    if market == "set3_total":
        return _lookup_ou(lab.get("set3_total"), line, pick), "market_lab_v741"
    if market == "player_total_games":
        block = lab.get("player_total_games") or {}
        player_block = next((v for name, v in block.items() if _name_key(name) == _name_key(player)), None) if isinstance(block, dict) else None
        return _lookup_ou(player_block, line, pick), "market_lab_v741"
    if market == "total_sets":
        return _total_sets_probability(match.get("total_sets"), line, pick), "total_sets"
    if market == "set1_exact_score":
        return _lookup_score_map(match.get("exact_first_set"), pick), "exact_first_set"
    if market == "exact_match_score":
        return _lookup_score_map(match.get("exact_match_score"), pick), "exact_match_score"
    if market == "game_state":
        states = match.get("game_states") or {}
        cp = str(int(selection.get("checkpoint") or 0))
        state_block = (states.get(cp) or states.get(int(cp))) if cp.isdigit() else None
        return _lookup_score_map(state_block, pick), "game_states"
    if market == "set1_tiebreak":
        row = lab.get("set1_tiebreak") or {}
        return (_pct(row.get(pick)) if isinstance(row, dict) else None), "market_lab_v741"
    if market == "match_total_aces":
        return _match_total_aces_probability(match, line, pick), "serve_props_v72_sum_poisson"
    return None, None


def _signal_label(selection):
    market, pick, line, player = str(selection.get("market") or ""), str(selection.get("pick") or ""), selection.get("line"), selection.get("player")
    titles = {
        "match_winner": "Wygra mecz", "set1_winner": "Wygra 1. set", "set2_winner": "Wygra 2. set", "set3_winner": "Wygra 3. set",
        "match_total": "Mecz · gemy", "set1_total": "1. set · gemy", "set2_total": "2. set · gemy", "set3_total": "3. set · gemy",
        "player_total_games": f"Gemy zawodnika · {player or ''}".strip(), "total_sets": "Liczba setów",
        "set1_exact_score": "Dokładny wynik 1. seta", "exact_match_score": "Dokładny wynik meczu",
        "game_state": f"Po {selection.get('checkpoint')} gemach", "set1_tiebreak": "Tie-break w 1. secie",
        "match_total_aces": "Asy w meczu", "most_aces": "Najwięcej asów",
    }
    title = titles.get(market, market)
    if line is not None and pick in {"over", "under"}:
        return f"{title} · {'O' if pick == 'over' else 'U'}{float(line):g}"
    return f"{title} · {pick}".strip(" ·")


def finalize_results(results: list[dict]):
    out, ready, signals_total = [], 0, 0
    for raw in results:
        if not isinstance(raw, dict):
            continue
        m = dict(raw)
        ctx = dict(m.get("superbet_market_v91") or {})
        selections = [x for x in (ctx.get("canonical_selections") or []) if isinstance(x, dict)]
        signals = []
        for selection in selections:
            probability, source = _model_probability(m, selection)
            if probability is None:
                continue
            row = dict(selection)
            row.update({
                "key": f"superbet|{selection.get('market')}|{selection.get('checkpoint') or ''}|{selection.get('player') or ''}|{selection.get('line') if selection.get('line') is not None else ''}|{selection.get('pick') or ''}",
                "label": _signal_label(selection), "score": round(float(probability), 3),
                "symphony_raw_probability": round(float(probability), 4), "symphony_market_adapter": VERSION,
                "symphony_source": f"superbet_market_v91+{source}", "symphony_actionable": True,
                "operator": BOOKMAKER, "operator_available": True, "operator_line_verified": True,
                "operator_line_source": selection.get("operator_line_source") or ctx.get("operator_offer_source") or "oddspapi_superbet_pl",
                "operator_offer_source": selection.get("operator_offer_source") or ctx.get("operator_offer_source") or "oddspapi_superbet_pl",
                "exact_path_supported": selection.get("market") in {
                    "match_winner", "set1_winner", "set2_winner", "set3_winner", "match_total", "set1_total",
                    "total_sets", "set1_exact_score", "exact_match_score", "game_state",
                },
            })
            signals.append(row)
        ctx["model_signals"] = signals
        ctx["model_signals_count"] = len(signals)
        ctx["available_selections_count"] = len(selections)
        ctx["model_coverage"] = round(len(signals) / len(selections), 4) if selections else 0.0
        ctx["finalized"] = True
        ctx["prices_used"] = False
        m["superbet_market_v91"] = ctx
        if ctx.get("operator_verified"):
            ready += 1
        signals_total += len(signals)
        out.append(m)
    return out, ready, signals_total


def _update_meta(mode: str, availability: dict, matched=0, ready=0, signals=0):
    meta = _read(META, {})
    if not isinstance(meta, dict):
        meta = {}
    meta["superbet_market_v91"] = {
        "version": VERSION, "mode": mode, "bookmaker": BOOKMAKER,
        "source_generated_at": availability.get("generated_at") if isinstance(availability, dict) else None,
        "refresh_status": availability.get("refresh_status") if isinstance(availability, dict) else None,
        "matched_matches": matched, "verified_matches": ready, "model_signals": signals,
        "prices_used": False, "monthly_request_safety_cap": MONTHLY_REQUEST_CAP,
    }
    _write(META, meta)


def prepare():
    rows = _read(RESULTS, [])
    rows = rows if isinstance(rows, list) else []
    availability = refresh_availability(rows)
    prepared, matched = prepare_results(rows, availability)
    _write(RESULTS, prepared)
    _update_meta("prepare", availability, matched=matched)
    return {
        "status": "OK", "version": VERSION, "mode": "prepare", "refresh_status": availability.get("refresh_status"),
        "matched_matches": matched, "fixtures": len(availability.get("fixtures") or []), "prices_used": False,
        "quota_guard": availability.get("quota_guard"),
    }


def finalize():
    rows = _read(RESULTS, [])
    rows = rows if isinstance(rows, list) else []
    availability = _read(AVAILABILITY, {})
    finalized, ready, signals = finalize_results(rows)
    _write(RESULTS, finalized)
    matched = sum(1 for m in finalized if (m.get("superbet_market_v91") or {}).get("status") in {"VERIFIED", "CACHE_STALE"})
    _update_meta("finalize", availability, matched=matched, ready=ready, signals=signals)
    return {"status": "OK", "version": VERSION, "mode": "finalize", "verified_matches": ready, "model_signals": signals, "prices_used": False}


def main():
    mode = str(sys.argv[1] if len(sys.argv) > 1 else "prepare").strip().casefold()
    if mode == "prepare":
        result = prepare()
    elif mode == "finalize":
        result = finalize()
    else:
        raise SystemExit("usage: superbet_market_context_v91.py [prepare|finalize]")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()