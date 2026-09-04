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
        "text_lines": list(parser.text),
    }


def rendered_text_from_html(html: str) -> str:
    return "\n".join(parse_html(html).get("text_lines") or [])


def rendered_dom_text(driver) -> str:
    """Return ordered rendered DOM text nodes without executing or parsing scripts."""
    try:
        nodes = driver.execute_script(
            """
            const root = document.body || document.documentElement;
            if (!root) return [];
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
            const out = [];
            let node;
            while ((node = walker.nextNode())) {
              const parent = node.parentElement;
              if (!parent) continue;
              const tag = (parent.tagName || '').toUpperCase();
              if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE'].includes(tag)) continue;
              const value = (node.nodeValue || '').replace(/\\s+/g, ' ').trim();
              if (value) out.push(value);
            }
            return out;
            """
        )
    except Exception:
        nodes = None
    if isinstance(nodes, list) and nodes:
        return "\n".join(str(value).strip() for value in nodes if str(value).strip())
    return rendered_text_from_html(driver.page_source)


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




_PRICE_TOKEN = re.compile(r"^\d+(?:[.,]\d{2,3})$")
_LINE_TOKEN = r"([+-]?\d+(?:[.,]\d+)?)"


def _float_token(value: object) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _event_id_from_url(url: str | None) -> str | None:
    path = urlparse(str(url or "")).path
    match = re.search(r"-(\d+)$", path)
    return match.group(1) if match else None


def _players_from_title(title: str | None) -> tuple[str | None, str | None]:
    head = str(title or "").split(":", 1)[0].strip()
    parts = re.split(r"\s+vs\s+", head, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None, None
    p1, p2 = (part.strip() or None for part in parts)
    return p1, p2


def _canonical_player(value: str, p1: str | None, p2: str | None) -> str:
    raw = str(value or "").strip()
    key = _norm(raw)
    if p1 and key == _norm(p1):
        return p1
    if p2 and key == _norm(p2):
        return p2
    return raw


def _price_after(lines: list[str], index: int, max_steps: int = 4) -> float | None:
    for candidate in lines[index + 1:index + 1 + max_steps]:
        token = candidate.strip()
        if _PRICE_TOKEN.fullmatch(token):
            value = _float_token(token)
            if value is not None and value >= 1.0:
                return value
    return None



def _semantic_match_total_table(lines: list[str]) -> list[dict]:
    """Parse the explicit Superbet match-total table.

    The table itself names all three columns (Gemy / PONIŻEJ / POWYŻEJ), so
    mapping successive numeric triples is structural parsing, not inference.
    """
    out: list[dict] = []
    header = ["liczba gemow", "gemy", "ponizej", "powyzej"]
    for index in range(0, max(0, len(lines) - 3)):
        if [_norm(value) for value in lines[index:index + 4]] != header:
            continue
        cursor = index + 4
        while cursor + 2 < len(lines):
            line_value = _float_token(lines[cursor])
            under_price = _float_token(lines[cursor + 1])
            over_price = _float_token(lines[cursor + 2])
            if line_value is None or under_price is None or over_price is None:
                break
            if not (1.0 <= line_value <= 100.0):
                break
            if not (1.0 <= under_price <= 1000.0 and 1.0 <= over_price <= 1000.0):
                break
            # Tennis total-game lines are half/integer game thresholds; requiring
            # a sensible threshold also prevents unrelated price triples from
            # being consumed after the table.
            if line_value < 5.0:
                break
            raw_base = f"Liczba gemów | {lines[cursor]}"
            out.append(_direct_selection(
                market="match_total",
                pick="under",
                line=line_value,
                odds=under_price,
                raw_label=f"{raw_base} | PONIŻEJ",
            ))
            out.append(_direct_selection(
                market="match_total",
                pick="over",
                line=line_value,
                odds=over_price,
                raw_label=f"{raw_base} | POWYŻEJ",
            ))
            cursor += 3
        break
    return out


def _semantic_inline_offer(lines: list[str]) -> list[dict]:
    """Parse self-describing rendered offer cards whose label contains semantics."""
    out: list[dict] = []
    total_sets_re = re.compile(
        rf"^Liczba setów\s*-\s*(Poniżej|Powyżej)\s+{_LINE_TOKEN}$",
        re.IGNORECASE,
    )
    for index, label in enumerate(lines):
        odds = _price_after(lines, index, max_steps=2)
        if odds is None:
            continue
        match = total_sets_re.fullmatch(label)
        if match:
            pick = "under" if _norm(match.group(1)) == "ponizej" else "over"
            out.append(_direct_selection(
                market="total_sets",
                pick=pick,
                line=float(match.group(2).replace(",", ".")),
                odds=odds,
                raw_label=label,
            ))
    return out


def _direct_selection(
    *,
    market: str,
    pick: str,
    odds: float,
    raw_label: str,
    line: float | None = None,
    player: str | None = None,
    set_no: int | None = None,
    source: str = "superbet_direct_public_rendered_text",
) -> dict:
    row = {
        "market": market,
        "pick": pick,
        "line": line,
        "player": player,
        "set_no": set_no,
        "raw_label": raw_label,
        "operator": "superbet.pl",
        "operator_available": True,
        "operator_price": odds,
        "operator_price_verified": True,
        "operator_price_source": source,
        "prices_used": False,
        "direct_source": True,
    }
    if line is not None:
        row.update({
            "operator_line_verified": True,
            "fixture_line_verified": True,
            "operator_line_source": source,
        })
    return row


def parse_visible_offer_text(
    visible_text: str,
    *,
    url: str | None = None,
    title: str | None = None,
) -> dict:
    """Normalize unambiguous public Superbet selections from rendered body text.

    Operator prices are captured as metadata only and are explicitly forbidden
    from influencing model math. Only descriptions that carry their own market
    semantics are accepted; column-position-only markets stay out.
    """
    lines = [line.strip() for line in str(visible_text or "").splitlines() if line.strip()]
    p1, p2 = _players_from_title(title)
    selections: list[dict] = []
    selections.extend(_semantic_match_total_table(lines))
    selections.extend(_semantic_inline_offer(lines))

    match_total_re = re.compile(
        rf"^(Poniżej|Powyżej) {_LINE_TOKEN} gemów w meczu$",
        re.IGNORECASE,
    )
    set_total_re = re.compile(
        rf"^(Poniżej|Powyżej) {_LINE_TOKEN} gemów w ([123])\.\s*secie$",
        re.IGNORECASE,
    )
    player_set_total_re = re.compile(
        rf"^(.+?) zdobędzie (poniżej|powyżej) {_LINE_TOKEN} gemów w ([123])\.\s*secie$",
        re.IGNORECASE,
    )
    set_handicap_re = re.compile(
        rf"^(.+?) wygra ([123])\.\s*set przy uwzględnieniu podanego Handicapu gemów \({_LINE_TOKEN}\)$",
        re.IGNORECASE,
    )
    exact_score_re = re.compile(r"^Mecz zakończy się wynikiem (\d+):(\d+)$", re.IGNORECASE)

    for index, label in enumerate(lines):
        odds = _price_after(lines, index)
        if odds is None:
            continue

        if p1 and label == f"{p1} wygra":
            selections.append(_direct_selection(
                market="match_winner", pick=p1, odds=odds, raw_label=label,
            ))
            continue
        if p2 and label == f"{p2} wygra":
            selections.append(_direct_selection(
                market="match_winner", pick=p2, odds=odds, raw_label=label,
            ))
            continue

        match = match_total_re.fullmatch(label)
        if match:
            pick = "under" if _norm(match.group(1)) == "ponizej" else "over"
            selections.append(_direct_selection(
                market="match_total",
                pick=pick,
                line=float(match.group(2).replace(",", ".")),
                odds=odds,
                raw_label=label,
            ))
            continue

        match = set_total_re.fullmatch(label)
        if match:
            pick = "under" if _norm(match.group(1)) == "ponizej" else "over"
            set_no = int(match.group(3))
            selections.append(_direct_selection(
                market=f"set{set_no}_total",
                pick=pick,
                line=float(match.group(2).replace(",", ".")),
                odds=odds,
                raw_label=label,
                set_no=set_no,
            ))
            continue

        match = player_set_total_re.fullmatch(label)
        if match:
            player = _canonical_player(match.group(1), p1, p2)
            pick = "under" if _norm(match.group(2)) == "ponizej" else "over"
            set_no = int(match.group(4))
            selections.append(_direct_selection(
                market="player_total_games",
                pick=pick,
                line=float(match.group(3).replace(",", ".")),
                odds=odds,
                raw_label=label,
                player=player,
                set_no=set_no,
            ))
            continue

        match = set_handicap_re.fullmatch(label)
        if match:
            player = _canonical_player(match.group(1), p1, p2)
            set_no = int(match.group(2))
            selections.append(_direct_selection(
                market=f"set{set_no}_game_handicap",
                pick=player,
                line=float(match.group(3).replace(",", ".")),
                odds=odds,
                raw_label=label,
                player=player,
                set_no=set_no,
            ))
            continue

        match = exact_score_re.fullmatch(label)
        if match:
            selections.append(_direct_selection(
                market="exact_match_score",
                pick=f"{int(match.group(1))}:{int(match.group(2))}",
                odds=odds,
                raw_label=label,
            ))

    dedup: dict[tuple, dict] = {}
    for row in selections:
        key = (
            row.get("market"),
            _norm(row.get("pick")),
            row.get("line"),
            _norm(row.get("player")),
            row.get("set_no"),
        )
        dedup.setdefault(key, row)
    selections = list(dedup.values())

    market_counts: dict[str, int] = {}
    for row in selections:
        market = str(row.get("market") or "unknown")
        market_counts[market] = market_counts.get(market, 0) + 1

    return {
        "mode": "READ_ONLY_PUBLIC_SUPERBET_DIRECT_NORMALIZED_OFFER",
        "operator": "superbet.pl",
        "event_id": _event_id_from_url(url),
        "url": url,
        "p1": p1,
        "p2": p2,
        "canonical_selections": selections,
        "canonical_selections_count": len(selections),
        "market_counts": dict(sorted(market_counts.items())),
        "operator_prices_captured": True,
        "prices_used": False,
        "production_influence": False,
        "playable_influence": False,
        "player_dna_influence": False,
        "symphony_influence": False,
    }


EVENT_API_HOST = "production-superbet-offer-pl.freetls.fastly.net"
COMBINATION_MARKET_ID = 238733
EVENT_JSON_SOURCE = "superbet_direct_public_event_json"


def _event_record(payload: object, event_id: str | None = None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    rows = payload.get("data")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if event_id is None or str(row.get("eventId") or "") == str(event_id):
            return row
    return None


def _players_from_event(row: dict, title: str | None = None) -> tuple[str | None, str | None]:
    match_name = str(row.get("matchName") or "")
    parts = [part.strip() for part in match_name.split("·") if part.strip()]
    if len(parts) == 2:
        return parts[0], parts[1]
    return _players_from_title(title)


def _set_no_from_odd(odd: dict) -> int | None:
    specifiers = odd.get("specifiers") if isinstance(odd.get("specifiers"), dict) else {}
    for value in (specifiers.get("setnr"),):
        try:
            number = int(str(value))
        except (TypeError, ValueError):
            number = 0
        if number in {1, 2, 3}:
            return number
    text = " ".join(str(odd.get(key) or "") for key in ("marketName", "name", "info"))
    match = re.search(r"(?<!\d)([123])\s*\.?\s*set", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    market_name = _norm(odd.get("marketName"))
    if market_name == "x set zwyciezca":
        try:
            number = int(str(odd.get("specialBetValue") or ""))
        except (TypeError, ValueError):
            number = 0
        if number in {1, 2, 3}:
            return number
    return None


def _line_from_odd(odd: dict) -> float | None:
    specifiers = odd.get("specifiers") if isinstance(odd.get("specifiers"), dict) else {}
    for key in ("total", "handicap", "hcp", "line"):
        value = _float_token(specifiers.get(key))
        if value is not None:
            return value
    raw = str(odd.get("specialBetValue") or "").strip()
    if re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", raw):
        return _float_token(raw)
    return None


def _market_key(value: object) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", _norm(value)).split())


def _ou_pick(*values: object) -> str | None:
    text = _norm(" ".join(str(value or "") for value in values))
    if "ponizej" in text:
        return "under"
    if "powyzej" in text:
        return "over"
    return None


def _player_from_odd(odd: dict, p1: str | None, p2: str | None) -> str | None:
    text = _norm(" ".join(str(odd.get(key) or "") for key in ("info", "name", "marketName")))
    if p1 and _norm(p1) in text:
        return p1
    if p2 and _norm(p2) in text:
        return p2
    code = str(odd.get("code") or "").strip()
    if code == "1":
        return p1
    if code == "2":
        return p2
    return None


def _score_from_odd(odd: dict) -> str | None:
    text = " ".join(str(odd.get(key) or "") for key in ("info", "name", "marketName"))
    match = re.search(r"(?<!\d)(\d+)\s*:\s*(\d+)(?!\d)", text)
    if not match:
        return None
    return f"{int(match.group(1))}:{int(match.group(2))}"


def _structured_selection(
    odd: dict,
    *,
    market: str,
    pick: str,
    p1: str | None,
    p2: str | None,
    line: float | None = None,
    player: str | None = None,
    set_no: int | None = None,
) -> dict | None:
    price = _float_token(odd.get("price"))
    if price is None or price < 1.0:
        return None
    raw_label = str(odd.get("info") or odd.get("name") or odd.get("marketName") or "").strip()
    row = _direct_selection(
        market=market,
        pick=pick,
        line=line,
        odds=price,
        raw_label=raw_label,
        player=player,
        set_no=set_no,
        source=EVENT_JSON_SOURCE,
    )
    row.update({
        "operator_market_id": odd.get("marketId"),
        "operator_outcome_id": odd.get("outcomeId"),
        "operator_selection_id": odd.get("uuid"),
        "operator_market_name": odd.get("marketName"),
        "operator_selection_name": odd.get("name"),
        "operator_selection_status": odd.get("status"),
        "operator_special_bet_value": odd.get("specialBetValue"),
        "operator_specifiers": (
            dict(odd.get("specifiers"))
            if isinstance(odd.get("specifiers"), dict)
            else {}
        ),
    })
    return row


def parse_event_payload(
    payload: object,
    *,
    event_id: str | None = None,
    url: str | None = None,
    title: str | None = None,
) -> dict:
    """Normalize active single-market selections from Superbet's public event JSON.

    Combination/BetBuilder rows are intentionally excluded. Prices are captured
    as operator metadata and never used as model inputs.
    """
    expected_event_id = event_id or _event_id_from_url(url)
    event = _event_record(payload, expected_event_id)
    if not event:
        return {
            "mode": "READ_ONLY_PUBLIC_SUPERBET_DIRECT_EVENT_JSON",
            "operator": "superbet.pl",
            "event_id": expected_event_id,
            "url": url,
            "canonical_selections": [],
            "canonical_selections_count": 0,
            "market_counts": {},
            "status": "EVENT_NOT_FOUND",
            "operator_prices_captured": False,
            "prices_used": False,
            "production_influence": False,
            "playable_influence": False,
            "player_dna_influence": False,
            "symphony_influence": False,
        }

    resolved_event_id = str(event.get("eventId") or expected_event_id or "") or None
    p1, p2 = _players_from_event(event, title)
    selections: list[dict] = []
    odds_seen = active_seen = combinations_skipped = unsupported_active = 0

    for odd in event.get("odds") or []:
        if not isinstance(odd, dict):
            continue
        odds_seen += 1
        if str(odd.get("status") or "").casefold() != "active":
            continue
        active_seen += 1
        market_name = str(odd.get("marketName") or "")
        market_norm = _norm(market_name)
        market_key = _market_key(market_name)
        info = str(odd.get("info") or "")
        name = str(odd.get("name") or "")
        combined = _norm(f"{market_name} {name} {info}")

        if int(odd.get("marketId") or 0) == COMBINATION_MARKET_ID or ";" in market_name:
            combinations_skipped += 1
            continue

        set_no = _set_no_from_odd(odd)
        player = _player_from_odd(odd, p1, p2)
        line = _line_from_odd(odd)
        pick_ou = _ou_pick(info, name, market_name)
        row = None

        if market_key == "zwyciezca" and player:
            row = _structured_selection(
                odd, market="match_winner", pick=player, p1=p1, p2=p2,
            )
        elif market_key == "x set zwyciezca" and set_no and player:
            row = _structured_selection(
                odd,
                market=f"set{set_no}_winner",
                pick=player,
                p1=p1,
                p2=p2,
                set_no=set_no,
            )
        elif market_key == "liczba gemow" and pick_ou and line is not None:
            row = _structured_selection(
                odd,
                market="match_total",
                pick=pick_ou,
                line=line,
                p1=p1,
                p2=p2,
            )
        elif market_key == "liczba setow" and pick_ou and line is not None:
            row = _structured_selection(
                odd,
                market="total_sets",
                pick=pick_ou,
                line=line,
                p1=p1,
                p2=p2,
            )
        elif "dokladny wynik" in market_norm:
            score = _score_from_odd(odd)
            if score:
                market = f"set{set_no}_exact_score" if set_no else "exact_match_score"
                row = _structured_selection(
                    odd,
                    market=market,
                    pick=score,
                    p1=p1,
                    p2=p2,
                    set_no=set_no,
                )
        elif (
            player
            and set_no
            and pick_ou
            and line is not None
            and "gemow" in combined
            and ("zdobedzie" in combined or "liczba gemow" in market_norm)
        ):
            row = _structured_selection(
                odd,
                market="player_total_games",
                pick=pick_ou,
                line=line,
                player=player,
                set_no=set_no,
                p1=p1,
                p2=p2,
            )
        elif set_no and pick_ou and line is not None and "gemow" in combined:
            row = _structured_selection(
                odd,
                market=f"set{set_no}_total",
                pick=pick_ou,
                line=line,
                set_no=set_no,
                p1=p1,
                p2=p2,
            )
        elif "handicap" in combined and "gem" in combined and player and line is not None:
            market = f"set{set_no}_game_handicap" if set_no else "match_game_handicap"
            row = _structured_selection(
                odd,
                market=market,
                pick=player,
                line=line,
                player=player,
                set_no=set_no,
                p1=p1,
                p2=p2,
            )

        if row is not None:
            selections.append(row)
        else:
            unsupported_active += 1

    dedup: dict[tuple, dict] = {}
    for row in selections:
        key = (
            row.get("market"),
            _norm(row.get("pick")),
            row.get("line"),
            _norm(row.get("player")),
            row.get("set_no"),
        )
        dedup.setdefault(key, row)
    selections = list(dedup.values())

    market_counts: dict[str, int] = {}
    for row in selections:
        market = str(row.get("market") or "unknown")
        market_counts[market] = market_counts.get(market, 0) + 1

    return {
        "mode": "READ_ONLY_PUBLIC_SUPERBET_DIRECT_EVENT_JSON",
        "operator": "superbet.pl",
        "source": "PUBLIC_EVENT_JSON",
        "event_id": resolved_event_id,
        "url": url,
        "p1": p1,
        "p2": p2,
        "start_time": event.get("utcDate"),
        "market_count_reported": event.get("marketCount"),
        "odds_rows_seen": odds_seen,
        "active_odds_rows_seen": active_seen,
        "combination_rows_skipped": combinations_skipped,
        "unsupported_active_rows": unsupported_active,
        "canonical_selections": selections,
        "canonical_selections_count": len(selections),
        "market_counts": dict(sorted(market_counts.items())),
        "operator_prices_captured": True,
        "prices_used": False,
        "production_influence": False,
        "playable_influence": False,
        "player_dna_influence": False,
        "symphony_influence": False,
        "status": "OK" if selections else "NO_SUPPORTED_ACTIVE_SELECTIONS",
    }


def capture_event_payload(driver, event_id: str) -> dict | None:
    """Capture the exact public event JSON already requested by the page."""
    try:
        entries = driver.get_log("performance")
    except Exception:
        return None
    expected_path = f"/v2/pl-PL/events/{event_id}"
    for entry in entries:
        try:
            envelope = json.loads(entry.get("message") or "{}")
            message = envelope.get("message") or {}
            if message.get("method") != "Network.responseReceived":
                continue
            params = message.get("params") or {}
            response = params.get("response") or {}
            parsed = urlparse(str(response.get("url") or ""))
            if parsed.netloc != EVENT_API_HOST or parsed.path != expected_path:
                continue
            if int(response.get("status") or 0) != 200:
                continue
            request_id = params.get("requestId")
            body = driver.execute_cdp_cmd(
                "Network.getResponseBody", {"requestId": request_id}
            )
            payload = json.loads(str((body or {}).get("body") or ""))
            return payload if isinstance(payload, dict) else None
        except Exception:
            continue
    return None


def browser_offer(url: str, timeout: int = 25) -> dict:
    """Fetch and normalize one explicitly selected public Superbet tennis match."""
    if not _allowed_url(url) or not re.fullmatch(r"/kursy/tenis/.+-\d+", urlparse(url).path):
        raise ValueError("browser offer requires one concrete public Superbet tennis match URL")
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:
        raise RuntimeError("browser offer requires selenium") from exc

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--lang=pl-PL")
    options.add_argument(f"--user-agent={USER_AGENT}")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(options=options)
    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)

        def offer_ready(drv):
            rendered_text = rendered_dom_text(drv)
            normalized = parse_visible_offer_text(rendered_text, url=url, title=drv.title)
            return int(normalized.get("canonical_selections_count") or 0) >= 4

        try:
            WebDriverWait(driver, timeout).until(offer_ready)
        except Exception:
            pass

        event_id = _event_id_from_url(url)
        payload = capture_event_payload(driver, str(event_id or ""))
        if payload is not None:
            result = parse_event_payload(
                payload, event_id=event_id, url=url, title=driver.title
            )
            result["transport"] = "BROWSER_CAPTURED_PUBLIC_XHR"
        else:
            rendered_text = rendered_dom_text(driver)
            result = parse_visible_offer_text(rendered_text, url=url, title=driver.title)
            result["source"] = "RENDERED_DOM_FALLBACK"
            result["transport"] = "BROWSER_RENDERED_DOM"
        result["final_url"] = driver.current_url
        result["title"] = driver.title
        result["status"] = (
            "OK"
            if int(result.get("canonical_selections_count") or 0) >= 4
            else "INSUFFICIENT_NORMALIZED_OFFER"
        )
        return result
    finally:
        driver.quit()

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
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

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

        event_id = _event_id_from_url(sample_url)
        payload = capture_event_payload(driver, str(event_id or ""))
        if payload is not None:
            normalized = parse_event_payload(
                payload, event_id=event_id, url=sample_url, title=driver.title
            )
            normalized_source = "PUBLIC_EVENT_JSON"
        else:
            rendered_text = rendered_dom_text(driver)
            normalized = parse_visible_offer_text(
                rendered_text, url=sample_url, title=driver.title
            )
            normalized_source = "RENDERED_DOM_FALLBACK"

        result["normalized_offer"] = {
            "source": normalized_source,
            "event_id": normalized.get("event_id"),
            "p1": normalized.get("p1"),
            "p2": normalized.get("p2"),
            "canonical_selections_count": normalized.get("canonical_selections_count"),
            "market_counts": normalized.get("market_counts"),
            "combination_rows_skipped": normalized.get("combination_rows_skipped"),
            "prices_used": normalized.get("prices_used"),
        }
        result["status"] = (
            "OK"
            if summary["has_operator_market_evidence"]
            and normalized_source == "PUBLIC_EVENT_JSON"
            and int(normalized.get("canonical_selections_count") or 0) >= 4
            and normalized.get("prices_used") is False
            else "INSUFFICIENT_MARKET_EVIDENCE"
        )
        return result
    finally:
        driver.quit()

def main() -> None:
    mode = str(sys.argv[1] if len(sys.argv) > 1 else "probe").strip().casefold()
    if mode == "probe":
        result = probe()
    elif mode == "probe-browser":
        result = browser_probe()
    elif mode == "offer-browser":
        if len(sys.argv) < 3:
            raise SystemExit("usage: superbet_direct.py offer-browser <superbet-match-url>")
        result = browser_offer(sys.argv[2])
    else:
        raise SystemExit("usage: superbet_direct.py [probe|probe-browser|offer-browser <url>]")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") != "OK":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
