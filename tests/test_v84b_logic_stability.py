from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import pbp_enrich
import specialist_learning_v79b as specialist
import history_tracker
from backend.autolearn_v84 import (
    _gate_current_calibration,
    _stabilize_ensemble_weights,
)

class _Resp:
    def __init__(self, status=200):
        self.status_code = status
        self.headers = {"Retry-After": "1"}
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")
    def json(self):
        return {"ok": True}

class _Session:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = 0
    def get(self, *args, **kwargs):
        self.calls += 1
        return _Resp(self.statuses.pop(0))

def test_pbp_one_real_request_is_one_quota_call(monkeypatch):
    seen = []
    monkeypatch.setattr(pbp_enrich, "record_calls", lambda role, n: seen.append((role, n)))
    api = pbp_enrich.API("x", call_cap=5)
    api.session = _Session([200])
    api.get("/demo")
    assert api.calls == 1
    assert api.session.calls == 1
    assert seen == [("pbp_current", 1)]

def test_pbp_retry_counts_two_real_requests(monkeypatch):
    seen = []
    monkeypatch.setattr(pbp_enrich, "record_calls", lambda role, n: seen.append((role, n)))
    monkeypatch.setattr(pbp_enrich.time, "sleep", lambda *_: None)
    api = pbp_enrich.API("x", call_cap=5)
    api.session = _Session([429, 200])
    api.get("/demo")
    assert api.calls == 2
    assert api.session.calls == 2
    assert seen == [("pbp_current", 1), ("pbp_current", 1)]

def _sig(pick, score):
    return {
        "key": f"set1_total|8.5|{pick}",
        "label": f"1S {pick}",
        "score": score,
        "market": "set1_total",
        "pick": pick,
        "line": 8.5,
    }

def test_consensus_2_over_vs_3_under_selects_only_under(monkeypatch):
    rows = {
        "adaptive": [_sig("over", 76)],
        "early": [_sig("over", 72)],
        "serve": [_sig("under", 74)],
        "form": [_sig("under", 73)],
        "surface": [_sig("under", 71)],
    }
    monkeypatch.setattr(specialist, "model_signals", lambda mid, m: rows[mid])
    out = specialist.consensus_signals({})
    assert len(out) == 1
    assert out[0]["pick"] == "under"
    assert out[0]["votes"] == 3
    assert out[0]["against_votes"] == 2
    assert out[0]["net_votes"] == 1

def test_consensus_tie_is_rejected(monkeypatch):
    rows = {
        "adaptive": [_sig("over", 76)],
        "early": [_sig("over", 72)],
        "serve": [_sig("under", 74)],
        "form": [_sig("under", 73)],
        "surface": [],
    }
    monkeypatch.setattr(specialist, "model_signals", lambda mid, m: rows[mid])
    assert specialist.consensus_signals({}) == []

def test_small_calibration_sample_cannot_give_one_model_100_percent():
    rows = [{"match_key": f"id:{i}", "target": i % 2} for i in range(19)]
    w, meta = _stabilize_ensemble_weights(
        {"current": 0.0, "catboost": 1.0},
        ["current", "catboost"],
        rows,
    )
    assert meta["guard_active"] is True
    assert w["catboost"] <= 0.8000001
    assert w["current"] >= 0.099999
    assert abs(sum(w.values()) - 1.0) < 1e-9

def test_large_calibration_sample_can_use_full_optimizer_weight():
    rows = [{"match_key": f"id:{i}", "target": i % 2} for i in range(50)]
    w, meta = _stabilize_ensemble_weights(
        {"current": 0.0, "catboost": 1.0},
        ["current", "catboost"],
        rows,
    )
    assert meta["guard_active"] is False
    assert w["catboost"] == 1.0

def test_bad_platt_candidate_is_rejected_on_cal_split():
    rows = [{"match_key": f"id:{i}", "base_score": 80, "target": 0} for i in range(40)]
    candidate = {
        "method": "platt_logit", "fit_scope": "train_only",
        "fit_rows": 100, "fit_matches": 50,
        "status": "active", "a": 8.0, "b": 8.0,
    }
    gated = _gate_current_calibration(candidate, rows)
    assert gated["status"] == "gated_identity"
    assert gated["gate_status"] == "rejected"
    assert gated["a"] == 1.0 and gated["b"] == 0.0

def test_identity_equivalent_calibration_is_allowed_within_tolerance():
    rows = [{"match_key": f"id:{i}", "base_score": 70 if i % 2 else 60, "target": i % 2} for i in range(40)]
    candidate = {
        "method": "platt_logit", "fit_scope": "train_only",
        "fit_rows": 100, "fit_matches": 50,
        "status": "active", "a": 1.0, "b": 0.0,
    }
    gated = _gate_current_calibration(candidate, rows)
    assert gated["status"] == "active"
    assert str(gated["gate_status"]).startswith("accepted")

def test_history_fallback_uses_tournament_to_disambiguate():
    hist = pd.DataFrame([
        {"winner_name": "A", "loser_name": "B", "tourney_date": 20260824, "tourney_name": "Event X", "score": "6-4 6-4"},
        {"winner_name": "B", "loser_name": "A", "tourney_date": 20260824, "tourney_name": "Event Y", "score": "6-3 6-3"},
    ])
    entry = {"p1": "A", "p2": "B", "scheduled_time": "2026-08-24T10:00:00+00:00", "tournament": "Event Y"}
    final = history_tracker.find_final_result(hist, entry)
    assert final is not None
    assert final["winner"] == "B"

def test_history_fallback_does_not_guess_between_two_equal_candidates():
    hist = pd.DataFrame([
        {"winner_name": "A", "loser_name": "B", "tourney_date": 20260824, "tourney_name": "Event X", "score": "6-4 6-4"},
        {"winner_name": "B", "loser_name": "A", "tourney_date": 20260824, "tourney_name": "Event Y", "score": "6-3 6-3"},
    ])
    entry = {"p1": "A", "p2": "B", "scheduled_time": "2026-08-24T10:00:00+00:00", "tournament": ""}
    assert history_tracker.find_final_result(hist, entry) is None

def test_pwa_uses_one_canonical_cache_key_per_data_json():
    sw = (ROOT / "frontend/sw.js").read_text(encoding="utf-8")
    app = (ROOT / "frontend/app.js").read_text(encoding="utf-8")
    assert "canonicalDataRequest" in sw
    assert "url.origin+url.pathname" in sw.replace(" ", "")
    assert "isDataJson" in sw
    assert "serviceWorker.register('sw.js?v=801')" in app
    assert ".then(r=>r.update())" in app
    assert "{cache:'no-store'}" in app

def test_symphony2_replaces_previous_scenario_pin():
    index = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "symphony2.js?v=210" in index
    assert "scenario-studio-v82a.js" not in index
    assert "scenario-runtime-v202.js" not in index


def test_history_tournament_can_beat_one_day_archive_date_drift():
    hist = pd.DataFrame([
        {"winner_name": "A", "loser_name": "B", "tourney_date": 20260824, "tourney_name": "Wrong Event", "score": "6-4 6-4"},
        {"winner_name": "B", "loser_name": "A", "tourney_date": 20260823, "tourney_name": "Target Event", "score": "6-3 6-3"},
    ])
    entry = {"p1": "A", "p2": "B", "scheduled_time": "2026-08-24T00:30:00+00:00", "tournament": "Target Event"}
    final = history_tracker.find_final_result(hist, entry)
    assert final is not None
    assert final["winner"] == "B"
