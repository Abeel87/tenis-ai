from __future__ import annotations

import json
import math
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "tennis.db"
RESULTS_PATH = ROOT / "frontend" / "data" / "results.json"
META_PATH = ROOT / "frontend" / "data" / "meta.json"
WINDOWS = (5, 10, 20)


def _key(value: Any) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _to_dt(value):
    d = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(d) else d


def _binary_metric(series: pd.Series) -> dict:
    x = pd.to_numeric(series, errors="coerce").dropna()
    if x.empty:
        return {"hits": 0, "n": 0, "pct": None}
    # all source binary columns are 0/1; strict >0.5 protects against float serialization noise
    hits = int((x > 0.5).sum())
    n = int(len(x))
    return {"hits": hits, "n": n, "pct": round(100.0 * hits / n, 1)}


def _binary_from_condition(series: pd.Series, fn) -> dict:
    x = pd.to_numeric(series, errors="coerce").dropna()
    if x.empty:
        return {"hits": 0, "n": 0, "pct": None}
    vals = x.map(fn)
    hits = int(vals.sum())
    n = int(len(vals))
    return {"hits": hits, "n": n, "pct": round(100.0 * hits / n, 1)}


def _avg_metric(series: pd.Series, scale=1.0, digits=1):
    x = pd.to_numeric(series, errors="coerce").dropna()
    if x.empty:
        return None
    return round(float(x.mean()) * scale, digits)


def _window(rows: pd.DataFrame, n: int) -> dict:
    x = rows.head(n).copy()
    metrics = {}
    if "won" in x:
        metrics["match_win"] = _binary_metric(x["won"])
    if "first_set_won" in x:
        metrics["set1_win"] = _binary_metric(x["first_set_won"])
    if "second_set_won" in x:
        metrics["set2_win"] = _binary_metric(x["second_set_won"])
    if "second_after_first_win" in x:
        metrics["closeout_after_set1_win"] = _binary_metric(x["second_after_first_win"])
    if "second_after_first_loss" in x:
        metrics["comeback_set2_after_set1_loss"] = _binary_metric(x["second_after_first_loss"])
    if "third_set_won" in x:
        metrics["deciding_set_win"] = _binary_metric(x["third_set_won"])
    for line, col in (
        ("8.5", "first_set_over85"),
        ("9.5", "first_set_over95"),
        ("10.5", "first_set_over105"),
        ("11.5", "first_set_over115"),
        ("12.5", "first_set_over125"),
    ):
        if col in x:
            metrics[f"set1_over_{line}"] = _binary_metric(x[col])
    if "sets_played" in x:
        metrics["match_2_sets"] = _binary_from_condition(x["sets_played"], lambda v: int(round(v)) == 2)
        metrics["match_3_sets"] = _binary_from_condition(x["sets_played"], lambda v: int(round(v)) == 3)

    averages = {}
    if "hold_rate" in x:
        averages["hold_rate"] = _avg_metric(x["hold_rate"], 100.0)
    if "break_rate" in x:
        averages["break_rate"] = _avg_metric(x["break_rate"], 100.0)
    if "serve_points_won" in x:
        averages["serve_points_won"] = _avg_metric(x["serve_points_won"], 100.0)
    if "return_points_won" in x:
        averages["return_points_won"] = _avg_metric(x["return_points_won"], 100.0)
    if "first_serve_won" in x:
        averages["first_serve_won"] = _avg_metric(x["first_serve_won"], 100.0)
    if "second_serve_won" in x:
        averages["second_serve_won"] = _avg_metric(x["second_serve_won"], 100.0)
    if "first_set_games" in x:
        averages["first_set_games"] = _avg_metric(x["first_set_games"], 1.0)

    return {
        "requested": n,
        "sample_matches": int(len(x)),
        "metrics": metrics,
        "averages": averages,
    }


def _trend_pack(rows: pd.DataFrame) -> dict:
    # latest 5 minus previous 5, in percentage points; descriptive only
    if rows is None or rows.empty:
        return {}
    a=rows.head(5)
    b=rows.iloc[5:10]
    if len(a)<3 or len(b)<3:
        return {}
    out={}
    for col in (
        "won","first_set_won","second_set_won","hold_rate","break_rate",
        "serve_points_won","return_points_won","first_serve_won","second_serve_won"
    ):
        if col not in rows.columns:
            continue
        x=pd.to_numeric(a[col],errors="coerce").dropna()
        y=pd.to_numeric(b[col],errors="coerce").dropna()
        if len(x)<2 or len(y)<2:
            continue
        out[col]=round(100.0*(float(x.mean())-float(y.mean())),1)
    aliases={"won":"match_win","first_set_won":"set1_win","second_set_won":"set2_win"}
    for src,dst in aliases.items():
        if src in out:
            out[dst]=out[src]
    return out


def build_player_tendencies(long_df: pd.DataFrame, player: str, surface: str = "", as_of=None) -> dict:
    if long_df is None or long_df.empty:
        return {"player": player, "available": False, "all": {}, "surface": {}}

    k = _key(player)
    if "player_key" in long_df.columns:
        x = long_df[long_df["player_key"].astype(str) == k].copy()
    else:
        x = long_df[long_df["player"].map(_key) == k].copy()

    cut = _to_dt(as_of)
    if "date" in x.columns:
        x["date"] = pd.to_datetime(x["date"], utc=True, errors="coerce")
        if cut is not None:
            # Source history has day precision, so same-day completed matches may legitimately be included.
            x = x[x["date"].isna() | (x["date"].dt.date <= cut.date())]
        x = x.sort_values("date", ascending=False, na_position="last")
    else:
        x = x.iloc[::-1]

    # Dedup defensive layer: player/opponent/date.
    dedupe_cols = [c for c in ("date", "player_key", "opponent_key") if c in x.columns]
    if dedupe_cols:
        x = x.drop_duplicates(subset=dedupe_cols, keep="first")

    surf = str(surface or "").strip().lower()
    sx = x[x["surface"].astype(str).str.lower() == surf].copy() if surf and "surface" in x.columns else x.iloc[0:0].copy()

    return {
        "player": player,
        "available": bool(len(x)),
        "source": "historical match results",
        "surface_name": surf,
        "all": {str(n): _window(x, n) for n in WINDOWS},
        "surface": {str(n): _window(sx, n) for n in WINDOWS},
        "trend": {
            "all": _trend_pack(x),
            "surface": _trend_pack(sx),
        },
    }


def enrich_results(db_path: Path = DB_PATH, results_path: Path = RESULTS_PATH, meta_path: Path = META_PATH) -> dict:
    results = _read_json(results_path, [])
    if not isinstance(results, list) or not results:
        return {"matches": 0, "profiles": 0, "status": "no_results"}
    if not db_path.exists():
        return {"matches": len(results), "profiles": 0, "status": "no_sqlite"}

    with sqlite3.connect(db_path) as con:
        long_df = pd.read_sql_query("select * from player_matches", con)

    cache = {}
    for m in results:
        surface = str(m.get("surface") or "").lower()
        as_of = m.get("scheduled_time")
        sides = {}
        for side in ("p1", "p2"):
            player = m.get(side)
            ck = (_key(player), surface, str(as_of)[:10])
            if ck not in cache:
                cache[ck] = build_player_tendencies(long_df, player, surface, as_of)
            sides[side] = cache[ck]
        m["tendencies_v71"] = {
            "version": "v7.1",
            "surface": surface,
            **sides,
        }

    _write_json(results_path, results)
    meta = _read_json(meta_path, {})
    if not isinstance(meta, dict):
        meta = {}
    meta.update(
        {
            "tendencies_v71_updated_at": datetime.now(timezone.utc).isoformat(),
            "tendencies_v71_profiles": len(cache),
            "tendencies_v71_matches": len(results),
        }
    )
    _write_json(meta_path, meta)
    return {"matches": len(results), "profiles": len(cache), "status": "ok"}


def main():
    print(json.dumps(enrich_results(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
