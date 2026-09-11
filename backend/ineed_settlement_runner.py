from __future__ import annotations

"""Direct result fallback for iNeed$ SHADOW settlement.

The normal iNeed$ runner can settle from the canonical history archive. This
small companion closes the timing/coverage gap for open iNeed$ bets by checking
the already-configured Live Tennis API by the bet's canonical match_id.
It never changes model, Symphony, PLAYABLE, training or real-betting logic.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from urllib.request import Request, urlopen

try:
    from .ineed_money import build_settlements
except ImportError:
    from ineed_money import build_settlements

BASE_URL = "https://api.livetennisapi.com/api/public/v1"
OPEN = {"PENDING", "SHADOW_PLACED"}
MAX_RESULT_CHECKS = 12


def post(url: str, token: str, body: dict) -> dict:
    req = Request(
        url,
        data=json.dumps(body).encode(),
        headers={"authorization": f"Bearer {token}", "content-type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode())


def _obj(payload):
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def _score_sets(match: dict) -> list[list[int]]:
    score = match.get("score") or {}
    games = score.get("games") or []
    try:
        p1 = list(games[0] or [])
        p2 = list(games[1] or [])
    except Exception:
        return []
    out: list[list[int]] = []
    for index in range(min(len(p1), len(p2))):
        try:
            a, b = int(p1[index]), int(p2[index])
        except (TypeError, ValueError):
            continue
        if a == 0 and b == 0 and index == min(len(p1), len(p2)) - 1:
            continue
        out.append([a, b])
    return out


def _set_complete(a: int, b: int) -> bool:
    hi, lo = max(a, b), min(a, b)
    return (hi >= 6 and hi - lo >= 2) or (hi == 7 and lo == 6)


def _winner_index(match: dict) -> int | None:
    winner = match.get("winner")
    try:
        winner = int(winner) if winner is not None else None
    except (TypeError, ValueError):
        return None
    return winner if winner in (1, 2) else None


def _name_key(value) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def final_from_match(match: dict, bet: dict) -> dict | None:
    """Convert Live Tennis API match data to the canonical settlement final."""
    snap = bet.get("placement_snapshot") or {}
    p1, p2 = snap.get("p1"), snap.get("p2")
    if not p1 or not p2:
        return None

    status = str(match.get("event_status") or "").strip()
    low = status.casefold()
    if low in {"postponed", "interrupted", "suspended"}:
        return None

    sets = _score_sets(match)
    winner_idx = _winner_index(match)
    actual_winner = p1 if winner_idx == 1 else p2 if winner_idx == 2 else None

    if low in {"cancelled", "canceled", "walk over", "walkover", "abandoned"}:
        return {
            "status": "void",
            "winner": actual_winner,
            "score_text": status or "Cancelled",
            "reason": status or "cancelled/walkover",
            "p1": p1,
            "p2": p2,
        }

    if low in {"retired", "retirement", "defaulted", "default"}:
        score = " · ".join(f"{a}:{b}" for a, b in sets)
        return {
            "status": "retired",
            "winner": actual_winner,
            "score_text": f"{score} · {status}".strip(" ·"),
            "reason": status or "Retired",
            "sets": sets,
            "completed_sets": [_set_complete(a, b) for a, b in sets],
            "first_set_score": f"{sets[0][0]}:{sets[0][1]}" if sets else None,
            "p1": p1,
            "p2": p2,
        }

    if winner_idx not in (1, 2) or not sets:
        return None
    set_wins_p1 = sum(1 for a, b in sets if a > b)
    set_wins_p2 = sum(1 for a, b in sets if b > a)
    if set_wins_p1 == set_wins_p2:
        return None
    score_winner = p1 if set_wins_p1 > set_wins_p2 else p2
    if _name_key(actual_winner) != _name_key(score_winner):
        return None

    return {
        "status": "completed",
        "winner": actual_winner,
        "score_text": " ".join(f"{a}-{b}" for a, b in sets),
        "sets": sets,
        "completed_sets": [_set_complete(a, b) for a, b in sets],
        "match_score": f"{set_wins_p1}:{set_wins_p2}",
        "number_of_sets": len(sets),
        "total_games": sum(a + b for a, b in sets),
        "first_set_score": f"{sets[0][0]}:{sets[0][1]}",
        "p1": p1,
        "p2": p2,
    }


def fetch_match(match_id: str, api_key: str) -> dict:
    req = Request(
        f"{BASE_URL}/matches/{match_id}",
        headers={"Authorization": f"Bearer {api_key}", "User-Agent": "TenisAI-iNeed-settlement/1.0"},
    )
    with urlopen(req, timeout=25) as response:
        return _obj(json.loads(response.read().decode()))


def live_final_rows(open_bets: list[dict], api_key: str) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    checked = ready = errors = 0
    seen: set[str] = set()
    for bet in open_bets or []:
        if str(bet.get("status")) not in OPEN:
            continue
        match_id = str(bet.get("match_id") or "").strip()
        if not match_id or match_id in seen or checked >= MAX_RESULT_CHECKS:
            continue
        seen.add(match_id)
        checked += 1
        try:
            match = fetch_match(match_id, api_key)
            final = final_from_match(match, bet)
        except Exception as exc:
            errors += 1
            print(f"iNeed result check {match_id}: {type(exc).__name__}")
            continue
        if not final:
            continue
        snap = bet.get("placement_snapshot") or {}
        rows.append({
            "match_id": match_id,
            "p1": snap.get("p1"),
            "p2": snap.get("p2"),
            "result": final,
        })
        ready += 1
    return rows, {"checked": checked, "ready": ready, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edge-url", required=True)
    parser.add_argument("--oidc-token", required=True)
    args = parser.parse_args()

    api_key = os.getenv("LIVE_TENNIS_API_KEY", "").strip()
    if not api_key:
        print("iNeed direct settlement skipped: LIVE_TENNIS_API_KEY missing")
        return 0

    state = post(args.edge_url, args.oidc_token, {"action": "state"})
    experiment = state.get("experiment") or {}
    open_bets = state.get("open_bets") or []
    final_rows, diag = live_final_rows(open_bets, api_key)
    settlements = build_settlements(open_bets, final_rows, experiment.get("config") or {})

    if not settlements:
        print(json.dumps({"ok": True, "settlements": 0, "result_checks": diag}, ensure_ascii=False))
        return 0

    payload = {
        "experiment_id": experiment.get("id"),
        "operator": "superbet.pl",
        "mode": "SHADOW",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluations": [],
        "settlements": settlements,
        "health": {
            "automatic_real_betting": False,
            "settlement_source": "live_tennis_api_direct_fallback",
            "result_checks": diag,
            "settlements": len(settlements),
        },
    }
    result = post(args.edge_url, args.oidc_token, {"action": "sync", "payload": payload})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
