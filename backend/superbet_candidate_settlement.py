from __future__ import annotations

"""Tenis AI v9.2.5 — settlement shadow for newly mapped Superbet families.

This layer freezes only operator-verified, model-derived selections. It is
strictly non-PLAYABLE: rows are collected for settlement/backtest evidence and
promotion readiness, but never change existing model maths, thresholds, training
or PLAYABLE accuracy.
"""

import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone

VERSION = "v9.2.5"
LAYER = "superbet_candidate_signals_v925"
TRACK_MIN_SCORE = 55.0
PROMOTION_SCORE_THRESHOLD = 68.0
PROMOTION_MIN_SETTLED = 40
PROMOTION_MIN_ACCURACY = 62.0
PROMOTION_MIN_WILSON = 0.50
PROMOTION_MAX_BRIER = 0.24

SETTLEMENT_SUPPORTED_MARKETS = {
    "any_set_to_nil",
    "set2_exact_score",
    "exact_sets",
    "match_games_parity",
    "set1_games_parity",
    "set2_games_parity",
    "p1_exactly_1_set",
    "p1_exactly_2_sets",
    "p2_exactly_1_set",
    "p2_exactly_2_sets",
    "p1_wins_a_set",
    "p2_wins_a_set",
    "set_handicap",
    "match_game_handicap",
    "set1_game_handicap",
    "set2_game_handicap",
    "set2_winner",
    "set3_winner",
    "set2_total",
    "set3_total",
    "player_total_games",
}
PBP_ONLY_MARKETS = {"set2_game_state"}
ACTIONABLE_EVIDENCE_MARKETS = {
    "match_game_handicap",
    "set1_game_handicap",
    "set2_game_handicap",
    "set2_winner",
    "set3_winner",
    "set2_total",
    "set3_total",
    "player_total_games",
}


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _key(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _match_key(row: dict) -> str:
    mid = row.get("match_id") if row.get("match_id") is not None else row.get("id")
    if mid is not None and str(mid) != "":
        return f"id:{mid}"
    return "|".join([
        _key(row.get("p1")),
        _key(row.get("p2")),
        str(row.get("scheduled_time") or "")[:10],
        _key(row.get("tournament")),
    ])


def _signature(row: dict) -> tuple:
    line = _num(row.get("line"))
    checkpoint = int(_num(row.get("checkpoint"), 0) or 0)
    return (
        str(row.get("market") or ""),
        _key(row.get("pick")),
        round(line, 6) if line is not None else None,
        checkpoint,
        _key(row.get("player")),
    )


def _candidate_signal(row: dict, now: datetime, source_model: str) -> dict:
    score = _num(row.get("score"))
    out = {
        "id": str(row.get("key") or "|".join(map(str, _signature(row)))),
        "key": row.get("key"),
        "label": row.get("label"),
        "market": str(row.get("market") or ""),
        "pick": row.get("pick"),
        "line": row.get("line"),
        "checkpoint": row.get("checkpoint"),
        "player": row.get("player"),
        "score": round(float(score), 1) if score is not None else None,
        "result": "pending",
        "source_model": source_model,
        "operator": "superbet.pl",
        "operator_available": True,
        "operator_line_verified": True,
        "operator_playable": False,
        "candidate_for_playable": True,
        "candidate_version": VERSION,
        "captured_at": now.isoformat(),
        "coverage_status": row.get("coverage_status") or "MODEL_DERIVED_SETTLEMENT_EVIDENCE",
    }
    return {k: v for k, v in out.items() if v is not None}


def capture_candidates(history: list[dict], results: list[dict], now: datetime | None = None):
    """Freeze operator-verified evidence rows before result settlement.

    Existing snapshots are immutable; a later operator refresh must not rewrite a
    forecast that was already captured for a match. Existing display/shadow rows
    plus selected exact operator-line model rows are tracked in this shadow layer
    only; production PLAYABLE remains untouched.
    """
    now = now or datetime.now(timezone.utc)
    index = {_match_key(m): m for m in results or [] if isinstance(m, dict)}
    out = []
    captured = 0
    excluded_pbp = 0

    for raw in history or []:
        if not isinstance(raw, dict):
            continue
        entry = dict(raw)
        if entry.get("status") not in ("pending", "upcoming") or entry.get(LAYER):
            out.append(entry)
            continue
        match = index.get(_match_key(entry))
        ctx = (match or {}).get("superbet_market_v91") or {}
        if not (
            isinstance(ctx, dict)
            and ctx.get("operator_verified") is True
            and ctx.get("status") == "VERIFIED"
        ):
            out.append(entry)
            continue

        rows = []
        seen = set()
        sources = (
            (ctx.get("coverage_shadow_signals") or [], "superbet_v924_display_shadow"),
            (ctx.get("model_signals") or [], "superbet_operator_line_model"),
        )
        for source_rows, source_model in sources:
            for signal in source_rows:
                if not isinstance(signal, dict):
                    continue
                market = str(signal.get("market") or "")
                if market in PBP_ONLY_MARKETS:
                    excluded_pbp += 1
                    continue
                if market not in SETTLEMENT_SUPPORTED_MARKETS:
                    continue
                if source_model == "superbet_operator_line_model" and market not in ACTIONABLE_EVIDENCE_MARKETS:
                    continue
                if source_model == "superbet_operator_line_model" and signal.get("operator_line_verified") is not True:
                    continue
                score = _num(signal.get("score"))
                if score is None or score < TRACK_MIN_SCORE:
                    continue
                sig = _signature(signal)
                if sig in seen:
                    continue
                seen.add(sig)
                rows.append(_candidate_signal(signal, now, source_model))

        if rows:
            entry[LAYER] = rows
            entry["superbet_candidate_captured_at_v925"] = now.isoformat()
            captured += len(rows)
        out.append(entry)

    return out, {
        "version": VERSION,
        "captured": captured,
        "pbp_only_excluded": excluded_pbp,
        "track_min_score": TRACK_MIN_SCORE,
        "operator_playable_changed": False,
    }


def _wilson_lower(hits: int, n: int, z: float = 1.96) -> float | None:
    if n <= 0:
        return None
    p = hits / n
    denom = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    margin = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)
    return max(0.0, (centre - margin) / denom)


def _brier(rows: list[dict]) -> float | None:
    scored = [r for r in rows if _num(r.get("score")) is not None and r.get("result") in {"hit", "miss"}]
    if not scored:
        return None
    return sum(
        ((_num(r.get("score")) / 100.0) - (1.0 if r.get("result") == "hit" else 0.0)) ** 2
        for r in scored
    ) / len(scored)


def _summary(rows: list[dict]) -> dict:
    settled = [r for r in rows if r.get("result") in {"hit", "miss"}]
    hits = sum(1 for r in settled if r.get("result") == "hit")
    tracking_brier = _brier(settled)

    promoted_sample = [
        r for r in settled
        if _num(r.get("score"), -1.0) >= PROMOTION_SCORE_THRESHOLD
    ]
    promotion_brier = _brier(promoted_sample)
    phits = sum(1 for r in promoted_sample if r.get("result") == "hit")
    pacc = 100.0 * phits / len(promoted_sample) if promoted_sample else None
    wilson = _wilson_lower(phits, len(promoted_sample))
    ready = bool(
        len(promoted_sample) >= PROMOTION_MIN_SETTLED
        and pacc is not None and pacc >= PROMOTION_MIN_ACCURACY
        and wilson is not None and wilson >= PROMOTION_MIN_WILSON
        and promotion_brier is not None and promotion_brier <= PROMOTION_MAX_BRIER
    )
    status = "REVIEW_READY" if ready else (
        "COLLECTING_SAMPLE" if len(promoted_sample) < PROMOTION_MIN_SETTLED else "HOLD"
    )
    return {
        "captured": len(rows),
        "pending": sum(1 for r in rows if r.get("result") == "pending"),
        "settled": len(settled),
        "hits": hits,
        "misses": len(settled) - hits,
        "void": sum(1 for r in rows if r.get("result") == "void"),
        "unverifiable": sum(1 for r in rows if r.get("result") == "unverifiable"),
        "accuracy": round(100.0 * hits / len(settled), 1) if settled else None,
        "brier": round(tracking_brier, 4) if tracking_brier is not None else None,
        "promotion_sample": len(promoted_sample),
        "promotion_hits": phits,
        "promotion_accuracy": round(pacc, 1) if pacc is not None else None,
        "promotion_brier": round(promotion_brier, 4) if promotion_brier is not None else None,
        "promotion_wilson_lower_95": round(wilson, 4) if wilson is not None else None,
        "promotion_status": status,
        "review_ready": ready,
    }


def build_candidate_stats(history: list[dict]) -> dict:
    all_rows = []
    by_market_rows: dict[str, list[dict]] = defaultdict(list)
    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        for row in entry.get(LAYER) or []:
            if not isinstance(row, dict):
                continue
            all_rows.append(row)
            by_market_rows[str(row.get("market") or "unknown")].append(row)

    by_market = {market: _summary(rows) for market, rows in sorted(by_market_rows.items())}
    ready = sorted(market for market, report in by_market.items() if report.get("review_ready"))
    return {
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layer": LAYER,
        "mode": "SETTLEMENT_SHADOW_ONLY",
        "overall": _summary(all_rows),
        "by_market": by_market,
        "review_ready_markets": ready,
        "promotion_gate": {
            "score_threshold": PROMOTION_SCORE_THRESHOLD,
            "min_settled": PROMOTION_MIN_SETTLED,
            "min_accuracy": PROMOTION_MIN_ACCURACY,
            "min_wilson_lower_95": PROMOTION_MIN_WILSON,
            "max_brier": PROMOTION_MAX_BRIER,
            "brier_population": "PROMOTION_SAMPLE_ONLY",
            "auto_promote": False,
        },
        "settlement_supported_markets": sorted(SETTLEMENT_SUPPORTED_MARKETS),
        "pbp_only_markets": sorted(PBP_ONLY_MARKETS),
        "contract": {
            "operator_verified_snapshots_only": True,
            "prices_used": False,
            "playable_accuracy_unchanged": True,
            "production_influence": False,
            "promotion_requires_review_after_gate": True,
        },
    }
