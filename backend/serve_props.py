from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from history_hygiene_v78a import clean_history

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
OUT = ROOT / "frontend" / "data"
RESULTS_PATH = OUT / "results.json"
META_PATH = OUT / "meta.json"

WINDOWS = (5, 10, 20)
ACE_LINES = (1.5, 2.5, 3.5, 4.5, 5.5, 7.5, 9.5, 11.5)
DF_LINES = (0.5, 1.5, 2.5, 3.5, 4.5, 5.5)
MIN_MODEL_MATCHES = 5


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


def _num(x):
    try:
        y = float(x)
        return y if math.isfinite(y) else None
    except (TypeError, ValueError):
        return None


def _parse_date(value):
    try:
        s = str(value or "").strip()
        if re.fullmatch(r"\d+(\.0+)?", s):
            s = str(int(float(s)))
        d = pd.to_datetime(s, format="%Y%m%d", errors="coerce")
        return None if pd.isna(d) else pd.Timestamp(d)
    except Exception:
        return None


def _parse_as_of(value):
    d = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(d) else d


def _match_games(score) -> float | None:
    if not isinstance(score, str):
        return None
    pairs = [(int(a), int(b)) for a, b in re.findall(r"(\d+)\s*[-:]\s*(\d+)", score)]
    if not pairs:
        return None
    return float(sum(a + b for a, b in pairs))


def _weighted_mean(values, weights):
    rows = [(float(v), float(w)) for v, w in zip(values, weights) if v is not None and math.isfinite(float(v)) and w > 0]
    if not rows:
        return None, 0
    z = sum(w for _, w in rows)
    return (sum(v * w for v, w in rows) / z if z else None), len(rows)


def _shrink(raw, prior, n, strength=3.0):
    if raw is None:
        return prior
    if prior is None:
        return raw
    n = max(0, int(n or 0))
    return (raw * n + prior * strength) / (n + strength)


def _colmap(df: pd.DataFrame):
    return {str(c).lower(): c for c in df.columns}


def _get(row, cm, *names):
    for n in names:
        c = cm.get(n.lower())
        if c is not None:
            return row.get(c)
    return None


def load_raw_history(cache_dir: Path = CACHE) -> pd.DataFrame:
    frames = []
    for p in sorted(cache_dir.glob("*.csv.gz")):
        # pbp cache is a directory; only raw TennisMyLife gz CSV files match here.
        try:
            d = pd.read_csv(p, compression="gzip", low_memory=False)
            if not d.empty:
                d = d.copy()
                d["_source_file"] = p.name
                frames.append(d)
        except Exception:
            continue
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def normalize_serve_props(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    cm = _colmap(raw)
    out = []
    for _, r in raw.iterrows():
        winner = _get(r, cm, "winner_name")
        loser = _get(r, cm, "loser_name")
        if not isinstance(winner, str) or not isinstance(loser, str):
            continue
        date = _parse_date(_get(r, cm, "tourney_date"))
        surface = str(_get(r, cm, "surface") or "").strip().lower()
        games = _match_games(str(_get(r, cm, "score") or ""))

        for side, opp, name, opp_name in (
            ("w", "l", winner, loser),
            ("l", "w", loser, winner),
        ):
            ace = _num(_get(r, cm, f"{side}_ace", f"{side}_aces"))
            df = _num(_get(r, cm, f"{side}_df", f"{side}_double_faults"))
            sv_gms = _num(_get(r, cm, f"{side}_SvGms", f"{side}_svgms", f"{side}_service_games"))
            opp_ace = _num(_get(r, cm, f"{opp}_ace", f"{opp}_aces"))
            opp_sv_gms = _num(_get(r, cm, f"{opp}_SvGms", f"{opp}_svgms", f"{opp}_service_games"))

            out.append(
                {
                    "date": date,
                    "surface": surface,
                    "player": str(name).strip(),
                    "player_key": _key(name),
                    "opponent": str(opp_name).strip(),
                    "opponent_key": _key(opp_name),
                    "aces": ace,
                    "double_faults": df,
                    "service_games": sv_gms,
                    "match_games": games,
                    "ace_per_service_game": (ace / sv_gms) if ace is not None and sv_gms and sv_gms > 0 else None,
                    "df_per_service_game": (df / sv_gms) if df is not None and sv_gms and sv_gms > 0 else None,
                    # Opponent served these aces against this player's return.
                    "aces_allowed_per_return_game": (opp_ace / opp_sv_gms) if opp_ace is not None and opp_sv_gms and opp_sv_gms > 0 else None,
                }
            )
    x = pd.DataFrame(out)
    if x.empty:
        return x
    x = x.drop_duplicates(subset=["date", "player_key", "opponent_key", "aces", "double_faults"], keep="first")
    return x


def _prior(df: pd.DataFrame, surface: str, col: str):
    if df.empty or col not in df.columns:
        return None
    x = df
    if surface and "surface" in x.columns:
        sx = x[x["surface"] == surface]
        if sx[col].notna().sum() >= 80:
            x = sx
    v = pd.to_numeric(x[col], errors="coerce").dropna()
    return float(v.mean()) if not v.empty else None


def _player_rows(df: pd.DataFrame, player: str, as_of, limit=20):
    if df.empty:
        return df
    x = df[df["player_key"] == _key(player)].copy()
    cut = _parse_as_of(as_of)
    if cut is not None and "date" in x.columns:
        # Raw archives have day precision only. Exclude the current day to avoid leaking
        # a same-day result that may have happened after the scheduled target match.
        x = x[x["date"].isna() | (x["date"].dt.date < cut.date())]
    return x.sort_values("date", ascending=False, na_position="last").head(limit)


def _profile(df: pd.DataFrame, player: str, surface: str, as_of) -> dict:
    x = _player_rows(df, player, as_of, 20)
    if x.empty:
        return {"player": player, "matches": 0, "ready_aces": False, "ready_df": False}

    weights = []
    for i, (_, r) in enumerate(x.iterrows()):
        w = 0.91 ** i
        if surface:
            w *= 1.45 if str(r.get("surface") or "") == surface else 0.78
        weights.append(w)

    metrics = {}
    for col in ("ace_per_service_game", "df_per_service_game", "aces_allowed_per_return_game", "aces", "double_faults", "match_games"):
        raw, n = _weighted_mean(x[col].tolist(), weights)
        prior = _prior(df, surface, col)
        metrics[col] = _shrink(raw, prior, n, 3.0)
        metrics[f"{col}_n"] = n

    ace_n = int(pd.to_numeric(x["aces"], errors="coerce").notna().sum())
    df_n = int(pd.to_numeric(x["double_faults"], errors="coerce").notna().sum())
    allow_n = int(pd.to_numeric(x["aces_allowed_per_return_game"], errors="coerce").notna().sum())

    return {
        "player": player,
        "matches": int(len(x)),
        "surface_matches": int((x["surface"] == surface).sum()) if surface else int(len(x)),
        "ready_aces": ace_n >= MIN_MODEL_MATCHES,
        "ready_df": df_n >= MIN_MODEL_MATCHES,
        "ace_matches": ace_n,
        "df_matches": df_n,
        "allow_matches": allow_n,
        **metrics,
    }


def _event_metric(values, line):
    x = pd.to_numeric(values, errors="coerce").dropna()
    if x.empty:
        return {"hits": 0, "n": 0, "pct": None}
    hits = int((x > float(line)).sum())
    n = int(len(x))
    return {"hits": hits, "n": n, "pct": round(100 * hits / n, 1)}


def _window(x: pd.DataFrame, n: int):
    y = x.head(n)
    aces = pd.to_numeric(y["aces"], errors="coerce").dropna()
    dfs = pd.to_numeric(y["double_faults"], errors="coerce").dropna()
    return {
        "requested": n,
        "sample_matches": int(len(y)),
        "aces": {
            "avg": round(float(aces.mean()), 2) if not aces.empty else None,
            "sample": int(len(aces)),
            "over": {str(line): _event_metric(y["aces"], line) for line in ACE_LINES},
        },
        "double_faults": {
            "avg": round(float(dfs.mean()), 2) if not dfs.empty else None,
            "sample": int(len(dfs)),
            "over": {str(line): _event_metric(y["double_faults"], line) for line in DF_LINES},
        },
    }


def _history_windows(df: pd.DataFrame, player: str, surface: str, as_of):
    x = _player_rows(df, player, as_of, 20)
    sx = x[x["surface"] == surface].copy() if surface else x.iloc[0:0].copy()
    return {
        "surface_name": surface,
        "all": {str(n): _window(x, n) for n in WINDOWS},
        "surface": {str(n): _window(sx, n) for n in WINDOWS},
    }


def poisson_over(mean: float, line: float) -> float | None:
    if mean is None or mean < 0:
        return None
    threshold = math.floor(float(line)) + 1  # Over 3.5 -> count >= 4
    term = math.exp(-mean)
    cdf = term
    for k in range(1, threshold):
        term *= mean / k
        cdf += term
    return max(0.0, min(1.0, 1.0 - cdf))


def _default_lines(mean: float, kind: str):
    if mean is None:
        return []
    center = max(0.5, math.floor(mean) - 0.5)
    vals = sorted({max(0.5, center - 1.0), center, center + 1.0, center + 2.0})
    cap = 15.5 if kind == "aces" else 8.5
    return [v for v in vals if v <= cap]


def _market(mean: float | None, ready: bool, sample: int, kind: str):
    if not ready or mean is None:
        return {"ready": False, "mean": None, "sample": sample, "lines": {}}
    lines = {}
    for line in _default_lines(mean, kind):
        p = poisson_over(mean, line)
        if p is None:
            continue
        lines[str(line)] = {
            "over": round(100 * p, 1),
            "under": round(100 * (1 - p), 1),
            "fair_over": round(1 / p, 2) if p > 0.001 else None,
            "fair_under": round(1 / (1 - p), 2) if (1 - p) > 0.001 else None,
        }
    return {
        "ready": True,
        "mean": round(mean, 2),
        "sample": sample,
        "suggested_line": max(0.5, math.floor(mean) - 0.5),
        "lines": lines,
    }


def _expected_service_games(match: dict, p1: dict, p2: dict) -> float:
    g = _num(match.get("expected_match_games"))
    if g is None:
        hist = [p1.get("match_games"), p2.get("match_games")]
        hist = [v for v in hist if v is not None]
        g = sum(hist) / len(hist) if hist else 22.0
    return max(7.0, min(18.0, float(g) / 2.0))


def _side_model(match: dict, own: dict, opp: dict, own_side: str, df_return_pressure: float | None):
    service_games = _expected_service_games(match, own, opp)

    own_ace_rate = own.get("ace_per_service_game")
    opp_allow = opp.get("aces_allowed_per_return_game")
    if own_ace_rate is None and own.get("aces") is not None and own.get("match_games"):
        own_ace_rate = own["aces"] / max(1.0, own["match_games"] / 2.0)
    if opp_allow is None:
        opp_allow = own_ace_rate

    ace_rate = None
    if own_ace_rate is not None:
        ace_rate = 0.72 * own_ace_rate + 0.28 * (opp_allow if opp_allow is not None else own_ace_rate)
    ace_mean = max(0.05, min(20.0, service_games * ace_rate)) if ace_rate is not None else None

    df_rate = own.get("df_per_service_game")
    if df_rate is None and own.get("double_faults") is not None and own.get("match_games"):
        df_rate = own["double_faults"] / max(1.0, own["match_games"] / 2.0)
    pressure = 1.0
    if df_return_pressure is not None:
        # Strong return can push a server a little harder on second serve; keep the effect small.
        pressure = max(0.90, min(1.10, 1.0 + (float(df_return_pressure) - 0.40) * 0.8))
    df_mean = max(0.02, min(10.0, service_games * df_rate * pressure)) if df_rate is not None else None

    quality = "HIGH" if own.get("ace_matches", 0) >= 10 and own.get("df_matches", 0) >= 10 and opp.get("allow_matches", 0) >= 8 else (
        "MEDIUM" if own.get("ace_matches", 0) >= 5 and own.get("df_matches", 0) >= 5 else "LOW"
    )

    return {
        "quality": quality,
        "estimated_service_games": round(service_games, 1),
        "aces": _market(ace_mean, bool(own.get("ready_aces")), int(own.get("ace_matches") or 0), "aces"),
        "double_faults": _market(df_mean, bool(own.get("ready_df")), int(own.get("df_matches") or 0), "df"),
    }


def enrich(results_path: Path = RESULTS_PATH, meta_path: Path = META_PATH):
    results = _read_json(results_path, [])
    if not isinstance(results, list) or not results:
        return {"status": "no_results"}

    raw = load_raw_history()
    raw,hygiene = clean_history(raw)
    hist = normalize_serve_props(raw)
    if hist.empty:
        for m in results:
            m["serve_props_v72"] = {"version": "v7.2", "ready": False, "reason": "ace_df_columns_unavailable"}
        _write_json(results_path, results)
        return {"status": "no_ace_df_data", "matches": len(results)}

    profile_cache = {}
    for m in results:
        try:
            best_of=5 if int(m.get("best_of") or 3)==5 else 3
        except (TypeError,ValueError):
            best_of=3
        if best_of==5:
            m["serve_props_v72"]={
                "version":"v7.8A-serve-props-hygiene",
                "ready":False,
                "reason":"bo5_full_match_not_supported",
                "format":"BO5 · N/D until dedicated engine",
            }
            continue
        surface = str(m.get("surface") or "").strip().lower()
        as_of = m.get("scheduled_time")
        pp = {}
        for side in ("p1", "p2"):
            name = m.get(side)
            ck = (_key(name), surface, str(as_of)[:10])
            if ck not in profile_cache:
                profile_cache[ck] = _profile(hist, name, surface, as_of)
            pp[side] = profile_cache[ck]

        p1_return = _num((m.get("p1_stats") or {}).get("return_points_won"))
        p2_return = _num((m.get("p2_stats") or {}).get("return_points_won"))
        side1 = _side_model(m, pp["p1"], pp["p2"], "p1", p2_return)
        side2 = _side_model(m, pp["p2"], pp["p1"], "p2", p1_return)

        side1["history"] = _history_windows(hist, m.get("p1"), surface, as_of)
        side2["history"] = _history_windows(hist, m.get("p2"), surface, as_of)

        m["serve_props_v72"] = {
            "version": "v7.2-serve-props",
            "ready": bool(side1["aces"]["ready"] or side1["double_faults"]["ready"] or side2["aces"]["ready"] or side2["double_faults"]["ready"]),
            "format": "BO3 estimate",
            "p1": side1,
            "p2": side2,
        }

    _write_json(results_path, results)
    meta = _read_json(meta_path, {})
    if not isinstance(meta, dict):
        meta = {}
    meta.update(
        {
            "serve_props_v72_updated_at": datetime.now(timezone.utc).isoformat(),
            "serve_props_v72_history_rows": int(len(hist)),
            "serve_props_v78a_hygiene_removed": int(hygiene.get("removed_rows",0)),
            "serve_props_v72_profiles": int(len(profile_cache)),
            "serve_props_v72_ready_matches": int(sum(1 for m in results if (m.get("serve_props_v72") or {}).get("ready"))),
        }
    )
    _write_json(meta_path, meta)
    return {
        "status": "ok",
        "matches": len(results),
        "history_rows": len(hist),
        "profiles": len(profile_cache),
        "ready": sum(1 for m in results if (m.get("serve_props_v72") or {}).get("ready")),
    }


def main():
    print(json.dumps(enrich(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
