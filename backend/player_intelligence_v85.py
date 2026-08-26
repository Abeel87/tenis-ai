from __future__ import annotations

import json
import math
import re
import sqlite3
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import pstdev
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
CACHE = ROOT / "data" / "cache" / "player_intelligence_v85"
DB_PATH = ROOT / "data" / "tennis.db"
RESULTS_PATH = OUT / "results.json"
HISTORY_PATH = OUT / "history.json"
META_PATH = OUT / "meta.json"
TELEMETRY_PATH = OUT / "model_telemetry_v84c.json"
PROFILE_CACHE_PATH = CACHE / "profiles.json"
STATE_PATH = CACHE / "state.json"
VERSION = "v8.5"
PRIMARY_DAYS = 365
FALLBACK_DAYS = 730
WINDOWS = (5, 10, 20)
MIN_PROFILE_N = 3
CAPTURE_CUTOFF_MINUTES = 5
SELECT_THRESHOLD = 0.65
MAX_FROZEN = 12
GENERATOR_TOP = 2


def _read(path: Path, fallback):
    try:
        x = json.loads(path.read_text(encoding="utf-8"))
        return x
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(value)))


def _dt(value):
    try:
        d = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _key(value: Any) -> str:
    s = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def _match_key(entry: dict) -> str:
    mid = entry.get("match_id") if entry.get("match_id") is not None else entry.get("id")
    if mid is not None and str(mid) != "":
        return f"id:{mid}"
    return "|".join([
        _key(entry.get("p1")), _key(entry.get("p2")),
        str(entry.get("scheduled_time") or "")[:10], _key(entry.get("tournament")),
    ])


def _surface(value: Any) -> str:
    x = str(value or "").strip().lower()
    if "indoor" in x and "hard" in x:
        return "indoor"
    if x in ("hard", "clay", "grass", "carpet", "indoor"):
        return x
    if "grass" in x:
        return "grass"
    if "clay" in x:
        return "clay"
    if "hard" in x:
        return "hard"
    return x or "unknown"


def _prob(v):
    x = _num(v)
    if x is None:
        return None
    if x > 1.0:
        x /= 100.0
    return _clamp(x, .01, .99)


def _pct(v):
    x = _num(v)
    if x is None:
        return None
    return x * 100.0 if 0 <= x <= 1 else x


def _range_score(v, lo, hi):
    x = _num(v)
    if x is None or hi <= lo:
        return None
    if 0 <= x <= 1 and hi > 1:
        x *= 100
    return _clamp((x - lo) / (hi - lo), 0, 1) * 100


def _weighted(values):
    rows = [(float(v), float(w)) for v, w in values if v is not None and w > 0]
    if not rows:
        return None
    z = sum(w for _, w in rows)
    return sum(v * w for v, w in rows) / z if z else None


def _opp_strength(rank) -> float:
    """0..1 rank-based difficulty proxy. Not ELO; deliberately bounded."""
    r = _num(rank)
    if r is None or r <= 0:
        return .50
    r = min(2000.0, max(1.0, r))
    return _clamp(1.0 - math.log(r) / math.log(2000.0), 0.0, 1.0)


def _quality(n: int, coverage: float, fallback_used: bool) -> str:
    if n >= 10 and coverage >= .78 and not fallback_used:
        return "HIGH"
    if n >= 5 and coverage >= .58:
        return "MEDIUM"
    if n >= MIN_PROFILE_N:
        return "LOW"
    return "N/D"


def _quality_rank(q: str) -> int:
    return {"N/D": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(str(q or "N/D").upper(), 0)


def _quality_min(a: str, b: str) -> str:
    return min((a, b), key=_quality_rank)


def _source_fingerprint(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "0:none"
    d = pd.to_datetime(df.get("date"), errors="coerce") if "date" in df.columns else pd.Series(dtype="datetime64[ns]")
    mx = "none" if d.empty or d.dropna().empty else str(d.max().date())
    return f"{len(df)}:{mx}"



def _parse_tourney_date(value):
    try:
        s = str(value or "").strip()
        if re.fullmatch(r"\d+(\.0+)?", s):
            s = str(int(float(s)))
        d = pd.to_datetime(s, format="%Y%m%d", errors="coerce")
        return d
    except Exception:
        return pd.NaT


def _set_pairs(score) -> list[tuple[int, int]]:
    if not isinstance(score, str):
        return []
    return [(int(a), int(b)) for a, b in re.findall(r"(\d+)\s*[-:]\s*(\d+)", score)][:5]


def _raw_enrichment() -> pd.DataFrame:
    """Read already-cached TennisMyLife CSVs. No network and no new API calls."""
    rows = []
    for path in sorted((ROOT / "data" / "cache").glob("*.csv.gz")):
        try:
            df = pd.read_csv(path, compression="gzip", low_memory=False)
        except Exception:
            continue
        if df.empty or "winner_name" not in df.columns or "loser_name" not in df.columns:
            continue
        for _, r in df.iterrows():
            wn, ln = r.get("winner_name"), r.get("loser_name")
            if not isinstance(wn, str) or not isinstance(ln, str):
                continue
            pairs = _set_pairs(str(r.get("score") or ""))
            date = _parse_tourney_date(r.get("tourney_date"))
            surf = _surface(r.get("surface"))
            for side, name, opp in (("w", wn, ln), ("l", ln, wn)):
                out = {
                    "date": date,
                    "surface": surf,
                    "player_key": _key(name),
                    "opponent_key": _key(opp),
                    "aces": _num(r.get(f"{side}_ace"), _num(r.get(f"{side}_aces"))),
                    "double_faults": _num(r.get(f"{side}_df"), _num(r.get(f"{side}_double_faults"))),
                    "score_text": str(r.get("score") or ""),
                }
                for i in range(5):
                    if i < len(pairs):
                        a, b = pairs[i]
                        won = (a > b) if side == "w" else (b > a)
                        out[f"set{i+1}_won"] = 1.0 if won else 0.0
                    else:
                        out[f"set{i+1}_won"] = None
                out["sets_played_rich"] = float(len(pairs)) if pairs else None
                rows.append(out)
    if not rows:
        return pd.DataFrame()
    x = pd.DataFrame(rows)
    x = x.drop_duplicates(subset=["date", "surface", "player_key", "opponent_key", "score_text"], keep="last")
    return x


def _merge_raw_enrichment(df: pd.DataFrame) -> pd.DataFrame:
    rich = _raw_enrichment()
    if df is None or df.empty or rich.empty:
        return df
    x = df.copy()
    if "date" in x.columns:
        x["date"] = pd.to_datetime(x["date"], errors="coerce").dt.normalize()
    rich["date"] = pd.to_datetime(rich["date"], errors="coerce").dt.normalize()
    if "surface" in x.columns:
        x["surface"] = x["surface"].astype(str).map(_surface)
    cols = ["date", "surface", "player_key", "opponent_key"]
    use = rich.drop_duplicates(subset=cols, keep="last")
    x = x.merge(use, on=cols, how="left", suffixes=("", "_rich"))
    if "sets_played_rich" in x.columns:
        base = pd.to_numeric(x.get("sets_played"), errors="coerce")
        rr = pd.to_numeric(x.get("sets_played_rich"), errors="coerce")
        x["sets_played"] = base.where(base.notna(), rr)
    return x


def _load_long_df() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    try:
        with sqlite3.connect(DB_PATH) as con:
            df = pd.read_sql_query("select * from player_matches", con)
    except Exception:
        return pd.DataFrame()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return _merge_raw_enrichment(df)


def _metric_pack(x: pd.DataFrame, col: str, prior: float | None = None) -> dict:
    if x is None or x.empty or col not in x.columns:
        return {"raw": None, "adjusted": None, "n": 0, "volatility": None}
    vals = pd.to_numeric(x[col], errors="coerce")
    good = vals.notna()
    if not good.any():
        return {"raw": None, "adjusted": None, "n": 0, "volatility": None}
    raw_vals = vals[good].astype(float).tolist()
    raw = float(sum(raw_vals) / len(raw_vals))
    weighted_rows = []
    for pos, (idx, row) in enumerate(x[good].iterrows()):
        v = _num(row.get(col))
        if v is None:
            continue
        recency = .91 ** pos
        difficulty = .72 + .56 * _opp_strength(row.get("opponent_rank"))
        weighted_rows.append((v, recency * difficulty))
    adjusted = _weighted(weighted_rows)
    n = len(raw_vals)
    if adjusted is not None and prior is not None:
        adjusted = (adjusted * n + float(prior) * 3.0) / (n + 3.0)
    vol = pstdev(raw_vals) if len(raw_vals) >= 2 else 0.0
    return {
        "raw": round(raw, 5),
        "adjusted": round(adjusted, 5) if adjusted is not None else None,
        "n": n,
        "volatility": round(vol, 5),
    }


def _surface_priors(df: pd.DataFrame, surface: str, as_of: pd.Timestamp) -> dict:
    if df is None or df.empty:
        return {}
    x = df.copy()
    if "date" in x.columns:
        x = x[x["date"].isna() | (x["date"] < as_of)]
    if "surface" in x.columns:
        sx = x[x["surface"].astype(str).map(_surface) == surface]
        if len(sx) >= 100:
            x = sx
    cols = [
        "won", "hold_rate", "break_rate", "serve_points_won", "return_points_won",
        "first_serve_won", "second_serve_won", "first_set_won", "second_set_won",
        "second_after_first_win", "second_after_first_loss", "third_set_won",
        "set4_won", "set5_won", "aces", "double_faults",
        "first_set_over85", "first_set_over95", "first_set_over105",
    ]
    out = {}
    for c in cols:
        if c in x.columns:
            s = pd.to_numeric(x[c], errors="coerce").dropna()
            if not s.empty:
                out[c] = float(s.mean())
    return out


def _window_pack(x: pd.DataFrame, n: int, priors: dict) -> dict:
    y = x.head(n).copy()
    cols = [
        "won", "hold_rate", "break_rate", "serve_points_won", "return_points_won",
        "first_serve_won", "second_serve_won", "first_set_won", "second_set_won",
        "second_after_first_win", "second_after_first_loss", "third_set_won",
        "set4_won", "set5_won", "aces", "double_faults",
        "first_set_over85", "first_set_over95", "first_set_over105",
    ]
    metrics = {c: _metric_pack(y, c, priors.get(c)) for c in cols}
    opp = [_opp_strength(v) for v in y.get("opponent_rank", pd.Series(dtype=float)).tolist()]
    ranks = pd.to_numeric(y.get("rank", pd.Series(dtype=float)), errors="coerce").dropna()
    set_counts = pd.to_numeric(y.get("sets_played", pd.Series(dtype=float)), errors="coerce").dropna()
    return {
        "requested": n,
        "sample_matches": int(len(y)),
        "metrics": metrics,
        "avg_opponent_strength": round(sum(opp) / len(opp), 4) if opp else None,
        "latest_rank": int(round(float(ranks.iloc[0]))) if not ranks.empty and ranks.iloc[0] > 0 else None,
        "avg_sets_played": round(float(set_counts.mean()), 2) if not set_counts.empty else None,
        "bo5_observed": int((set_counts >= 4).sum()) if not set_counts.empty else 0,
        "set4_win": _metric_pack(y, "set4_won", priors.get("set4_won")),
        "set5_win": _metric_pack(y, "set5_won", priors.get("set5_won")),
        "aces": _metric_pack(y, "aces", None),
        "double_faults": _metric_pack(y, "double_faults", None),
    }


def _trend(x: pd.DataFrame) -> dict:
    if x is None or len(x) < 6:
        return {}
    a, b = x.head(5), x.iloc[5:10]
    out = {}
    for c in ("won", "hold_rate", "break_rate", "serve_points_won", "return_points_won", "first_set_won"):
        if c not in x.columns:
            continue
        av = pd.to_numeric(a[c], errors="coerce").dropna()
        bv = pd.to_numeric(b[c], errors="coerce").dropna()
        if len(av) >= 2 and len(bv) >= 2:
            out[c] = round(100 * (float(av.mean()) - float(bv.mean())), 1)
    return out


def _profile_indexes(profile: dict, early_ehs=None) -> dict:
    w = profile.get("windows", {}).get("10") or profile.get("windows", {}).get("5") or {}
    m = w.get("metrics") or {}
    val = lambda k: (m.get(k) or {}).get("adjusted")
    serve = _weighted([
        (_range_score(val("hold_rate"), .60, .90), .38),
        (_range_score(val("serve_points_won"), .50, .72), .25),
        (_range_score(val("first_serve_won"), .55, .85), .20),
        (_range_score(val("second_serve_won"), .35, .65), .17),
    ])
    ret = _weighted([
        (_range_score(val("break_rate"), .10, .45), .46),
        (_range_score(val("return_points_won"), .28, .52), .54),
    ])
    form = _weighted([
        (_pct(val("won")), .45), (_pct(val("first_set_won")), .32), (_pct(val("second_set_won")), .23)
    ])
    mental = _weighted([
        (_pct(val("second_after_first_win")), .32),
        (_pct(val("second_after_first_loss")), .32),
        (_pct(val("third_set_won")), .20),
        (_pct(val("set5_won")), .12),
        (_pct(val("second_set_won")), .04),
    ])
    early = _pct(early_ehs)
    rank = w.get("latest_rank")
    rank_idx = None if rank is None else 100 * _opp_strength(rank)
    overall = _weighted([(serve, .25), (ret, .22), (form, .20), (mental, .13), (early, .08), (rank_idx, .12)])
    return {
        "serve": round(serve, 1) if serve is not None else None,
        "return": round(ret, 1) if ret is not None else None,
        "form": round(form, 1) if form is not None else None,
        "mental": round(mental, 1) if mental is not None else None,
        "early": round(early, 1) if early is not None else None,
        "rank_strength": round(rank_idx, 1) if rank_idx is not None else None,
        "overall": round(overall, 1) if overall is not None else None,
    }


def build_profile(df: pd.DataFrame, player: str, surface: str, as_of, early_ehs=None) -> dict:
    if df is None or df.empty:
        return {"player": player, "surface": surface, "quality": "N/D", "windows": {}, "indexes": {}}
    k = _key(player)
    x = df[df["player_key"].astype(str) == k].copy() if "player_key" in df.columns else df[df["player"].map(_key) == k].copy()
    cut = pd.to_datetime(as_of, utc=True, errors="coerce")
    if pd.isna(cut):
        cut = pd.Timestamp(datetime.now(timezone.utc))
    cut_naive = cut.tz_convert(None) if getattr(cut, "tzinfo", None) else cut
    if "date" in x.columns:
        x = x[x["date"].isna() | (x["date"] < cut_naive.normalize())]
    if "surface" in x.columns:
        x = x[x["surface"].astype(str).map(_surface) == surface]
    x = x.sort_values("date", ascending=False, na_position="last") if "date" in x.columns else x

    primary = x
    if "date" in x.columns:
        primary = x[x["date"].isna() | (x["date"] >= cut_naive - pd.Timedelta(days=PRIMARY_DAYS))]
    fallback_used = False
    usable = primary
    if len(primary) < 5 and "date" in x.columns:
        usable = x[x["date"].isna() | (x["date"] >= cut_naive - pd.Timedelta(days=FALLBACK_DAYS))]
        fallback_used = len(usable) > len(primary)
    usable = usable.head(20)
    priors = _surface_priors(df, surface, cut_naive)
    coverage_cols = [c for c in ("hold_rate", "break_rate", "serve_points_won", "return_points_won", "first_set_won") if c in usable.columns]
    coverage = 0.0 if not coverage_cols or usable.empty else sum(float(pd.to_numeric(usable[c], errors="coerce").notna().mean()) for c in coverage_cols) / len(coverage_cols)
    quality = _quality(len(usable), coverage, fallback_used)
    windows = {str(n): _window_pack(usable, n, priors) for n in WINDOWS}
    profile = {
        "version": VERSION,
        "player": player,
        "player_key": k,
        "surface": surface,
        "as_of": cut.isoformat(),
        "primary_days": PRIMARY_DAYS,
        "fallback_days": FALLBACK_DAYS,
        "fallback_used": fallback_used,
        "sample_matches": int(len(usable)),
        "quality": quality,
        "coverage": round(coverage, 4),
        "windows": windows,
        "trend": _trend(usable),
        "data_policy": "same_surface_only_l5_l10_l20_rank_weighted_shrinkage",
    }
    profile["indexes"] = _profile_indexes(profile, early_ehs)
    return profile


def _metric(profile: dict, key: str, window="10"):
    p = (((profile or {}).get("windows") or {}).get(str(window)) or {}).get("metrics") or {}
    return ((p.get(key) or {}).get("adjusted"))


def _idx(profile: dict, key: str):
    return _num(((profile or {}).get("indexes") or {}).get(key))


def _matchup_summary(p1: dict, p2: dict, best_of=None) -> dict:
    q = _quality_min(p1.get("quality", "N/D"), p2.get("quality", "N/D"))
    p1i, p2i = _idx(p1, "overall"), _idx(p2, "overall")
    serve_edge = None if _idx(p1, "serve") is None or _idx(p2, "return") is None else _idx(p1, "serve") - _idx(p2, "return")
    return_edge = None if _idx(p1, "return") is None or _idx(p2, "serve") is None else _idx(p1, "return") - _idx(p2, "serve")
    form_edge = None if _idx(p1, "form") is None or _idx(p2, "form") is None else _idx(p1, "form") - _idx(p2, "form")
    overall_edge = None if p1i is None or p2i is None else p1i - p2i
    reasons = []
    for label, edge in (("serwis vs return", serve_edge), ("return vs serwis", return_edge), ("forma", form_edge), ("profil łączny", overall_edge)):
        if edge is not None and abs(edge) >= 4:
            reasons.append({"factor": label, "edge_p1": round(edge, 1)})
    reasons = sorted(reasons, key=lambda x: -abs(x["edge_p1"]))[:3]
    return {
        "quality": q,
        "best_of": int(best_of) if _num(best_of) in (3, 5) else None,
        "p1_overall": p1i,
        "p2_overall": p2i,
        "edge_p1": round(overall_edge, 1) if overall_edge is not None else None,
        "serve_edge_p1": round(serve_edge, 1) if serve_edge is not None else None,
        "return_edge_p1": round(return_edge, 1) if return_edge is not None else None,
        "form_edge_p1": round(form_edge, 1) if form_edge is not None else None,
        "reasons": reasons,
    }


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-max(-8.0, min(8.0, float(x)))))


def _winner_probability(profile: dict, other: dict, set_no=0) -> float | None:
    if _quality_rank(profile.get("quality")) == 0 or _quality_rank(other.get("quality")) == 0:
        return None
    a = _idx(profile, "overall")
    b = _idx(other, "overall")
    if a is None or b is None:
        return None
    if set_no == 1:
        av, bv = _metric(profile, "first_set_won"), _metric(other, "first_set_won")
    elif set_no == 2:
        av, bv = _metric(profile, "second_set_won"), _metric(other, "second_set_won")
    elif set_no == 3:
        av, bv = _metric(profile, "third_set_won"), _metric(other, "third_set_won")
    else:
        av, bv = _metric(profile, "won"), _metric(other, "won")
    hist_edge = 0.0 if av is None or bv is None else (av - bv) * 100
    edge = .72 * (a - b) + .28 * hist_edge
    p = _sigmoid(edge / 13.5)
    return _clamp(p, .30, .70)


def _over_probability(p1: dict, p2: dict, line: float) -> float | None:
    line = _num(line)
    if line is None:
        return None
    if line <= 8.5:
        key = "first_set_over85"
    elif line <= 9.5:
        key = "first_set_over95"
    elif line <= 10.5:
        key = "first_set_over105"
    else:
        return None
    vals = [_metric(p1, key), _metric(p2, key)]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    p = sum(vals) / len(vals)
    # High holds push a little toward longer sets; bounded to avoid double counting.
    holds = [v for v in (_metric(p1, "hold_rate"), _metric(p2, "hold_rate")) if v is not None]
    if holds:
        p += max(-.05, min(.05, (sum(holds) / len(holds) - .74) * .35))
    return _clamp(p, .20, .90)


def _balanced_state_probability(p1: dict, p2: dict, checkpoint: int) -> float | None:
    h1, h2 = _metric(p1, "hold_rate"), _metric(p2, "hold_rate")
    if h1 is None or h2 is None:
        return None
    pair_hold = _clamp(h1 * h2, .10, .98)
    pairs = max(1, int(checkpoint) // 2)
    return _clamp(pair_hold ** pairs, .10, .92)


def signal_probability(match: dict, signal: dict) -> tuple[float | None, list[str]]:
    pi = match.get("player_intelligence_v85") or {}
    p1 = (pi.get("profiles") or {}).get("p1") or {}
    p2 = (pi.get("profiles") or {}).get("p2") or {}
    market = str(signal.get("market") or "").lower()
    pick = str(signal.get("pick") or "")
    nk = _key(pick)
    p1k, p2k = _key(match.get("p1")), _key(match.get("p2"))
    reasons = []

    if market in ("match_winner", "match_win") or "match_win" in str(signal.get("key") or ""):
        p = _winner_probability(p1, p2, 0)
        if p is None:
            return None, []
        out = p if nk == p1k else (1 - p if nk == p2k else None)
    elif market in ("set1_winner", "set1_win"):
        p = _winner_probability(p1, p2, 1)
        if p is None:
            return None, []
        out = p if nk == p1k else (1 - p if nk == p2k else None)
    elif market in ("set2_winner", "set2_win"):
        p = _winner_probability(p1, p2, 2)
        if p is None:
            return None, []
        out = p if nk == p1k else (1 - p if nk == p2k else None)
    elif market in ("set3_winner", "set3_win"):
        p = _winner_probability(p1, p2, 3)
        if p is None:
            return None, []
        out = p if nk == p1k else (1 - p if nk == p2k else None)
    elif market == "set1_total":
        p = _over_probability(p1, p2, _num(signal.get("line")))
        if p is None:
            return None, []
        out = p if nk == "over" else (1 - p if nk == "under" else None)
    elif market == "game_state" or market.startswith("state"):
        cp = signal.get("checkpoint")
        if cp is None:
            m = re.search(r"state\D*([246])", str(signal.get("key") or market))
            cp = int(m.group(1)) if m else None
        try:
            cp = int(cp)
        except Exception:
            return None, []
        expected = {2: "1:1", 4: "2:2", 6: "3:3"}.get(cp)
        if pick != expected:
            return None, []
        out = _balanced_state_probability(p1, p2, cp)
    else:
        return None, []

    if out is None:
        return None, []
    summary = pi.get("matchup") or {}
    for r in summary.get("reasons") or []:
        edge = _num(r.get("edge_p1"))
        if edge is None:
            continue
        direction = "P1" if edge > 0 else "P2"
        reasons.append(f"{r.get('factor')}: {direction} {abs(edge):.1f}")
    return _clamp(out, .05, .95), reasons[:3]


def _shadow(base: float, player_p: float, quality: str) -> tuple[float, float]:
    q = str(quality or "N/D").upper()
    alpha, cap = {
        "HIGH": (.25, .04), "MEDIUM": (.15, .02), "LOW": (.08, .01), "N/D": (0.0, 0.0)
    }.get(q, (0.0, 0.0))
    raw = base + alpha * (player_p - base)
    shift = max(-cap, min(cap, raw - base))
    return _clamp(base + shift, .01, .99), shift


def _support(player_p: float) -> int:
    return int(round(max(-10, min(10, (player_p - .50) / .03))))


def _cache_key(player: str, surface: str, as_of: str, fingerprint: str) -> str:
    return f"{_key(player)}|{surface}|{str(as_of)[:10]}|{fingerprint}"


def pre(now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    results = _read(RESULTS_PATH, [])
    meta = _read(META_PATH, {})
    cache = _read(PROFILE_CACHE_PATH, {"version": VERSION, "profiles": {}})
    if not isinstance(cache, dict):
        cache = {"version": VERSION, "profiles": {}}
    profiles_cache = cache.setdefault("profiles", {})
    df = _load_long_df()
    fp = _source_fingerprint(df)
    built = reused = 0

    out = []
    for match in results if isinstance(results, list) else []:
        m = dict(match)
        surf = _surface(m.get("surface"))
        sides = {}
        for side in ("p1", "p2"):
            name = m.get(side)
            early = (((m.get("early_hold_v7") or {}).get(side) or {}).get("ehs"))
            ck = _cache_key(name, surf, m.get("scheduled_time"), fp)
            p = profiles_cache.get(ck)
            if isinstance(p, dict) and p.get("version") == VERSION:
                reused += 1
            else:
                p = build_profile(df, str(name or ""), surf, m.get("scheduled_time"), early)
                profiles_cache[ck] = p
                built += 1
            sides[side] = p
        matchup = _matchup_summary(sides["p1"], sides["p2"], m.get("best_of"))
        m["player_intelligence_v85"] = {
            "version": VERSION,
            "mode": "SHADOW",
            "surface": surf,
            "profiles": sides,
            "matchup": matchup,
            "api_calls": 0,
            "cache_policy": "reuse_existing_history_no_new_api",
            "updated_at": now.isoformat(),
        }
        out.append(m)

    cache["version"] = VERSION
    cache["source_fingerprint"] = fp
    cache["updated_at"] = now.isoformat()
    # Avoid unbounded growth from per-day keys; keep newest 6000 cached profiles.
    if len(profiles_cache) > 6000:
        keep = list(profiles_cache.items())[-6000:]
        cache["profiles"] = dict(keep)
    _write(PROFILE_CACHE_PATH, cache)
    _write(RESULTS_PATH, out)
    if not isinstance(meta, dict):
        meta = {}
    meta.update({
        "player_intelligence_v85_version": VERSION,
        "player_intelligence_v85_mode": "SHADOW",
        "player_intelligence_v85_profiles_built": built,
        "player_intelligence_v85_profiles_reused": reused,
        "player_intelligence_v85_api_calls": 0,
        "player_intelligence_v85_updated_at": now.isoformat(),
    })
    _write(META_PATH, meta)
    return {"status": "ok", "matches": len(out), "built": built, "reused": reused, "api_calls": 0}


def _decorate_post(results: list[dict]) -> list[dict]:
    out = []
    for match in results or []:
        m = dict(match)
        pi = m.get("player_intelligence_v85") or {}
        quality = ((pi.get("matchup") or {}).get("quality")) or "N/D"
        auto = dict(m.get("autolearn_v84") or {})
        sigs = []
        for s0 in auto.get("signals") or []:
            s = dict(s0)
            pp, reasons = signal_probability(m, s)
            base = _prob(s.get("ensemble"))
            if pp is not None and base is not None:
                shadow, shift = _shadow(base, pp, quality)
                s["player_intelligence_v85"] = {
                    "version": VERSION,
                    "mode": "SHADOW",
                    "quality": quality,
                    "probability": round(pp * 100, 1),
                    "ensemble_base": round(base * 100, 1),
                    "shadow_score": round(shadow * 100, 1),
                    "shadow_shift_pp": round(shift * 100, 1),
                    "support_score": _support(pp),
                    "reasons": reasons,
                }
            sigs.append(s)
        auto["signals"] = sigs
        auto["by_key"] = {str(x.get("key")): x for x in sigs if x.get("key")}
        m["autolearn_v84"] = auto
        out.append(m)
    return out


def _capture_and_settle(history: list[dict], results: list[dict], now: datetime) -> tuple[list[dict], int, int]:
    current = {_match_key(m): m for m in results or []}
    captured = settled = 0
    out = []
    for entry0 in history or []:
        e = dict(entry0)
        auto_frozen = e.get("autolearn_signals_v84") or []
        existing = e.get("player_intelligence_signals_v85") or []
        if existing:
            amap = {str(s.get("key")): s for s in auto_frozen if s.get("key")}
            rows = []
            for p0 in existing:
                p = dict(p0)
                if p.get("result") not in ("hit", "miss"):
                    a = amap.get(str(p.get("key"))) or {}
                    if a.get("result") in ("hit", "miss"):
                        p["result"] = a.get("result")
                        p["settled_at"] = now.isoformat()
                        settled += 1
                rows.append(p)
            e["player_intelligence_signals_v85"] = rows
            out.append(e)
            continue

        if e.get("status") not in ("pending", "upcoming") or not auto_frozen:
            out.append(e); continue
        scheduled = _dt(e.get("scheduled_time"))
        if scheduled is None or scheduled <= now + timedelta(minutes=CAPTURE_CUTOFF_MINUTES):
            out.append(e); continue
        m = current.get(_match_key(e))
        if not m:
            out.append(e); continue
        bykey = ((m.get("autolearn_v84") or {}).get("by_key") or {})
        rows = []
        for a in auto_frozen[:MAX_FROZEN]:
            s = bykey.get(str(a.get("key"))) or {}
            p = s.get("player_intelligence_v85") or {}
            if _num(p.get("probability")) is None:
                continue
            rows.append({
                "key": a.get("key"), "label": a.get("label"), "market": a.get("market"),
                "pick": a.get("pick"), "line": a.get("line"), "checkpoint": a.get("checkpoint"),
                "player_probability": p.get("probability"),
                "ensemble_base": p.get("ensemble_base"),
                "shadow_score": p.get("shadow_score"),
                "support_score": p.get("support_score"),
                "quality": p.get("quality"),
                "reasons": p.get("reasons") or [],
                "generator_production_selected": bool(a.get("generator_selected")),
                "generator_shadow_selected": False,
                "result": "pending",
                "tracker_version": VERSION,
            })
        top = sorted([r for r in rows if _num(r.get("shadow_score"), 0) >= 65], key=lambda r: -_num(r.get("shadow_score"), 0))[:GENERATOR_TOP]
        top_keys = {str(r.get("key")) for r in top}
        for r in rows:
            r["generator_shadow_selected"] = str(r.get("key")) in top_keys
        if rows:
            e["player_intelligence_signals_v85"] = rows
            e["player_intelligence_v85_captured_at"] = now.isoformat()
            captured += 1
        out.append(e)
    return out, captured, settled


def _brier(y, p):
    return None if not y else sum((float(pi) - float(yi)) ** 2 for yi, pi in zip(y, p)) / len(y)


def _logloss(y, p):
    if not y:
        return None
    s = 0.0
    for yi, pi in zip(y, p):
        pi = _clamp(pi, 1e-6, 1 - 1e-6)
        s += -(yi * math.log(pi) + (1 - yi) * math.log(1 - pi))
    return s / len(y)


def _summary(rows: list[tuple[int, float]]) -> dict:
    if not rows:
        return {"n": 0, "selected_n": 0, "accuracy": None, "brier": None, "log_loss": None}
    y, p = [r[0] for r in rows], [r[1] for r in rows]
    selected = [r for r in rows if r[1] >= SELECT_THRESHOLD]
    return {
        "n": len(rows),
        "selected_n": len(selected),
        "accuracy": round(100 * sum(r[0] for r in selected) / len(selected), 1) if selected else None,
        "brier": round(_brier(y, p), 5),
        "log_loss": round(_logloss(y, p), 5),
    }


def _series(rows: list[dict], key: str) -> list[dict]:
    vals = []
    for r in sorted(rows, key=lambda x: x.get("scheduled_time") or ""):
        p = _prob(r.get(key))
        if p is None or p < SELECT_THRESHOLD:
            continue
        vals.append(1 if r.get("result") == "hit" else 0)
    out = []
    for i in range(4, len(vals)):
        w = vals[max(0, i - 7): i + 1]
        out.append({"n": i + 1, "accuracy": round(100 * sum(w) / len(w), 1)})
    return out[-24:]


def _telemetry(history: list[dict]) -> dict:
    rows = []
    pairs = defaultdict(list)
    surfaces = defaultdict(lambda: defaultdict(list))
    for e in history or []:
        for s in e.get("player_intelligence_signals_v85") or []:
            if s.get("result") not in ("hit", "miss"):
                continue
            y = 1 if s.get("result") == "hit" else 0
            row = {
                **s,
                "scheduled_time": e.get("scheduled_time"),
                "surface": _surface(e.get("surface")),
                "result": s.get("result"),
            }
            rows.append(row)
            for name, field in (("player", "player_probability"), ("ensemble", "ensemble_base"), ("ensemble_player_shadow", "shadow_score")):
                p = _prob(s.get(field))
                if p is not None:
                    pairs[name].append((y, p))
                    surfaces[row["surface"]][name].append((y, p))
            if s.get("generator_shadow_selected"):
                p = _prob(s.get("shadow_score"))
                if p is not None:
                    pairs["generator_player_shadow"].append((y, p))
    models = {k: _summary(v) for k, v in pairs.items()}
    for name, field in (("player", "player_probability"), ("ensemble", "ensemble_base"), ("ensemble_player_shadow", "shadow_score")):
        models.setdefault(name, _summary([]))
        models[name]["series"] = _series(rows, field)
    by_surface = {surf: {k: _summary(v) for k, v in groups.items()} for surf, groups in surfaces.items()}
    return {
        "version": VERSION,
        "mode": "SHADOW",
        "settled_rows": len(rows),
        "models": models,
        "by_surface": by_surface,
        "production_influence": False,
        "generator_assist": "disabled_shadow_only",
        "note": "Player Intelligence pozostaje SHADOW: nie zmienia Ensemble, Generatora ani final_score i nie wykonuje własnych requestów API.",
    }


def post(now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    results = _read(RESULTS_PATH, [])
    history = _read(HISTORY_PATH, [])
    meta = _read(META_PATH, {})
    telemetry = _read(TELEMETRY_PATH, {})
    if not isinstance(results, list): results = []
    if not isinstance(history, list): history = []
    results = _decorate_post(results)
    history, captured, settled = _capture_and_settle(history, results, now)
    pi_tel = _telemetry(history)
    if not isinstance(telemetry, dict): telemetry = {}
    telemetry["player_intelligence_v85"] = pi_tel
    if not isinstance(meta, dict): meta = {}
    meta.update({
        "player_intelligence_v85_version": VERSION,
        "player_intelligence_v85_mode": "SHADOW",
        "player_intelligence_v85_captured": captured,
        "player_intelligence_v85_settled_this_run": settled,
        "player_intelligence_v85_settled_total": pi_tel.get("settled_rows", 0),
        "player_intelligence_v85_api_calls": 0,
        "player_intelligence_v85_updated_at": now.isoformat(),
    })
    _write(RESULTS_PATH, results)
    _write(HISTORY_PATH, history)
    _write(TELEMETRY_PATH, telemetry)
    _write(META_PATH, meta)
    return {"status": "ok", "captured": captured, "settled": settled, "telemetry_rows": pi_tel.get("settled_rows", 0)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("pre", "post"), nargs="?", default="pre")
    args = ap.parse_args()
    result = pre() if args.mode == "pre" else post()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
