from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime

import pandas as pd

from backend import model


def _stable(value):
    if isinstance(value, dict):
        return {str(k): _stable(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_stable(v) for v in value]
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return _stable(value.item())
        except (ValueError, TypeError):
            pass
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return round(value, 12)
    return value


def _history() -> pd.DataFrame:
    rows = []
    for i in range(14):
        alpha_wins = i % 2 == 0
        winner = "Alpha Player" if alpha_wins else "Beta Player"
        loser = "Beta Player" if alpha_wins else "Alpha Player"
        rows.append(
            {
                "tourney_date": f"20260{8 + (i // 10)}{10 + (i % 10):02d}",
                "tourney_name": "Equivalence Open",
                "surface": "Hard",
                "source_tour": "atp",
                "winner_name": winner,
                "loser_name": loser,
                "winner_rank": 20 + i,
                "loser_rank": 35 + i,
                "score": "6-4 4-6 6-3" if alpha_wins else "7-5 6-4",
                "w_svpt": 72 + i,
                "w_1stIn": 45 + (i % 4),
                "w_1stWon": 34 + (i % 3),
                "w_2ndWon": 15 + (i % 2),
                "w_SvGms": 11 + (i % 2),
                "w_bpSaved": 4 + (i % 2),
                "w_bpFaced": 6 + (i % 3),
                "l_svpt": 69 + i,
                "l_1stIn": 42 + (i % 5),
                "l_1stWon": 29 + (i % 4),
                "l_2ndWon": 13 + (i % 3),
                "l_SvGms": 10 + (i % 3),
                "l_bpSaved": 3 + (i % 2),
                "l_bpFaced": 7 + (i % 3),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    long_df = model.normalize_matches(_history())
    result = model.analyse_match(
        long_df,
        {
            "p1": "Alpha Player",
            "p2": "Beta Player",
            "surface": "hard",
            "scheduled_time": "2026-09-16T18:00:00Z",
            "best_of": 3,
        },
    )
    cols = [
        "date",
        "player",
        "opponent",
        "won",
        "hold_rate",
        "break_rate",
        "serve_points_won",
        "return_points_won",
        "first_set_won",
        "second_set_won",
        "third_set_won",
        "first_set_games",
    ]
    normalized = long_df[cols].sort_values(["date", "player", "opponent"], kind="stable").to_dict("records")
    payload = _stable({"normalized_history": normalized, "analysis": result})
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    print(hashlib.sha256(raw.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    main()
