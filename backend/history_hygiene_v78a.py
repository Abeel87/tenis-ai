from __future__ import annotations

import re
import pandas as pd

SET_RE = re.compile(r"(\d+)\s*[-:]\s*(\d+)")
VOID_RE = re.compile(r"\b(RET|W/O|WO|DEF|ABD|ABN|CANCELLED|CANCELED)\b", re.I)


def score_is_complete(score, best_of=None) -> bool:
    """Conservative completion check for historical singles results."""
    if not isinstance(score, str) or not score.strip():
        return False
    if VOID_RE.search(score):
        return False
    sets = [(int(a), int(b)) for a, b in SET_RE.findall(score)]
    if len(sets) < 2:
        return False
    p1_sets = sum(1 for a, b in sets if a > b)
    p2_sets = sum(1 for a, b in sets if b > a)
    try:
        need = 3 if int(float(best_of)) == 5 else 2
    except (TypeError, ValueError):
        need = 2
    return max(p1_sets, p2_sets) >= need


def clean_history(df: pd.DataFrame):
    """Remove retired/walkover/abandoned/partial rows before any model learns from them."""
    if df is None or df.empty:
        return df, {"raw_rows": 0, "kept_rows": 0, "removed_rows": 0}

    out = df.copy()
    if "score" not in out.columns:
        return out, {"raw_rows": int(len(out)), "kept_rows": int(len(out)), "removed_rows": 0}

    bo_col = next((c for c in ("best_of","best_of_sets") if c in out.columns), None)
    if bo_col:
        mask = out.apply(lambda r: score_is_complete(r.get("score"), r.get(bo_col)), axis=1)
    else:
        mask = out["score"].map(score_is_complete)
    cleaned = out[mask].copy()
    return cleaned, {
        "raw_rows": int(len(out)),
        "kept_rows": int(len(cleaned)),
        "removed_rows": int((~mask).sum()),
    }
