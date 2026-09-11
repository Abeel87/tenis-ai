from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen

try:
    from .ineed_money import evaluate, build_settlements
except ImportError:
    from ineed_money import evaluate, build_settlements

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "frontend" / "data"
RESULTS = DATA / "results.json"
DIRECT = DATA / "superbet_direct_current.json"
HISTORY = DATA / "history.json"
CONFIG = ROOT / "config" / "ineed_superbet_pl.json"


def read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def post(url: str, token: str, body: dict) -> dict:
    req = Request(url, data=json.dumps(body).encode(), headers={"authorization": f"Bearer {token}", "content-type": "application/json"}, method="POST")
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def build_payload(state: dict) -> dict:
    results = read(RESULTS, [])
    direct = read(DIRECT, {})
    history = read(HISTORY, [])
    experiment = state.get("experiment") or {}
    cfg = experiment.get("config") or read(CONFIG, {})
    evaluations = evaluate(results if isinstance(results, list) else [], direct if isinstance(direct, dict) else {}, cfg, state)
    settlements = build_settlements(state.get("open_bets") or [], history if isinstance(history, list) else [], cfg)
    return {
        "experiment_id": experiment.get("id"), "operator": "superbet.pl", "mode": "SHADOW",
        "generated_at": datetime.now(timezone.utc).isoformat(), "evaluations": evaluations, "settlements": settlements,
        "health": {"automatic_real_betting": False, "results_rows": len(results) if isinstance(results, list) else 0,
                   "direct_status": direct.get("status") if isinstance(direct, dict) else None,
                   "evaluations": len(evaluations), "settlements": len(settlements)},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edge-url", required=True)
    ap.add_argument("--oidc-token", required=True)
    args = ap.parse_args()
    state = post(args.edge_url, args.oidc_token, {"action": "state"})
    payload = build_payload(state)
    result = post(args.edge_url, args.oidc_token, {"action": "sync", "payload": payload})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
