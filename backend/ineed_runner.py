from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from .ineed_money import evaluate, build_settlements
    from . import superbet_direct
except ImportError:
    from ineed_money import evaluate, build_settlements
    import superbet_direct

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
    req = Request(
        url,
        data=json.dumps(body).encode(),
        headers={"authorization": f"Bearer {token}", "content-type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


# The Superbet producer owns discovery; iNeed consumes the same implementation.
event_urls_from_payload = superbet_direct.event_urls_from_payload
_collect_dom_urls = superbet_direct._collect_dom_urls
discover_live_superbet_urls = superbet_direct.discover_live_superbet_urls


def _ineed_playable_results(results: list[dict]) -> list[dict]:
    out: list[dict] = []
    for match in results if isinstance(results, list) else []:
        if not isinstance(match, dict):
            continue
        layer = match.get("symphony2_playable") or {}
        if not isinstance(layer, dict):
            continue
        if not (
            layer.get("playable") is True
            and layer.get("final_playable_authority") is True
            and layer.get("authority") == "SYMPHONY2_FINAL_PLAYABLE"
            and layer.get("operator") == "superbet.pl"
        ):
            continue
        out.append(match)
    return out


def _seed_direct_urls(direct_feed: dict) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for match in (direct_feed.get("matches") or []) if isinstance(direct_feed, dict) else []:
        if not isinstance(match, dict):
            continue
        url = str(match.get("event_url") or "").strip()
        if not url or not superbet_direct._allowed_url(url):
            continue
        path = urlparse(url).path
        if not re.fullmatch(r"/kursy/tenis/.+-\d+", path):
            continue
        canonical = f"{superbet_direct.BASE}{path}"
        if canonical not in seen:
            seen.add(canonical)
            out.append(canonical)
    return out


def refresh_direct_for_ineed(results: list[dict], direct_feed: dict, discoverer=None) -> tuple[dict, dict]:
    """Refresh current Superbet quotes in memory for iNeed$ only.

    Existing Direct event URLs are always re-fetched, while public listing XHR
    discovery can add matches hidden by Superbet's virtualized listing. The
    canonical PLAYABLE layer is never modified.
    """
    if not isinstance(results, list) or not results:
        return direct_feed, {"status": "NO_RESULTS", "used_fresh_direct": False}

    target_rows = _ineed_playable_results(results)
    if not target_rows:
        return direct_feed, {
            "status": "NO_PLAYABLE_TARGETS",
            "playable_targets": 0,
            "used_fresh_direct": False,
        }

    seed_urls = _seed_direct_urls(direct_feed if isinstance(direct_feed, dict) else {})
    discovery_error = None
    try:
        discovered, diag = (discoverer or discover_live_superbet_urls)()
    except Exception as exc:
        discovered = []
        discovery_error = type(exc).__name__
        diag = {
            "status": "LIVE_DISCOVERY_FAILED",
            "error": discovery_error,
        }

    urls: list[str] = []
    seen: set[str] = set()
    for candidate in [*seed_urls, *discovered]:
        if candidate not in seen:
            seen.add(candidate)
            urls.append(candidate)

    if not urls:
        return direct_feed, {
            **diag,
            "status": "LIVE_DISCOVERY_FAILED" if discovery_error else "NO_DIRECT_URLS",
            "seed_urls": len(seed_urls),
            "playable_targets": len(target_rows),
            "used_fresh_direct": False,
        }

    try:
        fresh = superbet_direct.build_selected_direct_feed(target_rows, urls, max_matches=64)
    except Exception as exc:
        return direct_feed, {
            **diag,
            "status": "FRESH_DIRECT_BUILD_FAILED",
            "error": type(exc).__name__,
            "seed_urls": len(seed_urls),
            "playable_targets": len(target_rows),
            "total_candidate_urls": len(urls),
            "used_fresh_direct": False,
        }

    if fresh.get("status") != "OK" or not fresh.get("matches"):
        return direct_feed, {
            **diag,
            "status": str(fresh.get("status") or "NO_FRESH_DIRECT"),
            "seed_urls": len(seed_urls),
            "playable_targets": len(target_rows),
            "total_candidate_urls": len(urls),
            "fresh_resolved_matches": int(fresh.get("resolved_app_matches") or 0),
            "used_fresh_direct": False,
        }

    return fresh, {
        **diag,
        "status": "DEGRADED_SEED_REFRESH" if discovery_error else "OK",
        "live_discovery_error": discovery_error,
        "seed_urls": len(seed_urls),
        "playable_targets": len(target_rows),
        "total_candidate_urls": len(urls),
        "fresh_resolved_matches": int(fresh.get("resolved_app_matches") or 0),
        "fresh_candidate_matches": int(fresh.get("candidate_app_matches") or 0),
        "used_fresh_direct": True,
    }


def build_payload(state: dict) -> dict:
    results = read(RESULTS, [])
    direct = read(DIRECT, {})
    history = read(HISTORY, [])
    experiment = state.get("experiment") or {}
    cfg = experiment.get("config") or read(CONFIG, {})

    result_rows = results if isinstance(results, list) else []
    direct_feed = direct if isinstance(direct, dict) else {}
    fresh_direct, enrichment = refresh_direct_for_ineed(result_rows, direct_feed)

    evaluations = evaluate(result_rows, fresh_direct, cfg, state)
    settlements = build_settlements(
        state.get("open_bets") or [], history if isinstance(history, list) else [], cfg
    )
    return {
        "experiment_id": experiment.get("id"),
        "operator": "superbet.pl",
        "mode": "SHADOW",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluations": evaluations,
        "settlements": settlements,
        "health": {
            "automatic_real_betting": False,
            "results_rows": len(result_rows),
            "direct_status": fresh_direct.get("status") if isinstance(fresh_direct, dict) else None,
            "direct_source": fresh_direct.get("source") if isinstance(fresh_direct, dict) else None,
            "direct_enrichment": enrichment,
            "evaluations": len(evaluations),
            "settlements": len(settlements),
        },
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
