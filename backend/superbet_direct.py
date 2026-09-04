from __future__ import annotations

"""Read-only Superbet PL public tennis source probe.

This module is intentionally isolated from MODEL/RAW, Player DNA, Symphony and
PLAYABLE. It only verifies that public Superbet tennis pages are reachable and
that concrete match pages expose enough server-rendered information to support
later operator-offer normalization.

No login, no cookies, no bet placement, no model probability changes and no
writes to frontend/data.
"""

import json
import re
import sys
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE = "https://superbet.pl"
TENNIS_LISTING_URL = f"{BASE}/zaklady-bukmacherskie/tenis"
MAX_HTML_BYTES = 5_000_000
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
MARKET_MARKERS = (
    "liczba gemow",
    "handicap",
    "dokladny wynik",
    "zwyciezca",
    "liczba setow",
    "tiebreak",
    "set zwyciezca",
)


def _norm(value: object) -> str:
    text = str(value or "").casefold()
    replacements = str.maketrans({
        "ą": "a", "ć": "c", "ę": "e", "ł": "l",
        "ń": "n", "ó": "o", "ś": "s", "ż": "z", "ź": "z",
    })
    text = text.translate(replacements)
    return " ".join(re.sub(r"[^a-z0-9:+.\-/]+", " ", text).split())


def _allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "superbet.pl":
        return False
    return (
        parsed.path.startswith("/zaklady-bukmacherskie/tenis")
        or parsed.path.startswith("/kursy/tenis/")
    )


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.casefold() != "a":
            return
        href = next((v for k, v in attrs if k.casefold() == "href"), None)
        if href:
            self.links.append(str(href))

    def handle_data(self, data: str) -> None:
        value = " ".join(str(data or "").split())
        if value:
            self.text.append(value)


def parse_html(html: str) -> dict:
    parser = _PageParser()
    parser.feed(html or "")
    return {
        "links": parser.links,
        "text": " ".join(parser.text),
    }


def discover_match_urls(html: str) -> list[str]:
    parsed = parse_html(html)
    candidates = list(parsed["links"])

    # Superbet may render event anchors client-side while embedding their paths
    # in hydration JSON. Normalize common HTML/JSON escaping and scan that
    # payload too; this still consumes only the public page already fetched.
    decoded = unescape(html or "")
    for _ in range(3):
        newer = decoded.replace("\\u002F", "/").replace("\\u002f", "/").replace("\\/", "/")
        if newer == decoded:
            break
        decoded = newer
    candidates.extend(
        match.group(1)
        for match in re.finditer(
            r"(?<![a-zA-Z0-9.-])(?:https://superbet\.pl)?(/kursy/tenis/[a-zA-Z0-9%._~+\-]+-\d+)",
            decoded,
        )
    )

    out: list[str] = []
    seen: set[str] = set()
    for href in candidates:
        absolute = urljoin(BASE, href)
        if not _allowed_url(absolute):
            continue
        path = urlparse(absolute).path
        if not re.fullmatch(r"/kursy/tenis/.+-\d+", path):
            continue
        canonical = f"{BASE}{path}"
        if canonical not in seen:
            seen.add(canonical)
            out.append(canonical)
    return out


def summarize_match_page(html: str, url: str | None = None) -> dict:
    parsed = parse_html(html)
    text = str(parsed["text"])
    norm = _norm(text)
    markers = [marker for marker in MARKET_MARKERS if marker in norm]
    decimal_tokens = re.findall(r"(?<!\d)\d{1,3}[.,]\d{1,3}(?!\d)", text)
    signed_line_tokens = re.findall(r"(?<!\d)[+-]?\d+(?:[.,]\d+)?(?!\d)", text)
    return {
        "url": url,
        "text_length": len(text),
        "market_markers": markers,
        "market_marker_count": len(markers),
        "decimal_token_count": len(decimal_tokens),
        "numeric_token_count": len(signed_line_tokens),
        "has_operator_market_evidence": (
            len(text) >= 1000
            and len(markers) >= 2
            and len(decimal_tokens) >= 4
        ),
    }


def fetch_html(url: str, timeout: int = 25) -> str:
    if not _allowed_url(url):
        raise ValueError("only public Superbet PL tennis URLs are allowed")
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.7",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = str(response.headers.get("Content-Type") or "")
        if "text/html" not in content_type.casefold():
            raise RuntimeError(f"unexpected content type: {content_type}")
        raw = response.read(MAX_HTML_BYTES + 1)
        if len(raw) > MAX_HTML_BYTES:
            raise RuntimeError("Superbet HTML exceeds safety limit")
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def probe() -> dict:
    listing_html = fetch_html(TENNIS_LISTING_URL)
    match_urls = discover_match_urls(listing_html)
    result = {
        "mode": "READ_ONLY_PUBLIC_SUPERBET_DIRECT_PROBE",
        "production_influence": False,
        "playable_influence": False,
        "player_dna_influence": False,
        "symphony_influence": False,
        "listing_url": TENNIS_LISTING_URL,
        "match_urls_found": len(match_urls),
        "sample_match_url": match_urls[0] if match_urls else None,
    }
    if not match_urls:
        parsed_listing = parse_html(listing_html)
        normalized_raw = listing_html or ""
        for _ in range(3):
            newer = normalized_raw.replace("\\u002F", "/").replace("\\u002f", "/").replace("\\/", "/")
            if newer == normalized_raw:
                break
            normalized_raw = newer
        result["listing_diagnostic"] = {
            "html_length": len(listing_html),
            "text_length": len(str(parsed_listing.get("text") or "")),
            "anchor_href_count": len(parsed_listing.get("links") or []),
            "contains_tennis_match_path": "/kursy/tenis/" in normalized_raw,
        }
        result["status"] = "NO_MATCH_URLS"
        return result

    sample_url = match_urls[0]
    summary = summarize_match_page(fetch_html(sample_url), sample_url)
    result["sample"] = summary
    result["status"] = "OK" if summary["has_operator_market_evidence"] else "INSUFFICIENT_MARKET_EVIDENCE"
    return result



def browser_probe(timeout: int = 25) -> dict:
    """Probe the public JS-rendered site with an isolated headless browser."""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:
        raise RuntimeError("browser probe requires selenium") from exc

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--lang=pl-PL")
    options.add_argument(f"--user-agent={USER_AGENT}")

    driver = webdriver.Chrome(options=options)
    try:
        driver.set_page_load_timeout(timeout)
        driver.get(TENNIS_LISTING_URL)

        def listing_ready(drv):
            hrefs = [
                str(el.get_attribute("href") or "")
                for el in drv.find_elements(By.CSS_SELECTOR, 'a[href*="/kursy/tenis/"]')
            ]
            return any(_allowed_url(href) for href in hrefs) or bool(discover_match_urls(drv.page_source))

        try:
            WebDriverWait(driver, timeout).until(listing_ready)
        except Exception:
            pass

        listing_html = driver.page_source
        direct_hrefs = [
            str(el.get_attribute("href") or "")
            for el in driver.find_elements(By.CSS_SELECTOR, 'a[href*="/kursy/tenis/"]')
        ]
        match_urls = []
        seen = set()
        for candidate in [*direct_hrefs, *discover_match_urls(listing_html)]:
            absolute = urljoin(BASE, candidate)
            if not _allowed_url(absolute):
                continue
            path = urlparse(absolute).path
            if not re.fullmatch(r"/kursy/tenis/.+-\d+", path):
                continue
            canonical = f"{BASE}{path}"
            if canonical not in seen:
                seen.add(canonical)
                match_urls.append(canonical)

        result = {
            "mode": "READ_ONLY_PUBLIC_SUPERBET_DIRECT_BROWSER_PROBE",
            "production_influence": False,
            "playable_influence": False,
            "player_dna_influence": False,
            "symphony_influence": False,
            "listing_url": TENNIS_LISTING_URL,
            "listing_final_url": driver.current_url,
            "listing_title": driver.title,
            "match_urls_found": len(match_urls),
            "sample_match_url": match_urls[0] if match_urls else None,
        }
        if not match_urls:
            parsed = parse_html(listing_html)
            result["listing_diagnostic"] = {
                "html_length": len(listing_html),
                "text_length": len(str(parsed.get("text") or "")),
                "anchor_href_count": len(parsed.get("links") or []),
            }
            result["status"] = "NO_MATCH_URLS"
            return result

        sample_url = match_urls[0]
        driver.get(sample_url)

        def market_ready(drv):
            summary = summarize_match_page(drv.page_source, sample_url)
            return bool(summary.get("has_operator_market_evidence"))

        try:
            WebDriverWait(driver, timeout).until(market_ready)
        except Exception:
            pass

        summary = summarize_match_page(driver.page_source, sample_url)
        summary["final_url"] = driver.current_url
        summary["title"] = driver.title
        result["sample"] = summary
        result["status"] = "OK" if summary["has_operator_market_evidence"] else "INSUFFICIENT_MARKET_EVIDENCE"
        return result
    finally:
        driver.quit()

def main() -> None:
    mode = str(sys.argv[1] if len(sys.argv) > 1 else "probe").strip().casefold()
    if mode == "probe":
        result = probe()
    elif mode == "probe-browser":
        result = browser_probe()
    else:
        raise SystemExit("usage: superbet_direct.py [probe|probe-browser]")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") != "OK":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
