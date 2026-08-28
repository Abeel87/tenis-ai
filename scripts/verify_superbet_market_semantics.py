from __future__ import annotations

"""Fail closed when normalized Superbet market semantics drift.

This guard validates only the operator adapter contract. It does not inspect or
modify model probabilities, training, thresholds, SHADOW/PROD scores or prices.
"""

import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AVAILABILITY = ROOT / "frontend" / "data" / "superbet_market_availability_v91.json"

HANDICAP_MARKETS = {
    "match_game_handicap",
    "set1_game_handicap",
    "set2_game_handicap",
}
TOTAL_MARKETS = {
    "match_total",
    "set1_total",
    "set2_total",
    "set3_total",
    "total_sets",
    "player_total_games",
    "match_total_aces",
}
WINNER_MARKETS = {
    "match_winner",
    "set1_winner",
    "set2_winner",
    "set3_winner",
    "most_aces",
}


def _norm(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).casefold()
    return " ".join(text.split())


def _line(value):
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _close(a: float, b: float, eps: float = 1e-9) -> bool:
    return abs(float(a) - float(b)) <= eps


def validate_availability(report: dict) -> dict:
    assert isinstance(report, dict), "Superbet availability report must be an object"
    assert report.get("contains_prices") is False, "Superbet adapter must not persist prices"
    assert report.get("prices_used") is False, "Superbet adapter must not use prices"

    fixtures = report.get("fixtures") or []
    assert isinstance(fixtures, list), "Superbet fixtures must be a list"

    handicap_pairs = 0
    total_pairs = 0
    winner_pairs = 0
    selections_seen = 0

    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        p1 = str(fixture.get("p1") or "")
        p2 = str(fixture.get("p2") or "")
        p1_key, p2_key = _norm(p1), _norm(p2)

        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for selection in fixture.get("canonical_selections") or []:
            if not isinstance(selection, dict):
                continue
            selections_seen += 1
            market = str(selection.get("market") or "")
            market_id = str(selection.get("market_id") or "")
            grouped[(market, market_id)].append(selection)

            if market in WINNER_MARKETS:
                pick = _norm(selection.get("pick"))
                assert pick not in {"1", "2", "x"}, (
                    f"literal bookmaker outcome leaked into {market}: {selection.get('pick')!r}"
                )

        for (market, market_id), rows in grouped.items():
            if market in HANDICAP_MARKETS:
                by_pick = {_norm(row.get("pick")): row for row in rows if row.get("pick")}
                p1_row = by_pick.get(p1_key)
                p2_row = by_pick.get(p2_key)
                if not p1_row or not p2_row:
                    continue
                p1_line = _line(p1_row.get("line"))
                p2_line = _line(p2_row.get("line"))
                assert p1_line is not None and p2_line is not None, (
                    f"missing handicap line for {p1} vs {p2}, {market_id}"
                )
                assert _close(p1_line, -p2_line), (
                    f"handicap perspective mismatch for {p1} vs {p2}, {market} {market_id}: "
                    f"p1={p1_line:g}, p2={p2_line:g}"
                )
                handicap_pairs += 1

            elif market in TOTAL_MARKETS:
                by_side = {_norm(row.get("pick")): row for row in rows if row.get("pick")}
                over = by_side.get("over")
                under = by_side.get("under")
                if not over or not under:
                    continue
                over_line = _line(over.get("line"))
                under_line = _line(under.get("line"))
                assert over_line is not None and under_line is not None, (
                    f"missing total line for {market} {market_id}"
                )
                assert _close(over_line, under_line), (
                    f"O/U threshold mismatch for {market} {market_id}: "
                    f"over={over_line:g}, under={under_line:g}"
                )
                total_pairs += 1

        winner_rows = [
            row
            for (market, _market_id), rows in grouped.items()
            if market == "match_winner"
            for row in rows
        ]
        if winner_rows:
            picks = {_norm(row.get("pick")) for row in winner_rows if row.get("pick")}
            expected = {key for key in (p1_key, p2_key) if key}
            assert expected.issubset(picks), (
                f"match winner mapping incomplete for {p1} vs {p2}: picks={sorted(picks)}"
            )
            winner_pairs += 1

    return {
        "fixtures": len(fixtures),
        "selections": selections_seen,
        "handicap_pairs_checked": handicap_pairs,
        "total_pairs_checked": total_pairs,
        "winner_fixtures_checked": winner_pairs,
        "prices_used": False,
    }


def main() -> None:
    report = json.loads(AVAILABILITY.read_text(encoding="utf-8"))
    summary = validate_availability(report)
    print("SUPERBET_MARKET_SEMANTICS_OK " + json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
