from __future__ import annotations

import bisect
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from .player_intelligence_v85 import _load_long_df, _key as _player_key
    from .player_model_shadow_v89 import (
        NUMERIC_FEATURES as PI_NUMERIC,
        CATEGORICAL_FEATURES as PI_CATEGORICAL,
        build_training_rows,
        split_by_match,
        _match_key,
        _num,
        _prob,
        metrics,
        _fit as _fit_player,
        _predict as _predict_player,
    )
    from .ensemble_player_learning_v891 import learn_policy, alpha_for_row, _blend as player_blend
except ImportError:
    from player_intelligence_v85 import _load_long_df, _key as _player_key
    from player_model_shadow_v89 import (
        NUMERIC_FEATURES as PI_NUMERIC,
        CATEGORICAL_FEATURES as PI_CATEGORICAL,
        build_training_rows,
        split_by_match,
        _match_key,
        _num,
        _prob,
        metrics,
        _fit as _fit_player,
        _predict as _predict_player,
    )
    from ensemble_player_learning_v891 import learn_policy, alpha_for_row, _blend as player_blend

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data"
RESULTS = OUT / "results.json"
HISTORY = OUT / "history.json"
TELEMETRY = OUT / "model_telemetry_v84c.json"
META = OUT / "meta.json"
REPORT = OUT / "surface_elo_integration_v893.json"

VERSION = "v8.9.3"
MODE = "SHADOW"
BASE = 1500.0
SCALE = 400.0
SHRINK_N = 12.0
HALF_LIFE_DAYS = 720.0
ALPHA_GRID = tuple(round(i * .025, 3) for i in range(15))  # 0..0.35
ELO_NUMERIC = (
    "elo_p1_general", "elo_p2_general", "elo_p1_surface", "elo_p2_surface",
    "elo_p1_blended", "elo_p2_blended", "elo_general_edge_p1",
    "elo_surface_edge_p1", "elo_blended_edge_p1", "elo_edge_for_pick",
    "elo_edge_abs", "elo_probability_for_pick", "elo_confidence",
    "elo_p1_surface_n", "elo_p2_surface_n", "elo_p1_general_n", "elo_p2_general_n",
)
NUMERIC = tuple(PI_NUMERIC) + ELO_NUMERIC
CATEGORICAL = tuple(PI_CATEGORICAL) + ("elo_quality",)
FEATURES = NUMERIC + CATEGORICAL


def _read(path, fallback):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _surface(value):
    x = str(value or "").strip().lower()
    if "indoor" in x and "hard" in x: return "indoor"
    if "grass" in x: return "grass"
    if "clay" in x: return "clay"
    if "hard" in x: return "hard"
    return x if x in ("carpet", "indoor") else (x or "unknown")


def _expect(a, b):
    return 1.0 / (1.0 + 10.0 ** ((float(b) - float(a)) / SCALE))


def _k(n):
    return 40.0 if n < 12 else (30.0 if n < 40 else 22.0)


def _decay(rating, last_day, day):
    if last_day is None: return float(rating)
    days = max(0, int((day - last_day).days))
    return BASE + (float(rating) - BASE) * (0.5 ** (days / HALF_LIFE_DAYS))


def _events(df):
    """Collapse mirrored player_matches rows into one historical match."""
    if df is None or df.empty or not {"date", "player_key", "opponent_key", "won"}.issubset(df.columns):
        return []
    x = df.copy()
    x["_d"] = pd.to_datetime(x["date"], errors="coerce").dt.normalize()
    x["_s"] = x["surface"].astype(str).map(_surface) if "surface" in x.columns else "unknown"
    x["_w"] = pd.to_numeric(x["won"], errors="coerce")
    x = x[x["_d"].notna() & x["_w"].isin([0.0, 1.0])]
    out, bad = {}, set()
    for _, r in x.sort_values("_d", kind="stable").iterrows():
        p, o = str(r.get("player_key") or ""), str(r.get("opponent_key") or "")
        if not p or not o or p == o: continue
        winner, loser = (p, o) if float(r["_w"]) >= .5 else (o, p)
        mid = r.get("match_id")
        if mid is not None and str(mid) not in ("", "nan", "None"):
            key = ("id", str(mid))
        else:
            extra = tuple(str(r.get(c) or "") for c in ("tourney_name", "round", "score_text") if c in x.columns)
            key = ("pair", str(r["_d"]), r["_s"], tuple(sorted((p, o))), extra)
        event = (r["_d"], r["_s"], winner, loser)
        if key in out and out[key][2:] != event[2:]: bad.add(key)
        else: out.setdefault(key, event)
    for key in bad: out.pop(key, None)
    return sorted(out.values(), key=lambda z: (z[0], z[1], z[2], z[3]))


class EloIndex:
    """General + surface Elo. Lookups exclude the entire target match day."""

    def __init__(self, df):
        self.events = _events(df)
        self.g = defaultdict(list)           # player -> [(day,rating,n)]
        self.s = defaultdict(list)           # (player,surface) -> [(day,rating,n)]
        self.gdates, self.sdates = {}, {}
        self.players = set()
        self._build()

    def _build(self):
        gr, gn, gl = {}, {}, {}
        sr, sn, sl = {}, {}, {}
        for day, surf, winner, loser in self.events:
            self.players.update((winner, loser))
            gw, lo = _decay(gr.get(winner, BASE), gl.get(winner), day), _decay(gr.get(loser, BASE), gl.get(loser), day)
            nw, nl = gn.get(winner, 0), gn.get(loser, 0)
            ew = _expect(gw, lo)
            gr[winner], gr[loser] = gw + _k(nw) * (1-ew), lo - _k(nl) * (1-ew)
            gn[winner], gn[loser] = nw + 1, nl + 1
            gl[winner] = gl[loser] = day

            wk, lk = (winner, surf), (loser, surf)
            sw, so = _decay(sr.get(wk, BASE), sl.get(wk), day), _decay(sr.get(lk, BASE), sl.get(lk), day)
            snw, snl = sn.get(wk, 0), sn.get(lk, 0)
            sew = _expect(sw, so)
            sr[wk], sr[lk] = sw + _k(snw) * (1-sew), so - _k(snl) * (1-sew)
            sn[wk], sn[lk] = snw + 1, snl + 1
            sl[wk] = sl[lk] = day

            self.g[winner].append((day, gr[winner], gn[winner]))
            self.g[loser].append((day, gr[loser], gn[loser]))
            self.s[wk].append((day, sr[wk], sn[wk]))
            self.s[lk].append((day, sr[lk], sn[lk]))

        self.gdates = {k: [x[0] for x in v] for k, v in self.g.items()}
        self.sdates = {k: [x[0] for x in v] for k, v in self.s.items()}

    @staticmethod
    def _day(value):
        x = pd.to_datetime(value, utc=True, errors="coerce")
        return None if pd.isna(x) else x.tz_convert(None).normalize()

    def _last(self, timeline, dates, day):
        if not dates: return None
        i = bisect.bisect_left(dates, day) - 1  # strict: same day is excluded
        return timeline[i] if i >= 0 else None

    def player(self, name, surface, as_of):
        player_key = _player_key(name)
        day, surf = self._day(as_of), _surface(surface)
        if day is None or not player_key:
            return {"general": BASE, "surface": BASE, "blended": BASE, "general_n": 0, "surface_n": 0}
        gp = self._last(self.g.get(player_key, []), self.gdates.get(player_key, []), day)
        sp = self._last(self.s.get((player_key, surf), []), self.sdates.get((player_key, surf), []), day)
        g = _decay(gp[1], gp[0], day) if gp else BASE
        s = _decay(sp[1], sp[0], day) if sp else BASE
        ng, ns = (gp[2] if gp else 0), (sp[2] if sp else 0)
        rel = ns / (ns + SHRINK_N) if ns else 0.0
        return {
            "general": g, "surface": s, "blended": g * (1-rel) + s * rel,
            "general_n": ng, "surface_n": ns, "surface_reliability": rel,
        }

    def match(self, p1, p2, surface, as_of):
        a, b = self.player(str(p1 or ""), surface, as_of), self.player(str(p2 or ""), surface, as_of)
        ge, se, be = a["general"]-b["general"], a["surface"]-b["surface"], a["blended"]-b["blended"]
        mn_s, mn_g = min(a["surface_n"], b["surface_n"]), min(a["general_n"], b["general_n"])
        sc = mn_s/(mn_s+SHRINK_N) if mn_s else 0.0
        gc = mn_g/(mn_g+20.0) if mn_g else 0.0
        conf = math.sqrt(sc*gc) if sc and gc else 0.0
        quality = "HIGH" if mn_s >= 20 else ("MEDIUM" if mn_s >= 8 else ("LOW" if mn_s >= 3 else "N/D"))
        return {
            "p1": a, "p2": b, "general_edge_p1": ge, "surface_edge_p1": se,
            "blended_edge_p1": be, "p1_probability": _expect(a["blended"], b["blended"]),
            "confidence": conf, "quality": quality,
        }

    def stats(self):
        return {"events": len(self.events), "players": len(self.players), "player_surface_timelines": len(self.s)}


def _elo_features(snap, pick_side):
    side = str(pick_side or "").lower()
    direction = 1 if side == "p1" else (-1 if side == "p2" else 0)
    pp = snap["p1_probability"] if direction > 0 else ((1-snap["p1_probability"]) if direction < 0 else None)
    a, b = snap["p1"], snap["p2"]
    return {
        "elo_p1_general": a["general"], "elo_p2_general": b["general"],
        "elo_p1_surface": a["surface"], "elo_p2_surface": b["surface"],
        "elo_p1_blended": a["blended"], "elo_p2_blended": b["blended"],
        "elo_general_edge_p1": snap["general_edge_p1"], "elo_surface_edge_p1": snap["surface_edge_p1"],
        "elo_blended_edge_p1": snap["blended_edge_p1"],
        "elo_edge_for_pick": snap["blended_edge_p1"] * direction,
        "elo_edge_abs": abs(snap["blended_edge_p1"]), "elo_probability_for_pick": pp,
        "elo_confidence": snap["confidence"], "elo_quality": snap["quality"],
        "elo_p1_surface_n": a["surface_n"], "elo_p2_surface_n": b["surface_n"],
        "elo_p1_general_n": a["general_n"], "elo_p2_general_n": b["general_n"],
    }


def _enrich(rows, history_map, index):
    cache, out = {}, []
    for row in rows:
        r = dict(row)
        entry = history_map.get(str(r.get("match_key") or ""))
        if entry:
            key = _match_key(entry)
            snap = cache.get(key)
            if snap is None:
                snap = index.match(entry.get("p1"), entry.get("p2"), entry.get("surface"), entry.get("scheduled_time"))
                cache[key] = snap
            r.update(_elo_features(snap, r.get("pick_side")))
        else:
            for k in ELO_NUMERIC: r[k] = None
            r["elo_quality"] = "N/D"
        out.append(r)
    return out


def _frame(rows):
    data = []
    for r in rows:
        x = {k: (float("nan") if _num(r.get(k)) is None else _num(r.get(k))) for k in NUMERIC}
        x.update({k: str(r.get(k) or "N/D") for k in CATEGORICAL})
        data.append(x)
    return pd.DataFrame(data, columns=FEATURES)


def _fit_elo_cat(rows):
    from catboost import CatBoostClassifier
    if not rows or len({r["target"] for r in rows}) < 2: return None
    model = CatBoostClassifier(
        iterations=240, depth=5, learning_rate=.04, loss_function="Logloss",
        eval_metric="Logloss", random_seed=893, l2_leaf_reg=6.0,
        random_strength=.5, verbose=False, allow_writing_files=False, thread_count=2,
    )
    model.fit(_frame(rows), [int(r["target"]) for r in rows], cat_features=[FEATURES.index(c) for c in CATEGORICAL], verbose=False)
    return model


def _predict(model, rows):
    if model is None or not rows: return []
    return [float(x[1]) for x in model.predict_proba(_frame(rows))]


def _ensemble_prob(row, policy):
    if _prob(row.get("ensemble_score")) is None or _prob(row.get("player_probability")) is None: return None
    a, _ = alpha_for_row(row, policy)
    return player_blend(row, a)


def _eligible(row):
    return "winner" in str(row.get("market") or "").lower() and str(row.get("pick_side") or "").lower() in ("p1", "p2") and _prob(row.get("elo_probability_for_pick")) is not None


def _fuse(row, base, alpha):
    if base is None or not _eligible(row): return base
    ep = _prob(row.get("elo_probability_for_pick"))
    conf = max(0.0, min(1.0, _num(row.get("elo_confidence"), 0.0)))
    a = max(0.0, min(.35, alpha * (.25 + .75*conf)))
    return max(.01, min(.99, base*(1-a) + ep*a))


def _brier(rows, probs):
    pairs = [(r,p) for r,p in zip(rows, probs) if p is not None]
    return None if not pairs else sum((float(p)-int(r["target"]))**2 for r,p in pairs)/len(pairs)


def _learn_alpha(rows, bases):
    best = None
    for a in ALPHA_GRID:
        p = [_fuse(r,b,a) for r,b in zip(rows,bases)]
        score = (_brier(rows,p), a)
        if score[0] is not None and (best is None or score < best[0]): best = (score,a)
    return 0.0 if best is None else float(best[1])


def _metric(rows, probs):
    rr, pp = [], []
    for r,p in zip(rows, probs):
        if p is not None: rr.append(r); pp.append(float(p))
    return metrics(rr, pp)


def _gate(candidate, baseline, holdout_matches):
    if candidate.get("n",0) < 25 or holdout_matches < 8 or candidate.get("brier") is None or baseline.get("brier") is None:
        return {"status":"collecting","production_influence":False,"auto_promotion":False}
    bg = baseline["brier"] - candidate["brier"]
    lg = None if candidate.get("log_loss") is None or baseline.get("log_loss") is None else baseline["log_loss"]-candidate["log_loss"]
    ad = None if candidate.get("accuracy") is None or baseline.get("accuracy") is None else candidate["accuracy"]-baseline["accuracy"]
    promising = bg >= .001 and (lg is None or lg >= -.002) and (ad is None or ad >= -1.0)
    strong = promising and bg >= .003 and (lg is None or lg >= .001) and (ad is None or ad >= 0)
    return {
        "status":"strong_candidate" if strong else ("promising" if promising else "watch"),
        "production_influence":False,"auto_promotion":False,
        "brier_gain":round(bg,5),"log_loss_gain":round(lg,5) if lg is not None else None,
        "accuracy_delta_pp":round(ad,1) if ad is not None else None,
    }


def run(now=None):
    now = now or datetime.now(timezone.utc)
    history, telemetry, meta = _read(HISTORY, []), _read(TELEMETRY, {}), _read(META, {})
    if not isinstance(history,list): history=[]
    if not isinstance(telemetry,dict): telemetry={}
    if not isinstance(meta,dict): meta={}

    index = EloIndex(_load_long_df())
    hmap = {_match_key(e):e for e in history if isinstance(e,dict)}
    rows = _enrich(build_training_rows(history), hmap, index)
    train, holdout = split_by_match(rows)
    hm = len({r["match_key"] for r in holdout})
    enough = len(train)>=100 and len({r["match_key"] for r in train})>=30 and len(holdout)>=30 and hm>=8 and index.stats()["events"]>0

    blank={"n":0,"selected_n":0,"accuracy":None,"brier":None,"log_loss":None}
    out={k:dict(blank) for k in ("catboost_player","catboost_player_elo","ensemble_player","ensemble_player_elo","tabpfn","tabpfn_elo")}
    learned={"ensemble_elo_alpha":0.0,"tabpfn_elo_alpha":0.0}
    gates={k:{"status":"collecting","production_influence":False} for k in ("catboost_player_elo","ensemble_player_elo","tabpfn_elo")}

    if enough:
        base = _fit_player(train)
        elo = _fit_elo_cat(train)
        out["catboost_player"] = metrics(holdout, _predict_player(base,holdout))
        out["catboost_player_elo"] = metrics(holdout, _predict(elo,holdout))

        pol = learn_policy(train)
        train_ens = [_ensemble_prob(r,pol) for r in train]
        ae = _learn_alpha(train,train_ens)
        learned["ensemble_elo_alpha"]=ae
        hb = [_ensemble_prob(r,pol) for r in holdout]
        out["ensemble_player"]=_metric(holdout,hb)
        out["ensemble_player_elo"]=_metric(holdout,[_fuse(r,p,ae) for r,p in zip(holdout,hb)])

        train_tab=[_prob(r.get("tabpfn_score")) for r in train]
        at=_learn_alpha(train,train_tab)
        learned["tabpfn_elo_alpha"]=at
        ht=[_prob(r.get("tabpfn_score")) for r in holdout]
        out["tabpfn"]=_metric(holdout,ht)
        out["tabpfn_elo"]=_metric(holdout,[_fuse(r,p,at) for r,p in zip(holdout,ht)])

        gates={
            "catboost_player_elo":_gate(out["catboost_player_elo"],out["catboost_player"],hm),
            "ensemble_player_elo":_gate(out["ensemble_player_elo"],out["ensemble_player"],hm),
            "tabpfn_elo":_gate(out["tabpfn_elo"],out["tabpfn"],hm),
        }

    surface_rows=sum(1 for r in rows if _num(r.get("elo_p1_surface_n"),0)>0 and _num(r.get("elo_p2_surface_n"),0)>0)
    report={
        "version":VERSION,"generated_at":now.isoformat(),"mode":MODE,
        "status":"ACTIVE_SHADOW" if enough else "COLLECTING",
        "production_influence":False,"auto_promotion":False,
        "elo":{
            "method":"general_plus_surface_elo_with_sample_shrinkage_and_inactivity_decay",
            "same_day_policy":"exclude_entire_match_day_to_prevent_leakage",
            "rating_base":BASE,"scale":SCALE,"surface_shrink_n":SHRINK_N,"decay_half_life_days":HALF_LIFE_DAYS,
            **index.stats(),"rows_with_both_surface_history":surface_rows,
        },
        "training":{
            "rows_total":len(rows),"matches_total":len({r["match_key"] for r in rows}),
            "train_rows":len(train),"train_matches":len({r["match_key"] for r in train}),
            "holdout_rows":len(holdout),"holdout_matches":hm,"chronological_match_split":"80/20",
            "leakage_policy":"elo_strictly_before_match_day_and_fit_train_only_for_holdout",
        },
        "learned":learned,"holdout":out,"gates":gates,
        "note":"Elo zasila wyłącznie eksperymenty SHADOW: CatBoost+Player+Elo, Ensemble+Player Learning+Elo i TabPFN+Elo. 0% wpływu na PROD/Generator/final_score.",
    }
    telemetry["surface_elo_integration_v893"]=report
    meta.update({
        "surface_elo_v893_version":VERSION,"surface_elo_v893_mode":MODE,"surface_elo_v893_status":report["status"],
        "surface_elo_v893_events":index.stats()["events"],"surface_elo_v893_training_rows":len(rows),
        "surface_elo_v893_holdout_rows":len(holdout),"surface_elo_v893_production_influence":False,
        "surface_elo_v893_updated_at":now.isoformat(),
    })
    _write(REPORT,report); _write(TELEMETRY,telemetry); _write(META,meta)
    return {"status":report["status"],"events":index.stats()["events"],"training_rows":len(rows),"holdout_rows":len(holdout),"gates":{k:v.get("status") for k,v in gates.items()}}


if __name__=="__main__":
    print(json.dumps(run(),ensure_ascii=False,indent=2))
