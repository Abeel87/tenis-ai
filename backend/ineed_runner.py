from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
import unicodedata
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
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def _slug(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return text


def _pair_from_match_name(value: object) -> tuple[str | None, str | None]:
    text = " ".join(str(value or "").split())
    if not text:
        return None, None
    for separator in ("·", " vs ", " v "):
        parts = text.split(separator, 1)
        if len(parts) == 2:
            p1, p2 = parts[0].strip(), parts[1].strip()
            if p1 and p2:
                return p1, p2
    return None, None


def _iter_event_records(value):
    if isinstance(value, dict):
        event_id = str(value.get("eventId") or value.get("event_id") or "").strip()
        match_name = value.get("matchName") or value.get("match_name") or value.get("eventName")
        p1, p2 = _pair_from_match_name(match_name)
        if re.fullmatch(r"\d{5,20}", event_id) and p1 and p2:
            yield value
        for child in value.values():
            yield from _iter_event_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_event_records(child)


def event_urls_from_payload(payload: object) -> list[str]:
    """Extract concrete tennis event candidates from public Superbet listing JSON.

    The resulting URL is only a discovery carrier. Final fixture acceptance is
    still performed by ``superbet_direct`` against the exact public event JSON,
    including player names and scheduled time.
    """
    out: list[str] = []
    seen: set[str] = set()
    for row in _iter_event_records(payload):
        event_id = str(row.get("eventId") or row.get("event_id") or "").strip()
        match_name = row.get("matchName") or row.get("match_name") or row.get("eventName")
        p1, p2 = _pair_from_match_name(match_name)
        if not event_id or not p1 or not p2:
            continue

        concrete = None
        for key in ("url", "eventUrl", "event_url", "seoUrl", "seo_url", "link"):
            raw = str(row.get(key) or "").strip()
            if not raw:
                continue
            candidate = urljoin(superbet_direct.BASE, raw)
            if (
                superbet_direct._allowed_url(candidate)
                and re.fullmatch(r"/kursy/tenis/.+-\d+", urlparse(candidate).path)
            ):
                concrete = f"{superbet_direct.BASE}{urlparse(candidate).path}"
                break

        if concrete is None:
            left, right = _slug(p1), _slug(p2)
            if not left or not right:
                continue
            concrete = f"{superbet_direct.BASE}/kursy/tenis/{left}-vs-{right}-{event_id}"

        if concrete not in seen:
            seen.add(concrete)
            out.append(concrete)
    return out


def _collect_dom_urls(driver) -> list[str]:
    """Snapshot tennis links without retaining WebElement references.

    Superbet virtualizes the listing while scrolling, so Selenium WebElements
    can become stale between ``find_elements`` and ``get_attribute``. Reading
    hrefs atomically inside the page avoids that race. A WebElement fallback is
    kept only for drivers that cannot execute the snapshot script.
    """
    raw_hrefs: list[str] = []
    try:
        snapshot = driver.execute_script(
            """
            return Array.from(document.querySelectorAll('a[href*="/kursy/tenis/"]'))
              .map(a => a.href || a.getAttribute('href') || '')
              .filter(Boolean);
            """
        )
        if isinstance(snapshot, list):
            raw_hrefs.extend(str(value) for value in snapshot if value)
    except Exception:
        try:
            from selenium.webdriver.common.by import By
            from selenium.common.exceptions import StaleElementReferenceException

            for element in driver.find_elements(By.CSS_SELECTOR, 'a[href*="/kursy/tenis/"]'):
                try:
                    candidate = element.get_attribute("href")
                except StaleElementReferenceException:
                    continue
                except Exception:
                    continue
                if candidate:
                    raw_hrefs.append(str(candidate))
        except (ImportError, Exception):
            pass

    out: list[str] = []
    seen: set[str] = set()
    for candidate in raw_hrefs:
        absolute = urljoin(superbet_direct.BASE, candidate)
        if (
            superbet_direct._allowed_url(absolute)
            and re.fullmatch(r"/kursy/tenis/.+-\d+", urlparse(absolute).path)
        ):
            canonical = f"{superbet_direct.BASE}{urlparse(absolute).path}"
            if canonical not in seen:
                seen.add(canonical)
                out.append(canonical)

    try:
        for candidate in superbet_direct.discover_match_urls(driver.page_source):
            if candidate not in seen:
                seen.add(candidate)
                out.append(candidate)
    except Exception:
        pass
    return out


def _drain_public_listing_json(driver) -> list[str]:
    """Read only public listing XHR responses already loaded by the browser."""
    try:
        entries = driver.get_log("performance")
    except Exception:
        return []

    out: list[str] = []
    for entry in entries:
        try:
            envelope = json.loads(entry.get("message") or "{}")
            message = envelope.get("message") or {}
            if message.get("method") != "Network.responseReceived":
                continue
            params = message.get("params") or {}
            response = params.get("response") or {}
            parsed = urlparse(str(response.get("url") or ""))
            if parsed.netloc != superbet_direct.EVENT_API_HOST:
                continue
            if int(response.get("status") or 0) != 200:
                continue
            mime = str(response.get("mimeType") or response.get("headers", {}).get("content-type") or "")
            if "json" not in mime.casefold():
                continue
            request_id = params.get("requestId")
            if not request_id:
                continue
            body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
            raw = str((body or {}).get("body") or "")
            if not raw or len(raw) > 25_000_000:
                continue
            payload = json.loads(raw)
            out.extend(event_urls_from_payload(payload))
        except Exception:
            continue
    return out


def discover_live_superbet_urls(timeout: int = 30) -> tuple[list[str], dict]:
    """Discover a broader current tennis catalogue than the virtualized DOM alone.

    Uses incremental scrolling plus public listing XHR payloads. It does not log
    in, place bets, or feed prices into MODEL/RAW, Symphony or PLAYABLE.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:
        raise RuntimeError("live Direct enrichment requires selenium") from exc

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--lang=pl-PL")
    options.add_argument(f"--user-agent={superbet_direct.USER_AGENT}")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(options=options)
    seen: set[str] = set()
    urls: list[str] = []
    dom_found: set[str] = set()
    network_found: set[str] = set()
    transient_scroll_errors = 0

    def add(items, bucket: set[str]):
        for candidate in items:
            absolute = urljoin(superbet_direct.BASE, str(candidate or ""))
            if not (
                superbet_direct._allowed_url(absolute)
                and re.fullmatch(r"/kursy/tenis/.+-\d+", urlparse(absolute).path)
            ):
                continue
            canonical = f"{superbet_direct.BASE}{urlparse(absolute).path}"
            bucket.add(canonical)
            if canonical not in seen:
                seen.add(canonical)
                urls.append(canonical)

    try:
        driver.set_page_load_timeout(timeout)
        driver.get(superbet_direct.TENNIS_LISTING_URL)
        try:
            WebDriverWait(driver, min(timeout, 15)).until(lambda drv: bool(_collect_dom_urls(drv)))
        except Exception:
            pass

        stable_rounds = 0
        previous_count = -1
        previous_height = -1
        for _ in range(80):
            add(_collect_dom_urls(driver), dom_found)
            add(_drain_public_listing_json(driver), network_found)

            try:
                metrics = driver.execute_script(
                    """
                    const el = document.scrollingElement || document.documentElement;
                    const h = el ? (el.scrollHeight || 0) : 0;
                    const y = window.scrollY || (el ? el.scrollTop : 0) || 0;
                    const vh = window.innerHeight || 1000;
                    window.scrollBy(0, Math.max(800, Math.floor(vh * 0.85)));
                    return [h, y, vh];
                    """
                ) or [0, 0, 1000]
            except Exception:
                transient_scroll_errors += 1
                if transient_scroll_errors >= 5:
                    break
                time.sleep(0.25)
                continue

            height = int(metrics[0] or 0)
            y = int(metrics[1] or 0)
            vh = int(metrics[2] or 1000)
            time.sleep(0.35)

            count = len(urls)
            near_bottom = y + vh >= max(0, height - 250)
            if count == previous_count and height == previous_height and near_bottom:
                stable_rounds += 1
            else:
                stable_rounds = 0
            previous_count = count
            previous_height = height
            if stable_rounds >= 8:
                break

        add(_collect_dom_urls(driver), dom_found)
        add(_drain_public_listing_json(driver), network_found)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return urls, {
        "status": "OK" if urls else "NO_MATCH_URLS",
        "urls_found": len(urls),
        "dom_urls_found": len(dom_found),
        "network_event_urls_found": len(network_found),
        "transient_scroll_errors": transient_scroll_errors,
        "discovery": "INCREMENTAL_SCROLL_PLUS_PUBLIC_LISTING_XHR",
    }


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
